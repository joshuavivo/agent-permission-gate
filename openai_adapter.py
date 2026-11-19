"""Wire the gate to a real tool-calling model (OpenAI shown; Anthropic is the same
shape with different attribute names).

The gate's handle — `agent.call(name, args)` — is provider-agnostic. This module is
the thin translation between a provider's response and those calls, and back into
the messages you send on the next turn. No `openai` package and no API key are
needed to read this or run its test: the functions accept plain objects or dicts.

A real loop looks like:

    agent = gate.for_agent()
    messages = [{"role": "user", "content": "..."}]
    while True:
        resp = client.chat.completions.create(model=..., messages=messages, tools=TOOLS)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            break
        results, pending = dispatch(msg, agent)
        messages.append(msg)              # the assistant's tool-call turn
        messages.extend(results)          # read-only results, ready immediately
        for p in pending:                 # writes: a PERSON approves, never the model
            if show_to_human_and_approve(p):
                out = gate.approve(p["request_id"], approver="alice")
                messages.append(tool_result_message(p["tool_call_id"], out))
            else:
                gate.deny(p["request_id"], approver="alice")
                messages.append(tool_result_message(p["tool_call_id"], {"denied": True}))
"""
import json


def _get(obj, key):
    if obj is None:
        return None
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def tool_calls_from_openai(message):
    """Normalize an OpenAI chat message's tool calls to [{id, name, arguments}].

    `message` is `response.choices[0].message` — an SDK object or the equivalent
    dict. `arguments` arrives as a JSON string from the provider and is parsed to a
    dict here.
    """
    out = []
    for c in _get(message, "tool_calls") or []:
        fn = _get(c, "function")
        raw = _get(fn, "arguments")
        args = json.loads(raw) if isinstance(raw, str) else (raw or {})
        out.append({"id": _get(c, "id"), "name": _get(fn, "name"), "arguments": args})
    return out


def tool_result_message(tool_call_id, result):
    """The `role: tool` message to append so the model sees the outcome next turn."""
    return {"role": "tool", "tool_call_id": tool_call_id, "content": json.dumps(result)}


def dispatch(message, agent):
    """Run every tool call in a provider message through the gate.

    Returns `(results, pending)`:
      - `results` — `role: tool` messages for calls that ran now (the read-only ones);
        append them to the conversation.
      - `pending` — write calls the gate is holding for a person, each with the
        `request_id` to approve/deny and the `tool_call_id` to answer under. The
        model never appears in the approval path.
    """
    results, pending = [], []
    for call in tool_calls_from_openai(message):
        outcome = agent.call(call["name"], call["arguments"])
        if outcome.get("status") == "pending":
            pending.append({
                "tool_call_id": call["id"],
                "request_id": outcome["request_id"],
                "tool": call["name"],
                "args": call["arguments"],
            })
        else:
            results.append(tool_result_message(call["id"], outcome))
    return results, pending

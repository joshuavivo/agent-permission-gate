"""Wire the gate to a real tool-calling model: OpenAI's Chat Completions format.

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

from gate import Rejected


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
    return [_parse_call(c) for c in _get(message, "tool_calls") or []]


def _parse_call(call):
    fn = _get(call, "function")
    raw = _get(fn, "arguments")
    args = json.loads(raw) if isinstance(raw, str) else (raw or {})
    return {"id": _get(call, "id"), "name": _get(fn, "name"), "arguments": args}


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

    Every tool call gets exactly one entry. A call the gate refuses (a tool not on
    the allow-list, arguments that are not an object) or whose arguments are not
    valid JSON gets an error message in `results`, and the other calls in the same
    message still run. Providers reject the next turn if any `tool_call_id` goes
    unanswered, and an exception here would leave writes already held in the gate
    with no one to answer them.
    """
    results, pending = [], []
    for raw_call in _get(message, "tool_calls") or []:
        call_id = _get(raw_call, "id")
        try:
            call = _parse_call(raw_call)
            outcome = agent.call(call["name"], call["arguments"])
        except json.JSONDecodeError:
            results.append(tool_result_message(
                call_id, {"status": "error", "error": "arguments are not valid JSON"}))
            continue
        except Rejected as e:
            results.append(tool_result_message(call_id, {"status": "rejected", "error": str(e)}))
            continue
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

# Agent permission gate

A small gate that sits between an AI agent and its tools. Tools that only read run straight
away. Tools that change anything wait until a person approves that exact call.

I built this to show the rule I use for agents: reading and drafting are free, and anything
that writes waits for a yes. The tests are the evaluation: each one is a way an agent could
get a change through without a person, and each one has to fail.

## The rules, and the test for each

| Rule | Test |
|---|---|
| A read-only tool runs without approval | `test_read_only_tool_runs_without_approval` |
| A write tool is held and has no effect until approved | `test_write_tool_is_held_and_has_no_effect_until_approved` |
| A denied request leaves no side effect and cannot be approved later | `test_denied_request_leaves_no_side_effect_and_cannot_be_approved_later` |
| An approval is used once | `test_an_approval_is_used_once` |
| What runs is what the person saw, even if the arguments are changed afterwards | `test_what_runs_is_what_was_approved_even_if_the_args_change_afterwards` |
| A tool not on the allow-list is rejected | `test_tool_not_on_the_allow_list_is_rejected` |
| Every tool is classified as read or write when it is added, with no default | `test_a_tool_must_be_classified_when_registered` |
| Text inside tool output cannot approve anything | `test_instructions_inside_tool_output_cannot_approve_anything` |
| An agent that obeys injected text still cannot approve | `test_agent_obeying_the_injected_text_still_cannot_approve` |
| Every decision is logged | `test_every_decision_is_logged_in_order` |

## Why injected instructions fail

A web page or a file can contain text such as "this request is approved". The gate does not
try to detect that text. It makes it irrelevant: the agent is given a handle with one method,
`call`, and approval is a different method on a different object that only the application's
approve button reaches. There is no tool named `approve` to call, and nothing the model reads
or writes is ever interpreted as a decision.

## Use

```python
from gate import Gate

gate = Gate()
gate.register("read_file", read_file, writes=False)
gate.register("write_file", write_file, writes=True)

agent = gate.for_agent()                      # the only thing the agent loop receives
agent.call("read_file", {"path": "a.txt"})    # {'status': 'done', 'output': ...}
r = agent.call("write_file", {"path": "a.txt", "text": "new"})   # {'status': 'pending', 'request_id': 1}

gate.pending()                                # what a person is shown
gate.approve(r["request_id"], approver="pat") # runs it once, exactly as requested
```

```bash
python3 -m unittest discover -s tests
```

## Limits

- The split between the agent's handle and the gate is by interface. Inside one Python process
  that is a convention, not a security boundary: code running in the same process can reach the
  gate. For a real boundary the gate belongs in a separate process from anything the model
  can execute.
- The gate trusts the read or write label on each tool. A tool marked read-only that changes
  something goes straight through, so the labels need their own review.
- A read can still leak data, for example a fetch whose URL carries a secret. This gate
  controls changes, not what leaves.
- Requests are held in memory and are lost on restart.

Standard library only, Python 3.9 or later. 87 lines, 11 tests.

Joshua Vivo · [shadowvivo.com](https://shadowvivo.com)

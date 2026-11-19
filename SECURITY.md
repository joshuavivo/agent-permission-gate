# Security policy

This is a reference / portfolio project, not a hosted service. Its whole point is a
security property — an AI agent cannot approve its own write tool calls — so if you
find a way around that, I want to know.

## What to report

- A way the agent handle (`gate.for_agent()`) can approve, deny, or run a held
  write without a person calling `gate.approve`.
- A way text the model produces or reads gets interpreted as an approval.
- A way a held call runs with arguments different from the ones a person was shown.
- A way a denied or already-used request runs, or a tool off the allow-list runs.

Please report privately:

- Open a **GitHub Security Advisory** on this repository (Security → Report a
  vulnerability), or
- email **security@shadowvivo.com**.

No bounty is offered, but I'll credit you unless you'd rather stay anonymous.

## Scope and known limits (not bugs — see the README)

- The agent/gate split is by interface; inside one process it is a convention, not
  a kernel boundary. A real boundary puts the gate in a separate process from
  anything the model can execute.
- The gate trusts each tool's read/write label; a mislabelled tool is a review
  problem, not a gate bypass.
- A read-only tool can still leak data (a fetch whose URL carries a secret). This
  gate controls *changes*, not what leaves.

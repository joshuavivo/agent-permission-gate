# Changelog

Notable changes. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This file starts on 2026-11-21; earlier changes are in the git history and the merged pull requests.

## [Unreleased]

Fixes from an independent review. The theme: the audit log is the product, so it has to record
what really happened.

### Fixed
- **The log records outcomes, not only decisions.** An approved call whose tool raised was logged
  as "approved" with nothing after it, as if it had run. It is now logged "approved" then "failed"
  (with the error), or "approved" then "done". A read that raised was logged as "ran"; it is now
  logged as "failed".
- **Calls are checked when requested.** Missing or unknown arguments are refused and logged when
  the agent asks, instead of being held, approved by a person, and failing inside the tool. Tools
  Python can't inspect (builtins such as `dict`) skip the check and run as before.
- **Refused approvals are logged.** Approving a used request, or an id that doesn't exist, is now
  in the log with who clicked, as the README always said.
- **Hardening from an outside review.** A tool that raised `SystemExit` or a cancellation
  (any `BaseException`) left the log ending at "approved"; it is now logged "failed". A
  tool name that isn't text crashed with nothing logged; it is now refused and logged. An
  empty or missing approver (`None`) was accepted as who decided; it is now an error.
  Approve and deny take a lock, so two simultaneous clicks can't both run the call. A new
  request takes its id under the same lock (two requests made at once could share an id and
  one would overwrite the other), and `pending()` reads under it too.
- **`dispatch` answers a call whose output isn't JSON, or whose read tool raised.** A read tool returning a
  `datetime` made `dispatch` raise after a write in the same message was already held,
  so the caller got neither list; a read tool that raised did the same. It now answers that
  call with an error and returns both lists. Found by an outside review.
- **The injection test checks that a person was asked.** It used to share its input with the
  denied-write test and checked only the log order; it now also checks that the person was asked
  about exactly the send the injected text produced.

### Changed
- README's opening says what the log really holds (each call, who decided, whether it ran
  or failed) and that only tools labelled as writes are held; Limits adds that the log has
  no arguments, timestamps or outputs, and that arguments are checked by name, not type.
  Found by an outside review.
- README opens with what an unguarded agent could do, and the "why injected instructions fail"
  section points to Limits for where the real process boundary belongs.

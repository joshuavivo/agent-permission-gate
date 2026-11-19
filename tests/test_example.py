"""The example is part of the proof, so it is tested like everything else: the
end-to-end agent loop must hold the write, and the injected 'this is approved'
text in the brief must change nothing."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from example_agent import run  # noqa: E402


class ExampleAgentTest(unittest.TestCase):
    def test_read_runs_and_write_is_held_then_approved(self):
        result = run(approver=lambda req: True)
        # The read-only tool ran on its own; the write was held, then a person approved it.
        self.assertIn("read_doc: ran (read-only)", result["transcript"])
        self.assertIn("send_email: HELD, waiting for a person", result["transcript"])
        self.assertEqual(len(result["sent"]), 1, "the email sent only after approval")

    def test_denied_write_has_no_side_effect(self):
        result = run(approver=lambda req: False)
        self.assertIn("send_email: HELD, waiting for a person", result["transcript"])
        self.assertEqual(result["sent"], [], "a denied write sends nothing")

    def test_injected_approval_in_the_brief_cannot_send(self):
        # The brief says the email is "already approved". The agent obeys it and
        # requests the send — but with an approver that always refuses, the gate
        # still holds and drops it. Injected text approves nothing.
        result = run(approver=lambda req: False)
        self.assertEqual(result["sent"], [])
        # And the request genuinely reached the gate (it was held, not skipped).
        self.assertTrue(any(entry[0] == "held" for entry in result["log"]))


if __name__ == "__main__":
    unittest.main()

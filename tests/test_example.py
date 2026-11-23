"""The example is part of the proof, so it is tested like everything else: the
end-to-end agent loop must hold the write, and the injected 'this is approved'
text in the brief must change nothing."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from example_agent import BRIEF, run  # noqa: E402


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

    def test_injected_approval_in_the_brief_still_goes_to_a_person(self):
        # The brief says the send is "already approved". If that text could approve anything,
        # the send would go out without the person being asked. Instead the person is asked
        # about exactly the call the injected text produced, and their "no" is final.
        asked = []
        result = run(approver=lambda req: asked.append(req) or False)
        self.assertEqual([r["tool"] for r in asked], ["send_email"])
        self.assertEqual([e[0] for e in result["log"]], ["ran", "held", "denied"])
        self.assertEqual(result["sent"], [])

    def test_the_send_attempt_comes_from_the_injected_text(self):
        # Control: the same brief without the injected line. The user only asked for
        # a draft, so the model never tries to send. This is what makes the test
        # above meaningful: the model really does act on what it reads.
        clean = BRIEF.splitlines()[0] + "\n"
        result = run(approver=lambda req: True, brief=clean)
        self.assertEqual([e[0] for e in result["log"]], ["ran"])
        self.assertEqual(result["sent"], [])

if __name__ == "__main__":
    unittest.main()

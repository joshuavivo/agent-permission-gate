"""The OpenAI adapter, tested against provider-shaped fake objects — no SDK, no
network. A read-only tool call runs immediately; a write call is held for a person
exactly as the gate requires, and the model is never in the approval path."""
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from gate import Gate  # noqa: E402
from openai_adapter import dispatch, tool_calls_from_openai, tool_result_message  # noqa: E402


def fake_openai_message(tool_calls):
    """Mimic response.choices[0].message: objects with .tool_calls[].function.{name,arguments}."""
    calls = []
    for i, (name, args_json) in enumerate(tool_calls):
        fn = types.SimpleNamespace(name=name, arguments=args_json)
        calls.append(types.SimpleNamespace(id=f"call_{i}", function=fn))
    return types.SimpleNamespace(tool_calls=calls)


class AdapterTest(unittest.TestCase):
    def test_parses_openai_tool_calls_with_json_string_arguments(self):
        msg = fake_openai_message([("read_file", '{"path": "a.txt"}')])
        calls = tool_calls_from_openai(msg)
        self.assertEqual(calls, [{"id": "call_0", "name": "read_file", "arguments": {"path": "a.txt"}}])

    def test_also_accepts_plain_dict_messages(self):
        msg = {"tool_calls": [{"id": "c1", "function": {"name": "noop", "arguments": {"x": 1}}}]}
        self.assertEqual(tool_calls_from_openai(msg), [{"id": "c1", "name": "noop", "arguments": {"x": 1}}])

    def test_a_read_that_raises_still_gets_an_answer(self):
        # A read raising (say FileNotFoundError) after a write in the same message was held
        # made dispatch raise: no results, and the held write's tool call went unanswered.
        gate = Gate()
        def read_file(path):
            raise FileNotFoundError(path)
        gate.register("read_file", read_file, writes=False)
        gate.register("write_file", lambda path, text: None, writes=True)
        msg = fake_openai_message([("write_file", '{"path": "a", "text": "b"}'), ("read_file", '{"path": "x"}')])
        results, pending = dispatch(msg, gate.for_agent())
        self.assertEqual([p["tool_call_id"] for p in pending], ["call_0"])
        self.assertEqual([r["tool_call_id"] for r in results], ["call_1"])
        out = json.loads(results[0]["content"])
        self.assertEqual(out["status"], "error")
        self.assertIn("FileNotFoundError", out["error"])
        self.assertEqual(gate.log[-1][0], "failed")

    def test_a_read_whose_output_is_not_json_still_gets_an_answer(self):
        # A read returning a datetime made dispatch raise after the write in the same message
        # was already held, so neither list came back and the tool_call_ids went unanswered.
        import datetime
        gate = Gate()
        gate.register("now", lambda: datetime.datetime(2026, 1, 1), writes=False)
        gate.register("write_file", lambda path, text: None, writes=True)
        msg = fake_openai_message([("write_file", '{"path": "a", "text": "b"}'), ("now", "{}")])
        results, pending = dispatch(msg, gate.for_agent())
        self.assertEqual([p["tool_call_id"] for p in pending], ["call_0"])
        self.assertEqual([r["tool_call_id"] for r in results], ["call_1"])
        self.assertEqual(json.loads(results[0]["content"])["status"], "error")

    def test_dispatch_runs_reads_and_holds_writes(self):
        gate = Gate()
        read_calls, writes = [], []
        gate.register("read_file", lambda path: read_calls.append(path) or "contents", writes=False)
        gate.register("write_file", lambda path, text: writes.append((path, text)), writes=True)
        agent = gate.for_agent()

        msg = fake_openai_message([
            ("read_file", '{"path": "a.txt"}'),
            ("write_file", '{"path": "a.txt", "text": "new"}'),
        ])
        results, pending = dispatch(msg, agent)

        # The read ran and produced a tool-result message; the write is held.
        self.assertEqual(read_calls, ["a.txt"])
        self.assertEqual(writes, [], "the write did not happen without approval")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["role"], "tool")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["tool"], "write_file")

        # A person approves via the gate — never the model. Now the write happens.
        gate.approve(pending[0]["request_id"], approver="alice")
        self.assertEqual(writes, [("a.txt", "new")])

    def test_a_bad_call_is_answered_and_does_not_strand_the_others(self):
        # A write, then a tool the gate refuses, then malformed JSON, then a read, all
        # in one model message. The write must stay held for a person, every
        # tool_call_id must get exactly one answer, and the read must still run.
        gate = Gate()
        reads, writes = [], []
        gate.register("read_file", lambda path: reads.append(path) or "contents", writes=False)
        gate.register("write_file", lambda path, text: writes.append((path, text)), writes=True)
        agent = gate.for_agent()

        msg = fake_openai_message([
            ("write_file", '{"path": "a.txt", "text": "new"}'),
            ("delete_everything", "{}"),
            ("read_file", '{"path": "a.txt"'),
            ("read_file", '{"path": "b.txt"}'),
        ])
        results, pending = dispatch(msg, agent)

        answered = [m["tool_call_id"] for m in results] + [p["tool_call_id"] for p in pending]
        self.assertEqual(sorted(answered), ["call_0", "call_1", "call_2", "call_3"])
        self.assertEqual([p["tool_call_id"] for p in pending], ["call_0"])
        by_id = {m["tool_call_id"]: json.loads(m["content"]) for m in results}
        self.assertEqual(by_id["call_1"]["status"], "rejected")
        self.assertEqual(by_id["call_2"]["status"], "error")
        self.assertEqual(by_id["call_3"]["status"], "done")
        self.assertEqual(reads, ["b.txt"])
        self.assertEqual(writes, [])
        self.assertEqual([p["id"] for p in gate.pending()], [pending[0]["request_id"]])

    def test_tool_result_message_shape(self):
        m = tool_result_message("call_0", {"status": "done"})
        self.assertEqual(m, {"role": "tool", "tool_call_id": "call_0", "content": '{"status": "done"}'})


if __name__ == "__main__":
    unittest.main()

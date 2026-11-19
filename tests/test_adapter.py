"""The OpenAI adapter, tested against provider-shaped fake objects — no SDK, no
network. A read-only tool call runs immediately; a write call is held for a person
exactly as the gate requires, and the model is never in the approval path."""
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

    def test_tool_result_message_shape(self):
        m = tool_result_message("call_0", {"status": "done"})
        self.assertEqual(m, {"role": "tool", "tool_call_id": "call_0", "content": '{"status": "done"}'})


if __name__ == "__main__":
    unittest.main()

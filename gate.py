"""A permission gate for an AI agent's tool calls.

Tools that only read run straight away. Tools that change anything are held until a
person approves that exact call. The agent gets a handle that can request calls and
nothing else, so no text the model produces or reads can approve anything: approval
is a separate method the agent's handle does not have.
"""
import copy
import inspect
import json


class Rejected(Exception):
    """The call was refused outright."""


class Gate:
    """Held by the application. The person's approve/deny buttons call this object."""

    def __init__(self):
        self._tools = {}      # name -> (function, writes)
        self._requests = {}   # id -> {"tool", "args", "status"}
        self.log = []         # every decision, in order

    def register(self, name, fn, writes):
        """writes has no default on purpose: every tool must be classified when it is added.

        A name is registered once. Replacing it would change what an already-held request
        runs when it is approved, so a person could approve one function and run another.
        """
        if not isinstance(writes, bool):
            raise TypeError("writes must be True or False")
        if name in self._tools:
            raise ValueError(f"tool {name!r} is already registered")
        self._tools[name] = (fn, writes)

    def for_agent(self):
        return AgentHandle(self)

    def pending(self):
        return [{"id": i, "tool": r["tool"], "args": copy.deepcopy(r["args"])}
                for i, r in self._requests.items() if r["status"] == "pending"]

    def approve(self, request_id, approver):
        """Run the held call exactly as it was requested, once."""
        r = self._take(request_id)
        r["status"] = "approved"
        self.log.append(("approved", request_id, r["tool"], approver))
        fn, _ = self._tools[r["tool"]]
        return fn(**copy.deepcopy(r["args"]))

    def deny(self, request_id, approver):
        r = self._take(request_id)
        r["status"] = "denied"
        self.log.append(("denied", request_id, r["tool"], approver))

    def _take(self, request_id):
        r = self._requests.get(request_id)
        if r is None:
            raise Rejected(f"no request {request_id}")
        if r["status"] != "pending":
            raise Rejected(f"request {request_id} was already {r['status']}")  # an approval is used once
        return r

    def _call(self, name, args):
        if name not in self._tools:
            self.log.append(("rejected", None, name, "not on the allow-list"))
            raise Rejected(f"tool {name!r} is not on the allow-list")
        if not isinstance(args, dict):
            self.log.append(("rejected", None, name, "args must be an object"))
            raise Rejected("args must be an object")
        try:
            json.dumps(args)
        except (TypeError, ValueError):
            self.log.append(("rejected", None, name, "args must be plain data"))
            raise Rejected("args must be plain data") from None
        fn, writes = self._tools[name]
        try:  # a call the tool can't accept is refused now, not after a person approves it
            sig = inspect.signature(fn)
        except Exception:  # builtins like dict have none; a custom __signature__ can raise anything
            sig = None     # no signature to check, so the call itself will tell
        if sig is not None:
            try:
                sig.bind(**args)
            except TypeError as e:
                self.log.append(("rejected", None, name, f"args don't match the tool: {e}"))
                raise Rejected(f"args don't match {name!r}: {e}") from None
        if not writes:
            self.log.append(("ran", None, name, "read-only"))
            return {"status": "done", "output": fn(**args)}
        request_id = len(self._requests) + 1
        # Deep copy: what the person approves is what was asked, even if the caller changes its dict afterwards.
        self._requests[request_id] = {"tool": name, "args": copy.deepcopy(args), "status": "pending"}
        self.log.append(("held", request_id, name, "waiting for a person"))
        return {"status": "pending", "request_id": request_id}


class AgentHandle:
    """Everything the agent loop is given. It can ask; it cannot approve."""
    __slots__ = ("_request",)

    def __init__(self, gate):
        self._request = gate._call

    def call(self, name, args):
        return self._request(name, args)

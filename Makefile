# Standard-library Python; no install step.
.PHONY: test demo

test:   ## run the gate, example, and adapter tests (leaks fail the build)
	python3 -W error::ResourceWarning -m unittest discover -s tests -v

demo:   ## run the end-to-end example (injected "approved" text is still held)
	python3 example_agent.py

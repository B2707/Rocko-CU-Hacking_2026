---
name: feature-implementation-with-tests-and-docs
description: Workflow command scaffold for feature-implementation-with-tests-and-docs in CU-hakcing-2026.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /feature-implementation-with-tests-and-docs

Use this workflow when working on **feature-implementation-with-tests-and-docs** in `CU-hakcing-2026`.

## Goal

Implements a new feature or protocol, accompanied by updates to documentation and corresponding tests.

## Common Files

- `transmitter/transmitter.py`
- `receiver/decoder.py`
- `receiver/protocol.py`
- `receiver/eventlog.py`
- `TTS/classifier.c`
- `tests/test_transmitter.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Implement or modify core logic in one or more main source files (e.g., transmitter/transmitter.py, receiver/decoder.py, TTS/classifier.c).
- Update or create documentation files (e.g., README.md, ALGORITHM.md, protocol/spec docs).
- Add or update test files to cover the new feature (e.g., tests/test_transmitter.py, tests/test_receiver.py, tests/test_wake_gate.py).

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.
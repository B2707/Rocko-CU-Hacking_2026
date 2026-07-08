### Python
- Type hints on public functions; run the stack's type checker if one is chosen.
- One venv per repo; pin requirements the same day you install
  (`pip freeze > requirements.txt` after any install).
- Never bare `except:` — catch the narrowest exception and log the context.
- pathlib over os.path, f-strings, dataclasses/pydantic for structured data.
- pydantic (or equivalent) validates at API boundaries before use.

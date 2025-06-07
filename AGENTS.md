# AGENT Instructions

The repository contains a FastAPI backend and a Vue frontend.
Follow these guidelines when modifying files:

## Code Style
- Python code should follow PEP8 with 4 space indentation.
- Use descriptive names and include docstrings for new functions or modules.
- JavaScript/Vue code should use 2 space indentation and semicolons.

## Commits
- Provide meaningful commit messages in English summarizing the change.
- Do not amend or rebase existing commits.

## Dependencies and Testing
- After code changes run:
  - `pip install -r requirements.txt`
  - `npm install` inside `frontend`
- Attempt to start the backend with `python -m uvicorn app.main:app` to ensure the server loads.
- If dependency installation or server startup fails, mention it in the PR testing section.


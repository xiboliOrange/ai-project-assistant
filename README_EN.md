# Local AI Project Assistant

[中文](README.md) | English

A local project documentation assistant for developers. It helps users find answers across README files, design documents, API documentation, issues, and code comments, with clear citations that lead back to the original sources.

## Project Overview

When developers become familiar with an unfamiliar project, they often need to search across multiple documents and code files. A conventional chat-based AI can provide quick answers, but it is difficult to tell whether an answer comes from project materials, general model knowledge, or model-generated assumptions.

This project makes verifiability a core part of the experience. It answers questions based on project materials and ties responses to specific files, sections, paragraphs, or code lines whenever possible. When the available materials do not support a conclusion, the system clearly indicates insufficient evidence instead of presenting a fabricated answer as fact.

## Core Features

- Import project documents and build a local index;
- Ask natural-language questions based on project materials;
- Attach citations such as file names, sections, paragraphs, or line numbers to answers;
- Jump back to the relevant source content to verify an answer;
- Provide clear status and recovery guidance when materials are insufficient, citations are no longer valid, or model requests fail;
- Keep local document storage separate from model service configuration and clarify what content may be sent to an external model.

## Demo Scenario

After importing a project's README, architecture documents, API documentation, and issues, a user asks:

> Which modules does the client go through when a user login fails?

The system generates an explanation of the login flow based on the imported materials and displays relevant citations below the answer. By clicking a citation, the user can jump directly to the authentication flow section, login API documentation, or an issue describing error handling, making it easy to verify the answer.

If the imported materials do not cover a question, the system displays a message such as “There is not enough evidence in the current materials” instead of presenting an assumption as a project fact.

## Technical Direction

- Qt 5.14 client
- Python / FastAPI service
- Custom MCP Server
- Local file parsing, content chunking, and indexing
- Support for local models and user-configured model APIs

## Current Status

In development. The Python service supports file upload, metadata queries and edits, and manually triggered summary and keyword generation. Project Q&A, citations, and the Qt client remain in design or development.

### Run the file service

Use Python 3.11 or newer. Check `python --version` first; if the default is older, replace `python` in the first command below with the path to a Python 3.11 executable. From the project root:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

API documentation is available at `http://127.0.0.1:8000/docs`. Uploaded files and the SQLite index are stored locally in `data/uploads/` and `data/files.sqlite3`.

`POST /files/{id}/index` requires `AI_PROJECT_LLM_URL` (the full Chat Completions URL), `AI_PROJECT_LLM_MODEL`, and `AI_PROJECT_LLM_API_KEY` if the service requires a key. The file's UTF-8 content is sent to the configured model service only when this endpoint is called. Other file endpoints do not call a model.

File API test cases, automation, and reusable upload fixtures are in [`test/files/`](test/files/test-cases.md). Fixture files stay in `test/files/fixtures/` after test runs. Install test dependencies and run them with:

```powershell
.\venv\Scripts\python.exe -m pip install -r test\requirements.txt
.\venv\Scripts\python.exe -m unittest discover -s test\files -p "test_*.py" -v
```

## Future Additions

- Setup and environment instructions
- Screenshots and interactive demos
- System architecture diagram
- Feature development progress
- Directory structure and development guide

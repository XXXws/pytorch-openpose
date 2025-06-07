# Repository Guide: PyTorch OpenPose

## Overview
This project provides a web-based pose detection system using PyTorch.
The repository contains a Python backend powered by **FastAPI** and a
Vue.js frontend for user interaction. Core OpenPose logic resides in
`src/` and is wrapped into API services under `app/`.

```
├── app/        # FastAPI backend (routes & services)
├── src/        # PyTorch OpenPose models and utilities
├── frontend/   # Vue 3 web client
├── model/      # Pretrained model files (not included)
├── images/     # Sample images for demos
├── results/    # Output files (ignored by git)
```

## Backend
- **Entry point**: `python -m app.main` (uses FastAPI and uvicorn)
- **Configuration**: see `app/config.py` for paths and log level.
- **API modules**: located in `app/api/` (detection, video, realtime, health).
- **Core services**: `app/core/` implements detection service, video tasks,
  performance monitoring and FFmpeg utilities.
- **Pose models**: defined in `src/model.py` with wrappers in `src/body.py`
  and `src/hand.py`.

### Coding style
- Follow **PEP8** conventions; use four spaces for indentation.
- Keep line length under **120** characters.
- Prefer explicit logging via the `logging` module (see `app/logger.py`).
- Public APIs should return JSON-friendly structures or Pydantic models.

## Frontend
- Located under `frontend/` using Vue 3 and Element Plus.
- Development: `npm run dev` (default port **3000**).
- Build for production: `npm run build`.

## Installation
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Download pretrained models into the `model/` directory:
   - `body_pose_model.pth`
   - `hand_pose_model.pth`
3. (Optional) install front‑end dependencies:
   ```bash
   cd frontend && npm install
   ```

## Running
- **Backend**: `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001`
- **Frontend**: `npm run dev` from `frontend/`.
- API documentation available at `http://localhost:8001/docs`.

## Notes for Contributors
- Tests are not provided; manual verification via starting the server is
  recommended after changes.
- When adding new Python modules, place them within the appropriate
  package (`app` for API/service code, `src` for model logic).
- Keep dependencies minimal and update `requirements.txt` when new
  packages are required.
- Avoid committing large model files or result media; these paths are
  already listed in `.gitignore`.

---
name: speech-to-text-dashboard
description: Manage, run, debug and extend the Streamlit Speech to Text Dashboard in this repo (app.py). Use when the user wants to start the dashboard, transcribe a Thai MP3/MP4 locally with faster-whisper large-v3 on CPU, fetch a YouTube auto-transcript, fix install/runtime errors, or change the transcription settings or outputs (.txt / .md).
---

# Speech to Text Dashboard

Streamlit app (`app.py`) with two tabs:

1. **Online** - paste a YouTube URL (the user uploaded their media to their own channel) and fetch the auto-generated Thai captions via `youtube-transcript-api`, falling back to `yt-dlp`. Output is cleaned (tags, timestamps, consecutive duplicates removed) and offered as `.txt` and `.md`.
2. **Offline** - upload MP3/MP4, transcribe locally with `faster-whisper`, offer `.txt` and `.md`.

## Automated YouTube flow (Online tab)

`app.py` uploads the MP4 with `google-api-python-client` (OAuth desktop flow using `client_secret.json`, token cached in `token.json`), then polls every `POLL_INTERVAL_S` (45 s) up to `POLL_TIMEOUT_S` (15 min) for Thai auto-captions: `youtube-transcript-api` first, then the authenticated `captions.list/download` API (needed because unverified Google projects force uploads to Private, which the public route cannot read). Never commit `client_secret.json` / `token.json` (see `.gitignore`), never print their contents, and never run the upload without the user clicking the button: it publishes to their channel and costs API quota. The captions-API download path is untested against a live account.

## Run

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (WSL/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

Use Python 3.13 for the venv (3.10-3.13 work). On Windows `setup.ps1` installs 3.13 side by side with any newer Python; 3.14+ lacks wheels for `av<17` / `onnxruntime`, so installing into a 3.14+ venv fails.

## Fixed settings (do not change unless the user asks)

The offline tab must keep: `WhisperModel("large-v3", device="cpu", compute_type="int8")`, `language="th"`, `beam_size=5`, `vad_filter=True` with `min_silence_duration_ms=500`, `condition_on_previous_text=False`, and the Thai finance `INITIAL_PROMPT` constant in `app.py`. The machine has no GPU; never switch to CUDA.

## Known pitfalls

- `av>=17` breaks faster-whisper 1.2.1 (`open() got an unexpected keyword argument 'metadata_errors'`). Keep `av<17` in `requirements.txt`.
- First offline run downloads ~3 GB of model weights and is slow on CPU; transcription can take longer than the clip.
- YouTube captions can take minutes to appear after upload; "no transcript" often means retry later. YouTube may block requests from cloud IPs.
- Windows symlink warnings from `huggingface_hub` are harmless (`HF_HUB_DISABLE_SYMLINKS_WARNING=1` silences them).

## When updating the project

- Keep helpers (`clean_lines`, `to_markdown`, `extract_video_id`) pure so they can be tested without Streamlit.
- After editing, run `python -m py_compile app.py` and, if possible, launch with `streamlit run app.py` and exercise both tabs.
- Update `README.md` and `requirements.txt` whenever dependencies or usage change.
- Do not commit `.venv/`, downloaded media, or generated transcripts.

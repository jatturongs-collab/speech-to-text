# Master prompt: build this whole project with one request

**วิธีใช้ (How to use)**

1. เปิดโฟลเดอร์ว่างใน Claude Code (เช่น `D:\speech-to-text`)
2. (ถ้ามี) วางไฟล์ไอคอนไว้ที่ `assets/icon.png` และแบนเนอร์ที่ `assets/banner.webp` ก่อน
3. คัดลอกข้อความในกล่อง **MASTER PROMPT** ด้านล่างทั้งหมด ไปวางใน Claude Code
4. แก้ 5 ค่าที่อยู่ใน `[ ]` ด้านบนของ prompt ให้เป็นของคุณ (ชื่อผู้ถือลิขสิทธิ์, URL GitHub ฯลฯ)
5. Claude Code จะวางแผนให้ดูก่อน ตอบรับแผน แล้วมันจะสร้างทุกไฟล์ ทดสอบ และถามก่อน push

Copy the whole **MASTER PROMPT** block into Claude Code in an empty folder. It describes the app,
the Claude Skill, the docs, the scripts and the rules in one go, so you do not have to add features
one by one. The order in which these features were originally asked for is in
[prompt-history.md](prompt-history.md).

You still have to do these yourself (Claude Code cannot): create the Google Cloud project and
download `client_secret.json`, sign in to Google in the browser, and create the GitHub repo.

---

## MASTER PROMPT

```text
Build a complete, shareable project called "Speech to Text Dashboard" in this folder, plus a Claude
Skill for it. Plan first (plan mode), show me the plan, then build, test and tell me exactly what
you verified and what you could not verify. Ask me before you commit or push anything.

SETTINGS (use these values everywhere)
- [COPYRIGHT_HOLDER]  = AI investor alpha Jat
- [GITHUB_REPO_URL]   = https://github.com/<user>/speech-to-text
- [OUTPUT_FOLDER_EXAMPLE] = D:\speech-to-text
- Audience: a friend who is not a programmer, on a Windows 11 laptop, CPU only (no GPU).
- Content language: Thai audio (finance, e.g. Opportunity Day / earnings calls).

1. WHAT IT DOES
Turn Thai audio/video (MP3, MP4, M4A, WAV, MKV, WEBM) into clean .txt and .md transcripts, through
three routes, shown as three big tabs: "Auto 1 Click", "Online (YouTube)", "Offline (Ultra HQ)".

2. TECH
- Python app with Streamlit (>= 1.57). Files: app.py, requirements.txt, setup.ps1, uninstall.ps1,
  hq_transcribe.py (command-line version of the Offline route), SKILL.md, README.md, README.th.md,
  LICENSE, .gitignore, .streamlit/config.toml, assets/, prompt/.
- Python 3.13 venv. faster-whisper needs `av<17` (av 17+ breaks it with a `metadata_errors` error)
  and `onnxruntime`; neither has builds for Python 3.14/3.15, so the venv MUST be Python 3.13.
- ffmpeg is required. app.py must find it even when the PATH of the running process is stale
  (right after `winget install Gyan.FFmpeg`): look in PATH, then the Windows registry PATH, then
  the winget package folder (`find_ffmpeg()`), and show a green/red badge in the sidebar.
- Never hard-code personal paths, e-mails, project IDs or keys.

3. OFFLINE TAB (local, highest quality)
- faster-whisper model large-v3, CPU, compute_type int8, language "th", beam_size 5, VAD filter
  with min_silence_duration_ms 500, condition_on_previous_text False, and a short Thai finance
  initial_prompt. Show the model settings in the sidebar.
- Multiple files, up to 2 GB each. Transcribe one after another, with progress, elapsed time and a
  clear per-file status. Save .txt and .md; offer download. Stop button.

4. ONLINE TAB (YouTube auto-captions)
- Upload audio/video (2 GB per file). If it is audio-only, convert to MP4 with ffmpeg (black
  1280x720, 1 fps, aac 192k, libx264 ultrafast stillimage) with a real progress bar; kill ffmpeg if
  the user stops or closes the page.
- Upload to the user's own YouTube channel as Unlisted with the YouTube Data API (resumable upload,
  progress bar). Then poll every 30-60 s (timeout 15 min) for the auto-generated Thai captions.
  Get the text with `youtube-transcript-api`, fall back to the captions API (captions().list +
  download). Provide a "Check again" button when the wait times out.

5. AUTO 1 CLICK TAB (everything automatic)
- Select many files at once (no practical limit; each up to 20 GB) -> upload to YouTube one by one
  immediately, no extra clicks.
- A slider "wait before checking the transcript" from 15 to 90 minutes, default 30. Wait the FULL
  time first, then check ONCE; if not ready, retry every 300 s, at most 6 times.
- When a transcript is ready, show a blinking green flag and the text with download buttons.
- Per-item status for every file in the queue. Handle a YouTube channel daily-limit error
  (`uploadLimitExceeded`) differently from an API quota error: stop the batch and explain which one
  it was and what to do.
- Stop button (a callback; a Streamlit rerun interrupts the script, so cleanup must be in `finally`).

6. PERSISTENCE (closing the browser must not lose work)
- Save every job to `jobs.json`, transcripts to `transcripts/`, and an event log to `history.jsonl`.
  On start, resume/check unfinished jobs WITHOUT opening a browser sign-in (never pop up Google
  login at startup). The port of Streamlit may change between runs; that must not matter.

7. YOUTUBE ACCOUNT, DELETE AND HISTORY
- OAuth with `client_secret.json` (next to app.py) and `token.json`. Scopes: youtube.upload and
  youtube.force-ssl. Use `prompt="consent select_account"` so the user can choose an account. A
  sidebar button "Switch Google account". Clear message if client_secret.json is missing.
- A panel listing the videos on the channel (old uploads included) with a checkbox column and
  "delete selected" with a confirm dialog; also delete a single video after a job. Handle the empty
  list without crashing; mark a video deleted only if the API call really succeeded.
- Sidebar "History (Log)": a list of events; clicking one opens a dialog with details.

8. UI
- Bilingual Thai/English with a switch at the top of the sidebar; every label and message in both.
- Page title "Speech to Text Dashboard", icon from assets/icon.png (`st.logo` and page_icon).
- Two themes in .streamlit/config.toml, following the system setting and the Settings menu:
  warm cream light (background #F0EEE6, primary #C8643F, text #3D3929) and dark (background
  #0b1220, accent #22d3ee). Font: IBM Plex Sans Thai. Rounded corners 0.75rem.
- Tabs must be big, bold, framed, with a clear background (small CSS using `color-mix` so it follows
  both themes). Tab "Auto 1 Click" first.
- Uploads: `maxUploadSize = 20480` in config and `max_upload_size` per uploader (2048 Offline,
  2048 Online, 20480 Auto). Show "2GB per file (MAX)" and the accepted formats next to each uploader.
- Sidebar button "Open the guide (README)": a dialog that shows README.th.md when the UI is Thai and
  README.md when English. Render GitHub `> [!CAUTION]` as a red box with a flag, `### 🔴 text` as a
  red bold paragraph at 125% size, `**🔴 label**` as red bold, and `![..](assets/..)` as images.

9. SCRIPTS
- setup.ps1 (Windows): install ffmpeg with winget if missing; install Python 3.13 with winget if
  missing (side by side, never touch other Python versions); create .venv with `py -3.13`; run
  `pip install -r requirements.txt`; check every exit code and stop with a clear message on failure.
- uninstall.ps1: ask y/N (default No) for each item: .venv, the Whisper model cache (~3 GB under
  the Hugging Face cache), token.json, jobs.json, history.jsonl, transcripts, __pycache__,
  client_secret.json, ffmpeg. Never delete the project folder or the user's own media files.
- hq_transcribe.py: command-line version (input file, --output-dir; writes .txt and .srt).

10. README.md (English) and README.th.md (Thai, same content, Thai first for Thai readers)
- Banner image, tab table, requirements, "Install & run" with numbered Windows steps (1 prerequisites
  (Git or Download ZIP; Python 3.13 is installed by setup.ps1), 2 get the project, 3 run setup.ps1
  with `-ExecutionPolicy Bypass`, 4 start the app, 5 add client_secret.json) plus macOS/Linux/WSL
  and Uninstall sections. Each command in its own code block.
- Auto 1 Click section: the prerequisite "Set up client_secret.json" must be a RED FLAG: a
  `> [!CAUTION]` box AND a `### 🔴` heading-line (red, bold, 125%), followed by a normal-size
  example: "Copy client_secret.json to the same folder as app.py" with a PowerShell directory
  listing of [OUTPUT_FOLDER_EXAMPLE].
- Step-by-step "Set up client_secret.json" (Google Cloud: project, enable YouTube Data API v3,
  OAuth consent screen/Audience = External, Testing, add Test users, create a Desktop-app OAuth
  client, download the JSON). Explain: in Testing mode the sign-in expires after 7 days; unverified
  projects upload as Private; quota is about 1,600 units per upload of 10,000 per day.
- Formats and limits table, Appearance, "Closed the page? Your work is not lost", Stop/History/
  channel list, Claude Skill section, License section.
- Troubleshooting (each with the exact error text and the fix): `File must be 200MB or smaller`
  (maxUploadSize); `Failed to build 'av'` (use Python 3.13 venv); `metadata_errors` (av<17);
  ffmpeg not found (reopen PowerShell / winget); client_secret.json not found;
  `Error 403: access_denied` / "Access blocked" (your e-mail is not a Test user: Google Cloud ->
  Google Auth Platform -> Audience -> Test users -> Add users); `403 access_not_configured`
  (enable YouTube Data API v3); no transcript after 15 min; `uploadLimitExceeded` (channel daily
  limit: wait 24 h, verify the channel by phone, or switch to a second Google account added as a
  Test user); Offline is slow (expected on CPU).

11. CLAUDE SKILL
- SKILL.md with name `speech-to-text-dashboard`: when to use it, how to run, the project layout,
  the rules above (Python 3.13, av<17, never commit secrets), and how to extend it.

12. PUBLIC-REPO SAFETY (the repo will be public)
- .gitignore: client_secret.json, token.json, .venv/, __pycache__/, media files (mp3, mp4, m4a,
  wav, mkv, webm), *.srt, jobs.json, history.jsonl, transcripts/.
- LICENSE: MIT, "Copyright (c) 2026 [COPYRIGHT_HOLDER]". Mention it in the README.
- Before any commit, list the files to be added and scan them for e-mails, keys, project IDs and
  personal paths. Use an allowlist `git add`, never `git add .`.

13. HOW TO TEST (do this and report honestly)
- Run the real app in the built-in browser with FAKE YouTube and FAKE Whisper functions (real
  ffmpeg): check all three tabs, both themes, both languages, Stop, the delete/bulk-delete dialogs,
  the README dialog, persistence after a page reload, and the empty channel list.
- `python -m py_compile`, parse-check the .ps1 files, and run the Streamlit AppTest.
- State clearly what was NOT verified (real YouTube upload/delete, a real second Google account,
  a real model download).
```

---

## ถ้าอยากสั่งทีละส่วน (optional: step-by-step instead of one prompt)

If one huge prompt is too much, paste these shorter prompts one after another. Each uses the
sections of the MASTER PROMPT by number.

1. `Read prompt/prompt.md. Build sections 1, 2, 3, 9 and 12 only (the Offline tab, hq_transcribe.py,
   setup/uninstall scripts, .gitignore, license). Test, then stop.`
2. `Now add sections 4 and 7 (Online tab, YouTube account, delete, history).`
3. `Now add section 5 and 6 (Auto 1 Click, persistence, Stop).`
4. `Now add section 8 (themes, tabs, bilingual UI, README viewer).`
5. `Now write section 10 and 11 (README.md, README.th.md, SKILL.md). Then run section 13.`

## Tips

- Say "plan first" so Claude Code shows the plan before it writes code.
- Keep secrets out of the chat: never paste `client_secret.json`, tokens or passwords. If an error
  contains your e-mail or project ID, remove it before pasting.
- Ask for evidence: "tell me what you tested and what you could not test".
- Ask it to commit and push only when you are happy: "commit and push".

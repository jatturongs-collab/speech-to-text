# Speech to Text Dashboard

![Speech to Text](assets/banner.webp)

A Streamlit dashboard (dark theme, Thai / English UI) that turns Thai audio/video into clean `.txt` and `.md` transcripts.

> คู่มือภาษาไทย (Thai guide): [README.th.md](README.th.md)

| Tab | How it works | Needs |
|-----|--------------|-------|
| **Online (YouTube)** | Converts MP3 → MP4 if needed, **uploads it to your own YouTube channel automatically**, waits for YouTube's auto-generated Thai captions and downloads them. Fast, light on your PC. | Internet, a Google account, `client_secret.json` (see below) |
| **Offline (Ultra HQ)** | Upload one or many MP3, MP4, M4A, WAV, MKV or WEBM files (up to **2 GB each**); transcribed one after another locally by `faster-whisper` **large-v3**, CPU only (`int8`). Highest quality, slow. | ~6 GB free RAM, ~3 GB disk for the model |

## Requirements

- **Python 3.10 – 3.13** (3.14+ is not supported yet: the `av` dependency has no wheels)
- **ffmpeg** on your PATH (needed for the MP3 → MP4 converter). Windows: `winget install Gyan.FFmpeg`, macOS: `brew install ffmpeg`, Linux/WSL: `sudo apt install ffmpeg`
- Windows, macOS, Linux or WSL2. No GPU needed.

## Install & run

```bash
git clone https://github.com/jatturongs-collab/speech-to-text.git
cd speech-to-text

python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# WSL / Linux / macOS:   source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

The browser opens at <http://localhost:8501>. Use the **ไทย / English** switch in the sidebar, and the **Open the guide (README)** button in the sidebar to read this guide inside the app.

## Closed the page? Your uploads are not lost

Every upload to YouTube is saved in `jobs.json` (and every fetched transcript in the `transcripts/` folder) next to `app.py`. Both are git-ignored.

When you start the app again, the **Uploaded jobs** panel at the top lists them. For every job that was still waiting, the app **checks YouTube once right away**. If the transcript is ready you get a 🚩 flag, and the `.txt` / `.md` download buttons appear in the panel. Jobs that are not ready yet have a **Check now** button.

- The silent startup check never opens a sign-in window. Unlisted videos can be read without signing in; Private videos need your saved sign-in (`token.json`), otherwise press **Check now**.
- If you close the page **while the file is still uploading**, that upload is incomplete and must be started again. Once the upload finishes, the job is saved.
- Uploaded something earlier, before this feature existed? Use **Find recent videos on my YouTube channel** in the panel, then **Add and check transcript**.

**Why do I see different ports?** Streamlit opens `http://localhost:8501`, or 8502, 8503… if 8501 is still in use by an older copy that is still running. Each browser tab is a separate session. The random port during Google sign-in (for example `localhost:61503`) is only the temporary address Google redirects to; it is normal and closes after sign-in. Neither causes any problem now, because your progress is stored on disk, not in the browser page. Tip: stop the old copy (Ctrl+C in its PowerShell window) before starting a new one.

## Stop, history log and the channel video list

- **Stop / cancel job:** every long job (Auto 1 Click, the Online upload, the Offline transcription) shows a **หยุด / ยกเลิกงาน** button while it runs. Pressing it ends the job at once, also stops a running MP3 → MP4 conversion, and writes the event to the history.
  - If the upload had **not** finished, nothing is left on YouTube.
  - If it had, the video stays on your channel and the job is marked **Stopped**; **Check now** in the jobs list still works.
  - Offline: if the model is still being downloaded the first time, the stop takes effect when that download finishes.
- **History log:** the left sidebar has **ประวัติการทำงาน (Log)**. It lists the latest events (uploads, transcripts found, checks, stops, deletions, errors). **Click an entry** for its details (time, title, video link, message). **ดูประวัติทั้งหมด** shows the full table and lets you download the log file. The log is stored in `history.jsonl` next to `app.py` (git-ignored).
- **Videos on my YouTube channel:** open this panel (under the jobs list) and press **Load videos from my channel** to list your latest 50 uploads, including old ones from before this app.
  - Tick the rows you want (or **Select all**), then **Add as records and check transcripts** to put old videos into the jobs list and fetch their transcripts.
  - **Delete selected from YouTube** removes the ticked videos **permanently**. A confirmation dialog lists them and you must tick *I understand this cannot be undone* before the delete button works. This can delete any video on your channel, not only ones uploaded by this app.

## Auto 1 Click tab

> [!CAUTION]
> 🚩 **Prerequisite: set up `client_secret.json` first**

### 🔴 This tab uploads to your own YouTube channel, so it cannot work without a `client_secret.json` file next to `app.py`. Follow [Set up `client_secret.json`](#set-up-client_secretjson-needed-for-the-automatic-upload) (see below) before you use it. You only do it once.

**🔴 Example:** copy the file `client_secret.json` into the same folder as `app.py`:

```text
Directory: D:\speech-to-text

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a---          11/11/2026  4:42 AM            419 client_secret.json
-a---          11/11/2026  2:08 PM         106425 app.py
```

The fastest path: upload one **or many** files and walk away. **Choosing the files starts everything immediately, with no extra confirmation.**

Accepted formats: **MP3, M4A, WAV, MP4, MKV, WEBM**. Upload size is effectively unlimited (a 20 GB per-file cap), because the heavy part, the YouTube upload, does not use your PC. Files are processed one after another as a queue, and each file gets its own result card.

1. Converts audio-only files (MP3, M4A, WAV, or an MP4/MKV/WEBM that has no video track) to MP4 with a black picture. Real videos are uploaded as they are.
2. Uploads it to your YouTube channel as **Unlisted**.
3. Waits the full time set by the slider (**15 – 90 minutes, default 30**, counted from the end of the upload). It does not check during this time.
4. Checks for the Thai captions. If they are not ready, it re-checks every **5 minutes** (up to 6 more times, then stops; see `AUTO_RETRY_INTERVAL_S` and `AUTO_MAX_RETRIES` in `app.py`).
5. When the transcript is found, a 🚩 flag blinks, and the `.txt` / `.md` download buttons appear.
6. Below the result, **Delete this video from YouTube** removes the uploaded video from your channel once you no longer need it. It asks for confirmation first, and deleting is **permanent**. The transcript already shown in the dashboard stays until you close the page, so download it first. (The Online tab has the same button.) This uses the permissions you already granted, so no new sign-in is needed.

Keep the page open while it waits. This tab needs the same `client_secret.json` setup as below.

Things to know about many files:
- Streamlit holds uploaded files in RAM while the page is open, so for very large or very many files, add them in batches.
- YouTube's free API quota allows roughly **6 uploads per day** (about 1,600 of 10,000 units each). If the quota runs out, the remaining files are marked *Failed* with a clear message; try again the next day.
- **Stop** cancels the whole batch: files not yet uploaded are skipped, files already on YouTube stay there.

## Online tab: how it works

1. **Step 1** (only if you have an MP3): upload the MP3 and click **Convert to MP4**. YouTube rejects raw MP3 files, so the app adds a plain black picture.
2. **Step 2:** click **Upload to YouTube & Fetch Transcript**. The app
   - signs in to Google (browser opens the first time only),
   - uploads the MP4 to your channel as **Unlisted** (or **Private**),
   - checks every 45 seconds whether the Thai auto-captions exist (up to **15 minutes**, with a live "time elapsed" message),
   - shows the cleaned transcript with `.txt` and `.md` download buttons.
3. If 15 minutes pass with no captions, the video stays on your channel. Use **Check again** later, or the manual "I already have a YouTube URL" box.

You can also upload an MP4 you already have (the uploader in Step 2) instead of converting an MP3.

## Set up `client_secret.json` (needed for the automatic upload)

> [!CAUTION]
> 🚩 **Required, one time only.** Without `client_secret.json`, the **Auto 1 Click** and **Online** tabs cannot upload to YouTube.

It gives the app permission to upload to **your own** channel.

1. Go to <https://console.cloud.google.com/> and sign in with the Google account that owns your YouTube channel.
2. Create a project: top bar → project picker → **New project** (any name, e.g. `transcription-dashboard`).
3. Enable the API: **APIs & Services → Library** → search **YouTube Data API v3** → **Enable**.
4. Configure the consent screen: **APIs & Services → OAuth consent screen** (or *Google Auth Platform* → *Branding / Audience*).
   - User type: **External**. Fill in app name and your email.
   - Under **Audience / Test users**, **add your own Google email** as a test user. Leave the app in *Testing* mode.
5. Create the credentials: **APIs & Services → Credentials → Create credentials → OAuth client ID**.
   - Application type: **Desktop app**. Name it anything.
   - Click **Download JSON**.
6. **Rename the downloaded file to `client_secret.json`** and put it in the project folder (next to `app.py`).
7. Run the app and click **Upload to YouTube & Fetch Transcript**. A browser window opens:
   - Choose your account. If you see *"Google hasn't verified this app"*, click **Advanced → Go to … (unsafe)**. This is expected for your own private project.
   - Tick the YouTube permissions and continue. A `token.json` file is created so you won't be asked again.

> **Keep `client_secret.json` and `token.json` private.** They are already in `.gitignore`. Never commit or share them.

Good to know:
- **Unverified projects force uploads to Private.** The app handles this: if the public route can't read a Private video, it reads the captions through your authenticated account instead. For truly Unlisted uploads you would have to submit the project for Google's API audit, which you don't need for this tool.
- **Testing-mode tokens expire after 7 days**; the app just asks you to sign in again.
- **Quota:** each upload costs ~1,600 of the 10,000 free daily API units, so roughly 5–6 uploads a day.
- The sign-in window opens on the machine running Streamlit, so this feature works when you run the app **locally**, not on a remote server.

## Offline tab settings

`large-v3`, `device="cpu"`, `compute_type="int8"`, `language="th"`, `beam_size=5`, VAD filter with 500 ms min silence, `condition_on_previous_text=False` (prevents repetition loops), plus an initial prompt of Thai financial terms (see `INITIAL_PROMPT` in `app.py`; edit it for other domains). The first run downloads the model (~3 GB).

## Supported formats and upload limits

| Where | Formats | Files | Limit per file |
|-------|---------|-------|----------------|
| Auto 1 Click | MP3, M4A, WAV, MP4, MKV, WEBM | many | 20 GB (effectively unlimited) |
| Online → converter | MP3, M4A, WAV | one | 2 GB |
| Online → upload a video | MP4, MKV, WEBM | one | 2 GB |
| Offline | MP3, MP4, M4A, WAV, MKV, WEBM | many | 2 GB |

The limits are set per uploader in `app.py` (`UPLOAD_MB_AUTO`, `UPLOAD_MB_OFFLINE`) and the server-wide cap is `maxUploadSize` in `.streamlit/config.toml`.

## Appearance

The look is set in `.streamlit/config.toml` (colours, font, server upload cap). The only custom CSS is one small block (`tab_style()` in `app.py`) that makes the tabs bigger, bolder and framed; it takes its colours from the active theme. There are two themes: a **warm cream light theme** (terracotta accent) and the original **dark theme**. Streamlit follows your computer's light/dark setting by default; to choose, open the **⋮** menu (top right) and pick **System / Light / Dark**. The choice is remembered by the browser. Edit the `[theme.light]` / `[theme.dark]` sections to restyle the app, and run `streamlit run app.py` from the project folder so the file is picked up.

## Troubleshooting

- `File must be 200MB or smaller` → the limit is `maxUploadSize` (MB) in `.streamlit/config.toml`; restart after changing it.
- `Failed to build 'av'` → you are on Python 3.14+. Use 3.13 or older.
- `open() got an unexpected keyword argument 'metadata_errors'` → `av` is too new; run `pip install "av<17"`.
- *client_secret.json not found* → follow the setup section above and place the file next to `app.py`.
- *Access blocked / 403 access_not_configured* → the YouTube Data API v3 isn't enabled for your project, or your email isn't listed as a test user.
- *Upload fine, but no transcript after 15 minutes* → YouTube can be slow, or it couldn't detect speech. Press **Check again** after a while, and confirm the video has captions in YouTube Studio.
- *"The user has exceeded the number of videos they may upload" (`uploadLimitExceeded`)* → your YouTube **channel** reached its own daily upload limit (this is not the API quota). Options: wait about 24 hours; verify the channel with a phone number at <https://www.youtube.com/verify> (raises the limit); or use another Google account: press **Switch Google account** in the left sidebar, add the new email as a **Test user** in Google Cloud (consent screen → Audience), then start an upload and pick the new account. Videos and jobs of the old account cannot be checked or deleted from the new one.
- Offline run is slow → expected on CPU with the full `large-v3` model. Try a short clip first.

## Claude Skill

`SKILL.md` lets Claude Code manage and extend this project. Copy it into `.claude/skills/speech-to-text-dashboard/` (or your personal skills folder) to use it.

## License

[MIT](LICENSE) © 2026 AI investor alpha Jat

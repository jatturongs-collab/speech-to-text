# Prompts used to build this project

These are the prompts, in order, that were given to Claude Code to build this Speech to Text
dashboard (and its Claude Skill). They are kept in the original wording, including typos and mixed
Thai / English, so you can see how the project grew step by step.

Left out on purpose: pasted error logs, screenshots and one-word replies. Where a prompt contained
a personal folder path, it was shortened.

---

## Part 1 · Command-line tool (before the dashboard)

### 1. CPU-only Thai speech-to-text pipeline

```text
Create a high-quality, CPU-only local Speech-to-Text pipeline for Thai language using `faster-whisper`. 
I am running Windows 11 with PowerShell and strictly have NO GPU. Quality is the top priority, even if it heavily loads the CPU.

Please write the following two files to my current directory:

1. `setup.ps1`
- A PowerShell script to install `ffmpeg` via winget and `faster-whisper` via pip.

2. `hq_transcribe.py`
- Uses `faster-whisper` with the `large-v3-turbo` model.
- Explicitly set `device="cpu"` and `compute_type="int8"`.
- To maximize Thai language accuracy on CPU, set `beam_size=5` and `vad_filter=True` (with `min_silence_duration_ms=500`).
- Include this exact `initial_prompt` to force correct spelling of Thai financial terminology: "นี่คือคลิปOpportunity Day อธิบายงบการเงิน หุ้น SET, กำไรสุทธิ, ไตรมาส, อัตรากำไรขั้นต้น, ขาดทุน, YoY, QoQ, EBITDA, ยอดขาย, CAPEX"
- Use `argparse` to accept the input audio/video file path.
- Export both a `.txt` transcript and an `.srt` subtitle file with proper timestamps.

Please generate and save these files directly to the disk now.
```

### 2. Follow-up questions while setting up

```text
what I need to do next ?
```

### 3. More quality

```text
ต้องการให้เพิ่ม Ultra High Quality
```

---

## Part 2 · The Streamlit dashboard and the Claude Skill

### 4. The dashboard project

```text
Act as an expert Python Developer. I want to create a complete transcription dashboard project that I will push to my GitHub repo to share with my friend. 

Please create a Claude Skill and a Python-based Web Dashboard (using `streamlit`) for media file transcription (MP3/MP4 to .txt and .md). 

The dashboard must have a UI with 2 main options/tabs:

### Option 1: Online (YouTube Auto-Transcription)
- Workflow: The user uploads a media file to their own YouTube channel (handled manually or via API). In the dashboard, the user inputs the YouTube URL.
- The dashboard should have a "Fetch Transcript" button.
- Use `yt-dlp` or `youtube-transcript-api` to fetch the auto-generated Thai transcript.
- Clean the transcript (remove timestamps/duplicates) and provide a download button for both `.txt` and `.md` formats.

### Option 2: Offline (Ultra High-Quality Local Transcription)
- Workflow: The user uploads a local MP3/MP4 file directly into the dashboard.
- The dashboard should have a "Start Local Transcription" button.
- Strictly use `faster-whisper` with the FULL `large-v3` model.
- Hardware constraints (CRITICAL): This will run on Windows/WSL2 with strictly NO GPU (CPU ONLY). 
- You MUST configure the model with: `device="cpu"` and `compute_type="int8"`.
- To ensure Thai language quality and prevent hallucination loops, set: `language="th"`, `beam_size=5`, `vad_filter=True` (min silence 500ms), and `condition_on_previous_text=False`.
- Include an initial prompt for Thai financial terms: "นี่คือคลิปอธิบายงบการเงิน หุ้น SET, กำไรสุทธิ, ไตรมาส, อัตรากำไรขั้นต้น, ขาดทุน, YoY, QoQ, EBITDA, ยอดขาย, CAPEX"
- Provide download buttons for the final `.txt` and `.md` files.

### Deliverables:
Please generate and save the following project structure directly to my disk:
1. `app.py` - The main Streamlit dashboard application with a modern, clean UI.
2. `requirements.txt` - All necessary Python packages (streamlit, faster-whisper, yt-dlp, youtube-transcript-api, etc.).
3. `SKILL.md` - A Claude Skill file defining how Claude should manage, run, or update this project in the future. Give it a clear `name:` and `description:` in the YAML frontmatter.
4. `README.md` - Instructions for my friend on how to `pip install -r requirements.txt` and run `streamlit run app.py` on their machine.

Please write these files to the current directory now.
```

### 5. YouTube does not accept MP3: add a converter

```text
I found a limitation: YouTube does not accept raw MP3 files. 

Please update the Streamlit dashboard (`app.py`) to solve this problem. 
In the "Option 1: Online (YouTube Auto-Transcription)" tab, please add an "MP3 to YouTube-Ready MP4 Converter" helper utility.

Workflow for this utility:
1. The user uploads an MP3 file to this section in the dashboard.
2. Use Python's `subprocess` to run `ffmpeg` and convert the MP3 into an MP4 by adding a static black background video track.
3. Suggested ffmpeg command structure: 
   `ffmpeg -f lavfi -i color=c=black:s=1280x720:r=1 -i input.mp3 -c:a aac -vcodec libx264 -shortest output.mp4`
4. Show a progress indicator while converting.
5. Provide a "Download MP4 for YouTube" button so the user can download it and upload it to their YouTube channel.

Please apply these changes directly to `app.py`. Ensure the UI is intuitive so my friend knows to use this tool if they only have an MP3 file.
```

### 6. Small follow-ups

```text
you mean I  need to open new session of power shell and run dashboard
```

```text
I got error the file must be smaller than 200M. can you fix it.
```

```text
can you increate to 500M .
```

### 7. Thai text and clearer steps for the MP3 converter

```text
update UI and  

🎵 Only have an MP3? Convert it to a YouTube-ready MP4 first

YouTube does not accept raw MP3 files. This tool wraps your audio in an MP4 with a plain black picture so you can upload it to your channel. Then come back here and paste the video URL below.

เพิ่ม ภาษาไทยอันนี่
"
Youtube ไม่รับ MP3 format : ปกติ Voice Record จะเป็น MP3 and Video is MP4.

Additional Step 1.1 : upload MP3
Additional Step 1.2 : convert MP3 to MP4

หลังจากนั้นก็ upload MP4 file to youtube แบบที่เรา upload file ขึ้น youtube.
หลัง upload ขึ้น youtube สำเร็จ อีกสักพัก 1 ชม Youtube จะสร้าง transcript file ให้ทำ Step 2# ต่อ"
```

### 8. A better design

```text
can you design the better web or how we do that ?
```

```text
b, Thai/English
```

(The "b" picked the dark "pro tool" style; "Thai/English" asked for a language switch.)

---

## Part 3 · Automating the YouTube upload

### 9. Automatic upload and subtitle polling

```text
Please update the Streamlit dashboard (`app.py`) to fully automate the "Option 1: YouTube Auto-Transcription" workflow.

I want to eliminate the manual YouTube upload step. Please implement the following features:

1. Automated YouTube Upload:
- Integrate the `google-api-python-client` and `google-auth-oauthlib` libraries.
- After the user uploads an MP4 (or after the app converts an MP3 to MP4), provide a button to "Upload to YouTube & Fetch Transcript".
- The script should authenticate using a local `client_secret.json` file. 
- Automatically upload the MP4 to the authenticated user's YouTube channel as a "Private" or "Unlisted" video.
- Retrieve the new Video ID upon successful upload.

2. Subtitle Polling & Progress UI:
- YouTube auto-transcription takes time. Implement a polling loop (checking every 30-60 seconds) to check if the Thai auto-generated subtitles are available.
- Use `youtube-transcript-api` to attempt fetching the transcript inside the loop.
- Use Streamlit's `st.spinner` or a progress bar/status message to show the user that the app is waiting for YouTube to process the audio (e.g., "Waiting for YouTube to generate subtitles... This may take several minutes. Time elapsed: X seconds").
- Add a timeout mechanism (e.g., stop checking after 15 minutes) to prevent infinite loops.

3. Final Output:
- Once the transcript is successfully fetched, display it and provide the `.txt` and `.md` download buttons.

4. Documentation Update:
- Please also update `README.md` and `requirements.txt` to include the new Google API libraries.
- Add a clear instruction section in `README.md` explaining how the user can generate the `client_secret.json` from the Google Cloud Console to make this feature work.

Please apply these complex changes directly to the project files.
```

### 10. Questions about the Google sign-in

```text
อันนีหมายความว่าอย่างไร While the Google project is in Testing mode, the sign-in expires after 7 days. แล้วถ้าใช่ account ส่วนตัวได้ไหม
```

```text
what do you mean "Sign-in: the app signs in with client_secret.json. A browser opens the first time, then token.json is reused. The upload goes to your channel in chunks with a progress bar, and the app gets the new video ID." ?
```

```text
Google shows its own sign-in page., I don't see google show anything when I ran this ".\.venv\Scripts\python.exe -m streamlit run app.py"
```

(Then a red "client_secret.json not found" screenshot, and a Google "Error 403: access_denied" paste. Both were solved by creating the credentials and adding the user as a Test user.)

```text
upload complete and wait for  รอ YouTube สร้างคำบรรยาย
```

---

## Part 4 · More features

### 11. "Auto 1 Click" tab

```text
เพิ่ม Tab "Auto 1 Click"
Tab นี่ให้แค่ upload MP3 and upload youtube auto without user click.
option :Click Bar for waiting from 15 min to 90 min
Default 30 min.
After upload finish do check available of transcription after default or above timer select.
If the transcription available ,flag blink
```

```text
wait the full time first, then check once ,Check interval is 300 seconds,
```

### 12. Delete a YouTube video, and a README in the sidebar

```text
can you add delete youtube function in the below and add readme file in  left hand side so user can open for detail.
```

### 13. Closing the page must not lose the upload

```text
I found problem when the media file have been upload and finish but webpage have been closed then I start the app.py again it open newpage. can you have check first if the file have been complete upload therefore youtube might already have transcript then you can download and report . I found the https port are random use not sure if that would be problem.
```

### 14. Stop button, old YouTube records, bulk delete and history

```text
เพิ่ม ปุ่ม stop ยกเลิกงานกลางคันให้ด้วย  เพิ่ม record  youtube เก่าที่ upload แล้วก็มี list มี checkbox สำหรับ delete มี log file or history ด้าน panel ซ้ายมือให้กด click ดูรายละเอียดได้
```

### 15. More file formats, many files, bigger files

```text
Add feature
1# can you add support .wav and other format M4A, WAV, MKV, WEBM file as well
2# in  "Auto 1 Click" TAB, อัปโหลดไฟล์ with multiple file and above no.1# with no limited since upload to youtube not use PC resource.
3# in  "offline" TAB , 2GB per file (MAX) • MP3, MP4, M4A, WAV, MKV, WEBM and อัปโหลดไฟล์ with multiple file
```

### 16. Online limit, Thai guide, red-flag prerequisite

```text
1#in  "online" TAB , 2GB per file (MAX)
2#"Transcription" left Panel, in Tab "ไทย" or "English" 
When select "ไทย" เปิดคู่มือ( README)
คู่มือการใช้งาน ให้เพิ่มภาษาไทยกำกับ แทรกภาษาอังกฤษ ลงใน README
When select "English"  keep the existing เปิดคู่มือ( README) that is fine


in README , 

Auto 1 Click tab ,Put prerequisite  "Set up client_secret.json" in Red Flag (See below)
```

---

## Part 5 · Look and feel, and publishing

### 17. Theme like the reference screenshot

A screenshot of a warm cream and terracotta app was attached with:

```text
ถ้าทำ theming แบบนี ได้ไหม
```

```text
ทำได้เลย
```

### 18. Name, icon and tabs

An icon image was attached with:

```text
I like name Speech to Text rather than Transcription .  can you change it ?
I have icon file in attach. can you add it ?

font TAB อยากได้ตัวหนาใหญ่ สัก 50% กรอบและ background ชัดกว่านี่
```

### 19. YouTube channel upload limit

After a YouTube "uploadLimitExceeded" error:

```text
ผมใช่  second email ทำต่อได้ ทำอย่างไงต่อดี
```

### 20. Publish to GitHub

```text
could you upload this work into github url: https://github.com/jatturongs-collab/speech-to-text
```

### 21. MIT license and a red, bold README highlight

```text
เพิ่ม MIT and 

Change README

Highlight change to red font bold and 25% size.

"This tab uploads to your own YouTube channel, so it cannot work without a client_secret.json file next to app.py. 
Follow Set up client_secret.json (see below) before you use it. You only do it once."

Add normal font size

"
ตัวอย่าง(Red Font) :

normal font size

copy file "client_secret.json" มาอยู่ที่เดียวกับ  "app.py" 

Directory: D:\speech-to-text

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a---          11/11/2026  4:42 AM            419 client_secret.json
-a---          11/11/2026  2:08 PM         106425 app.py
"
```

```text
LICENSE (MIT) เอาไว้ทำไม ?
```

```text
ใช่ชือนี้แทน "AI investor alpha Jat" and you can push
```

### 22. This prompt folder

```text
can you add folder "prompt" , create file prompt and add prompt that I have ask you to do this skill.
```

---

## Tips if you want to reuse this

- Start with the first dashboard prompt (number 4) to get the base app, then add features one at a time, as above.
- Describe the limit or the pain you hit ("YouTube does not accept raw MP3 files") and ask for a fix. It worked better than asking for a big redesign in one step.
- Ask for what the *friend* will see ("make the UI intuitive") and for the README to be updated each time.

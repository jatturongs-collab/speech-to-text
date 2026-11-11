"""Speech to Text Dashboard (Streamlit)

Tab 1: Online  - MP3 -> MP4 helper + fetch the auto-generated Thai transcript from YouTube.
Tab 2: Offline - local, CPU-only transcription with faster-whisper large-v3.

Look & feel is set in .streamlit/config.toml (dark theme). UI language: Thai / English.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import streamlit as st

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
INITIAL_PROMPT = (
    "นี่คือคลิปอธิบายงบการเงิน หุ้น SET, กำไรสุทธิ, ไตรมาส, อัตรากำไรขั้นต้น, "
    "ขาดทุน, YoY, QoQ, EBITDA, ยอดขาย, CAPEX"
)
MODEL_NAME = "large-v3"
MEDIA_TYPES = ["mp3", "mp4", "m4a", "wav", "mkv", "webm"]

# Upload limits per file (MB). Streamlit keeps uploads in RAM, so "no limit" is a very high cap.
UPLOAD_MB_AUTO = 20480      # Auto 1 Click: effectively unlimited (uploading to YouTube is not CPU heavy)
UPLOAD_MB_OFFLINE = 2048    # Offline and Online tabs: 2 GB per file
AUDIO_ONLY_EXTS = {".mp3", ".m4a", ".wav"}   # always need a picture before YouTube accepts them
VIDEO_MIME = {".mp4": "video/mp4", ".mkv": "video/x-matroska", ".webm": "video/webm"}

# YouTube automation (Option 1)
APP_DIR = Path(__file__).resolve().parent
CLIENT_SECRET = APP_DIR / "client_secret.json"   # downloaded from Google Cloud Console
TOKEN_FILE = APP_DIR / "token.json"              # created after the first sign-in (keep private!)
JOBS_FILE = APP_DIR / "jobs.json"                # uploads in progress/finished (survives closing the page)
OUT_DIR = APP_DIR / "transcripts"                # every fetched transcript is also saved here
HISTORY_FILE = APP_DIR / "history.jsonl"         # log of what the app did (shown in the sidebar)
YT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",     # upload videos
    "https://www.googleapis.com/auth/youtube.force-ssl",  # read captions of your own videos
]
POLL_INTERVAL_S = 45     # how often to check for subtitles
POLL_TIMEOUT_S = 15 * 60  # stop waiting after 15 minutes
# "Auto 1 Click": wait the full chosen time first, check once, then retry every 5 minutes
AUTO_RETRY_INTERVAL_S = 300
AUTO_MAX_RETRIES = 6     # extra checks after the first one (6 x 5 min = 30 min grace)

# ----------------------------------------------------------------------------
# UI text (Thai / English)
# ----------------------------------------------------------------------------
TEXT = {
    "th": {
        "title": "Speech to Text Dashboard",
        "subtitle": "แปลงไฟล์เสียง/วิดีโอภาษาไทยเป็นข้อความ .txt และ .md",
        "language": "ภาษา / Language",
        "engine": "ตั้งค่าโมเดล (ออฟไลน์)",
        "engine_model": "โมเดล",
        "engine_hw": "ประมวลผล",
        "engine_lang": "ภาษาเสียง",
        "engine_vad": "VAD ตัดช่วงเงียบ",
        "engine_loop": "กันวนซ้ำ",
        "ffmpeg": "ffmpeg",
        "ffmpeg_ok": "พร้อมใช้งาน",
        "ffmpeg_missing": "ไม่พบ (ต้องใช้ตัวแปลง MP3→MP4)",
        "tab_online": "ออนไลน์ (YouTube)",
        "tab_offline": "ออฟไลน์ (คุณภาพสูงสุด)",
        "online_intro": "ให้ YouTube สร้าง transcript ให้อัตโนมัติ เร็ว ไม่ใช้แรงเครื่อง",
        "s1_title": "Step 1 · อัปโหลดไฟล์ขึ้น YouTube",
        "s1_caption": "อัปโหลดไฟล์ขึ้นช่อง YouTube ของคุณเอง (ตั้งเป็น Unlisted ได้)",
        "mp3_title": "มีแต่ไฟล์เสียง (MP3 / M4A / WAV) ใช่ไหม?",
        "mp3_info": "**YouTube ไม่รับไฟล์ MP3** ปกติไฟล์อัดเสียงจะเป็น MP3 ส่วนวิดีโอจะเป็น MP4 "
                    "เครื่องมือนี้จะแปลง MP3 เป็น MP4 (ภาพพื้นหลังสีดำ) เพื่อให้อัปโหลดขึ้น YouTube ได้",
        "s11": "Step 1.1 · อัปโหลดไฟล์เสียง",
        "s12": "Step 1.2 · แปลงเป็น MP4",
        "s13": "Step 1.3 · ไปที่ Step 2 เพื่ออัปโหลดอัตโนมัติ (หรือดาวน์โหลดไปอัปโหลดเอง)",
        "upload_mp3": "อัปโหลดไฟล์เสียง (MP3, M4A, WAV)",
        "convert_btn": "แปลงเป็น MP4",
        "converting": "กำลังแปลงไฟล์",
        "convert_done": "แปลงเสร็จแล้ว",
        "convert_fail": "แปลงไฟล์ไม่สำเร็จ",
        "mp4_ready": "พร้อมแล้ว",
        "download_mp4": "ดาวน์โหลด MP4 สำหรับ YouTube",
        "wait_note": "YouTube ต้องใช้เวลาสร้างคำบรรยาย (ปกติไม่กี่นาที) แอปจะอัปโหลดแล้วตรวจให้อัตโนมัติ "
                     "นานสูงสุด {mins} นาที",
        "s2_title": "Step 2 · อัปโหลดขึ้น YouTube และดึง transcript อัตโนมัติ",
        "s2_caption": "ต้องมีไฟล์ client_secret.json ในโฟลเดอร์โปรเจกต์ (ดูวิธีสร้างใน README)",
        "src_mp4_upload": "มีไฟล์วิดีโออยู่แล้ว (MP4 / MKV / WEBM)? อัปโหลดตรงนี้ได้เลย",
        "src_using": "ไฟล์ที่จะอัปโหลด",
        "src_none": "ยังไม่มีไฟล์ MP4: แปลงจาก MP3 ด้านบน หรืออัปโหลด MP4 ที่นี่",
        "privacy": "ความเป็นส่วนตัวของวิดีโอ",
        "privacy_unlisted": "Unlisted (แนะนำ)",
        "privacy_private": "Private",
        "privacy_note": "ถ้าโปรเจกต์ Google ยังไม่ผ่านการตรวจสอบ API วิดีโอจะถูกบังคับเป็น Private "
                        "แอปจะดึงคำบรรยายผ่านบัญชีของคุณแทน",
        "auto_btn": "อัปโหลดขึ้น YouTube และดึง Transcript",
        "no_secret": "ไม่พบไฟล์ client_secret.json ในโฟลเดอร์โปรเจกต์ ดูวิธีสร้างใน README",
        "signin": "กำลังเข้าสู่ระบบ Google (ถ้าเบราว์เซอร์เปิดขึ้น ให้กดอนุญาตแล้วกลับมาที่หน้านี้)...",
        "uploading": "กำลังอัปโหลดขึ้น YouTube",
        "uploaded": "อัปโหลดสำเร็จ · รหัสวิดีโอ {vid}",
        "waiting": "รอ YouTube สร้างคำบรรยาย... อาจใช้เวลาหลายนาที · "
                   "เวลาที่ผ่านไป {elapsed} วินาที · ตรวจครั้งถัดไปใน {nxt} วินาที",
        "waiting_label": "รอ YouTube สร้างคำบรรยาย",
        "checking": "กำลังตรวจหาคำบรรยาย...",
        "timeout": "หมดเวลา {mins} นาทีแล้วยังไม่พบคำบรรยาย วิดีโอยังอยู่ในช่องของคุณ "
                   "กด \"ตรวจอีกครั้ง\" ภายหลังได้",
        "recheck_btn": "ตรวจอีกครั้ง",
        "upload_fail": "อัปโหลดไม่สำเร็จ",
        "yt_link": "เปิดวิดีโอบน YouTube",
        "manual_title": "มีลิงก์ YouTube อยู่แล้ว? ดึง transcript ด้วยตนเอง",
        "tab_auto": "Auto 1 Click",
        "auto_intro": "อัปโหลดไฟล์เสียงหรือวิดีโอ (เลือกได้หลายไฟล์) แค่นี้พอ ระบบจะแปลงเป็น MP4 ถ้าจำเป็น อัปโหลดขึ้น YouTube รอ และตรวจ transcript ให้เองทั้งหมด",
        "auto_wait": "เวลารอก่อนตรวจ transcript (นาที) หลังอัปโหลดเสร็จ",
        "auto_upload": "อัปโหลดไฟล์ (เลือกได้หลายไฟล์): MP3, M4A, WAV, MP4, MKV, WEBM",
        "auto_note": "เมื่อเลือกไฟล์ ระบบจะเริ่มอัปโหลดขึ้นช่อง YouTube ของคุณทันที (Unlisted) ตามลำดับทีละไฟล์ โดยไม่ถามซ้ำ",
        "st_convert": "1 · แปลง MP3 เป็น MP4",
        "st_upload": "2 · อัปโหลดขึ้น YouTube",
        "st_wait": "3 · รอและตรวจ transcript",
        "auto_waiting": "รอ YouTube สร้างคำบรรยาย... เหลืออีก {remaining} (ตั้งไว้ {total} นาที) แล้วจึงตรวจ",
        "auto_retry": "ยังไม่พร้อม · ตรวจซ้ำครั้งที่ {n}/{m} ในอีก {remaining}",
        "auto_giveup": "ตรวจแล้ว {n} ครั้งยังไม่พบคำบรรยาย วิดีโอยังอยู่ในช่องของคุณ "
                       "ลองดูใน YouTube Studio หรือเพิ่มเวลารอแล้วลองอีกครั้ง",
        "auto_ready": "พบ transcript แล้ว!",
        "auto_ready_static": "Transcript พร้อมแล้ว",
        "reset_btn": "เริ่มใหม่ (ไฟล์ถัดไป)",
        "reset_hint": "ลบไฟล์เดิมออกแล้วเลือกไฟล์ใหม่ ระบบจะเริ่มอัตโนมัติ",
        "stop_btn": "หยุด / ยกเลิกงาน",
        "stopped_msg": "ยกเลิกงานแล้ว ถ้าอัปโหลดยังไม่เสร็จ จะไม่มีวิดีโอบน YouTube "
                       "ถ้าอัปโหลดเสร็จแล้ว วิดีโอยังอยู่ในช่องและกด \"ตรวจตอนนี้\" ในรายการงานได้ "
                       "(ต้องการเริ่มใหม่ ให้ลบไฟล์แล้วเลือกไฟล์ใหม่)",
        "job_stopped": "หยุดแล้ว",
        "hist_title": "ประวัติการทำงาน (Log)",
        "hist_none": "ยังไม่มีประวัติ",
        "hist_all": "ดูประวัติทั้งหมด",
        "hist_detail": "รายละเอียดเหตุการณ์",
        "hist_download": "ดาวน์โหลดไฟล์ log (.jsonl)",
        "f_time": "เวลา",
        "f_event": "เหตุการณ์",
        "f_title": "ชื่อ",
        "f_video": "วิดีโอ",
        "f_msg": "รายละเอียด",
        "ev_upload_done": "อัปโหลดสำเร็จ",
        "ev_transcript_found": "พบ transcript",
        "ev_check_empty": "ตรวจแล้ว ยังไม่พร้อม",
        "ev_stopped": "ยกเลิกงาน",
        "ev_deleted": "ลบวิดีโอ",
        "ev_delete_failed": "ลบไม่สำเร็จ",
        "ev_bulk_deleted": "ลบหลายรายการ",
        "ev_error": "เกิดข้อผิดพลาด",
        "ev_record_added": "เพิ่ม record",
        "ev_gave_up": "หมดเวลารอ",
        "ev_offline_done": "ถอดเสียงออฟไลน์เสร็จ",
        "ev_account_switched": "เปลี่ยนบัญชี Google",
        "chan_title": "วิดีโอในช่อง YouTube ของฉัน (เพิ่ม record เก่า / ลบหลายรายการ)",
        "chan_load": "โหลดรายการวิดีโอจากช่อง (ล่าสุด 50)",
        "chan_none": "กดปุ่มด้านบนเพื่อโหลดรายการวิดีโอที่เคยอัปโหลดไว้",
        "chan_empty": "ไม่มีวิดีโอในช่อง YouTube แล้ว",
        "chan_all": "เลือกทั้งหมด",
        "chan_clear": "ล้างที่เลือก",
        "chan_selected": "เลือกแล้ว {n} รายการ",
        "chan_add": "เพิ่มเป็น record และตรวจ transcript",
        "chan_delete": "ลบที่เลือกออกจาก YouTube",
        "chan_added": "เพิ่ม/ตรวจ {n} รายการแล้ว พบ transcript {f} รายการ",
        "col_select": "เลือก",
        "col_title": "ชื่อวิดีโอ",
        "col_date": "วันที่",
        "col_id": "รหัสวิดีโอ",
        "col_state": "สถานะในแอป",
        "state_none": "ยังไม่มี record",
        "bulk_title": "ลบวิดีโอหลายรายการ?",
        "bulk_warn": "จะลบ {n} วิดีโอออกจากช่อง YouTube ของคุณ **ถาวร กู้คืนไม่ได้** "
                     "(รวมวิดีโอที่ไม่ได้อัปโหลดผ่านแอปนี้ด้วย)",
        "bulk_ack": "ฉันเข้าใจว่าลบแล้วกู้คืนไม่ได้",
        "bulk_confirm": "ลบ {n} รายการถาวร",
        "bulk_done": "ลบสำเร็จ {ok} รายการ",
        "bulk_failed": "ลบไม่สำเร็จ {n} รายการ",
        "batch_progress": "กำลังจัดการไฟล์ {i}/{n}",
        "batch_uploaded": "อัปโหลดครบทุกไฟล์แล้ว",
        "batch_results": "ผลลัพธ์แต่ละไฟล์",
        "batch_quota": "โควต้า YouTube API ของวันนี้หมด ไฟล์ที่เหลือจึงไม่ได้อัปโหลด ลองใหม่พรุ่งนี้ "
                       "(อัปโหลดหนึ่งไฟล์ใช้ ~1,600 จาก 10,000 หน่วยต่อวัน)",
        "file_removed": "ไฟล์ถูกลบออกจากช่องอัปโหลดก่อนเริ่มทำงาน",
        "auto_mem_note": "แอปไม่จำกัดจำนวนและขนาดไฟล์ แต่ไฟล์ที่อัปโหลดเข้าแดชบอร์ดจะอยู่ใน RAM ชั่วคราว "
                         "ไฟล์ใหญ่หรือหลายไฟล์พร้อมกันควรทยอยอัปโหลด และ YouTube จำกัดโควต้าราว 6 ไฟล์ต่อวัน",
        "it_queued": "รอคิว",
        "it_uploading": "กำลังอัปโหลด",
        "it_waiting": "รอ YouTube",
        "it_done": "พร้อมแล้ว",
        "it_failed": "ผิดพลาด",
        "it_timeout": "หมดเวลารอ",
        "it_stopped": "ยกเลิก",
        "line_wait": ":material/hourglass_top: **{name}** · เหลืออีก {remaining} (ตั้งไว้ {total} นาที) แล้วจึงตรวจ",
        "line_retry": ":material/refresh: **{name}** · ยังไม่พร้อม ตรวจซ้ำครั้งที่ {n}/{m} ในอีก {remaining}",
        "line_done": ":material/check_circle: **{name}** · พบ transcript แล้ว",
        "line_timeout": ":material/timer_off: **{name}** · หมดเวลารอ",
        "clear_results": "ล้างผลลัพธ์",
        "batch_limit": "ช่อง YouTube นี้อัปโหลดครบจำนวนที่ YouTube อนุญาตต่อวันแล้ว (uploadLimitExceeded) "
                       "ไฟล์ที่เหลือจึงไม่ได้อัปโหลด ทางเลือก: รอประมาณ 24 ชั่วโมง, ยืนยันช่องด้วยเบอร์โทรที่ "
                       "youtube.com/verify เพื่อเพิ่มขีดจำกัด หรือกด \"เปลี่ยนบัญชี Google\" ที่แถบซ้ายเพื่อใช้อีเมลอื่น",
        "acct_title": "บัญชี Google",
        "acct_connected": "เชื่อมต่อแล้ว",
        "acct_none": "ยังไม่ได้เชื่อมต่อ",
        "acct_switch": "เปลี่ยนบัญชี Google",
        "acct_done": "ออกจากระบบแล้ว การอัปโหลดครั้งต่อไปจะให้เลือกบัญชี Google ใหม่",
        "acct_note": "อีเมลใหม่ต้องถูกเพิ่มเป็น Test user ใน Google Cloud ด้วย และวิดีโอ/งานของบัญชีเดิม "
                     "จะตรวจหรือลบจากบัญชีใหม่ไม่ได้",
        "del_btn": "ลบวิดีโอนี้ออกจาก YouTube",
        "del_hint": "ลบวิดีโอที่แอปอัปโหลดไว้ออกจากช่องของคุณ (แนะนำให้ดาวน์โหลด .txt/.md ก่อน)",
        "del_title": "ลบวิดีโอออกจาก YouTube?",
        "del_warn": "วิดีโอ \"{title}\" จะถูกลบออกจากช่อง YouTube ของคุณ **ถาวร กู้คืนไม่ได้** "
                    "ส่วน transcript ที่ได้แล้วในแดชบอร์ดนี้จะยังอยู่ (ปิดหน้านี้แล้วจะหาย)",
        "del_confirm": "ลบถาวร",
        "del_cancel": "ยกเลิก",
        "del_done": "ลบวิดีโอออกจาก YouTube แล้ว",
        "del_fail": "ลบไม่สำเร็จ",
        "readme_btn": "เปิดคู่มือ (README)",
        "readme_title": "คู่มือการใช้งาน",
        "readme_missing": "ไม่พบไฟล์ README.md ในโฟลเดอร์โปรเจกต์",
        "jobs_title": "งานที่อัปโหลดไว้ (ยังอยู่แม้ปิดหน้าเว็บ)",
        "jobs_none": "ยังไม่มีงานที่บันทึกไว้ งานจะถูกบันทึกอัตโนมัติหลังอัปโหลดขึ้น YouTube สำเร็จ",
        "jobs_checking": "กำลังตรวจ transcript ของงานที่ค้างอยู่...",
        "jobs_found": "พบ transcript {n} งาน",
        "job_waiting": "รอ YouTube",
        "job_done": "พร้อมแล้ว",
        "job_uploaded": "อัปโหลดเมื่อ {when}",
        "job_check_btn": "ตรวจตอนนี้",
        "job_not_ready": "ยังไม่พบคำบรรยาย YouTube อาจยังประมวลผลอยู่ ลองใหม่ภายหลัง",
        "job_preview": "ดูตัวอย่าง",
        "channel_hint": "เคยอัปโหลดไปแล้วแต่ไม่มีในรายการนี้? ค้นหาจากช่อง YouTube ของคุณได้",
        "channel_btn": "ค้นหาวิดีโอล่าสุดในช่อง YouTube ของฉัน",
        "channel_add": "เพิ่มและตรวจ transcript",
        "channel_none": "ไม่พบวิดีโอใหม่ที่ยังไม่อยู่ในรายการ",
        "url": "ลิงก์ YouTube",
        "caption_lang": "รหัสภาษาของคำบรรยาย",
        "fetch_btn": "ดึง Transcript",
        "fetching": "กำลังดึง transcript...",
        "bad_url": "อ่านรหัสวิดีโอจากลิงก์นี้ไม่ได้",
        "fetch_fail": "ดึง transcript ไม่ได้ YouTube อาจยังประมวลผลอยู่ (ลองใหม่ภายหลัง) "
                      "หรือวิดีโอนี้ไม่มีคำบรรยายในภาษานี้",
        "details": "รายละเอียด",
        "fetched": "ดึงมาได้ {n} บรรทัด (หลังทำความสะอาด)",
        "offline_intro": "ถอดเสียงในเครื่องด้วย **faster-whisper {model}** (CPU, int8) รองรับ MP3, MP4, M4A, WAV, MKV, WEBM "
                         "ไฟล์ละไม่เกิน 2 GB เลือกได้หลายไฟล์ (ถอดทีละไฟล์ตามลำดับ) คุณภาพสูงสุดแต่ช้า "
                         "รอบแรกจะดาวน์โหลดโมเดล (~3 GB)",
        "upload_media": "อัปโหลดไฟล์เสียง / วิดีโอ (เลือกได้หลายไฟล์)",
        "start_btn": "เริ่มถอดเสียง",
        "loading_model": "กำลังโหลดโมเดล {model} (รอบแรกจะดาวน์โหลด)...",
        "transcribing": "กำลังถอดเสียง",
        "done": "เสร็จแล้ว",
        "failed": "ถอดเสียงไม่สำเร็จ",
        "empty_state": "อัปโหลดไฟล์เพื่อเริ่มต้น",
        "m_time": "เวลาที่ใช้",
        "m_audio": "ความยาวเสียง",
        "m_lines": "จำนวนบรรทัด",
        "m_chars": "จำนวนตัวอักษร",
        "dl_txt": "ดาวน์โหลด .txt",
        "dl_md": "ดาวน์โหลด .md",
        "preview": "ตัวอย่าง (กดไอคอนมุมขวาเพื่อคัดลอก)",
    },
    "en": {
        "title": "Speech to Text Dashboard",
        "subtitle": "Turn Thai audio/video into clean .txt and .md transcripts",
        "language": "ภาษา / Language",
        "engine": "Model settings (offline)",
        "engine_model": "Model",
        "engine_hw": "Compute",
        "engine_lang": "Audio language",
        "engine_vad": "VAD silence cut",
        "engine_loop": "Anti-loop",
        "ffmpeg": "ffmpeg",
        "ffmpeg_ok": "ready",
        "ffmpeg_missing": "not found (needed for MP3→MP4)",
        "tab_online": "Online (YouTube)",
        "tab_offline": "Offline (Ultra HQ)",
        "online_intro": "Let YouTube generate the transcript for you. Fast, light on your machine.",
        "s1_title": "Step 1 · Upload to YouTube",
        "s1_caption": "Upload your media to your own YouTube channel (Unlisted is fine).",
        "mp3_title": "Only have an audio file (MP3 / M4A / WAV)?",
        "mp3_info": "**YouTube does not accept MP3 files.** Voice recordings are usually MP3 and video is MP4. "
                    "This tool wraps your audio in an MP4 with a plain black picture so YouTube will take it.",
        "s11": "Step 1.1 · Upload the audio file",
        "s12": "Step 1.2 · Convert to MP4",
        "s13": "Step 1.3 · Go to Step 2 to upload automatically (or download and upload it yourself)",
        "upload_mp3": "Upload an audio file (MP3, M4A, WAV)",
        "convert_btn": "Convert to MP4",
        "converting": "Converting to MP4",
        "convert_done": "Conversion complete",
        "convert_fail": "Conversion failed",
        "mp4_ready": "Ready",
        "download_mp4": "Download MP4 for YouTube",
        "wait_note": "YouTube needs a while to generate captions (usually a few minutes). The app uploads, "
                     "then checks automatically for up to {mins} minutes.",
        "s2_title": "Step 2 · Upload to YouTube & fetch the transcript automatically",
        "s2_caption": "Requires client_secret.json in the project folder (see the README).",
        "src_mp4_upload": "Already have a video (MP4 / MKV / WEBM)? Upload it here",
        "src_using": "File to upload",
        "src_none": "No MP4 yet: convert an MP3 above, or upload an MP4 here.",
        "privacy": "Video privacy",
        "privacy_unlisted": "Unlisted (recommended)",
        "privacy_private": "Private",
        "privacy_note": "If your Google project hasn't passed API verification, uploads are forced to "
                        "Private. The app then reads the captions through your own account instead.",
        "auto_btn": "Upload to YouTube & Fetch Transcript",
        "no_secret": "client_secret.json was not found in the project folder. See the README to create it.",
        "signin": "Signing in to Google (if a browser opens, allow access and come back here)...",
        "uploading": "Uploading to YouTube",
        "uploaded": "Uploaded · video id {vid}",
        "waiting": "Waiting for YouTube to generate subtitles... This may take several minutes. "
                   "Time elapsed: {elapsed} seconds · next check in {nxt} s",
        "waiting_label": "Waiting for YouTube to generate subtitles",
        "checking": "Checking for subtitles...",
        "timeout": "Stopped after {mins} minutes without finding subtitles. The video is still on "
                   "your channel; use \"Check again\" later.",
        "recheck_btn": "Check again",
        "upload_fail": "Upload failed",
        "yt_link": "Open the video on YouTube",
        "manual_title": "Already have a YouTube URL? Fetch manually",
        "tab_auto": "Auto 1 Click",
        "auto_intro": "Just upload audio or video files (several at once is fine). The app converts them to MP4 if "
                      "needed, uploads them to YouTube, waits, and checks for the transcripts, all by itself.",
        "auto_wait": "Time to wait before checking for the transcript (minutes, after the upload)",
        "auto_upload": "Upload files (several allowed): MP3, M4A, WAV, MP4, MKV, WEBM",
        "auto_note": "Choosing files starts uploading them to your YouTube channel at once (Unlisted), one after "
                     "another, with no further confirmation.",
        "st_convert": "1 · Convert MP3 to MP4",
        "st_upload": "2 · Upload to YouTube",
        "st_wait": "3 · Wait and check for the transcript",
        "auto_waiting": "Waiting for YouTube to generate subtitles... {remaining} left "
                        "(set to {total} min), then checking",
        "auto_retry": "Not ready yet · re-check {n}/{m} in {remaining}",
        "auto_giveup": "Checked {n} times and found no subtitles. The video is still on your channel; "
                       "look in YouTube Studio, or raise the wait time and try again.",
        "auto_ready": "Transcript found!",
        "auto_ready_static": "Transcript is ready",
        "reset_btn": "Start over (next file)",
        "reset_hint": "Remove the old file and choose a new one; it starts automatically.",
        "stop_btn": "Stop / cancel job",
        "stopped_msg": "Job cancelled. If the upload had not finished, nothing is on YouTube. If it had, "
                       "the video is still on your channel and \"Check now\" in the jobs list still works "
                       "(to start over, remove the file and choose a new one).",
        "job_stopped": "Stopped",
        "hist_title": "History log",
        "hist_none": "No history yet.",
        "hist_all": "View full history",
        "hist_detail": "Event details",
        "hist_download": "Download the log file (.jsonl)",
        "f_time": "Time",
        "f_event": "Event",
        "f_title": "Title",
        "f_video": "Video",
        "f_msg": "Details",
        "ev_upload_done": "Upload finished",
        "ev_transcript_found": "Transcript found",
        "ev_check_empty": "Checked, not ready",
        "ev_stopped": "Job cancelled",
        "ev_deleted": "Video deleted",
        "ev_delete_failed": "Delete failed",
        "ev_bulk_deleted": "Bulk delete",
        "ev_error": "Error",
        "ev_record_added": "Record added",
        "ev_gave_up": "Gave up waiting",
        "ev_offline_done": "Offline transcription done",
        "ev_account_switched": "Switched Google account",
        "chan_title": "Videos on my YouTube channel (add old records / delete several)",
        "chan_load": "Load videos from my channel (latest 50)",
        "chan_none": "Press the button above to load the videos you uploaded earlier.",
        "chan_empty": "There are no videos left on the channel.",
        "chan_all": "Select all",
        "chan_clear": "Clear selection",
        "chan_selected": "{n} selected",
        "chan_add": "Add as records and check transcripts",
        "chan_delete": "Delete selected from YouTube",
        "chan_added": "Added/checked {n} video(s); transcripts found: {f}",
        "col_select": "Select",
        "col_title": "Video title",
        "col_date": "Date",
        "col_id": "Video ID",
        "col_state": "Status in app",
        "state_none": "No record yet",
        "bulk_title": "Delete several videos?",
        "bulk_warn": "This will **permanently delete** {n} video(s) from your YouTube channel and "
                     "cannot be undone (including videos not uploaded through this app).",
        "bulk_ack": "I understand this cannot be undone",
        "bulk_confirm": "Delete {n} permanently",
        "bulk_done": "Deleted {ok} video(s)",
        "bulk_failed": "{n} video(s) could not be deleted",
        "batch_progress": "Processing file {i} of {n}",
        "batch_uploaded": "All uploads finished",
        "batch_results": "Results per file",
        "batch_quota": "Today's YouTube API quota is used up, so the remaining files were not uploaded. "
                       "Try again tomorrow (one upload costs ~1,600 of 10,000 units per day).",
        "file_removed": "The file was removed from the uploader before it started.",
        "auto_mem_note": "The app sets no limit on the number or size of files, but files sent to the "
                         "dashboard are held in RAM for a while. Add big or many files in batches; "
                         "YouTube's quota allows roughly 6 uploads per day.",
        "it_queued": "Queued",
        "it_uploading": "Uploading",
        "it_waiting": "Waiting for YouTube",
        "it_done": "Ready",
        "it_failed": "Failed",
        "it_timeout": "Timed out",
        "it_stopped": "Cancelled",
        "line_wait": ":material/hourglass_top: **{name}** · {remaining} left (set to {total} min), then checking",
        "line_retry": ":material/refresh: **{name}** · not ready, re-check {n}/{m} in {remaining}",
        "line_done": ":material/check_circle: **{name}** · transcript found",
        "line_timeout": ":material/timer_off: **{name}** · gave up waiting",
        "clear_results": "Clear results",
        "batch_limit": "This YouTube channel has reached the number of uploads YouTube allows per day "
                       "(uploadLimitExceeded), so the remaining files were not uploaded. Options: wait about "
                       "24 hours, verify the channel with a phone number at youtube.com/verify to raise the "
                       "limit, or press \"Switch Google account\" in the left sidebar to use another email.",
        "acct_title": "Google account",
        "acct_connected": "Connected",
        "acct_none": "Not connected",
        "acct_switch": "Switch Google account",
        "acct_done": "Signed out. The next upload will let you choose a Google account.",
        "acct_note": "The new email must also be added as a Test user in Google Cloud, and videos/jobs "
                     "of the previous account can't be checked or deleted from the new one.",
        "del_btn": "Delete this video from YouTube",
        "del_hint": "Removes the video this app uploaded from your channel "
                    "(download the .txt/.md first).",
        "del_title": "Delete the video from YouTube?",
        "del_warn": "The video \"{title}\" will be **permanently deleted** from your YouTube channel "
                    "and cannot be restored. The transcript already in this dashboard stays "
                    "(until you close the page).",
        "del_confirm": "Delete permanently",
        "del_cancel": "Cancel",
        "del_done": "The video was deleted from YouTube.",
        "del_fail": "Delete failed",
        "readme_btn": "Open the guide (README)",
        "readme_title": "User guide",
        "readme_missing": "README.md was not found in the project folder.",
        "jobs_title": "Uploaded jobs (kept even if you close the page)",
        "jobs_none": "No saved jobs yet. A job is saved automatically after an upload to YouTube succeeds.",
        "jobs_checking": "Checking transcripts for pending jobs...",
        "jobs_found": "Found {n} transcript(s)",
        "job_waiting": "Waiting for YouTube",
        "job_done": "Ready",
        "job_uploaded": "Uploaded {when}",
        "job_check_btn": "Check now",
        "job_not_ready": "No subtitles yet. YouTube may still be processing; try again later.",
        "job_preview": "Show preview",
        "channel_hint": "Uploaded earlier but not in this list? Look it up on your YouTube channel.",
        "channel_btn": "Find recent videos on my YouTube channel",
        "channel_add": "Add and check transcript",
        "channel_none": "No new videos that aren't already in the list.",
        "url": "YouTube URL",
        "caption_lang": "Caption language code",
        "fetch_btn": "Fetch Transcript",
        "fetching": "Fetching transcript...",
        "bad_url": "Could not read a YouTube video id from that URL.",
        "fetch_fail": "Could not fetch a transcript. Captions may still be processing "
                      "(try again later), or the video has none in this language.",
        "details": "Details",
        "fetched": "Fetched {n} lines (after cleaning).",
        "offline_intro": "Runs **faster-whisper {model}** fully on your CPU (int8). Supports MP3, MP4, M4A, WAV, MKV, WEBM, "
                         "up to 2 GB per file, several files at once (transcribed one after another). "
                         "Best quality, but slow. The first run downloads the model (~3 GB).",
        "upload_media": "Upload audio / video (multiple files allowed)",
        "start_btn": "Start Local Speech to Text",
        "loading_model": "Loading {model} (first time downloads the model)...",
        "transcribing": "Transcribing",
        "done": "Done",
        "failed": "Speech to Text failed",
        "empty_state": "Upload a file to get started.",
        "m_time": "Time taken",
        "m_audio": "Audio length",
        "m_lines": "Lines",
        "m_chars": "Characters",
        "dl_txt": "Download .txt",
        "dl_md": "Download .md",
        "preview": "Preview (use the icon at top right to copy)",
    },
}

ICON_PATH = APP_DIR / "assets" / "icon.png"
st.set_page_config(page_title="Speech to Text Dashboard",
                   page_icon=str(ICON_PATH) if ICON_PATH.exists() else ":material/graphic_eq:",
                   layout="wide")
if ICON_PATH.exists():
    st.logo(str(ICON_PATH), size="large")


# ----------------------------------------------------------------------------
# Helpers (pure functions first)
# ----------------------------------------------------------------------------
def extract_video_id(url: str) -> str | None:
    """Return the 11-char YouTube video id from common URL shapes."""
    url = url.strip()
    if re.fullmatch(r"[\w-]{11}", url):
        return url
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in ("youtu.be",):
        vid = parsed.path.lstrip("/").split("/")[0]
    elif host.endswith("youtube.com"):
        if parsed.path == "/watch":
            vid = parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            vid = parts[1] if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v") else ""
    else:
        return None
    return vid if re.fullmatch(r"[\w-]{11}", vid or "") else None


def clean_lines(lines: list[str]) -> list[str]:
    """Strip tags/timestamps/noise markers, drop empty and consecutive duplicate lines."""
    out: list[str] = []
    for line in lines:
        line = re.sub(r"<[^>]+>", "", line)                       # <c>, <00:00:01.000>
        line = re.sub(r"\[\s*(?:ดนตรี|เสียงดนตรี|music|applause|เสียงปรบมือ)\s*\]", "", line, flags=re.I)
        line = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?\b", "", line)  # timestamps
        line = re.sub(r"\s+", " ", line).strip()
        if line and (not out or out[-1] != line):
            out.append(line)
    return out


def to_markdown(title: str, lines: list[str], meta: dict[str, str]) -> str:
    paragraphs = [" ".join(lines[i:i + 5]) for i in range(0, len(lines), 5)]
    meta_md = "\n".join(f"- **{k}:** {v}" for k, v in meta.items())
    return f"# {title}\n\n{meta_md}\n\n---\n\n" + "\n\n".join(paragraphs) + "\n"


def fmt_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fetch_with_transcript_api(video_id: str, lang: str) -> list[str]:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    transcripts = api.list(video_id)
    try:
        tr = transcripts.find_generated_transcript([lang])
    except Exception:
        tr = transcripts.find_transcript([lang])  # manual subs as a fallback
    return [s.text for s in tr.fetch()]


def fetch_with_ytdlp(url: str, lang: str) -> list[str]:
    """Fallback: download auto subtitles (vtt) with yt-dlp and read the text lines."""
    import yt_dlp

    with tempfile.TemporaryDirectory() as tmp:
        opts = {
            "skip_download": True,
            "writeautomaticsub": True,
            "writesubtitles": True,
            "subtitleslangs": [lang],
            "subtitlesformat": "vtt",
            "outtmpl": os.path.join(tmp, "sub.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        files = [f for f in os.listdir(tmp) if f.endswith(".vtt")]
        if not files:
            raise RuntimeError("yt-dlp found no subtitles for this video.")
        with open(os.path.join(tmp, files[0]), encoding="utf-8") as f:
            raw = f.read().splitlines()
    skip = ("WEBVTT", "Kind:", "Language:", "NOTE")
    return [l for l in raw if l.strip() and "-->" not in l and not l.startswith(skip)]


def get_video_title(url: str) -> str:
    try:
        import yt_dlp

        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "no_warnings": True}) as ydl:
            return ydl.extract_info(url, download=False).get("title") or "YouTube Transcript"
    except Exception:
        return "YouTube Transcript"


def audio_duration(path: str) -> float | None:
    """Duration in seconds (uses PyAV, already installed with faster-whisper)."""
    try:
        import av

        with av.open(path) as c:
            return c.duration / 1_000_000 if c.duration else None
    except Exception:
        return None


def mp3_to_mp4(src: str, dst: str, on_progress) -> None:
    """Add a static black 1280x720 video track to audio so YouTube accepts it."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg was not found. Install it (Windows: `winget install Gyan.FFmpeg`, "
            "macOS: `brew install ffmpeg`, Linux/WSL: `sudo apt install ffmpeg`) "
            "and restart the dashboard."
        )
    total = audio_duration(src)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
        "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=1",
        "-i", src,
        "-c:a", "aac", "-b:a", "192k",
        "-vcodec", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-shortest",
        "-progress", "pipe:1",
        dst,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    try:
        for line in proc.stdout:
            if line.startswith("out_time_us=") and total:
                try:
                    on_progress(min(int(line.split("=")[1]) / 1_000_000 / total, 1.0))
                except ValueError:
                    pass  # "N/A" at the start
        err = proc.stderr.read()
        if proc.wait() != 0:
            raise RuntimeError(err.strip() or f"ffmpeg exited with code {proc.returncode}")
    finally:
        if proc.poll() is None:   # interrupted (Stop button / page closed): don't leave ffmpeg running
            proc.kill()


def get_youtube_service(allow_browser: bool = True):
    """Authenticate with client_secret.json (browser sign-in the first time, then token.json).

    allow_browser=False never opens a sign-in window (used for silent checks at startup).
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), YT_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None  # revoked/expired refresh token -> sign in again
    if not creds or not creds.valid:
        if not allow_browser:
            raise RuntimeError("Google sign-in required")
        if not CLIENT_SECRET.exists():
            raise FileNotFoundError(str(CLIENT_SECRET))
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), YT_SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent select_account")
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def needs_conversion(path: str) -> bool:
    """True if the file must be wrapped in an MP4 with a black picture before YouTube accepts it.

    MP3/M4A/WAV are audio only. MP4/MKV/WEBM are uploaded as they are, unless they have no video track.
    """
    if Path(path).suffix.lower() in AUDIO_ONLY_EXTS:
        return True
    try:
        import av

        with av.open(path) as c:
            return not any(s.type == "video" for s in c.streams)
    except Exception:
        return False   # can't tell: let YouTube decide


def upload_video(yt, path: str, title: str, privacy: str, lang: str, on_progress) -> str:
    """Resumable upload; returns the new video id."""
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title[:100] or "Transcription upload",
            "description": "Uploaded for automatic captioning.",
            "categoryId": "22",
            "defaultAudioLanguage": lang,   # helps YouTube pick the right speech model
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(path, mimetype=VIDEO_MIME.get(Path(path).suffix.lower(), "video/mp4"), chunksize=8 * 1024 * 1024, resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            on_progress(status.progress())
    on_progress(1.0)
    return response["id"]


def fetch_with_captions_api(yt, video_id: str, lang: str) -> list[str]:
    """Read the caption track through the authenticated API (works for Private videos)."""
    items = yt.captions().list(part="snippet", videoId=video_id).execute().get("items", [])
    track = next((i for i in items if i["snippet"].get("language", "").startswith(lang)), None)
    if not track:
        return []
    raw = yt.captions().download_media(id=track["id"], tfmt="srt").execute()
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
    return [l for l in text.splitlines()
            if l.strip() and "-->" not in l and not l.strip().isdigit()]


def try_fetch_transcript(yt, video_id: str, lang: str) -> tuple[list[str] | None, str]:
    """One attempt: public route first, then the authenticated API. Returns (lines, last_error)."""
    errors = []
    try:
        lines = fetch_with_transcript_api(video_id, lang)
        if lines:
            return lines, ""
    except Exception as e:
        errors.append(f"youtube-transcript-api: {type(e).__name__}")
    if yt is not None:
        try:
            lines = fetch_with_captions_api(yt, video_id, lang)
            if lines:
                return lines, ""
            errors.append("captions API: no track yet")
        except Exception as e:
            errors.append(f"captions API: {e}")
    else:
        errors.append("not signed in (Private videos need sign-in)")
    return None, " | ".join(errors)


def wait_for_transcript(yt, video_id: str, lang: str, render, interval: int = POLL_INTERVAL_S,
                        timeout: int = POLL_TIMEOUT_S) -> tuple[list[str] | None, str]:
    """Poll every `interval` seconds until subtitles appear or `timeout` passes.

    `render(elapsed_s, next_check_s)` is called once per second so the UI can show progress.
    """
    start = time.time()
    next_check, last_err = 0.0, ""
    while True:
        elapsed = time.time() - start
        if elapsed >= next_check:
            lines, last_err = try_fetch_transcript(yt, video_id, lang)
            if lines:
                return lines, ""
            next_check = (time.time() - start) + interval
        if time.time() - start >= timeout:
            return None, last_err
        render(int(time.time() - start), max(0, int(next_check - (time.time() - start))))
        time.sleep(1)


def load_jobs() -> list[dict]:
    try:
        data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_jobs(jobs: list[dict]) -> None:
    tmp = JOBS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(JOBS_FILE)


def upsert_job(job: dict) -> None:
    """Add a job, or merge into the existing one with the same video_id."""
    jobs = load_jobs()
    for existing in jobs:
        if existing.get("video_id") == job["video_id"]:
            existing.update(job)
            break
    else:
        jobs.append(job)
    save_jobs(jobs)


def update_job(video_id: str, **changes) -> None:
    """Change fields of an existing job. Does nothing if the video isn't a saved job."""
    jobs = load_jobs()
    for job in jobs:
        if job.get("video_id") == video_id:
            job.update(changes)
            save_jobs(jobs)
            return


def save_transcript(video_id: str, txt: str, md: str) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / f"{video_id}.txt").write_text(txt, encoding="utf-8")
    (OUT_DIR / f"{video_id}.md").write_text(md, encoding="utf-8")


def read_transcript(video_id: str) -> tuple[str, str] | None:
    try:
        return ((OUT_DIR / f"{video_id}.txt").read_text(encoding="utf-8"),
                (OUT_DIR / f"{video_id}.md").read_text(encoding="utf-8"))
    except OSError:
        return None


def log_event(event: str, **fields) -> None:
    """Append one line to history.jsonl (shown in the sidebar). Never raises."""
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "event": event}
    rec.update({k: v for k, v in fields.items() if v not in (None, "")})
    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def load_history() -> list[dict]:
    """All log entries, newest first."""
    entries = []
    try:
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        return []
    return entries[::-1]


def list_recent_uploads(yt, limit: int = 10) -> list[dict]:
    """Newest videos on the signed-in channel (used to recover uploads the app lost track of)."""
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    items = yt.playlistItems().list(part="snippet", playlistId=uploads,
                                    maxResults=limit).execute().get("items", [])
    return [{"video_id": i["snippet"]["resourceId"]["videoId"], "title": i["snippet"]["title"],
             "published": i["snippet"].get("publishedAt", "")} for i in items]


def store_online_result(lines: list[str], url: str, lang: str, video_id: str, secs: float,
                        method: str, title: str | None = None, key: str = "online") -> None:
    cleaned = clean_lines(lines)
    title = title or get_video_title(url)
    meta = {"Source": url, "Language": lang, "Method": method,
            "Generated": datetime.now().strftime("%Y-%m-%d %H:%M")}
    st.session_state[key] = {
        "txt": "\n".join(cleaned),
        "md": to_markdown(title, cleaned, meta),
        "n_lines": len(cleaned),
        "secs": secs,
        "audio": None,
        "name": video_id,
    }
    # Keep a copy on disk and mark the saved job as done, so it survives closing the page
    res = st.session_state[key]
    save_transcript(video_id, res["txt"], res["md"])
    update_job(video_id, status="done", title=title)
    log_event("transcript_found", video_id=video_id, title=title, lines=res["n_lines"],
              method=method)


@st.cache_resource(show_spinner=False)
def load_model():
    from faster_whisper import WhisperModel

    return WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Speech to Text")
    lang_choice = st.segmented_control(
        "Language", ["th", "en"], default="th", required=True,
        format_func=lambda v: "ไทย" if v == "th" else "English",
        key="ui_lang", label_visibility="collapsed",
    )
T = TEXT[lang_choice or "th"]


def t(key: str, **kw) -> str:
    return T[key].format(**kw) if kw else T[key]


def render_readme(text: str) -> None:
    """st.markdown plus GitHub-style alerts: '> [!CAUTION] ...' becomes a red box with a 🚩."""
    alert = re.compile(r"(?m)^> \[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*\n((?:>.*(?:\n|$))*)")
    boxes = {"CAUTION": st.error, "WARNING": st.warning, "NOTE": st.info, "IMPORTANT": st.info,
             "TIP": st.success}
    # README conventions (plain Markdown, so GitHub shows them too):
    #   "### 🔴 text"  -> in the app: red, bold, 125% size paragraph (GitHub: an H3, i.e. bold and 125%)
    #   "**🔴 text**"  -> in the app: red bold label (GitHub: bold with a red dot)
    special = re.compile(r"(?m)^(?:!\[([^\]]*)\]\((assets/[^)]+)\)|### 🔴 (.+?))[ \t]*$")

    def red_html(line: str) -> str:
        from html import escape

        h = escape(line.replace("**", ""))
        h = re.sub(r"`([^`]+)`", r'<code style="color:inherit">\1</code>', h)
        h = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" style="color:inherit">\1</a>', h)
        return f'<p style="color:#E5372B;font-weight:700;font-size:125%;margin:.5rem 0 1rem">{h}</p>'

    def flush(part: str) -> None:
        if part.strip():
            st.markdown(re.sub(r"\*\*🔴 (.+?)\*\*", r":red[**\1**]", part))

    def md(chunk: str) -> None:
        pos_i = 0
        for sm in special.finditer(chunk):
            flush(chunk[pos_i:sm.start()])
            if sm.group(3):
                st.html(red_html(sm.group(3)))
            else:
                path = APP_DIR / sm.group(2)
                if path.exists():
                    st.image(str(path), width="stretch", alt=sm.group(1))
            pos_i = sm.end()
        flush(chunk[pos_i:])

    pos = 0
    for m in alert.finditer(text):
        if text[pos:m.start()].strip():
            md(text[pos:m.start()])
        body = "\n".join(re.sub(r"^>\s?", "", line) for line in m.group(2).splitlines()).strip()
        if m.group(1) == "CAUTION":
            boxes["CAUTION"](body.removeprefix("🚩").lstrip(), icon="🚩")   # the box already has the flag
        else:
            boxes[m.group(1)](body)
        pos = m.end()
    if text[pos:].strip():
        md(text[pos:])


@st.dialog(t("readme_title"), width="large")
def readme_dialog():
    # Thai UI -> README.th.md (Thai with English terms); English UI -> README.md
    readme = APP_DIR / "README.th.md" if (lang_choice or "th") == "th" else APP_DIR / "README.md"
    if not readme.exists():
        readme = APP_DIR / "README.md"
    if readme.exists():
        render_readme(readme.read_text(encoding="utf-8"))
    else:
        st.warning(t("readme_missing"))


@st.dialog(t("del_title"), icon=":material/delete:")
def confirm_delete_dialog(video: dict):
    """Ask once more, then delete the video this app uploaded (cannot be undone)."""
    video_id = video.get("video_id") or video.get("id")
    st.warning(t("del_warn", title=video.get("title") or video_id), icon=":material/warning:")
    c1, c2 = st.columns(2)
    if c1.button(t("del_cancel"), width="stretch"):
        st.rerun()
    if c2.button(t("del_confirm"), type="primary", width="stretch",
                 icon=":material/delete_forever:"):
        try:
            from googleapiclient.errors import HttpError

            yt = get_youtube_service()
            try:
                yt.videos().delete(id=video_id).execute()
            except HttpError as e:
                if getattr(e.resp, "status", None) != 404:   # 404 = already gone, treat as deleted
                    raise
            video["deleted"] = True
            update_job(video_id, status="deleted")
            log_event("deleted", video_id=video_id, title=video.get("title"))
            st.rerun()
        except Exception as e:
            st.error(f"{t('del_fail')}: {e}")
            log_event("delete_failed", video_id=video_id, title=video.get("title"), message=str(e))


def stop_job(kind: str) -> None:
    """Callback of the Stop buttons. It runs first in the re-run that interrupts the running job."""
    job = st.session_state.pop("active_job", None) or {}
    if kind == "auto":
        batch = st.session_state.get("auto_batch", [])
        for it in batch:
            if it["status"] in ("queued", "uploading", "waiting"):
                uploaded = bool(it.get("video_id"))
                it["status"] = "stopped"
                if uploaded:
                    update_job(it["video_id"], status="stopped")
                log_event("stopped", kind="auto", video_id=it.get("video_id"), title=it["title"],
                          message=("stopped after the upload finished (video is still on YouTube)"
                                   if uploaded else
                                   "stopped before the upload finished (nothing was left on YouTube)"))
        st.session_state.setdefault("auto_ignore_ids", set()).update(it["file_id"] for it in batch)
    else:
        video_id = job.get("video_id")
        log_event("stopped", kind=kind, video_id=video_id, title=job.get("title"),
                  message=("stopped after the upload finished (video is still on YouTube)" if video_id
                           else "stopped before the job finished"))
        if video_id:
            update_job(video_id, status="stopped")
    st.session_state[f"{kind}_stopped"] = True


EVENT_ICONS = {
    "upload_done": ":material/cloud_done:", "transcript_found": ":material/check_circle:",
    "check_empty": ":material/hourglass_empty:", "stopped": ":material/stop_circle:",
    "deleted": ":material/delete:", "delete_failed": ":material/error:",
    "bulk_deleted": ":material/delete_sweep:", "error": ":material/error:",
    "record_added": ":material/playlist_add:", "gave_up": ":material/timer_off:",
    "offline_done": ":material/memory:", "account_switched": ":material/switch_account:",
}


def ev_label(event: str) -> str:
    return T.get(f"ev_{event}", event)


@st.dialog(t("hist_detail"), width="large")
def history_detail_dialog(rec: dict):
    st.markdown(f"#### {ev_label(rec.get('event', ''))}")
    st.markdown(f"**{t('f_time')}:** {rec.get('ts', '').replace('T', ' ')}")
    if rec.get("title"):
        st.markdown(f"**{t('f_title')}:** {rec['title']}")
    if rec.get("video_id"):
        st.markdown(f"**{t('f_video')}:** [{rec['video_id']}](https://youtu.be/{rec['video_id']})")
    if rec.get("message"):
        st.markdown(f"**{t('f_msg')}:**")
        st.code(str(rec["message"]), language=None, wrap_lines=True)
    extra = {k: v for k, v in rec.items()
             if k not in ("ts", "event", "title", "video_id", "message", "url")}
    if extra:
        st.json(extra)


@st.dialog(t("hist_all"), width="large")
def history_all_dialog():
    entries = load_history()
    if not entries:
        st.caption(t("hist_none"))
        return
    rows = [{t("f_time"): e.get("ts", "").replace("T", " "), t("f_event"): ev_label(e.get("event", "")),
             t("f_title"): e.get("title", ""), t("f_video"): e.get("video_id", ""),
             t("f_msg"): e.get("message", "")} for e in entries]
    st.dataframe(rows, hide_index=True, width="stretch", height=420)
    st.download_button(t("hist_download"), HISTORY_FILE.read_bytes(), file_name="history.jsonl",
                       mime="application/json", icon=":material/download:")


def render_account_sidebar() -> None:
    """Shows whether a Google account is connected and lets the user sign out to pick another."""
    with st.expander(t("acct_title"), icon=":material/account_circle:"):
        if TOKEN_FILE.exists():
            st.badge(t("acct_connected"), icon=":material/check_circle:", color="green")
            if st.button(t("acct_switch"), key="acct_switch", width="stretch",
                         icon=":material/switch_account:"):
                try:
                    TOKEN_FILE.unlink()
                    log_event("account_switched", message="token.json removed; the next upload asks "
                                                           "which Google account to use")
                except OSError as e:
                    st.error(str(e))
                else:
                    st.success(t("acct_done"))
        else:
            st.badge(t("acct_none"), icon=":material/info:", color="gray")
        st.caption(t("acct_note"))


def render_history_sidebar() -> None:
    entries = load_history()
    with st.expander(f"{t('hist_title')} ({len(entries)})", icon=":material/history:"):
        if not entries:
            st.caption(t("hist_none"))
        for i, rec in enumerate(entries[:10]):
            stamp = rec.get("ts", "")[5:16].replace("T", " ")
            if st.button(f"{stamp} · {ev_label(rec.get('event', ''))}", key=f"hist_{i}",
                         width="stretch", icon=EVENT_ICONS.get(rec.get("event"), ":material/circle:"),
                         help=rec.get("title") or rec.get("video_id")):
                history_detail_dialog(rec)
        if entries and st.button(t("hist_all"), key="hist_all", width="stretch",
                                 icon=":material/list_alt:"):
            history_all_dialog()


@st.dialog(t("bulk_title"), icon=":material/delete_sweep:", width="large")
def bulk_delete_dialog(videos: list[dict]):
    """Delete several channel videos at once (needs an extra 'I understand' tick)."""
    st.warning(t("bulk_warn", n=len(videos)), icon=":material/warning:")
    st.markdown("\n".join(f"- {v['title']} (`{v['video_id']}`)" for v in videos[:30])
                + (f"\n- … +{len(videos) - 30}" if len(videos) > 30 else ""))
    ack = st.checkbox(t("bulk_ack"), key="bulk_ack")
    c1, c2 = st.columns(2)
    if c1.button(t("del_cancel"), width="stretch", key="bulk_cancel"):
        st.rerun()
    if c2.button(t("bulk_confirm", n=len(videos)), type="primary", width="stretch", disabled=not ack,
                 icon=":material/delete_forever:", key="bulk_go"):
        from googleapiclient.errors import HttpError

        ok, failed = 0, []
        try:
            yt = get_youtube_service()
            bar = st.progress(0.0)
            for n, v in enumerate(videos, 1):
                try:
                    yt.videos().delete(id=v["video_id"]).execute()
                    ok += 1
                    update_job(v["video_id"], status="deleted")
                except HttpError as e:
                    if getattr(e.resp, "status", None) == 404:   # already gone
                        ok += 1
                        update_job(v["video_id"], status="deleted")
                    else:
                        failed.append(f"{v['video_id']}: {e}")
                bar.progress(n / len(videos))
        except Exception as e:
            failed.append(str(e))
        log_event("bulk_deleted", message=f"deleted {ok}, failed {len(failed)}",
                  ids=[v["video_id"] for v in videos], errors=failed[:5] or None)
        gone = {v["video_id"] for v in videos}
        st.session_state["channel_vids"] = [v for v in st.session_state.get("channel_vids", [])
                                            if v["video_id"] not in gone or v["video_id"] in
                                            {f.split(":")[0] for f in failed}]
        st.session_state["chan_ver"] = st.session_state.get("chan_ver", 0) + 1
        st.session_state["chan_all"] = False
        st.session_state["bulk_report"] = {"ok": ok, "failed": failed}
        st.rerun()


with st.sidebar:
    st.markdown(f"##### {t('engine')}")
    with st.container(border=True):
        st.markdown(
            f"**{t('engine_model')}** · `{MODEL_NAME}`  \n"
            f"**{t('engine_hw')}** · `CPU / int8`  \n"
            f"**{t('engine_lang')}** · `th`  \n"
            f"**{t('engine_vad')}** · `500 ms`  \n"
            f"**{t('engine_loop')}** · `on`"
        )
    if shutil.which("ffmpeg"):
        st.badge(f"{t('ffmpeg')}: {t('ffmpeg_ok')}", icon=":material/check_circle:", color="green")
    else:
        st.badge(f"{t('ffmpeg')}: {t('ffmpeg_missing')}", icon=":material/error:", color="red")
    if st.button(t("readme_btn"), icon=":material/menu_book:", width="stretch", key="readme_open"):
        readme_dialog()
    render_account_sidebar()
    render_history_sidebar()


def show_result(key: str):
    """Metrics + download buttons + preview for a stored result."""
    res = st.session_state.get(key)
    if not res:
        return
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("m_time"), fmt_duration(res["secs"]), border=True)
    m2.metric(t("m_audio"), fmt_duration(res["audio"]) if res["audio"] else "-", border=True)
    m3.metric(t("m_lines"), f"{res['n_lines']:,}", border=True)
    m4.metric(t("m_chars"), f"{len(res['txt']):,}", border=True)
    c1, c2 = st.columns(2)
    c1.download_button(t("dl_txt"), res["txt"], file_name=f"{res['name']}.txt", mime="text/plain",
                       width="stretch", icon=":material/download:", type="primary", key=f"{key}_txt")
    c2.download_button(t("dl_md"), res["md"], file_name=f"{res['name']}.md", mime="text/markdown",
                       width="stretch", icon=":material/download:", key=f"{key}_md")
    st.caption(t("preview"))
    st.code(res["txt"], language=None, wrap_lines=True, height=320)


# ----------------------------------------------------------------------------
# Header + tabs
# ----------------------------------------------------------------------------
st.title(t("title"), anchor=False)
st.caption(t("subtitle"))

def ready_flag(text: str) -> None:
    """A flag that blinks (12 times, then stays on). Respects 'reduce motion' settings."""
    try:
        is_dark = st.context.theme.type == "dark"
    except Exception:
        is_dark = False
    accent = "#22d3ee" if is_dark else "#A94E2C"   # readable on the dark and on the cream theme
    st.html(
        "<style>"
        "@keyframes flagblink{0%,100%{opacity:1}50%{opacity:.15}}"
        ".ready-flag{display:inline-block;padding:.6rem 1.1rem;border-radius:.6rem;"
        f"border:1px solid {accent};color:{accent};font-weight:600;font-size:1.15rem;"
        "animation:flagblink 1s ease-in-out 12}"
        "@media (prefers-reduced-motion:reduce){.ready-flag{animation:none}}"
        "</style>"
        f'<div class="ready-flag">🚩 {text}</div>'
    )


def check_job(job: dict, yt) -> bool:
    """Look for the transcript of a saved job; on success store it (memory + disk) and mark it done."""
    lines, err = try_fetch_transcript(yt, job["video_id"], "th")
    update_job(job["video_id"], checked_at=time.time(), last_error=err)
    if not lines:
        log_event("check_empty", video_id=job["video_id"], title=job.get("title"), message=err)
    if lines:
        store_online_result(lines, job["url"], "th", job["video_id"], 0.0,
                            "YouTube auto captions (recovered)", title=job.get("title"),
                            key=f"job_{job['video_id']}")
        return True
    return False


def jobs_startup_check() -> None:
    """Once per browser session: look for transcripts of uploads that are still waiting."""
    if st.session_state.get("jobs_checked"):
        return
    st.session_state["jobs_checked"] = True
    pending = [j for j in load_jobs() if j.get("status") == "waiting"]
    if not pending:
        return
    yt = None
    if TOKEN_FILE.exists():
        try:
            yt = get_youtube_service(allow_browser=False)   # never pop up a sign-in at startup
        except Exception:
            yt = None
    found = 0
    with st.spinner(t("jobs_checking")):
        for job in pending:
            found += bool(check_job(job, yt))
    if found:
        ready_flag(t("jobs_found", n=found))
        st.toast(f"🚩 {t('jobs_found', n=found)}")


def render_jobs_panel() -> None:
    jobs = [j for j in load_jobs() if j.get("status") != "deleted"]
    jobs.sort(key=lambda j: j.get("uploaded_at", 0), reverse=True)
    with st.expander(f"{t('jobs_title')} ({len(jobs)})", icon=":material/history:",
                     expanded=bool(jobs)):
        if not jobs:
            st.caption(t("jobs_none"))
        for job in jobs:
            vid = job["video_id"]
            title = job.get("title") or vid
            safe = re.sub(r'[\\/:*?"<>|]+', "_", title).strip()[:80] or vid
            when = datetime.fromtimestamp(job.get("uploaded_at", 0)).strftime("%Y-%m-%d %H:%M")
            with st.container(border=True):
                c1, c2 = st.columns([4, 2], vertical_alignment="center")
                c1.markdown(f"**{title}**")
                c1.caption(f"{t('job_uploaded', when=when)} · [{vid}]({job['url']})")
                if job.get("status") == "done":
                    c2.badge(t("job_done"), icon=":material/check_circle:", color="green")
                elif job.get("status") == "stopped":
                    c2.badge(t("job_stopped"), icon=":material/stop_circle:", color="gray")
                else:
                    c2.badge(t("job_waiting"), icon=":material/schedule:", color="orange")

                b1, b2, _ = st.columns([2, 3, 2])
                if job.get("status") != "done" and b1.button(
                        t("job_check_btn"), key=f"jobchk_{vid}", icon=":material/refresh:"):
                    try:
                        ok = check_job(job, get_youtube_service())
                    except Exception as e:
                        ok = False
                        st.error(str(e))
                    if ok:
                        st.rerun()
                    st.warning(t("job_not_ready"))
                if b2.button(t("del_btn"), key=f"jobdel_{vid}", icon=":material/delete:"):
                    confirm_delete_dialog(job)

                if job.get("status") == "done":
                    data = read_transcript(vid)
                    if data:
                        txt, md = data
                        d1, d2 = st.columns(2)
                        d1.download_button(t("dl_txt"), txt, file_name=f"{safe}.txt",
                                           mime="text/plain", width="stretch",
                                           icon=":material/download:", type="primary",
                                           key=f"jobtxt_{vid}")
                        d2.download_button(t("dl_md"), md, file_name=f"{safe}.md",
                                           mime="text/markdown", width="stretch",
                                           icon=":material/download:", key=f"jobmd_{vid}")
                        if st.toggle(t("job_preview"), key=f"jobprev_{vid}"):
                            st.code(txt, language=None, wrap_lines=True, height=240)



def render_channel_panel() -> None:
    """All videos on the channel: add old uploads as records, tick several and delete them."""
    known = {j["video_id"]: j for j in load_jobs()}
    with st.expander(t("chan_title"), icon=":material/video_library:"):
        if msg := st.session_state.pop("chan_msg", None):
            st.success(msg)
        report = st.session_state.pop("bulk_report", None)
        if report:
            st.success(t("bulk_done", ok=report["ok"]), icon=":material/delete_sweep:")
            if report["failed"]:
                st.error(t("bulk_failed", n=len(report["failed"])))
                st.code("\n".join(report["failed"]))
        if st.button(t("chan_load"), key="chan_load", icon=":material/sync:"):
            try:
                st.session_state["channel_vids"] = list_recent_uploads(get_youtube_service(), 50)
                st.session_state["chan_ver"] = st.session_state.get("chan_ver", 0) + 1
                st.session_state["chan_all"] = False
            except Exception as e:
                st.error(str(e))
                log_event("error", where="load channel videos", message=str(e))
        vids = st.session_state.get("channel_vids")
        if vids is None:
            st.caption(t("chan_none"))
            return
        if not vids:   # e.g. every video was just deleted: an empty table can't hold a checkbox column
            st.caption(t("chan_empty"))
            return

        import pandas as pd

        labels = {"done": t("job_done"), "waiting": t("job_waiting"), "stopped": t("job_stopped")}
        df = pd.DataFrame({
            "select": [bool(st.session_state.get("chan_all"))] * len(vids),
            "title": [v["title"] for v in vids],
            "date": [v["published"][:10] for v in vids],
            "id": [v["video_id"] for v in vids],
            "state": [labels.get(known.get(v["video_id"], {}).get("status"), t("state_none"))
                      for v in vids],
        })
        edited = st.data_editor(
            df, key=f"chan_editor_{st.session_state.get('chan_ver', 0)}", hide_index=True,
            width="stretch", disabled=["title", "date", "id", "state"],
            column_config={
                "select": st.column_config.CheckboxColumn(t("col_select"), width="small"),
                "title": st.column_config.TextColumn(t("col_title")),
                "date": st.column_config.TextColumn(t("col_date"), width="small"),
                "id": st.column_config.TextColumn(t("col_id"), width="small"),
                "state": st.column_config.TextColumn(t("col_state")),
            })
        picked = [v for v, flag in zip(vids, edited["select"].tolist()) if flag]

        s1, s2, s3 = st.columns([2, 2, 3], vertical_alignment="center")
        if s1.button(t("chan_all"), key="chan_sel_all", width="stretch"):
            st.session_state["chan_all"] = True
            st.session_state["chan_ver"] = st.session_state.get("chan_ver", 0) + 1
            st.rerun()
        if s2.button(t("chan_clear"), key="chan_sel_none", width="stretch"):
            st.session_state["chan_all"] = False
            st.session_state["chan_ver"] = st.session_state.get("chan_ver", 0) + 1
            st.rerun()
        s3.caption(t("chan_selected", n=len(picked)))

        a1, a2 = st.columns(2)
        if a1.button(t("chan_add"), key="chan_add", disabled=not picked, width="stretch",
                     icon=":material/playlist_add:"):
            n_done = found = 0
            try:
                yt = get_youtube_service()
                with st.spinner(t("checking")):
                    for v in picked:
                        job = known.get(v["video_id"])
                        if job is None:
                            try:
                                stamp = datetime.fromisoformat(
                                    v["published"].replace("Z", "+00:00")).timestamp()
                            except ValueError:
                                stamp = time.time()
                            job = {"video_id": v["video_id"],
                                   "url": f"https://youtu.be/{v['video_id']}",
                                   "title": v["title"], "uploaded_at": stamp, "status": "waiting"}
                            upsert_job(job)
                            log_event("record_added", video_id=v["video_id"], title=v["title"])
                        if job.get("status") != "done":
                            found += bool(check_job(job, yt))
                        n_done += 1
            except Exception as e:
                st.error(str(e))
                log_event("error", where="add records", message=str(e))
            st.session_state["chan_msg"] = t("chan_added", n=n_done, f=found)
            st.rerun()
        if a2.button(t("chan_delete"), key="chan_del", disabled=not picked, width="stretch",
                     type="primary", icon=":material/delete_sweep:"):
            bulk_delete_dialog(picked)


jobs_startup_check()
render_jobs_panel()
render_channel_panel()

def tab_style() -> None:
    """Bigger, bolder tabs with a clear frame and background.

    The only custom CSS in the app. It needs no palette: colours come from the live theme in the
    browser (text colour for the frame/background, the tab's own primary colour for the active
    pill), so it follows the light/dark switch instantly. Targets the keyed st.tabs
    (.st-key-main_tabs) and ARIA roles, which are stable across Streamlit versions.
    """
    k = ".st-key-main_tabs"
    st.html(f"""<style>
{k} [role="tablist"] {{
  gap: .6rem; padding: .45rem; border-radius: 1rem;
  background: color-mix(in srgb, currentColor 9%, transparent);
  border: 2px solid color-mix(in srgb, currentColor 35%, transparent);
}}
{k} [role="tab"] {{
  position: relative; isolation: isolate; height: auto; padding: .55rem 1.25rem;
  border-radius: .7rem; cursor: pointer;
}}
{k} [role="tab"] p {{ font-size: 21px; font-weight: 700; line-height: 1.4; }}
{k} [role="tab"]:not([aria-selected="true"]) {{ color: inherit; }}
{k} [role="tab"]:not([aria-selected="true"]):hover {{
  background: color-mix(in srgb, currentColor 12%, transparent);
}}
{k} [role="tab"][aria-selected="true"]::before {{
  content: ""; position: absolute; inset: 0; z-index: -1; border-radius: inherit;
  background: currentColor;   /* the tab's colour is the theme's primary colour */
}}
{k} [role="tab"][aria-selected="true"] p,
{k} [role="tab"][aria-selected="true"] span {{ color: Canvas; }}   /* white on light, dark on dark */
{k} .react-aria-SelectionIndicator {{ display: none; }}
@media (max-width: 640px) {{
  {k} [role="tab"] {{ padding: .4rem .7rem; }}
  {k} [role="tab"] p {{ font-size: 16px; }}
}}
</style>""")


tab_style()
tab_auto, tab_online, tab_offline = st.tabs([
    f":material/bolt: {t('tab_auto')}",
    f":material/cloud: {t('tab_online')}",
    f":material/memory: {t('tab_offline')}",
], key="main_tabs")

# ---- Option 0: Auto 1 Click -------------------------------------------------
with tab_auto:
    st.caption(t("auto_intro"))
    wait_min = st.slider(t("auto_wait"), min_value=15, max_value=90, value=30, step=5,
                         format="%d min", key="auto_wait_min")
    auto_files = st.file_uploader(t("auto_upload"), type=MEDIA_TYPES, accept_multiple_files=True,
                                  max_upload_size=UPLOAD_MB_AUTO, key="auto_files")
    st.caption(f":material/bolt: {t('auto_note')}")
    st.caption(f":material/memory: {t('auto_mem_note')}")

    batch: list[dict] = st.session_state.setdefault("auto_batch", [])
    ignore: set = st.session_state.setdefault("auto_ignore_ids", set())
    files = {f.file_id: f for f in (auto_files or [])}
    known = {it["file_id"] for it in batch}
    for f in auto_files or []:
        if f.file_id not in known and f.file_id not in ignore:
            batch.append({"file_id": f.file_id, "name": f.name,
                          "title": os.path.splitext(f.name)[0], "status": "queued",
                          "video_id": None, "url": None, "uploaded_at": None,
                          "attempts": 0, "next_at": None, "error": None})
    for it in batch:   # removed from the uploader before it was processed
        if it["status"] in ("queued", "uploading") and it["file_id"] not in files:
            it["status"], it["error"] = "failed", t("file_removed")

    queued = [it for it in batch if it["status"] in ("queued", "uploading")]
    waiting = [it for it in batch if it["status"] == "waiting" and not it.get("deleted")]
    just_done: list[str] = []
    yt = None

    # Stop button: created BEFORE the long work so it can be pressed while it runs.
    stop_slot = st.empty()
    if queued and not CLIENT_SECRET.exists():
        st.error(t("no_secret"))
        queued = []
    if queued or waiting:
        st.session_state.pop("auto_stopped", None)
        st.session_state["active_job"] = {"kind": "auto", "title": f"{len(queued) + len(waiting)} file(s)"}
        stop_slot.button(t("stop_btn"), key="auto_stop", icon=":material/stop_circle:",
                         on_click=stop_job, args=("auto",))
    elif st.session_state.pop("auto_stopped", None):
        st.warning(t("stopped_msg"), icon=":material/stop_circle:")

    # 1) Queue: convert (if needed) + upload every new file, one after another. No button.
    if queued:
        overall = st.progress(0.0)
        stop_key = None   # set when every later upload would fail for the same reason
        for idx, it in enumerate(queued, 1):
            overall.progress((idx - 1) / len(queued), text=t("batch_progress", i=idx, n=len(queued)))
            if stop_key:
                it["status"], it["error"] = "failed", t(stop_key)
                continue
            f = files[it["file_id"]]
            stt = st.status(f"{idx}/{len(queued)} · {it['name']}", expanded=True)
            try:
                with stt, tempfile.TemporaryDirectory() as tmpdir:
                    it["status"] = "uploading"
                    suffix = os.path.splitext(f.name)[1].lower() or ".bin"
                    src = os.path.join(tmpdir, "input" + suffix)
                    with open(src, "wb") as fh:
                        fh.write(f.getbuffer())
                    if needs_conversion(src):
                        dst = os.path.join(tmpdir, "output.mp4")
                        bar = st.progress(0.0, text=f"{t('converting')}...")
                        mp3_to_mp4(src, dst, lambda p, b=bar: b.progress(
                            p, text=f"{t('converting')}... {p:.0%}"))
                        bar.progress(1.0, text=t("convert_done"))
                    else:
                        dst = src   # real video: YouTube takes it as it is
                    if yt is None:
                        stt.update(label=f"{idx}/{len(queued)} · {t('signin')}")
                        yt = get_youtube_service()
                    stt.update(label=f"{idx}/{len(queued)} · {t('st_upload')} · {it['name']}")
                    bar2 = st.progress(0.0)
                    video_id = upload_video(
                        yt, dst, it["title"], "unlisted", "th",
                        lambda p, b=bar2: b.progress(p, text=f"{t('uploading')} {p:.0%}"))
                    it.update(video_id=video_id, url=f"https://youtu.be/{video_id}",
                              uploaded_at=time.time(), status="waiting")
                    upsert_job({"video_id": video_id, "url": it["url"], "title": it["title"],
                                "uploaded_at": it["uploaded_at"], "status": "waiting"})
                    log_event("upload_done", video_id=video_id, title=it["title"], url=it["url"],
                              source="auto")
                    st.write(f":material/check_circle: {t('uploaded', vid=video_id)} · {it['url']}")
                    stt.update(label=f"{idx}/{len(queued)} · {it['name']}", state="complete",
                               expanded=False)
            except Exception as e:
                it["status"], it["error"] = "failed", str(e)
                stt.update(state="error")
                st.error(f"{it['name']}: {t('upload_fail')}: {e}")
                log_event("error", where="auto upload", title=it["name"], message=str(e))
                if "uploadLimitExceeded" in str(e):
                    stop_key = "batch_limit"
                elif "quotaExceeded" in str(e):
                    stop_key = "batch_quota"
        overall.progress(1.0, text=t("batch_uploaded"))
        waiting = [it for it in batch if it["status"] == "waiting" and not it.get("deleted")]

    # 2) Wait the full chosen time (no checking), then check once; retry every 5 min if needed.
    #    Re-running the page resumes from the saved timestamps.
    if waiting:
        timeout_s = wait_min * 60
        wstatus = st.status(t("st_wait"), expanded=True)
        try:
            with wstatus:
                if yt is None:
                    yt = get_youtube_service()
                board = st.empty()
                while True:
                    now = time.time()
                    rows, still = [], 0
                    for it in waiting:
                        if it["status"] == "waiting":
                            due = it["uploaded_at"] + timeout_s if it["attempts"] == 0 else it["next_at"]
                            if now >= due:
                                got, err = try_fetch_transcript(yt, it["video_id"], "th")
                                it["attempts"] += 1
                                if got:
                                    key = f"auto_result_{it['video_id']}"
                                    store_online_result(
                                        got, it["url"], "th", it["video_id"],
                                        time.time() - it["uploaded_at"],
                                        "YouTube auto captions (Auto 1 Click)",
                                        title=it["title"], key=key)
                                    it["status"], it["result_key"] = "done", key
                                    just_done.append(it["title"])
                                    st.toast(f"🚩 {t('auto_ready')}: {it['title']}")
                                elif it["attempts"] > AUTO_MAX_RETRIES:
                                    it["status"], it["error"] = "timeout", err
                                    log_event("gave_up", video_id=it["video_id"], title=it["title"],
                                              message=err or f"no subtitles after {it['attempts']} checks")
                                else:
                                    it["next_at"] = time.time() + AUTO_RETRY_INTERVAL_S
                                    due = it["next_at"]
                        if it["status"] == "waiting":
                            still += 1
                            due = it["uploaded_at"] + timeout_s if it["attempts"] == 0 else it["next_at"]
                            left = fmt_duration(max(0, due - now))
                            rows.append(
                                t("line_wait", name=it["title"], remaining=left, total=wait_min)
                                if it["attempts"] == 0 else
                                t("line_retry", name=it["title"], n=it["attempts"],
                                  m=AUTO_MAX_RETRIES, remaining=left))
                        elif it["status"] == "done":
                            rows.append(t("line_done", name=it["title"]))
                        else:
                            rows.append(t("line_timeout", name=it["title"]))
                    board.markdown("\n\n".join(rows))
                    if not still:
                        break
                    time.sleep(1)
                wstatus.update(label=t("done"), state="complete", expanded=False)
        except Exception as e:
            wstatus.update(label=t("upload_fail"), state="error")
            st.error(f"{e}")
            log_event("error", where="auto wait", message=str(e))
    if queued or waiting:
        st.session_state.pop("active_job", None)
    stop_slot.empty()

    # 3) Blinking flag + one result card per file
    if just_done:
        ready_flag(f"{t('auto_ready')} ({len(just_done)})")
    if batch:
        st.markdown(f"##### {t('batch_results')} ({len(batch)})")
    for it in batch:
        label = f"{it['title']} · {t('it_' + it['status'])}" + (" · " + t("del_done") if it.get("deleted") else "")
        with st.expander(label, expanded=(len(batch) == 1)):
            if it.get("url"):
                st.link_button(t("yt_link"), it["url"], icon=":material/open_in_new:")
            if it["status"] == "done":
                show_result(it["result_key"])
            elif it["status"] == "failed":
                st.error(it.get("error") or t("upload_fail"))
            elif it["status"] == "timeout":
                st.warning(t("auto_giveup", n=it["attempts"]))
                if it.get("error"):
                    st.code(it["error"])
            elif it["status"] == "stopped":
                st.caption(t("stopped_msg"))
            if it.get("video_id") and not it.get("deleted"):
                st.caption(t("del_hint"))
                if st.button(t("del_btn"), key=f"del_auto_{it['video_id']}", icon=":material/delete:"):
                    confirm_delete_dialog(it)

    if batch:
        if st.button(t("reset_btn"), key="auto_reset", icon=":material/restart_alt:"):
            ignore.update(files.keys())
            st.session_state["auto_batch"] = []
            st.rerun()
        st.caption(t("reset_hint"))

# ---- Option 1: Online -------------------------------------------------------
with tab_online:
    st.caption(t("online_intro"))

    st.subheader(t("s1_title"), anchor=False)
    st.caption(t("s1_caption"))

    with st.container(border=True):
        st.markdown(f"##### :material/audio_file: {t('mp3_title')}")
        st.info(t("mp3_info"), icon=":material/info:")

        has_mp3 = st.session_state.get("mp3_conv") is not None
        has_mp4 = "mp4" in st.session_state

        st.markdown(f"**{t('s11')}** " + (":green-badge[:material/check:]" if has_mp3 else ""))
        mp3 = st.file_uploader(t("upload_mp3"), type=["mp3", "m4a", "wav"], key="mp3_conv",
                               max_upload_size=UPLOAD_MB_OFFLINE, label_visibility="collapsed")

        st.markdown(f"**{t('s12')}** " + (":green-badge[:material/check:]" if has_mp4 else ""))
        if st.button(t("convert_btn"), key="convert_btn", disabled=mp3 is None,
                     icon=":material/movie:"):
            base = os.path.splitext(mp3.name)[0]
            with tempfile.TemporaryDirectory() as tmpdir:
                src = os.path.join(tmpdir, "input" + (os.path.splitext(mp3.name)[1].lower() or ".mp3"))
                dst = os.path.join(tmpdir, "output.mp4")
                with open(src, "wb") as f:
                    f.write(mp3.getbuffer())
                bar = st.progress(0.0, text=f"{t('converting')}...")
                try:
                    mp3_to_mp4(src, dst, lambda p: bar.progress(p, text=f"{t('converting')}... {p:.0%}"))
                    bar.progress(1.0, text=t("convert_done"))
                    with open(dst, "rb") as f:
                        st.session_state["mp4"] = {"data": f.read(), "name": f"{base}.mp4"}
                except Exception as e:
                    st.session_state.pop("mp4", None)
                    bar.empty()
                    st.error(f"{t('convert_fail')}: {e}")

        mp4 = st.session_state.get("mp4")
        if mp4:
            st.success(f"{t('mp4_ready')}: {mp4['name']} ({len(mp4['data']) / 1_048_576:.1f} MB)",
                       icon=":material/check_circle:")
            st.markdown(f"**{t('s13')}**")
            st.download_button(t("download_mp4"), mp4["data"], file_name=mp4["name"],
                               mime="video/mp4", type="primary", width="stretch",
                               icon=":material/download:", key="mp4_dl")

    st.warning(t("wait_note", mins=POLL_TIMEOUT_S // 60), icon=":material/schedule:")

    # ---- Step 2: automatic upload + subtitle polling -------------------------
    st.subheader(t("s2_title"), anchor=False)
    st.caption(t("s2_caption"))

    mp4_up = st.file_uploader(t("src_mp4_upload"), type=["mp4", "mkv", "webm"], key="mp4_up",
                              max_upload_size=UPLOAD_MB_OFFLINE)
    if mp4_up is not None:
        src_name, src_bytes = mp4_up.name, mp4_up.getbuffer()
    elif st.session_state.get("mp4"):
        src_name, src_bytes = st.session_state["mp4"]["name"], st.session_state["mp4"]["data"]
    else:
        src_name, src_bytes = None, None

    if src_name:
        st.caption(f":material/movie: {t('src_using')}: **{src_name}** "
                   f"({len(src_bytes) / 1_048_576:.1f} MB)")
    else:
        st.caption(f":material/info: {t('src_none')}")

    col_priv, col_lang = st.columns([3, 1])
    privacy = col_priv.segmented_control(
        t("privacy"), ["unlisted", "private"], default="unlisted", required=True,
        format_func=lambda v: t(f"privacy_{v}"), key="privacy",
    ) or "unlisted"
    lang = col_lang.text_input(t("caption_lang"), value="th", max_chars=8)
    st.caption(f":material/lock: {t('privacy_note')}")

    if st.session_state.pop("online_stopped", None):
        st.warning(t("stopped_msg"), icon=":material/stop_circle:")

    if st.button(t("auto_btn"), type="primary", key="auto_btn", disabled=src_name is None,
                 icon=":material/cloud_upload:"):
        if not CLIENT_SECRET.exists():
            st.error(t("no_secret"))
        else:
            st.session_state["active_job"] = {"kind": "online", "video_id": None,
                                              "title": os.path.splitext(src_name)[0]}
            stop_slot_on = st.empty()
            stop_slot_on.button(t("stop_btn"), key="online_stop", icon=":material/stop_circle:",
                                on_click=stop_job, args=("online",))
            status = st.status(t("signin"), expanded=True)
            tmp_path = None
            try:
                with status:
                    yt = get_youtube_service()
                    status.update(label=t("uploading"))
                    bar = st.progress(0.0)
                    with tempfile.NamedTemporaryFile(
                            delete=False, suffix=os.path.splitext(src_name)[1] or ".mp4") as tmp:
                        tmp.write(src_bytes)
                        tmp_path = tmp.name
                    title = os.path.splitext(src_name)[0]
                    video_id = upload_video(
                        yt, tmp_path, title, privacy, lang,
                        lambda p: bar.progress(p, text=f"{t('uploading')} {p:.0%}"))
                    url_new = f"https://youtu.be/{video_id}"
                    st.session_state["yt_video"] = {"id": video_id, "url": url_new, "title": title}
                    st.session_state["active_job"]["video_id"] = video_id
                    upsert_job({"video_id": video_id, "url": url_new, "title": title,
                                "uploaded_at": time.time(), "status": "waiting"})
                    log_event("upload_done", video_id=video_id, title=title, url=url_new,
                              source="online")
                    st.write(f":material/check_circle: {t('uploaded', vid=video_id)} · {url_new}")

                    status.update(label=t("waiting_label"))
                    waiting = st.empty()
                    started = time.time()
                    lines, last_err = wait_for_transcript(
                        yt, video_id, lang,
                        lambda el, nxt: waiting.info(t("waiting", elapsed=el, nxt=nxt),
                                                     icon=":material/hourglass_top:"))
                    waiting.empty()
                    if lines:
                        store_online_result(lines, url_new, lang, video_id,
                                            time.time() - started, "YouTube auto captions (auto)",
                                            title=title)
                        status.update(label=t("done"), state="complete", expanded=False)
                    else:
                        status.update(label=t("waiting_label"), state="error", expanded=True)
                        st.warning(t("timeout", mins=POLL_TIMEOUT_S // 60))
                        log_event("gave_up", video_id=video_id, title=title,
                                  message=last_err or "no subtitles within the time limit")
                        if last_err:
                            st.code(last_err)
                st.session_state.pop("active_job", None)
                stop_slot_on.empty()
            except FileNotFoundError:
                status.update(label=t("no_secret"), state="error")
                st.session_state.pop("active_job", None)
            except Exception as e:
                status.update(label=t("upload_fail"), state="error")
                st.error(f"{t('upload_fail')}: {e}")
                log_event("error", where="online upload", title=src_name, message=str(e))
                if "uploadLimitExceeded" in str(e):
                    st.info(t("batch_limit"), icon=":material/info:")
                st.session_state.pop("active_job", None)
                stop_slot_on.empty()
            finally:
                if tmp_path:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    # Link to the uploaded video + "check again" if no transcript was stored for it yet
    yv = st.session_state.get("yt_video")
    if yv and yv.get("deleted"):
        st.caption(f":material/delete: {t('del_done')}")
    elif yv:
        st.link_button(t("yt_link"), yv["url"], icon=":material/open_in_new:")
        if st.session_state.get("online", {}).get("name") != yv["id"]:
            if st.button(t("recheck_btn"), key="recheck", icon=":material/refresh:"):
                with st.spinner(t("checking")):
                    try:
                        yt = get_youtube_service()
                        lines, err = try_fetch_transcript(yt, yv["id"], lang)
                    except Exception as e:
                        lines, err = None, str(e)
                if lines:
                    store_online_result(lines, yv["url"], lang, yv["id"], 0.0,
                                        "YouTube auto captions (auto)", title=yv["title"])
                    st.rerun()
                else:
                    st.warning(t("fetch_fail"))
                    if err:
                        st.code(err)

    # ---- Manual fallback: transcript from any YouTube URL --------------------
    with st.expander(t("manual_title"), icon=":material/link:"):
        url = st.text_input(t("url"), placeholder="https://www.youtube.com/watch?v=...")
        if st.button(t("fetch_btn"), key="fetch", icon=":material/subtitles:"):
            video_id = extract_video_id(url)
            if not video_id:
                st.error(t("bad_url"))
            else:
                started = time.time()
                with st.spinner(t("fetching")):
                    lines, error = None, None
                    try:
                        lines = fetch_with_transcript_api(video_id, lang)
                    except Exception as e1:
                        try:
                            lines = fetch_with_ytdlp(url, lang)
                        except Exception as e2:
                            error = f"youtube-transcript-api: {e1}\n\nyt-dlp: {e2}"
                if error or not lines:
                    st.error(t("fetch_fail"))
                    if error:
                        with st.expander(t("details")):
                            st.code(error)
                else:
                    store_online_result(lines, url, lang, video_id, time.time() - started,
                                        "YouTube auto captions")
    if "online" in st.session_state:
        show_result("online")
    if yv and not yv.get("deleted"):
        st.caption(t("del_hint"))
        if st.button(t("del_btn"), key="del_online", icon=":material/delete:"):
            confirm_delete_dialog(yv)

# ---- Option 2: Offline ------------------------------------------------------
with tab_offline:
    st.markdown(t("offline_intro", model=MODEL_NAME))
    uploads = st.file_uploader(t("upload_media"), type=MEDIA_TYPES, accept_multiple_files=True,
                               max_upload_size=UPLOAD_MB_OFFLINE, key="media_up")

    results: list[dict] = st.session_state.setdefault("offline_results", [])
    done_ids = {r["file_id"] for r in results}
    pending = [f for f in (uploads or []) if f.file_id not in done_ids]

    if not uploads and not results:
        st.caption(f":material/upload_file: {t('empty_state')}")
    if st.session_state.pop("offline_stopped", None):
        st.warning(t("stopped_msg"), icon=":material/stop_circle:")

    if st.button(f"{t('start_btn')} ({len(pending)})" if pending else t("start_btn"), type="primary",
                 key="local", disabled=not pending, icon=":material/play_arrow:"):
        st.session_state["active_job"] = {"kind": "offline", "title": f"{len(pending)} file(s)"}
        stop_slot_off = st.empty()
        stop_slot_off.button(t("stop_btn"), key="local_stop", icon=":material/stop_circle:",
                             on_click=stop_job, args=("offline",))
        overall = st.progress(0.0)
        model = None
        for idx, f in enumerate(pending, 1):
            overall.progress((idx - 1) / len(pending), text=t("batch_progress", i=idx, n=len(pending)))
            status = st.status(f"{idx}/{len(pending)} · {f.name}", expanded=True)
            tmp_path = None
            try:
                with status:
                    suffix = os.path.splitext(f.name)[1].lower() or ".bin"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(f.getbuffer())
                        tmp_path = tmp.name
                    if model is None:
                        status.update(label=f"{idx}/{len(pending)} · "
                                            f"{t('loading_model', model=MODEL_NAME)}")
                        model = load_model()
                    segments, info = model.transcribe(
                        tmp_path,
                        language="th",
                        beam_size=5,
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=500),
                        condition_on_previous_text=False,
                        initial_prompt=INITIAL_PROMPT,
                    )
                    total = info.duration or 1
                    status.update(label=f"{idx}/{len(pending)} · {t('transcribing')}... {f.name}")
                    bar = st.progress(0.0)
                    live = st.empty()
                    start, lines = time.time(), []
                    for seg in segments:
                        text = seg.text.strip()
                        if text:
                            lines.append(text)
                        bar.progress(min(seg.end / total, 1.0),
                                     text=f"{fmt_duration(seg.end)} / {fmt_duration(total)}")
                        live.caption(text)
                    live.empty()
                    status.update(label=f"{idx}/{len(pending)} · {f.name}", state="complete",
                                  expanded=False)
                base = os.path.splitext(f.name)[0]
                meta = {"File": f.name, "Model": f"faster-whisper {MODEL_NAME} (CPU, int8)",
                        "Language": "th", "Audio length": fmt_duration(total),
                        "Generated": datetime.now().strftime("%Y-%m-%d %H:%M")}
                key = f"offline_{f.file_id}"
                st.session_state[key] = {
                    "txt": "\n".join(lines),
                    "md": to_markdown(base, lines, meta),
                    "n_lines": len(lines),
                    "secs": time.time() - start,
                    "audio": total,
                    "name": base,
                }
                results.append({"file_id": f.file_id, "name": f.name, "key": key})
                log_event("offline_done", title=f.name, lines=len(lines),
                          message=f"{fmt_duration(time.time() - start)} for {fmt_duration(total)} of audio")
            except Exception as e:
                status.update(label=f"{f.name}: {t('failed')}", state="error")
                st.error(f"{f.name}: {t('failed')}: {e}")
                log_event("error", where="offline transcription", title=f.name, message=str(e))
            finally:
                if tmp_path:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
        overall.progress(1.0, text=t("done"))
        st.session_state.pop("active_job", None)
        stop_slot_off.empty()

    for r in results:
        with st.expander(r["name"], expanded=(len(results) == 1)):
            show_result(r["key"])
    if results and st.button(t("clear_results"), key="offline_clear", icon=":material/delete_sweep:"):
        st.session_state["offline_results"] = []
        st.rerun()

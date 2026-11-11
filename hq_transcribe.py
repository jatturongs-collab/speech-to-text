"""High-quality CPU-only Thai transcription with faster-whisper (large-v3-turbo)."""
import argparse
import sys
from pathlib import Path

from faster_whisper import WhisperModel

INITIAL_PROMPT = (
    "นี่คือคลิปOpportunity Day อธิบายงบการเงิน หุ้น SET, กำไรสุทธิ, ไตรมาส, "
    "อัตรากำไรขั้นต้น, ขาดทุน, YoY, QoQ, EBITDA, ยอดขาย, CAPEX"
)


def srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Thai STT (faster-whisper, CPU, int8)")
    parser.add_argument("input", help="Path to audio/video file")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: same folder as input)")
    parser.add_argument("--ultra", action="store_true",
                        help="Ultra High Quality: full large-v3, float32, beam 10, "
                             "temperature fallback (much slower, ~6GB RAM)")
    args = parser.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print(f"Error: input file not found: {src}", file=sys.stderr)
        return 1
    out_dir = Path(args.output_dir) if args.output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / f"{src.stem}.txt"
    srt_path = out_dir / f"{src.stem}.srt"

    if args.ultra:
        model_name, compute_type = "large-v3", "float32"
        extra = dict(
            beam_size=10,
            best_of=5,
            patience=2.0,
            temperature=[0.0, 0.2, 0.4, 0.6],
            condition_on_previous_text=False,  # avoids repetition loops / drift
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
        )
    else:
        model_name, compute_type = "large-v3-turbo", "int8"
        extra = dict(beam_size=5)

    print(f"Loading model {model_name} (CPU, {compute_type})...")
    model = WhisperModel(model_name, device="cpu", compute_type=compute_type)

    segments, info = model.transcribe(
        str(src),
        language="th",
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        initial_prompt=INITIAL_PROMPT,
        **extra,
    )
    total = info.duration or 0
    print(f"Audio duration: {total:.1f}s - transcribing...")

    with open(txt_path, "w", encoding="utf-8") as ftxt, \
         open(srt_path, "w", encoding="utf-8") as fsrt:
        for i, seg in enumerate(segments, start=1):
            text = seg.text.strip()
            ftxt.write(text + "\n")
            fsrt.write(f"{i}\n{srt_time(seg.start)} --> {srt_time(seg.end)}\n{text}\n\n")
            pct = f"{seg.end / total * 100:5.1f}%" if total else ""
            print(f"[{srt_time(seg.start)}] {pct} {text}")

    print(f"\nSaved:\n  {txt_path}\n  {srt_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

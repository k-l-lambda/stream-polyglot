#!/usr/bin/env python3
"""
Resume transcription from existing VAD fragments.

Uses the cached fragment WAVs in /tmp/tmp22ty58a_/ and calls m4t API
to transcribe each one, with retry logic and progress checkpointing.

Usage:
    python resume_transcribe.py [--start N] [--batch-size 50]
"""

import glob
import json
import os
import re
import sys
import time
import requests

M4T_API_URL = "http://localhost:8001"
FRAGMENTS_DIR = "/tmp/tmp22ty58a_"
OUTPUT_DIR = "/home/camus/work/stream-polyglot/output/liequn-24-vad"
CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "transcribe_checkpoint.json")
SRT_OUTPUT = os.path.join(OUTPUT_DIR, "李群李代数_第24讲_酉群（续）.srt")

MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds, doubles each retry
LANGUAGE = "cmn"


def parse_fragment_times(filename: str):
    """Extract (start, end) seconds from fragment filename."""
    m = re.search(r'fragment_(\d+\.\d+)_(\d+\.\d+)\.wav', os.path.basename(filename))
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def transcribe_chunk(chunk_path: str, retries: int = MAX_RETRIES) -> str:
    """Call m4t /v1/transcribe with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            with open(chunk_path, "rb") as f:
                resp = requests.post(
                    f"{M4T_API_URL}/v1/transcribe",
                    files={"audio": ("chunk.wav", f, "audio/wav")},
                    data={"language": LANGUAGE},
                    timeout=60,
                )
            resp.raise_for_status()
            return resp.json().get("output_text", "").strip()
        except Exception as exc:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            if attempt < retries:
                print(f"  ⚠ Attempt {attempt}/{retries} failed: {exc} — retrying in {wait:.0f}s")
                time.sleep(wait)
            else:
                print(f"  ❌ All {retries} attempts failed: {exc}")
                return ""


def format_srt_ts(seconds: float) -> str:
    """Format seconds to SRT timestamp HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0, help="Start from fragment index (0-based)")
    parser.add_argument("--batch-size", type=int, default=0, help="Process N fragments then stop (0=all)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Discover all fragments, sorted by start time
    fragment_files = sorted(glob.glob(os.path.join(FRAGMENTS_DIR, "fragment_*.wav")))
    total = len(fragment_files)
    print(f"Found {total} fragments in {FRAGMENTS_DIR}")

    # Load checkpoint (previously transcribed segments)
    segments = []
    start_idx = args.start
    if os.path.exists(CHECKPOINT_FILE) and args.start == 0:
        with open(CHECKPOINT_FILE) as f:
            checkpoint = json.load(f)
        segments = checkpoint.get("segments", [])
        start_idx = checkpoint.get("next_index", 0)
        print(f"Resuming from checkpoint: {start_idx}/{total} ({len(segments)} segments done)")

    end_idx = total
    if args.batch_size > 0:
        end_idx = min(start_idx + args.batch_size, total)

    print(f"Processing fragments {start_idx} to {end_idx - 1}")

    t0 = time.time()
    for i in range(start_idx, end_idx):
        fpath = fragment_files[i]
        start, end = parse_fragment_times(fpath)
        if start is None:
            print(f"  [{i+1}/{total}] Skipping unparseable: {os.path.basename(fpath)}")
            continue

        elapsed = time.time() - t0
        rate = (i - start_idx + 1) / max(elapsed, 0.01)
        remaining = (end_idx - i - 1) / max(rate, 0.01)
        print(f"  [{i+1}/{total}] {start:.1f}–{end:.1f}s (ETA: {remaining:.0f}s)", end=" ")

        text = transcribe_chunk(fpath)
        if text:
            segments.append({"start": start, "end": end, "text": text})
            print(f"✓ {text[:40]}...")
        else:
            print("✗ (empty)")

        # Checkpoint every 50 fragments
        if (i + 1) % 50 == 0 or i == end_idx - 1:
            with open(CHECKPOINT_FILE, "w") as f:
                json.dump({"segments": segments, "next_index": i + 1}, f, ensure_ascii=False)

    # Save final checkpoint
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"segments": segments, "next_index": end_idx}, f, ensure_ascii=False)

    elapsed = time.time() - t0
    print(f"\nTranscription done: {len(segments)} segments in {elapsed:.1f}s")

    # Write SRT if all fragments are processed
    if end_idx >= total:
        segments.sort(key=lambda s: s["start"])
        srt_lines = []
        for idx, seg in enumerate(segments, 1):
            srt_lines.append(f"{idx}")
            srt_lines.append(f"{format_srt_ts(seg['start'])} --> {format_srt_ts(seg['end'])}")
            srt_lines.append(seg["text"])
            srt_lines.append("")

        with open(SRT_OUTPUT, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
        print(f"✅ SRT written: {SRT_OUTPUT} ({len(segments)} entries)")
    else:
        print(f"⏸ Partial run ({start_idx}→{end_idx}). Run again to continue.")


if __name__ == "__main__":
    main()

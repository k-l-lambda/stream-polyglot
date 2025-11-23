#!/usr/bin/env python3
"""
Test audio split chunking functionality
"""
import sys
import os
import tempfile
sys.path.insert(0, '/home/camus/work/stream-polyglot')

from main import audio_split, extract_audio

# Configuration
video_path = "/home/camus/work/stream-polyglot/assets/After watching this, your brain will not be the same  Lara Boyd  TEDxVancouver - TEDx Talks (144p, h264).mp4"
api_url = "http://localhost:8000"

print("=== Testing Audio Split with Chunking ===")
print(f"Video: {os.path.basename(video_path)}")
print(f"API: {api_url}\n")

# Extract audio
with tempfile.TemporaryDirectory() as temp_dir:
    audio_path = os.path.join(temp_dir, 'test_audio.wav')

    print("Step 1: Extracting audio...")
    if not extract_audio(video_path, audio_path):
        print("✗ Failed to extract audio")
        sys.exit(1)
    print("✓ Audio extracted\n")

    print("Step 2: Testing audio split (should trigger chunking for 14-minute audio)...")
    vocals_bytes, accompaniment_bytes, sr = audio_split(audio_path, api_url, verbose=True, max_chunk_duration=300.0)

    if vocals_bytes and accompaniment_bytes:
        print(f"\n✓ Audio split successful!")
        print(f"  Vocals size: {len(vocals_bytes) / 1024 / 1024:.2f} MB")
        print(f"  Accompaniment size: {len(accompaniment_bytes) / 1024 / 1024:.2f} MB")
        print(f"  Sample rate: {sr} Hz")
    else:
        print("\n✗ Audio split failed")
        sys.exit(1)

print("\n=== Test completed successfully ===")

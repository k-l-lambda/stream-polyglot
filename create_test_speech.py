#!/usr/bin/env python3
"""Create a test audio file with actual speech for SRT testing"""

import requests
import numpy as np
import soundfile as sf

API_URL = "http://localhost:8000"

# Create three speech segments
texts = [
    "Hello, welcome to the video translation test.",
    "This is the second segment of our demonstration.",
    "Thank you for watching this test video."
]

print("Generating speech segments...")
audio_segments = []

for i, text in enumerate(texts):
    print(f"Segment {i+1}: {text}")
    
    response = requests.post(
        f"{API_URL}/v1/text-to-speech",
        json={
            "text": text,
            "source_lang": "eng",
            "speaker_id": 0
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        audio = np.array(result['output_audio'], dtype=np.float32)
        audio_segments.append(audio)
        print(f"  Generated {len(audio) / 16000:.2f}s of audio")
    else:
        print(f"  ERROR: {response.status_code}")
        exit(1)

# Combine segments with 1-second silence between them
sample_rate = 16000
silence = np.zeros(int(sample_rate * 1.0))

combined_audio = []
for i, segment in enumerate(audio_segments):
    if i > 0:
        combined_audio.append(silence)
    combined_audio.append(segment)

final_audio = np.concatenate(combined_audio)

# Save as WAV file
output_file = 'test_speech_eng.wav'
sf.write(output_file, final_audio, sample_rate)

print(f"\n✓ Created test audio: {output_file}")
print(f"  Duration: {len(final_audio) / sample_rate:.2f}s")
print(f"  Sample rate: {sample_rate} Hz")
print(f"  Segments: {len(audio_segments)}")

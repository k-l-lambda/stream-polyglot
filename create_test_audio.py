#!/usr/bin/env python3
"""Create a short test audio file with multiple speech segments for SRT testing"""

import numpy as np
import soundfile as sf

def generate_tone(frequency, duration, sample_rate=16000):
    """Generate a sine wave tone"""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    return np.sin(frequency * 2 * np.pi * t)

# Create a 10-second audio with three distinct segments
sample_rate = 16000
silence = np.zeros(int(sample_rate * 0.5))  # 0.5s silence

# Segment 1: 1-2 seconds (tone at 440 Hz)
segment1 = generate_tone(440, 1.0, sample_rate)

# Segment 2: 4-6 seconds (tone at 554 Hz)
segment2 = generate_tone(554, 2.0, sample_rate)

# Segment 3: 8-9.5 seconds (tone at 659 Hz)
segment3 = generate_tone(659, 1.5, sample_rate)

# Combine segments with silences
audio = np.concatenate([
    silence,  # 0-0.5s
    segment1,  # 0.5-1.5s
    silence * 5,  # 1.5-4s (2.5s silence)
    segment2,  # 4-6s
    silence * 4,  # 6-8s (2s silence)
    segment3,  # 8-9.5s
    silence  # 9.5-10s
])

# Save as WAV file
output_file = 'test_audio_short.wav'
sf.write(output_file, audio.astype(np.float32), sample_rate)

print(f"Created test audio: {output_file}")
print(f"Duration: {len(audio) / sample_rate:.2f}s")
print(f"Sample rate: {sample_rate} Hz")
print("Expected segments:")
print("  1. ~0.5-1.5s (440 Hz tone)")
print("  2. ~4.0-6.0s (554 Hz tone)")
print("  3. ~8.0-9.5s (659 Hz tone)")

#!/usr/bin/env python3
"""
Test script for voice cloning functionality

Tests the integration between:
1. m4t voice-clone API endpoint
2. stream-polyglot voice_clone_translation function
"""

import os
import sys
import requests
import base64
import soundfile as sf

# Test configuration
M4T_API_URL = os.getenv("M4T_API_URL", "http://localhost:8000")
REFERENCE_AUDIO = "/home/camus/work/stream-polyglot/assets/speaker_samples/speaker_011_cmn.wav"
TEST_OUTPUT_DIR = "/home/camus/work/stream-polyglot/test_output"

def print_status(message):
    """Print status message"""
    print(f"\n{'='*60}")
    print(f"  {message}")
    print(f"{'='*60}")

def test_m4t_health():
    """Test if m4t server is running"""
    print_status("Test 1: m4t Server Health Check")

    try:
        response = requests.get(f"{M4T_API_URL}/health", timeout=5)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Server is healthy")
            print(f"   Model loaded: {result.get('model_loaded', False)}")
            print(f"   Device: {result.get('device', 'unknown')}")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to m4t server at {M4T_API_URL}")
        print(f"   Please start the server with: cd /home/camus/work/m4t && ./restart.sh")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_reference_audio():
    """Check if reference audio exists and is readable"""
    print_status("Test 2: Reference Audio Check")

    if not os.path.exists(REFERENCE_AUDIO):
        print(f"❌ Reference audio not found: {REFERENCE_AUDIO}")
        return False

    try:
        audio, sr = sf.read(REFERENCE_AUDIO)
        duration = len(audio) / sr
        channels = "mono" if len(audio.shape) == 1 else f"{audio.shape[1]}-channel"

        print(f"✅ Reference audio loaded")
        print(f"   Path: {REFERENCE_AUDIO}")
        print(f"   Duration: {duration:.2f}s")
        print(f"   Sample rate: {sr} Hz")
        print(f"   Channels: {channels}")
        print(f"   Size: {len(audio)} samples")
        return True
    except Exception as e:
        print(f"❌ Error reading audio: {e}")
        return False

def test_voice_clone_api():
    """Test m4t voice-clone API directly"""
    print_status("Test 3: m4t Voice Clone API")

    # Test parameters
    test_cases = [
        {
            "name": "English text with Chinese reference",
            "text": "Hello, this is a voice cloning test.",
            "text_language": "eng",
            "prompt_text": "你好",
            "prompt_language": "cmn",
            "seed": 42
        },
        {
            "name": "Chinese text with Chinese reference",
            "text": "你好，这是一个语音克隆测试。",
            "text_language": "cmn",
            "prompt_text": "你好",
            "prompt_language": "cmn",
            "seed": 42
        }
    ]

    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)

    for i, test in enumerate(test_cases, 1):
        print(f"\n  Test 3.{i}: {test['name']}")

        try:
            # Read reference audio
            with open(REFERENCE_AUDIO, 'rb') as f:
                audio_data = f.read()

            # Prepare request
            files = {'audio': ('reference.wav', audio_data, 'audio/wav')}
            data = {
                'text': test['text'],
                'text_language': test['text_language'],
                'prompt_text': test['prompt_text'],
                'prompt_language': test['prompt_language'],
                'seed': str(test['seed'])
            }

            # Call API
            print(f"    Calling API...")
            response = requests.post(
                f"{M4T_API_URL}/v1/voice-clone",
                files=files,
                data=data,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()

                # Save output audio
                audio_bytes = base64.b64decode(result['output_audio_base64'])
                output_path = os.path.join(TEST_OUTPUT_DIR, f"test3_{i}_output.wav")
                with open(output_path, 'wb') as f:
                    f.write(audio_bytes)

                # Verify output
                audio, sr = sf.read(output_path)
                duration = len(audio) / sr

                print(f"    ✅ Success!")
                print(f"       Output: {output_path}")
                print(f"       Duration: {duration:.2f}s")
                print(f"       Sample rate: {sr} Hz")
                print(f"       Processing time: {result.get('processing_time', 0):.2f}s")
            else:
                print(f"    ❌ API returned status {response.status_code}")
                print(f"       Response: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False

    return True

def test_stream_polyglot_function():
    """Test stream-polyglot voice_clone_translation function"""
    print_status("Test 4: stream-polyglot Integration")

    # Add stream-polyglot to path
    sys.path.insert(0, '/home/camus/work/stream-polyglot')

    try:
        from main import voice_clone_translation
        print(f"✅ Imported voice_clone_translation function")
    except ImportError as e:
        print(f"❌ Cannot import function: {e}")
        return False

    # Test function call
    print(f"\n  Calling voice_clone_translation...")

    try:
        audio_bytes = voice_clone_translation(
            ref_audio_path=REFERENCE_AUDIO,
            text="Hello from stream-polyglot!",
            text_language="eng",
            prompt_text="你好",
            prompt_language="cmn",
            api_url=M4T_API_URL,
            seed=42,
            verbose=False
        )

        if audio_bytes:
            # Save output
            output_path = os.path.join(TEST_OUTPUT_DIR, "test4_stream_polyglot_output.wav")
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)

            # Verify
            audio, sr = sf.read(output_path)
            duration = len(audio) / sr

            print(f"  ✅ Function call successful!")
            print(f"     Output: {output_path}")
            print(f"     Duration: {duration:.2f}s")
            print(f"     Sample rate: {sr} Hz")
            return True
        else:
            print(f"  ❌ Function returned None (error)")
            return False

    except Exception as e:
        print(f"  ❌ Error calling function: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  Voice Clone Test Suite")
    print("="*60)

    results = []

    # Run tests
    results.append(("m4t server health", test_m4t_health()))

    if results[-1][1]:  # Only continue if server is healthy
        results.append(("Reference audio check", test_reference_audio()))
        results.append(("m4t API test", test_voice_clone_api()))
        results.append(("stream-polyglot integration", test_stream_polyglot_function()))
    else:
        print("\n⚠️  Skipping remaining tests (server not available)")

    # Print summary
    print_status("Test Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print(f"\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

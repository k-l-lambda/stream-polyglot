# Stream-Polyglot

**Seamless multilingual video/audio translation and subtitle generation tool**

Stream-Polyglot is a cross-platform video and audio translation application that leverages the SeamlessM4T API to provide high-quality speech-to-text translation, subtitle generation, and audio dubbing capabilities across 100+ languages.

## Features

- **Video Translation**: Extract audio from video files, translate speech to text in target language
- **Subtitle Generation**: Automatically generate SRT/VTT subtitle files with accurate timestamps
- **Bilingual Subtitles**: Generate subtitles with both source and target languages
- **Audio Dubbing**: Replace original audio with translated speech (text-to-speech in target language)
- **Voice Cloning Translation**: Generate voice-cloned audio from bilingual SRT files using GPT-SoVITS
- **🆕 Lecture Annotator**: End-to-end pipeline for lecture video annotation — download, transcribe, extract key frames, and generate structured notes with multimodal LLM
- **🆕 Speaker Clustering**: Cluster audio segments by speaker identity using voice embeddings (resemblyzer)
- **🆕 VAD-based Transcription**: Voice Activity Detection for sentence-level segmentation with checkpoint/resume support
- **Multi-format Support**: Works with MP4, MKV, WebM, AVI, and various audio formats (WAV, MP3, FLAC, M4A, OGG)
- **100+ Languages**: Supports speech input in 101 languages and text output in 96 languages via SeamlessM4T
- **Cross-platform**: Runs on Windows, macOS, and Linux

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Stream-Polyglot                          │
├─────────────────────────────┬───────────────────────────────────┤
│   Translation Pipeline      │    Lecture Annotator Pipeline     │
│                             │                                   │
│  Video/Audio                │  YouTube URL / Local Video        │
│       │                     │       │                           │
│       ▼                     │       ▼                           │
│  FFmpeg Audio Extract       │  yt-dlp Download                  │
│       │                     │       │                           │
│       ▼                     │       ▼                           │
│  m4t API (SeamlessM4T)      │  Whisper / m4t ASR → SRT         │
│       │                     │       │                           │
│       ├──▶ Subtitles (SRT)  │       ▼                           │
│       │    └▶ LLM Refiner   │  Key Frame Extraction (ffmpeg)    │
│       │                     │       │                           │
│       ├──▶ Voice Clone      │       ▼                           │
│       │    (GPT-SoVITS)     │  Multimodal LLM Annotation        │
│       │                     │       │                           │
│       └──▶ Audio Dubbing    │       ▼                           │
│            (TTS)            │  Structured Markdown Notes        │
└─────────────────────────────┴───────────────────────────────────┘
```

## Technology Stack

### Core Dependencies
- **Python 3.10+**: Main programming language
- **FFmpeg**: Video/audio processing and manipulation
- **m4t API**: SeamlessM4T translation backend (required)

### Python Libraries
- **python-dotenv**: Environment variable management
- **requests**: HTTP client for m4t API communication
- **ffmpeg-python**: FFmpeg wrapper for video/audio operations (planned)
- **pysrt**: SRT subtitle file parsing and generation (planned)
- **webvtt-py**: WebVTT subtitle format support (planned)
- **soundfile**: Audio file I/O (planned)
- **numpy**: Numerical operations for audio processing (planned)

### Optional
- **MoviePy**: Alternative video editing library (user-friendly)
- **PyAV**: Low-level FFmpeg bindings for advanced control

## Installation

### Prerequisites

1. **FFmpeg**: Install FFmpeg on your system
   ```bash
   # Ubuntu/Debian
   sudo apt-get install ffmpeg

   # macOS
   brew install ffmpeg

   # Windows
   # Download from https://ffmpeg.org/download.html
   ```

2. **m4t API Server**: Start the SeamlessM4T API server by Docker (8GB GPU memory required at least)

   ```bash
   # Pull the m4t Docker image
   docker pull kllambda/m4t:v1.0.0

   # Run the m4t server (requires GPU)
   docker run -d \
     --name m4t-server \
     --gpus all \
     -p 8000:8000 \
     kllambda/m4t:v1.0.0

   # Check server status
   curl http://localhost:8000/health
   ```

   The server will be available at `http://localhost:8000` by default.

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/stream-polyglot.git
   cd stream-polyglot
   ```

2. Create virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure m4t API endpoint (optional):

   **Option 1: Using .env file (recommended)**
   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit .env and set M4T_API_URL
   # M4T_API_URL=http://localhost:8000
   ```

   **Option 2: Using environment variable**
   ```bash
   export M4T_API_URL=http://localhost:8000
   ```

   **Option 3: Using command-line argument**
   ```bash
   python main.py test --api-url http://localhost:8000
   ```

## Usage

### Generate Subtitles

Generate Chinese subtitles for English video:

```bash
python -m main video.mp4 --lang eng:cmn --subtitle
```

### Generate Bilingual Subtitles

Generate bilingual subtitles (English + Chinese):

```bash
python -m main video.mp4 --lang eng:cmn --subtitle --subtitle-source-lang
```

Output format (video.eng-cmn.srt):
```srt
1
00:00:01,000 --> 00:00:04,000
你好，今天怎么样？
Hello, how are you today?

2
00:00:05,000 --> 00:00:08,000
我很好，谢谢！
I'm doing great, thank you!
```

### Automatic Subtitle Refinement with LLM

**NEW FEATURE**: Automatically refine generated subtitles with LLM (subtitle-refiner) to improve translation quality:

```bash
# Generate and automatically refine subtitles (bilingual mode enabled by default)
python -m main video.mp4 --lang eng:cmn --subtitle --subtitle-refiner

# Explicitly specify bilingual mode (same result as above)
python -m main video.mp4 --lang eng:cmn --subtitle --subtitle-source-lang --subtitle-refiner
```

**Important**: Using `--subtitle-refiner` automatically enables `--subtitle-source-lang` to generate bilingual subtitles, as the refiner works best with both source and target languages for context.

**How it works:**
1. Generates bilingual subtitle file (source + target languages)
2. Automatically runs subtitle-refiner on the generated SRT file
3. LLM reviews and improves translations for accuracy and naturalness
4. Outputs refined subtitle file (e.g., `video.eng-cmn.refined.srt`)

**Benefits:**
- **Better translations**: LLM refines machine translations for naturalness
- **Context awareness**: Reviews subtitles in windowed context for coherence
- **Bilingual by default**: Both languages help LLM understand context better
- **Automated workflow**: No manual refinement step needed
- **Preserves timing**: Only improves text, keeps original timestamps

**Requirements:**
- subtitle-refiner must be installed at `../stream-polyglot-refiner/subtitle-refiner/`
- OpenAI API key configured in subtitle-refiner environment
- Additional processing time: ~1-2 minutes per 100 subtitle entries

### Generate Audio Dubbing

Replace audio with translated speech:

```bash
python -m main video.mp4 --lang eng:jpn --audio
```

### Split Audio into Vocals and Accompaniment

**NEW FEATURE**: Use `--split` to separate vocals from background music before timeline segmentation:

```bash
# Split audio before generating subtitles
python -m main video.mp4 --lang eng:cmn --subtitle --split

# Split audio before generating audio dubbing
python -m main video.mp4 --lang eng:jpn --audio --split

# Works with both subtitle and audio generation
python -m main video.mp4 --lang eng:cmn --subtitle --audio --split
```

**How it works:**
1. Extracts audio from video using FFmpeg
2. **Detects audio duration and splits into chunks if needed (>5 minutes)**
3. **Starts audio splitting in background thread** (non-blocking)
   - For short audio (<5 min): Single API call
   - For long audio (>5 min): Client-side chunking, multiple API calls, automatic concatenation
4. Continues immediately with VAD segmentation and ASR processing
5. Split audio is saved asynchronously to cache directory (`.stream-polyglot-cache/[video_name]/split/`)
   - `vocals.wav`: Clean human voice/speech
   - `accompaniment.wav`: Background music and other sounds
6. **Note**: Original audio (not separated vocals) is used for VAD segmentation and ASR to maintain compatibility

**Benefits:**
- **No duration limit**: Client-side chunking handles audio of any length
- **No network timeout**: Each chunk is sent separately (5-minute max per request)
- **No performance impact**: Audio splitting runs in background, doesn't delay subtitle/audio generation
- **Audio archival**: Saves separated vocals and accompaniment for later use
- **Audio editing**: Provides clean vocal and accompaniment tracks for video editing
- **Cached for reuse**: Split audio is saved for future processing
- **Optional feature**: Only used when `--split` flag is set (normal processing without it)

**Use cases:**
- Archive separate vocal and music tracks from videos
- Provide clean audio sources for video editing workflows
- Extract vocals or accompaniment for remixing purposes

**Requirements:**
- m4t server must have Spleeter installed (`pip install spleeter`)
- Audio splitting runs asynchronously in background (no processing delay)

### Lecture Annotation (NEW)

**End-to-end lecture video annotation**: Download a YouTube lecture → transcribe with Whisper/m4t → extract key frames → generate structured Markdown notes with multimodal LLM.

```bash
# Full pipeline from YouTube URL
python -m lecture_annotator "https://www.youtube.com/watch?v=VIDEO_ID" \
  -o ./output/my-lecture \
  -l zh \
  -m large-v3 \
  --annotate-model pa/gemini-3.1-pro-preview

# From local video (skip download)
python -m lecture_annotator --skip-download \
  --video ./lecture.mp4 --audio ./lecture.wav \
  -o ./output/my-lecture -l zh -m large-v3

# From existing SRT + video (skip download & transcription)
python -m lecture_annotator --skip-download --skip-transcribe \
  --video ./lecture.mp4 --srt ./lecture.srt \
  -o ./output/my-lecture

# Annotation only (have SRT + frames already)
python -m lecture_annotator --skip-download --skip-transcribe --skip-frames \
  --srt ./lecture.srt --frames ./frames/ \
  -o ./output/my-lecture
```

**Pipeline stages:**

| Stage | Module | Description |
|-------|--------|-------------|
| 1. Download | `download.py` | yt-dlp: YouTube → MP4 + 16kHz WAV |
| 2. Transcribe | `transcribe.py` | Whisper / m4t API → SRT subtitles |
| 3. Extract Frames | `extract_frames.py` | Semantic / uniform / scene-change → key frames |
| 4. Annotate | `annotate.py` | Multimodal LLM (SRT + screenshots) → Markdown notes |

**Frame extraction strategies:**
- `semantic` (default): Extracts at formula, theorem, transition, or long-pause moments (SRT-driven)
- `uniform`: Every N seconds
- `scene`: ffmpeg scene-change detection

**Output** — structured Markdown with:
- Table of contents with timestamps
- Collapsible original subtitles per paragraph
- Embedded key frame screenshots
- LLM-generated annotations (formula explanations, theoretical background, concept summaries)

**Key options:**

| Option | Default | Description |
|--------|---------|-------------|
| `-l, --language` | auto | Whisper language code (`zh`, `en`, …) |
| `-m, --model` | `base` | Whisper model size (`tiny`…`large-v3`) |
| `--m4t-url` | — | m4t API URL (preferred over local Whisper) |
| `--annotate-model` | `pa/gemini-3.1-pro-preview` | LLM for annotation |
| `--frame-strategy` | `semantic` | `semantic` / `uniform` / `scene` |
| `--max-frames` | `50` | Maximum frames to extract |

See [`lecture_annotator/README.md`](lecture_annotator/README.md) for full API documentation.

### VAD-based Resume Transcription (NEW)

For long lecture videos where transcription may be interrupted, use checkpoint-based resume:

```bash
# First run: transcribe with m4t API + VAD segmentation
python resume_transcribe.py --start 0 --batch-size 50

# If interrupted, resume from checkpoint automatically
python resume_transcribe.py
```

Features:
- VAD (Voice Activity Detection) for sentence-level fragment segmentation
- Checkpoint file tracks progress — resume from where you left off
- Configurable batch size and retry logic with exponential backoff
- Outputs SRT with natural sentence boundaries (better than fixed-interval splitting)

### Speaker Clustering (NEW)

Cluster audio segments by speaker identity for multi-speaker videos:

```python
from speaker_clustering import cluster_speakers

# Cluster audio fragments by speaker
clusters = cluster_speakers(
    fragments_dir="./cache/fragments/",
    n_speakers=2,  # expected number of speakers
)
# Returns: {speaker_id: [fragment_paths]}
```

Uses resemblyzer voice embeddings + scikit-learn clustering.

### Generate Voice-Cloned Audio from Bilingual Subtitles

**NEW FEATURE**: Generate voice-cloned audio using bilingual SRT subtitles with GPT-SoVITS voice cloning:

```bash
# Option 1: Use existing cached timeline (fast)
# First generate bilingual subtitle to create cache
python -m main video.mp4 --lang eng:cmn --subtitle --subtitle-source-lang

# Then generate voice-cloned audio using cache
python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.srt

# Option 2: Direct voice cloning (automatic segmentation if no cache)
# If cache doesn't exist, it will automatically extract audio and segment it
python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.srt

# Option 3: Infer language from SRT filename
python -m main --trans-voice video.eng-cmn.srt

# Option 4: Use fixed seed for reproducible voice cloning
python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.srt --seed 42
```

**Random Seed for Reproducibility:**
- `--seed` parameter controls the randomness in voice generation
- **Default (no --seed)**: Generates one random seed at the start and uses it for ALL segments in that generation
  - This ensures consistency across all voice cloned segments in a single run
  - Different runs will produce different (but internally consistent) results
- **Fixed seed (--seed 42)**: Uses the same seed across runs for fully reproducible results
  - Same input + same seed = identical output audio
  - Useful for A/B testing, debugging, or when consistent output is required

**Verbose Mode for Debugging:**
```bash
# Enable verbose mode to save intermediate audio files
python -m main video.mp4 --lang eng:cmn --trans-voice video.eng-cmn.srt --verbose
```

- `--verbose` enables detailed logging and saves all intermediate voice-cloned audio segments
- Intermediate files are saved to: `<cache_dir>/voice_clone_debug/`
- Files are named: `segment_NNNN_<src_lang>-<tgt_lang>_<text_preview>.wav`
- Example filename: `segment_0042_eng-cmn_Hello_how_are_you_today....wav`
- Useful for debugging voice cloning quality issues or inspecting individual segments
- Debug files are preserved across runs (not auto-deleted)

**How it works:**
1. Reads bilingual SRT file (target language + source language)
2. Checks for cached timeline; if not found, automatically extracts audio and segments it
3. Matches subtitle timing with cached audio fragments
4. Uses cached fragment audio as reference for voice cloning
5. Generates target language speech with cloned voice characteristics (using the same seed for all segments)
6. Concatenates all segments into final audio track

**Benefits:**
- Preserves original speaker's voice characteristics
- Better than generic TTS (more natural and expressive)
- Reuses cached timeline data for fast processing
- Automatic segmentation if cache doesn't exist
- Perfect for dubbing videos while maintaining voice identity
- Consistent voice characteristics across all segments (same seed used for all cloning operations)

### Generate Both Subtitles and Audio

Create both subtitle file and dubbed audio:

```bash
python -m main video.mp4 --lang eng:cmn --subtitle --audio
```

### Specify Custom Output Directory

```bash
python -m main video.mp4 --lang jpn:eng --subtitle --output ./translated/
```

### Use Custom API Server

```bash
python -m main video.mp4 --lang eng:cmn --subtitle --api-url http://192.168.1.100:8000
```

### View All Options

```bash
python -m main --help
```

## Supported Languages

SeamlessM4T supports 101 languages for speech input and 96 languages for text output.

### Popular Languages

| Language | Code | Speech Input | Text Output |
|----------|------|--------------|-------------|
| English | eng | ✓ | ✓ |
| Chinese (Simplified) | cmn | ✓ | ✓ |
| Chinese (Traditional) | cmn_Hant | ✓ | ✓ |
| Japanese | jpn | ✓ | ✓ |
| Korean | kor | ✓ | ✓ |
| French | fra | ✓ | ✓ |
| German | deu | ✓ | ✓ |
| Spanish | spa | ✓ | ✓ |
| Russian | rus | ✓ | ✓ |
| Arabic | arb | ✓ | ✓ |

See [m4t documentation](http://localhost:8000/languages) for the complete language list.

## Subtitle Formats

### SRT (SubRip)
```srt
1
00:00:01,000 --> 00:00:04,000
Hello, how are you today?

2
00:00:05,000 --> 00:00:08,000
I'm doing great, thank you!
```

### VTT (WebVTT)
```vtt
WEBVTT

00:00:01.000 --> 00:00:04.000
Hello, how are you today?

00:00:05.000 --> 00:00:08.000
I'm doing great, thank you!
```

## Container Format Support

| Format | Extension | Subtitle Support | Audio Tracks | Recommended Use Case |
|--------|-----------|------------------|--------------|----------------------|
| MP4 | .mp4 | Limited (mov_text) | Single | Universal compatibility |
| MKV | .mkv | Excellent (SRT, ASS, multiple tracks) | Multiple | Professional archiving |
| WebM | .webm | WebVTT | Single | Web streaming |
| AVI | .avi | Poor (external only) | Single | Legacy support |

## Performance

### Processing Speed
- **Subtitle Generation**: ~0.2-0.5x real-time (5-minute video → 10-25 minutes)
- **Audio Dubbing**: ~0.1-0.3x real-time (requires TTS for entire audio)
- **Video Remuxing**: Near real-time (no re-encoding)

### Hardware Requirements
- **CPU**: Multi-core recommended for parallel processing
- **RAM**: 4GB minimum, 8GB+ recommended
- **GPU**: Optional (m4t server uses GPU for inference)
- **Storage**: ~10x video file size for temporary processing

## Project Structure

```
stream-polyglot/
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── main.py                     # Main CLI entry point (translation pipeline)
├── audio_timeline.py           # Audio timeline + VAD segmentation
├── speaker_clustering.py       # Speaker clustering via voice embeddings
├── srt_utils.py                # SRT parsing/generation utilities
├── resume_transcribe.py        # VAD-based checkpoint resume transcription
│
├── lecture_annotator/          # 🆕 Lecture annotation pipeline
│   ├── __init__.py
│   ├── __main__.py             # CLI: python -m lecture_annotator
│   ├── pipeline.py             # End-to-end orchestration
│   ├── download.py             # YouTube download (yt-dlp)
│   ├── transcribe.py           # Whisper / m4t ASR → SRT
│   ├── extract_frames.py       # Key frame extraction (semantic/uniform/scene)
│   ├── annotate.py             # Multimodal LLM annotation → Markdown
│   ├── srt_utils.py            # SRT utilities (shared)
│   └── README.md               # Detailed API documentation
│
├── subtitle-refiner/           # LLM-based subtitle refinement
│
├── output/                     # Pipeline output directory
│   ├── liequn-24/              # Example: 李群李代数 第24讲 (Whisper)
│   └── liequn-24-vad/          # Example: same lecture (VAD + m4t, higher quality)
│
├── tests/                      # Unit tests
├── docs/                       # Documentation
├── memo/                       # Development notes
└── assets/                     # Static assets
```

## Roadmap

### v0.1.0 — Core Translation ✅
- [x] FFmpeg video/audio processing
- [x] m4t API client (SeamlessM4T)
- [x] SRT subtitle generation with accurate timestamps
- [x] Bilingual subtitle support
- [x] Audio VAD segmentation (audio_timeline.py)
- [x] CLI interface (main.py)

### v0.2.0 — Voice & Refinement ✅
- [x] Audio dubbing with TTS
- [x] Voice cloning via GPT-SoVITS
- [x] LLM-based subtitle refinement (subtitle-refiner)
- [x] Audio splitting (vocals/accompaniment via Spleeter)
- [x] Speaker clustering (resemblyzer + scikit-learn)

### v0.3.0 — Lecture Annotator ✅ (Current)
- [x] YouTube download pipeline (yt-dlp, cookies/proxy support)
- [x] Multi-backend ASR: Whisper (openai/faster) + m4t API
- [x] Key frame extraction (semantic/uniform/scene strategies)
- [x] Paragraph-start frame auto-extraction
- [x] Multimodal LLM annotation (SRT + screenshots → Markdown)
- [x] VAD-based resume transcription with checkpointing

### v1.0.0 — Future
- [ ] GUI interface (Streamlit/Qt)
- [ ] WebVTT subtitle support
- [ ] Batch processing for multiple videos
- [ ] Real-time streaming translation

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Troubleshooting

### Common Issues

**Q: "FFmpeg not found" error**
```bash
# Verify FFmpeg installation
ffmpeg -version

# Add FFmpeg to PATH (Windows)
# Add C:\path\to\ffmpeg\bin to System Environment Variables
```

**Q: "m4t API connection refused"**
```bash
# Check if m4t server is running
curl http://localhost:8000/health

# Start m4t server
cd ~/work/m4t
./start_dev.sh
```

**Q: "Audio/subtitle out of sync"**
```bash
# Use --sync-offset parameter to adjust timing
python stream-polyglot.py translate \
  --input video.mp4 \
  --sync-offset 0.5  # Delay subtitles by 0.5 seconds
```

## License

MIT License - see [LICENSE](LICENSE) file for details

## Acknowledgments

- **SeamlessM4T** (Meta AI): Multilingual translation model
- **FFmpeg**: Video/audio processing framework
- Community contributors and testers

## Contact

- **Issues**: https://github.com/yourusername/stream-polyglot/issues
- **Discussions**: https://github.com/yourusername/stream-polyglot/discussions

---

**Stream-Polyglot** - Breaking language barriers, one frame at a time.

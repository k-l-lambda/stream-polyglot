"""
__main__.py — CLI entry point for lecture_annotator.

Usage:
    python -m lecture_annotator https://youtu.be/xxx -o ./output/
    python -m lecture_annotator --help
"""

from __future__ import annotations

import argparse
import logging
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="lecture_annotator",
        description=(
            "End-to-end lecture video annotation pipeline.\n"
            "Downloads YouTube video → Whisper ASR → Key frame extraction → LLM annotation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Full pipeline
  python -m lecture_annotator https://youtu.be/xxx -o ./output/

  # Skip download (already have video)
  python -m lecture_annotator --skip-download --video ./video.mp4 --audio ./audio.wav -o ./output/

  # Skip transcription (already have SRT)
  python -m lecture_annotator --skip-download --video ./video.mp4 --srt ./subtitles.srt -o ./output/

  # Annotation only (have SRT + frames)
  python -m lecture_annotator --skip-download --skip-transcribe --skip-frames \\
      --srt ./subtitles.srt --frames ./frames/ -o ./output/
""",
    )

    # Positional: YouTube URL (optional when skipping download)
    parser.add_argument(
        "url",
        nargs="?",
        default="",
        help="YouTube video URL (required unless --skip-download)",
    )

    # Output
    parser.add_argument(
        "-o", "--output-dir",
        default="./output",
        help="Output directory (default: ./output)",
    )

    # Download options
    dl_group = parser.add_argument_group("download options")
    dl_group.add_argument("--cookies", help="Path to cookies.txt for yt-dlp")
    dl_group.add_argument("--proxy", help="Proxy URL (e.g. socks5://127.0.0.1:1080)")

    # Transcription options
    asr_group = parser.add_argument_group("transcription options")
    asr_group.add_argument(
        "--language", "-l",
        default=None,
        help="Language code for Whisper (zh, en, …). None = auto-detect.",
    )
    asr_group.add_argument(
        "--model", "-m",
        default="base",
        dest="whisper_model",
        help="Whisper model size: tiny, base, small, medium, large-v3 (default: base)",
    )

    # Frame extraction options
    frame_group = parser.add_argument_group("frame extraction options")
    frame_group.add_argument(
        "--frame-strategy",
        default="semantic",
        choices=["semantic", "uniform", "scene"],
        help="Frame extraction strategy (default: semantic)",
    )
    frame_group.add_argument(
        "--frame-interval",
        type=float,
        default=60.0,
        help="Interval in seconds for 'uniform' strategy (default: 60.0)",
    )
    frame_group.add_argument(
        "--max-frames",
        type=int,
        default=50,
        help="Maximum number of frames to extract (default: 50)",
    )

    # Annotation options
    ann_group = parser.add_argument_group("annotation options")
    ann_group.add_argument(
        "--annotate-model",
        default="pa/gemini-3.1-pro-preview",
        help="LLM model for annotation (default: pa/gemini-3.1-pro-preview)",
    )
    ann_group.add_argument(
        "--api-key",
        default=None,
        help="PPIO API key (default: $PPIO_API_KEY env var)",
    )

    # Skip controls
    skip_group = parser.add_argument_group("skip controls")
    skip_group.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download step (use --video/--audio instead)",
    )
    skip_group.add_argument(
        "--video",
        dest="video_path",
        default=None,
        help="Path to existing video file (with --skip-download)",
    )
    skip_group.add_argument(
        "--audio",
        dest="audio_path",
        default=None,
        help="Path to existing audio file (with --skip-download)",
    )
    skip_group.add_argument(
        "--skip-transcribe",
        action="store_true",
        help="Skip transcription step (use --srt instead)",
    )
    skip_group.add_argument(
        "--srt",
        dest="srt_path",
        default=None,
        help="Path to existing SRT file (with --skip-transcribe)",
    )
    skip_group.add_argument(
        "--skip-frames",
        action="store_true",
        help="Skip frame extraction step (use --frames instead)",
    )
    skip_group.add_argument(
        "--frames",
        dest="frames_dir",
        default=None,
        help="Path to existing frames directory (with --skip-frames)",
    )

    # Logging
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    args = parser.parse_args()

    # Validate: URL required unless skipping download
    if not args.skip_download and not args.url:
        parser.error("YouTube URL is required unless --skip-download is set")

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Run pipeline
    from .pipeline import run_pipeline

    try:
        result = run_pipeline(
            url=args.url,
            output_dir=args.output_dir,
            cookies=args.cookies,
            proxy=args.proxy,
            language=args.language,
            whisper_model=args.whisper_model,
            frame_strategy=args.frame_strategy,
            frame_interval=args.frame_interval,
            max_frames=args.max_frames,
            annotate_model=args.annotate_model,
            api_key=args.api_key,
            skip_download=args.skip_download,
            video_path=args.video_path,
            audio_path=args.audio_path,
            skip_transcribe=args.skip_transcribe,
            srt_path=args.srt_path,
            skip_frames=args.skip_frames,
            frames_dir=args.frames_dir,
        )

        if result["success"]:
            print("\n✅ Pipeline succeeded!")
            for key, val in result.items():
                if key != "success" and val:
                    print(f"  {key}: {val}")
        else:
            print("\n❌ Pipeline failed.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        logging.getLogger(__name__).error("Pipeline failed: %s", exc, exc_info=True)
        print(f"\n❌ Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

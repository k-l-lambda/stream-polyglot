"""
lecture_annotator — End-to-end YouTube lecture annotation pipeline.

Modules:
    download        — YouTube video download (yt-dlp + ffmpeg)
    transcribe      — Whisper ASR to SRT subtitles
    extract_frames  — Key frame extraction (semantic/uniform/scene)
    annotate        — LLM multimodal annotation
    pipeline        — Orchestrates all steps into a single pipeline

Usage:
    from lecture_annotator import run_pipeline

    result = run_pipeline("https://youtu.be/xxx", "./output/")
"""

__version__ = "0.1.0"

from .pipeline import run_pipeline
from .download import download_video
from .transcribe import transcribe_audio
from .extract_frames import extract_key_frames
from .annotate import annotate_lecture

__all__ = [
    "run_pipeline",
    "download_video",
    "transcribe_audio",
    "extract_key_frames",
    "annotate_lecture",
]

"""
LLM Annotation Module for Lecture Videos.

Takes SRT subtitles + keyframe screenshots, sends them to LLM for analysis,
and produces a structured Markdown document with annotations.

Pipeline position: YouTube → Download → ASR(SRT) → Keyframes → **LLM Annotate** → Markdown
"""

from __future__ import annotations

import base64
import glob
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):  # type: ignore[misc]
        return iterable

from .srt_utils import format_srt_timestamp, parse_srt_file

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------
DEFAULT_BASE_URL = "https://api.ppinfra.com/v3/openai"
DEFAULT_MODEL = "pa/gemini-3.1-pro-preview"
DEFAULT_API_KEY_ENV = "PPIO_API_KEY"
PARAGRAPH_GAP_SECONDS = 5.0  # gap threshold to split paragraphs
MAX_FRAMES_PER_PARAGRAPH = 1  # default: send at most 1 screenshot per paragraph

SYSTEM_PROMPT = (
    "你是一位理论物理/技术课程讲解专家。"
    "你的任务是对课程视频的字幕片段（可能附带板书/PPT截图）进行深度注解。"
    "请使用 Markdown 格式输出。"
)

USER_PROMPT_TEMPLATE = """\
以下是课程视频的一段字幕文本（时间 {start} ~ {end}）：

{subtitle_text}

请针对这段内容：
1. 识别并解释板书/PPT中出现的所有公式（逐一说明每个符号含义）
2. 补充必要的理论背景知识
3. 用通俗语言解释核心概念
4. 如有截图，描述截图中的板书内容

如果这段内容没有公式或技术概念，则简要概括要点即可。"""


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _ts_readable(seconds: float) -> str:
    """Convert seconds to HH:MM:SS display string."""
    return format_srt_timestamp(seconds).split(",")[0]


def _parse_frame_timestamp(filename: str) -> Optional[float]:
    """
    Extract timestamp (seconds) from a frame filename.

    Supported patterns:
        frame_000120.0_formula.jpg  →  120.0
        frame_000120.5.jpg          →  120.5
        frame_00120.jpg             →  120.0
    """
    basename = Path(filename).stem  # strip extension
    # Try: frame_XXXX.X or frame_XXXX.X_label
    m = re.search(r'frame[_-]?(\d+(?:\.\d+)?)', basename)
    if m:
        return float(m.group(1))
    return None


def _load_frames_index(frames_dir: str) -> List[Tuple[float, str]]:
    """
    Scan *frames_dir* for image files and return sorted list of (timestamp, path).
    """
    if not frames_dir or not os.path.isdir(frames_dir):
        return []

    extensions = {"*.jpg", "*.jpeg", "*.png", "*.webp"}
    files: List[str] = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(frames_dir, ext)))

    indexed: List[Tuple[float, str]] = []
    for fpath in files:
        ts = _parse_frame_timestamp(os.path.basename(fpath))
        if ts is not None:
            indexed.append((ts, fpath))

    indexed.sort(key=lambda x: x[0])
    return indexed


def _frames_in_range(
    frames_index: List[Tuple[float, str]],
    start: float,
    end: float,
    max_frames: int = MAX_FRAMES_PER_PARAGRAPH,
) -> List[str]:
    """Return up to *max_frames* frame paths whose timestamp falls in [start, end]."""
    candidates = [path for ts, path in frames_index if start <= ts <= end]
    if len(candidates) <= max_frames:
        return candidates
    # Evenly sample
    step = len(candidates) / max_frames
    return [candidates[int(i * step)] for i in range(max_frames)]


def _image_to_base64_url(image_path: str) -> str:
    """Read an image file and return a data-URI suitable for OpenAI image_url."""
    ext = Path(image_path).suffix.lower().lstrip(".")
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


# ---------------------------------------------------------------------------
# SRT → paragraphs
# ---------------------------------------------------------------------------

def _group_into_paragraphs(
    subtitles: List[Dict],
    gap_threshold: float = PARAGRAPH_GAP_SECONDS,
) -> List[Dict]:
    """
    Merge consecutive subtitle entries into semantic paragraphs.

    A new paragraph starts when the gap between the end of the previous
    entry and the start of the next exceeds *gap_threshold* seconds.

    Returns list of dicts:
        {start, end, text, subtitle_count}
    """
    if not subtitles:
        return []

    paragraphs: List[Dict] = []
    cur_start = subtitles[0]["start"]
    cur_end = subtitles[0]["end"]
    cur_texts: List[str] = [subtitles[0]["text"]]

    for sub in subtitles[1:]:
        gap = sub["start"] - cur_end
        if gap > gap_threshold:
            # Flush current paragraph
            paragraphs.append({
                "start": cur_start,
                "end": cur_end,
                "text": " ".join(cur_texts),
                "subtitle_count": len(cur_texts),
            })
            cur_start = sub["start"]
            cur_end = sub["end"]
            cur_texts = [sub["text"]]
        else:
            cur_end = sub["end"]
            cur_texts.append(sub["text"])

    # Flush last
    paragraphs.append({
        "start": cur_start,
        "end": cur_end,
        "text": " ".join(cur_texts),
        "subtitle_count": len(cur_texts),
    })
    return paragraphs


# ---------------------------------------------------------------------------
# LLM interaction
# ---------------------------------------------------------------------------

def _get_client(api_key: Optional[str] = None, base_url: str = DEFAULT_BASE_URL):
    """Create an OpenAI-compatible client."""
    from openai import OpenAI

    key = api_key or os.environ.get(DEFAULT_API_KEY_ENV, "")
    if not key:
        raise ValueError(
            f"No API key provided. Pass api_key= or set ${DEFAULT_API_KEY_ENV}"
        )
    return OpenAI(base_url=base_url, api_key=key)


def analyze_frame(
    image_path: str,
    context_text: str = "",
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
) -> str:
    """
    Standalone visual analysis of a single lecture screenshot.

    Args:
        image_path: Path to the image file.
        context_text: Optional surrounding subtitle text for context.
        model: LLM model identifier.
        api_key: API key (falls back to env var).
        base_url: API endpoint.

    Returns:
        LLM-generated description/analysis of the frame.
    """
    client = _get_client(api_key, base_url)
    data_url = _image_to_base64_url(image_path)

    user_content: list = []
    if context_text:
        user_content.append({
            "type": "text",
            "text": f"以下是截图对应时间段的字幕内容：\n{context_text}\n\n请描述并解释截图中的板书/PPT内容，包括所有公式及其符号含义。",
        })
    else:
        user_content.append({
            "type": "text",
            "text": "请描述并解释这张课程截图中的板书/PPT内容，包括所有公式及其符号含义。",
        })

    user_content.append({
        "type": "image_url",
        "image_url": {"url": data_url},
    })

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_tokens=2048,
        temperature=0.3,
    )
    return response.choices[0].message.content or ""


def _annotate_paragraph(
    client,
    paragraph: Dict,
    frame_paths: List[str],
    model: str,
    max_retries: int = 3,
) -> str:
    """
    Call LLM to annotate a single paragraph, optionally with images.

    Retries up to *max_retries* times with exponential backoff on failure.

    Returns the annotation text (Markdown).
    """
    start_str = _ts_readable(paragraph["start"])
    end_str = _ts_readable(paragraph["end"])

    user_content: list = []

    # Text prompt
    prompt_text = USER_PROMPT_TEMPLATE.format(
        start=start_str,
        end=end_str,
        subtitle_text=paragraph["text"],
    )
    user_content.append({"type": "text", "text": prompt_text})

    # Attach images
    for fpath in frame_paths:
        try:
            data_url = _image_to_base64_url(fpath)
            user_content.append({
                "type": "image_url",
                "image_url": {"url": data_url},
            })
        except Exception as e:
            logger.warning("Failed to encode image %s: %s", fpath, e)

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=4096,
                temperature=0.3,
            )
            choices = response.choices
            if not choices:
                raise ValueError("API returned empty choices list")
            return choices[0].message.content or ""
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = 2 ** (attempt - 1)  # 1s, 2s, 4s …
                logger.warning(
                    "Attempt %d/%d failed for paragraph [%s ~ %s]: %s — retrying in %ds",
                    attempt, max_retries, start_str, end_str, exc, wait,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "All %d attempts failed for paragraph [%s ~ %s]: %s",
                    max_retries, start_str, end_str, exc,
                )

    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def _build_markdown(
    video_title: str,
    paragraphs: List[Dict],
    annotations: List[str],
    frame_map: List[List[str]],
    frames_dir: str,
    output_path: str,
) -> str:
    """Assemble the final Markdown document."""
    lines: List[str] = []

    # Title
    title = video_title or "课程讲义"
    lines.append(f"# {title}\n")
    lines.append(f"> 自动生成的课程注解文档（共 {len(paragraphs)} 个段落）\n")

    # Table of contents
    lines.append("## 目录\n")
    for i, para in enumerate(paragraphs, 1):
        ts = _ts_readable(para["start"])
        lines.append(f"- [{ts} 段落 {i}](#段落-{i})")
    lines.append("")

    lines.append("---\n")

    # Compute relative path from output file to frames_dir
    output_dir = os.path.dirname(os.path.abspath(output_path))
    frames_dir_abs = os.path.abspath(frames_dir) if frames_dir else ""

    for i, (para, annotation, frames) in enumerate(
        zip(paragraphs, annotations, frame_map), 1
    ):
        start_str = _ts_readable(para["start"])
        end_str = _ts_readable(para["end"])

        lines.append(f"## 段落 {i}\n")
        lines.append(f"**时间：** {start_str} ~ {end_str}\n")

        # Original subtitle
        lines.append("<details><summary>📝 原始字幕</summary>\n")
        lines.append(f"{para['text']}\n")
        lines.append("</details>\n")

        # Screenshots
        if frames:
            lines.append("**课程截图：**\n")
            for fpath in frames:
                rel = os.path.relpath(fpath, output_dir)
                fname = os.path.basename(fpath)
                lines.append(f"![{fname}]({rel})\n")

        # Annotation
        lines.append("### 注解\n")
        lines.append(f"{annotation}\n")

        lines.append("---\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def annotate_lecture(
    srt_path: str,
    frames_dir: str,
    output_path: str,
    video_title: str = "",
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    gap_threshold: float = PARAGRAPH_GAP_SECONDS,
    max_frames_per_paragraph: int = MAX_FRAMES_PER_PARAGRAPH,
) -> str:
    """
    Annotate a lecture video using LLM analysis of subtitles and keyframes.

    Args:
        srt_path: Path to the SRT subtitle file.
        frames_dir: Directory containing keyframe screenshots.
        output_path: Where to write the output Markdown file.
        video_title: Title for the generated document.
        model: LLM model identifier (PPIO-compatible).
        api_key: API key; falls back to $PPIO_API_KEY env var.
        base_url: OpenAI-compatible API base URL.
        gap_threshold: Seconds of silence to start a new paragraph.
        max_frames_per_paragraph: Max screenshots to attach per LLM call.

    Returns:
        The absolute path of the generated Markdown file.
    """
    # 1. Parse SRT
    logger.info("Parsing SRT: %s", srt_path)
    subtitles = parse_srt_file(srt_path)
    if not subtitles:
        raise ValueError(f"No subtitles found in {srt_path}")
    logger.info("Loaded %d subtitle entries.", len(subtitles))

    # 2. Load frame index
    frames_index = _load_frames_index(frames_dir)
    logger.info("Found %d keyframe screenshots.", len(frames_index))

    # 3. Group into paragraphs
    paragraphs = _group_into_paragraphs(subtitles, gap_threshold)
    logger.info("Grouped into %d paragraphs.", len(paragraphs))

    # 4. Prepare LLM client
    client = _get_client(api_key, base_url)

    # 5. Annotate each paragraph
    annotations: List[str] = []
    frame_map: List[List[str]] = []

    for para in tqdm(paragraphs, desc="Annotating paragraphs", unit="para"):
        # Find frames in range
        frames = _frames_in_range(
            frames_index,
            para["start"],
            para["end"],
            max_frames=max_frames_per_paragraph,
        )
        frame_map.append(frames)

        try:
            annotation = _annotate_paragraph(client, para, frames, model)
        except Exception as exc:
            logger.error(
                "Failed to annotate paragraph [%s ~ %s]: %s",
                _ts_readable(para["start"]),
                _ts_readable(para["end"]),
                exc,
            )
            annotation = f"⚠️ 注解失败: {exc}"

        annotations.append(annotation)

    # 6. Generate Markdown
    markdown = _build_markdown(
        video_title, paragraphs, annotations, frame_map, frames_dir, output_path,
    )

    # 7. Write output
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    result_path = os.path.abspath(output_path)
    logger.info("Annotation complete → %s", result_path)
    return result_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Simple CLI wrapper."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Annotate a lecture video from SRT + keyframes using LLM."
    )
    parser.add_argument("srt", help="Path to SRT subtitle file")
    parser.add_argument("frames", help="Directory with keyframe screenshots")
    parser.add_argument("-o", "--output", default="lecture_notes.md",
                        help="Output Markdown path (default: lecture_notes.md)")
    parser.add_argument("-t", "--title", default="", help="Video title")
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL,
                        help=f"LLM model (default: {DEFAULT_MODEL})")
    parser.add_argument("--api-key", default=None,
                        help=f"API key (default: ${DEFAULT_API_KEY_ENV} env)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help="API base URL")
    parser.add_argument("--gap", type=float, default=PARAGRAPH_GAP_SECONDS,
                        help="Paragraph gap threshold in seconds")
    parser.add_argument("--max-frames", type=int, default=MAX_FRAMES_PER_PARAGRAPH,
                        help="Max frames per paragraph")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    result = annotate_lecture(
        srt_path=args.srt,
        frames_dir=args.frames,
        output_path=args.output,
        video_title=args.title,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        gap_threshold=args.gap,
        max_frames_per_paragraph=args.max_frames,
    )
    print(f"✅ Done: {result}")


if __name__ == "__main__":
    main()

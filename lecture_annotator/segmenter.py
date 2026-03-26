"""
Transcript-wide lecture segmentation with titled paragraphs.

Runs after SRT generation and before frame extraction / annotation.
Uses an OpenAI-compatible model (default: gpt5.4) to segment the full
transcript into paragraph-scale sections, typically 3–10 minutes each,
and assigns a short title to every segment.
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import Dict, List, Optional

from .srt_utils import format_srt_timestamp, parse_srt_file

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
DEFAULT_SEGMENT_MODEL = "gpt5.4"
DEFAULT_API_KEY_ENV = "LLM_API_KEY"
TARGET_MIN_MINUTES = 3.0
TARGET_MAX_MINUTES = 10.0
ABS_MIN_SECONDS = 90.0
ABS_MAX_SECONDS = 900.0

SEGMENT_SYSTEM_PROMPT = """
你是课程结构分析助手。你的任务是通读整篇课程字幕，生成后续流程使用的“规范段落划分”。

重要：你拿到的不是纯文本，而是带有明确开始/结束时间轴的字幕序列。你必须同时结合：
- 字幕文本内容
- 每条字幕的开始/结束时间
- 累积时长与段落篇幅
来做分段判断。

要求：
1. 输出 JSON，对整个课程进行顺序分段。
2. 每段必须覆盖一段连续时间区间，段与段之间不能乱序、不能重叠。
3. 每段都要有简洁小标题，标题应概括该段核心内容。
4. 分段必须显式参考字幕时间轴，而不是只按语义文本切分。
5. 段落时长原则上控制在 3-10 分钟。
6. 若内容结构确实需要，可略微超出，但避免过短碎片化。
7. 尽量在主题切换、论证阶段切换、公式推导阶段切换处断开。
8. 不要遗漏内容；整篇字幕必须被完整覆盖。
9. 输出只允许是 JSON，不要附加解释。
""".strip()


def _get_client(api_key: Optional[str] = None, base_url: str = DEFAULT_BASE_URL):
    from openai import OpenAI

    key = api_key or os.environ.get(DEFAULT_API_KEY_ENV, "")
    if not key:
        raise ValueError(
            f"No API key provided. Pass api_key= or set ${DEFAULT_API_KEY_ENV}"
        )
    return OpenAI(base_url=base_url, api_key=key)


def _compact_transcript(subtitles: List[Dict]) -> str:
    lines = []
    for idx, sub in enumerate(subtitles, start=1):
        start = format_srt_timestamp(sub["start"]).split(",")[0]
        end = format_srt_timestamp(sub["end"]).split(",")[0]
        text = " ".join(sub["text"].split())
        lines.append(f"[{idx}] {start} --> {end} | {text}")
    return "\n".join(lines)


def _build_segmentation_prompt(subtitles: List[Dict]) -> str:
    total_minutes = 0.0
    if subtitles:
        total_minutes = (subtitles[-1]["end"] - subtitles[0]["start"]) / 60.0
    suggested = max(1, round(total_minutes / 6.0))
    transcript = _compact_transcript(subtitles)
    schema = {
        "segments": [
            {
                "start_subtitle_index": 1,
                "end_subtitle_index": 15,
                "title": "示例标题"
            }
        ]
    }
    return f"""
请对下面整篇课程字幕做分段，并给每段起一个小标题。

注意：下面每一行字幕都带有开始时间和结束时间。你必须把“时间轴”作为分段依据的一部分，而不是只看文本语义。

分段原则：
- 每段目标时长约 3-10 分钟
- 必须结合字幕的开始/结束时间来控制段落篇幅
- 尽量按内容主题/推导阶段划分
- 段落不要碎
- 必须完整覆盖整篇字幕
- 使用字幕索引范围来定义每一段

课程总时长约：{total_minutes:.1f} 分钟
建议段数可参考：{suggested} 段左右（不是硬约束）

请严格输出 JSON，结构如下：
{json.dumps(schema, ensure_ascii=False, indent=2)}

可用字幕（每行格式为 [索引] 开始 --> 结束 | 文本）：
{transcript}
""".strip()


def _coerce_segments(raw: object) -> List[Dict]:
    if isinstance(raw, dict):
        raw = raw.get("segments", [])
    if not isinstance(raw, list):
        raise ValueError("Segmentation response must contain a list of segments")

    segments: List[Dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        start_idx = int(item["start_subtitle_index"])
        end_idx = int(item["end_subtitle_index"])
        title = str(item.get("title", "")).strip()
        if not title:
            title = f"第{len(segments)+1}段"
        segments.append({
            "start_subtitle_index": start_idx,
            "end_subtitle_index": end_idx,
            "title": title,
        })
    if not segments:
        raise ValueError("No valid segments returned by model")
    return segments


def _extract_json(text: str) -> object:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if not part or part.lower() == "json":
                continue
            text = part.removeprefix("json").strip()
            break
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("Could not locate JSON in model response")


def _validate_and_materialize(subtitles: List[Dict], raw_segments: List[Dict]) -> List[Dict]:
    count = len(subtitles)
    prev_end = 0
    materialized: List[Dict] = []

    for i, seg in enumerate(raw_segments, start=1):
        start_idx = max(1, min(count, seg["start_subtitle_index"]))
        end_idx = max(1, min(count, seg["end_subtitle_index"]))
        if end_idx < start_idx:
            start_idx, end_idx = end_idx, start_idx
        if start_idx > prev_end + 1:
            start_idx = prev_end + 1
        if start_idx <= prev_end:
            start_idx = prev_end + 1
        if start_idx > count:
            break
        if end_idx < start_idx:
            end_idx = start_idx
        if i == len(raw_segments):
            end_idx = count
        end_idx = min(count, end_idx)

        start_sub = subtitles[start_idx - 1]
        end_sub = subtitles[end_idx - 1]
        materialized.append({
            "index": len(materialized) + 1,
            "start_subtitle_index": start_idx,
            "end_subtitle_index": end_idx,
            "start": start_sub["start"],
            "end": end_sub["end"],
            "title": seg["title"],
            "text": "\n".join(s["text"] for s in subtitles[start_idx - 1:end_idx]),
            "subtitle_count": end_idx - start_idx + 1,
        })
        prev_end = end_idx
        if prev_end >= count:
            break

    if not materialized:
        raise ValueError("Segmentation produced no materialized segments")

    if materialized[-1]["end_subtitle_index"] < count:
        tail_start = materialized[-1]["end_subtitle_index"] + 1
        start_sub = subtitles[tail_start - 1]
        end_sub = subtitles[-1]
        materialized.append({
            "index": len(materialized) + 1,
            "start_subtitle_index": tail_start,
            "end_subtitle_index": count,
            "start": start_sub["start"],
            "end": end_sub["end"],
            "title": "补充分段",
            "text": "\n".join(s["text"] for s in subtitles[tail_start - 1:count]),
            "subtitle_count": count - tail_start + 1,
        })

    return _merge_duration_outliers(materialized)


def _merge_duration_outliers(segments: List[Dict]) -> List[Dict]:
    if len(segments) <= 1:
        return segments

    merged: List[Dict] = []
    i = 0
    while i < len(segments):
        seg = dict(segments[i])
        duration = seg["end"] - seg["start"]
        if duration < ABS_MIN_SECONDS:
            if i + 1 < len(segments):
                nxt = segments[i + 1]
                seg["end_subtitle_index"] = nxt["end_subtitle_index"]
                seg["end"] = nxt["end"]
                seg["text"] = seg["text"] + "\n" + nxt["text"]
                seg["subtitle_count"] += nxt["subtitle_count"]
                seg["title"] = f"{seg['title']} / {nxt['title']}"
                i += 1
            elif merged:
                prev = merged[-1]
                prev["end_subtitle_index"] = seg["end_subtitle_index"]
                prev["end"] = seg["end"]
                prev["text"] = prev["text"] + "\n" + seg["text"]
                prev["subtitle_count"] += seg["subtitle_count"]
                i += 1
                continue
        merged.append(seg)
        i += 1

    for idx, seg in enumerate(merged, start=1):
        seg["index"] = idx
    return merged


def segment_transcript(
    srt_path: str,
    output_dir: str,
    *,
    api_key: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_SEGMENT_MODEL,
) -> str:
    subtitles = parse_srt_file(srt_path)
    if not subtitles:
        raise ValueError(f"No subtitles found in {srt_path}")

    logger.info("Segmenting transcript with %s: %s", model, srt_path)
    client = _get_client(api_key, base_url)
    prompt = _build_segmentation_prompt(subtitles)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SEGMENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        timeout=300,
    )
    content = response.choices[0].message.content or ""
    raw = _extract_json(content)
    raw_segments = _coerce_segments(raw)
    segments = _validate_and_materialize(subtitles, raw_segments)

    payload = {
        "source_srt": os.path.abspath(srt_path),
        "model": model,
        "target_duration_minutes": {
            "min": TARGET_MIN_MINUTES,
            "max": TARGET_MAX_MINUTES,
        },
        "segments": [
            {
                "index": seg["index"],
                "start": seg["start"],
                "end": seg["end"],
                "start_ts": format_srt_timestamp(seg["start"]),
                "end_ts": format_srt_timestamp(seg["end"]),
                "title": seg["title"],
                "text": seg["text"],
                "subtitle_count": seg["subtitle_count"],
                "start_subtitle_index": seg["start_subtitle_index"],
                "end_subtitle_index": seg["end_subtitle_index"],
                "duration_seconds": round(seg["end"] - seg["start"], 3),
                "duration_minutes": round((seg["end"] - seg["start"]) / 60.0, 3),
            }
            for seg in segments
        ],
    }

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "transcript_segments.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("Transcript segmentation written: %s (%d segments)", out_path, len(segments))
    return os.path.abspath(out_path)


def load_segments_json(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    segments = payload.get("segments", [])
    if not isinstance(segments, list):
        raise ValueError("Invalid segmentation JSON: segments must be a list")
    return segments

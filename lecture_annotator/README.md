# lecture_annotator

YouTube 讲座视频下载 + Whisper ASR 转录子模块，属于 [stream-polyglot](../) 项目。

## 功能

| 模块 | 说明 |
|------|------|
| `download.py` | 使用 yt-dlp 下载 YouTube 视频 (≤720p mp4) 并提取 16kHz mono WAV 音频 |
| `transcribe.py` | 使用 Whisper (openai-whisper 或 faster-whisper) 生成 SRT 字幕 |
| `segmenter.py` | 在 SRT 完成后，用 `gpt5.4` 通读全文，按 3–10 分钟原则做课程分段并生成小标题 |

## 安装依赖

### 基础依赖（下载 + 音频提取）

```bash
# yt-dlp（如果尚未安装）
pip install yt-dlp

# ffmpeg（系统级）
sudo apt install ffmpeg        # Debian/Ubuntu
brew install ffmpeg             # macOS
```

### ASR 依赖（二选一）

#### 方案 A: openai-whisper（官方实现）

```bash
pip install openai-whisper

# 如果 GPU 可用，确保安装了 torch CUDA 版本：
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

#### 方案 B: faster-whisper（CTranslate2，更省显存）

```bash
pip install faster-whisper
```

> 💡 两者装一个即可。`transcribe.py` 会自动检测并选择可用的后端。  
> 优先使用 openai-whisper，如果不可用则回退到 faster-whisper。

## 快速使用

### 命令行

```bash
# 1. 下载视频 + 提取音频
python -m lecture_annotator.download "https://www.youtube.com/watch?v=VIDEO_ID" -o /tmp/lectures

# 2. 转录为 SRT
python -m lecture_annotator.transcribe /tmp/lectures/video_title.wav -o /tmp/lectures -l zh -m large-v3

# 3. 运行完整课程注释流水线（现会在 SRT 后自动做 transcript-wide segmentation）
python -m lecture_annotator "https://www.youtube.com/watch?v=VIDEO_ID" -o /tmp/lectures --annotate-model gpt5.4
```

### Python API

```python
from lecture_annotator.download import download_video
from lecture_annotator.transcribe import transcribe_audio

# 第一步：下载
result = download_video(
    "https://www.youtube.com/watch?v=VIDEO_ID",
    "/tmp/lectures",
    # cookies="/path/to/cookies.txt",   # 可选：应对 YouTube 封 IP
    # proxy="socks5://127.0.0.1:1080",  # 可选：代理
)
print(result)
# {
#     'video': PosixPath('/tmp/lectures/Video_Title.mp4'),
#     'audio': PosixPath('/tmp/lectures/Video_Title.wav'),
#     'title': 'Video Title',
#     'duration': 3600.0
# }

# 第二步：转录
srt_path = transcribe_audio(
    result["audio"],
    "/tmp/lectures",
    language="zh",       # 可选，None 则自动检测
    model_size="large-v3",
)
print(srt_path)  # /tmp/lectures/Video_Title.srt
```

## API 文档

### `download_video(url, output_dir, *, cookies=None, proxy=None) -> dict`

下载 YouTube 视频并提取音频。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `url` | `str` | YouTube 视频 URL |
| `output_dir` | `str \| Path` | 输出目录（自动创建） |
| `cookies` | `str \| Path \| None` | Netscape cookies.txt 路径。为 None 时，下载失败后自动尝试 `~/.config/yt-dlp/cookies.txt` |
| `proxy` | `str \| None` | 代理 URL，如 `http://127.0.0.1:7890` 或 `socks5://127.0.0.1:1080` |

**返回：**

```python
{
    'video': Path,     # 下载的 MP4 文件路径
    'audio': Path,     # 提取的 16kHz mono WAV 路径
    'title': str,      # 视频标题
    'duration': float, # 时长（秒）
}
```

**YouTube 封 IP 处理策略：**
1. 优先直接下载
2. 遇到 403 / bot 检测 → 自动使用 `~/.config/yt-dlp/cookies.txt`（如果存在）
3. 也可显式传入 `cookies` 参数

---

### `transcribe_audio(audio_path, output_dir, *, language=None, model_size='large-v3') -> str`

使用 Whisper 对音频做 ASR，生成 SRT 字幕。

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `audio_path` | `str \| Path` | 输入音频文件路径（推荐 16kHz mono WAV） |
| `output_dir` | `str \| Path` | SRT 输出目录 |
| `language` | `str \| None` | 语言代码（`"zh"`, `"en"` 等），None 自动检测 |
| `model_size` | `str` | 模型大小：`"large-v3"` / `"medium"` / `"small"` / `"base"` / `"tiny"` |

**返回：** SRT 文件的绝对路径字符串。

**后端选择：**
- 优先使用 `openai-whisper`
- 如不可用，回退到 `faster-whisper`
- 两者均未安装则抛出 `ImportError`

## 新分段机制

现在的课程注释流水线会在 SRT 生成后自动增加一个步骤：

1. 读取整篇字幕
2. 使用 `gpt5.4` 对全文进行一次通观式分段
3. 为每个段落生成一个小标题
4. 输出 `transcript_segments.json`
5. 后续抽帧与注释都以这个 JSON 里的段落边界为准

每个段落原则上控制在 **3–10 分钟**，但会优先服从课程内容结构。

`transcript_segments.json` 中每段包含：
- `start` / `end`
- `start_ts` / `end_ts`
- `title`
- `text`
- `start_subtitle_index` / `end_subtitle_index`

## 项目结构

```
lecture_annotator/
├── __init__.py       # 包初始化
├── download.py       # YouTube 下载 + 音频提取
├── transcribe.py     # Whisper ASR → SRT
├── segmenter.py      # 全文分段 + 小标题（gpt5.4）
└── README.md         # 本文件
```

## License

与 stream-polyglot 主项目一致。

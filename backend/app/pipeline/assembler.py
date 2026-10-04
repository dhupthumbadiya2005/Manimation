"""Join scene videos into the final video.

Each scene is first conformed so its audio track is exactly as long as its video
(narration often ends before the last animation does; a narration-less fallback
render has no audio at all) and uses one common audio format. Without this, a
short audio track would shift every later scene's narration out of sync.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

AUDIO_ARGS = ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]


def _probe(path: Path) -> tuple[float, bool]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    streams = json.loads(out)["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    return float(video["duration"]), any(s["codec_type"] == "audio" for s in streams)


def conform(video: Path, out: Path) -> Path:
    """Copy the video stream; pad/trim audio to the video length (silence if none)."""
    duration, has_audio = _probe(video)
    if has_audio:
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(video),
               "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-af", "apad", "-t", f"{duration:.3f}"]
    else:
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(video),
               "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
               "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-t", f"{duration:.3f}"]
    subprocess.run(cmd + AUDIO_ARGS + [str(out)], check=True)
    return out


def concat(videos: list[Path], out: Path) -> Path:
    if not videos:
        raise ValueError("no scene videos to assemble")
    work = out.parent / "assembly"
    work.mkdir(exist_ok=True)
    parts = [conform(v, work / f"part_{i:02d}.mp4") for i, v in enumerate(videos)]
    list_file = work / "parts.txt"
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c", "copy", str(out)],
        check=True,
    )
    return out

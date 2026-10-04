"""One-session narration bank and the assembler's audio alignment (offline)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline import assembler, narration  # noqa: E402
from manim_kit import tts_deepgram  # noqa: E402

SCENE = '''
class Scene01(ThemedVoiceoverScene):
    def construct(self):
        with self.voiceover(text="First line.") as t:
            pass
        with self.voiceover(text="Second line.") as t:
            pass
        with self.voiceover("Positional third.") as t:
            pass
'''


def test_scene_lines_in_file_order():
    assert narration.scene_lines(SCENE) == ["First line.", "Second line.", "Positional third."]


def test_bank_key_changes_with_any_line_or_voice():
    k = narration.bank_key("flux-priya-en", ["a", "b"])
    assert k == narration.bank_key("flux-priya-en", ["a", "b"])
    assert k != narration.bank_key("flux-priya-en", ["a", "c"])
    assert k != narration.bank_key("flux-meena-en", ["a", "b"])


class FakeSocket:
    """Replays the observed Flux protocol: SpeechStarted, Flushed, audio, SpeechMetadata."""

    def __init__(self, n_turns):
        self.sent = []
        self.inbox = []
        for i in range(n_turns):
            self.inbox += [json.dumps({"type": "SpeechStarted", "speech_id": str(i)}),
                           json.dumps({"type": "Flushed", "speech_id": str(i)}),
                           bytes([i + 1]) * 4, bytes([i + 1]) * 2,
                           json.dumps({"type": "SpeechMetadata", "speech_id": str(i)})]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send(self, message):
        self.sent.append(json.loads(message))

    def recv(self, timeout=None):
        return self.inbox.pop(0)


def test_session_splits_audio_per_turn_in_one_connection():
    sockets = []

    def connect(url, **kwargs):
        sockets.append(FakeSocket(3))
        assert "model=flux-priya-en" in url and "linear16" in url
        return sockets[-1]

    clips = tts_deepgram.synthesize_session(["a", "b", "c"], "flux-priya-en", "KEY", connect=connect)
    assert len(sockets) == 1                                   # one session for every line
    assert clips == [b"\x01" * 6, b"\x02" * 6, b"\x03" * 6]
    kinds = [m["type"] for m in sockets[0].sent]
    assert kinds == ["Speak", "Flush"] * 3 + ["Close"]


def test_service_serves_lines_from_bank_without_api_key(tmp_path, monkeypatch):
    bank = tmp_path / "bank"
    bank.mkdir()
    tts_deepgram.write_wav(b"\x00\x00" * 2400, bank / "001.wav")
    (bank / "manifest.json").write_text(json.dumps(
        {"voice": "flux-priya-en", "bank": "bank", "items": {"First line.": "001.wav"}}))
    monkeypatch.setenv("MANIMATION_NARRATION_BANK", str(bank / "manifest.json"))
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)

    svc = tts_deepgram.DeepgramService(voice="flux-priya-en", cache_dir=tmp_path / "cache")
    result = svc.generate_from_text("First line.")
    assert result["original_audio"].endswith(".wav") and result["input_data"]["bank"] == "bank"
    assert (tmp_path / "cache" / result["original_audio"]).stat().st_size > 0
    with pytest.raises(tts_deepgram.DeepgramError):
        svc.generate_from_text("A line that is not in the bank.")


def _clip(path: Path, seconds: float, audio_seconds: float | None):
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s=320x180:r=15:d={seconds}"]
    if audio_seconds:
        cmd += ["-f", "lavfi", "-i", f"sine=f=440:d={audio_seconds}", "-c:a", "aac"]
    subprocess.run(cmd + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def test_assembler_keeps_narration_in_sync(tmp_path):
    parts = [_clip(tmp_path / "a.mp4", 3, 1.5),    # narration ends early
             _clip(tmp_path / "b.mp4", 2, None),   # no narration at all
             _clip(tmp_path / "c.mp4", 2, 2)]
    out = assembler.concat(parts, tmp_path / "final.mp4")
    durations = {s["codec_type"]: float(s["duration"]) for s in json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", str(out)],
        capture_output=True, text=True, check=True).stdout)["streams"]}
    assert abs(durations["audio"] - durations["video"]) < 0.15
    assert abs(durations["video"] - 7) < 0.15

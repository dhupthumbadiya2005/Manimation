"""Deepgram TTS client, with HTTP mocked (no network, no credits)."""

import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from manim_kit import tts_deepgram  # noqa: E402
from manim_kit.tts_deepgram import DeepgramError, synthesize  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://api.deepgram.com/v2/speak", code, "err", {}, io.BytesIO(body))


@pytest.fixture
def calls(monkeypatch):
    log = []
    monkeypatch.setattr(tts_deepgram.time, "sleep", lambda s: None)
    return log


def test_request_shape(monkeypatch, calls):
    def fake_urlopen(req, timeout):
        calls.append(req)
        return FakeResponse(b"MP3DATA")

    monkeypatch.setattr(tts_deepgram.urllib.request, "urlopen", fake_urlopen)
    assert synthesize("Hello there", "flux-priya-en", "KEY") == b"MP3DATA"
    req = calls[0]
    assert req.full_url == "https://api.deepgram.com/v2/speak?model=flux-priya-en&encoding=mp3"
    assert req.get_header("Authorization") == "Token KEY"
    assert json.loads(req.data) == {"text": "Hello there"}


def test_retries_transient_errors(monkeypatch, calls):
    responses = [http_error(429), http_error(503), FakeResponse(b"OK")]

    def fake_urlopen(req, timeout):
        calls.append(req)
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(tts_deepgram.urllib.request, "urlopen", fake_urlopen)
    assert synthesize("x", "flux-priya-en", "KEY") == b"OK" and len(calls) == 3


@pytest.mark.parametrize("code,needle", [(401, "API key"), (402, "out of credits"), (400, r"failed \(400\)")])
def test_clear_errors(monkeypatch, code, needle):
    def fake_urlopen(req, timeout):
        raise http_error(code, b'{"err_msg":"bad"}')

    monkeypatch.setattr(tts_deepgram.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(DeepgramError, match=needle):
        synthesize("x", "flux-priya-en", "KEY")


def test_service_requires_key(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    with pytest.raises(DeepgramError, match="DEEPGRAM_API_KEY"):
        tts_deepgram.DeepgramService(cache_dir=tmp_path)


def test_service_writes_and_caches_audio(monkeypatch, tmp_path, calls):
    def fake_urlopen(req, timeout):
        calls.append(req)
        return FakeResponse(b"MP3DATA")

    monkeypatch.setattr(tts_deepgram.urllib.request, "urlopen", fake_urlopen)
    svc = tts_deepgram.DeepgramService(voice="flux-meena-en", api_key="KEY", cache_dir=tmp_path)
    result = svc.generate_from_text("Two smaller areas.")
    assert (tmp_path / result["original_audio"]).read_bytes() == b"MP3DATA"
    assert result["input_data"]["voice"] == "flux-meena-en"

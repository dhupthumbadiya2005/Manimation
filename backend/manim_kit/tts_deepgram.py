"""Deepgram Flux TTS for manim-voiceover.

Voice is a Flux model string, e.g. ``flux-priya-en`` (Indian English, female).
Catalog: https://developers.deepgram.com/docs/flux-tts/voices

Consistent tone across a video
------------------------------
Each separate request starts the voice "fresh", so lines synthesized one by one
drift slightly in tone. Flux keeps its prosody across turns *within one
WebSocket connection*, so the pipeline synthesizes every line of a video in a
single session (``synthesize_session``), one turn per line, and stores the
audio in a *narration bank* (a folder of WAVs + ``manifest.json``). Renders
get the bank via ``MANIMATION_NARRATION_BANK`` and ``DeepgramService`` serves
lines from it. A line missing from the bank falls back to one REST request.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path

from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService, initialize_speech_service, path_to_string

SPEAK_URL = "https://api.deepgram.com/v2/speak"
SPEAK_WS_URL = "wss://api.deepgram.com/v2/speak"
DEFAULT_VOICE = "flux-priya-en"
SAMPLE_RATE = 24000
RETRYABLE = {429, 500, 502, 503, 504}


class DeepgramError(RuntimeError):
    pass


# ---- one line, REST (fallback) ---------------------------------------------------

def synthesize(text: str, voice: str, api_key: str, *, retries: int = 3, timeout: float = 60) -> bytes:
    """Return MP3 bytes for ``text`` spoken by ``voice`` (independent request)."""
    url = f"{SPEAK_URL}?{urllib.parse.urlencode({'model': voice, 'encoding': 'mp3'})}"
    body = json.dumps({"text": text}).encode()
    headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")[:300]
            if err.code in RETRYABLE and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            if err.code in (401, 403):
                raise DeepgramError(f"Deepgram rejected the API key ({err.code}). Check DEEPGRAM_API_KEY.") from err
            if err.code == 402:
                raise DeepgramError("Deepgram account is out of credits (402).") from err
            raise DeepgramError(f"Deepgram TTS failed ({err.code}): {detail}") from err
        except urllib.error.URLError as err:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise DeepgramError(f"Could not reach Deepgram: {err.reason}") from err
    raise AssertionError("unreachable")


# ---- whole video, one WebSocket session -----------------------------------------------

def synthesize_session(texts: list[str], voice: str, api_key: str, *, timeout: float = 60,
                       connect=None) -> list[bytes]:
    """Speak ``texts`` as consecutive turns of ONE session so the voice keeps the
    same tone throughout. Returns raw 16-bit mono PCM (``SAMPLE_RATE`` Hz) per text.

    Protocol per turn (observed): SpeechStarted -> Flushed -> binary audio ->
    SpeechMetadata. A turn's audio is everything received before its SpeechMetadata.
    """
    if connect is None:
        from websockets.sync.client import connect
    from websockets.exceptions import InvalidStatus

    query = urllib.parse.urlencode({"model": voice, "encoding": "linear16", "sample_rate": SAMPLE_RATE})
    try:
        ws = connect(f"{SPEAK_WS_URL}?{query}", additional_headers={"Authorization": f"Token {api_key}"},
                     max_size=None, open_timeout=timeout)
    except InvalidStatus as err:
        code = err.response.status_code
        if code in (401, 403):
            raise DeepgramError(f"Deepgram rejected the API key ({code}). Check DEEPGRAM_API_KEY.") from err
        if code == 402:
            raise DeepgramError("Deepgram account is out of credits (402).") from err
        raise DeepgramError(f"Deepgram session failed to open ({code}).") from err
    except OSError as err:
        raise DeepgramError(f"Could not reach Deepgram: {err}") from err

    clips: list[bytes] = []
    with ws:
        # Queue every turn up front; the server streams them back in order.
        for text in texts:
            ws.send(json.dumps({"type": "Speak", "text": text}))
            ws.send(json.dumps({"type": "Flush"}))
        current = bytearray()
        while len(clips) < len(texts):
            try:
                message = ws.recv(timeout=timeout)
            except TimeoutError as err:
                raise DeepgramError(f"Deepgram stopped responding after {len(clips)}/{len(texts)} lines.") from err
            if isinstance(message, bytes):
                current.extend(message)
                continue
            event = json.loads(message)
            if event.get("type") == "SpeechMetadata":
                clips.append(bytes(current))
                current = bytearray()
            elif event.get("type") == "Error":
                raise DeepgramError(f"Deepgram error: {event}")
        ws.send(json.dumps({"type": "Close"}))
    return clips


def write_wav(pcm: bytes, path: Path) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)


def build_bank(texts: list[str], voice: str, api_key: str, out_dir: Path, **kwargs) -> Path:
    """Synthesize ``texts`` in one session into ``out_dir``; returns the manifest path."""
    unique = list(dict.fromkeys(texts))
    clips = synthesize_session(unique, voice, api_key, **kwargs)
    out_dir.mkdir(parents=True, exist_ok=True)
    items = {}
    for i, (text, pcm) in enumerate(zip(unique, clips), start=1):
        name = f"{i:03d}.wav"
        write_wav(pcm, out_dir / name)
        items[text] = name
    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps({"voice": voice, "bank": out_dir.name, "items": items}, indent=1))
    return manifest


def _load_bank(voice: str) -> tuple[Path, dict] | None:
    path = os.environ.get("MANIMATION_NARRATION_BANK")
    if not path or not Path(path).exists():
        return None
    manifest = json.loads(Path(path).read_text())
    return (Path(path).parent, manifest) if manifest.get("voice") == voice else None


# ---- manim-voiceover service ------------------------------------------------------------

class DeepgramService(SpeechService):
    def __init__(self, voice: str = DEFAULT_VOICE, api_key: str | None = None, **kwargs: object) -> None:
        initialize_speech_service(self, kwargs)
        self.voice = voice
        self.api_key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self.bank = _load_bank(voice)
        if not self.api_key and self.bank is None:
            raise DeepgramError("DEEPGRAM_API_KEY is not set.")

    def generate_from_text(self, text: str, cache_dir=None, path=None, **kwargs: object):
        if cache_dir is None:
            cache_dir = self.cache_dir
        input_text = remove_bookmarks(text)
        input_data = {"input_text": input_text, "service": "deepgram", "voice": self.voice}

        bank_file = None
        if self.bank is not None:
            bank_dir, manifest = self.bank
            if input_text in manifest["items"]:
                bank_file = bank_dir / manifest["items"][input_text]
                input_data["bank"] = manifest["bank"]   # a new bank never reuses old cached audio

        cached = self.get_cached_result(input_data, cache_dir)
        if cached is not None:
            return cached

        if bank_file is not None:
            audio_path = self.get_audio_basename(input_data) + ".wav" if path is None else path_to_string(path)
            shutil.copyfile(bank_file, Path(cache_dir) / audio_path)
        else:
            if not self.api_key:
                raise DeepgramError("Line not in the narration bank and DEEPGRAM_API_KEY is not set.")
            audio_path = self.get_audio_basename(input_data) + ".mp3" if path is None else path_to_string(path)
            (Path(cache_dir) / audio_path).write_bytes(synthesize(input_text, self.voice, self.api_key))
        return {"input_text": text, "input_data": input_data, "original_audio": audio_path}

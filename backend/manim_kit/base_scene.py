"""Base scene every generated scene subclasses.

- applies the active theme (background + default text colors)
- records layout after every animation (see ``layout_log``)
- exposes ``with self.voiceover(text=...) as tracker:`` in every mode:
  * ``MANIMATION_TTS=deepgram`` -> narration with Deepgram Flux TTS; voice from
    ``MANIMATION_TTS_VOICE`` (default ``flux-priya-en``, Indian English female)
  * ``MANIMATION_TTS=gtts``  -> real narration via manim-voiceover + Google TTS
  * ``MANIMATION_TTS=silent`` (default) -> no audio; duration estimated from word
    count, so previews keep realistic pacing and render offline
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from manim import MathTex, Scene, Tex, Text, MarkupText, config

from .layout_log import snapshot_scene, write_log
from .theme import load_active_theme

T = load_active_theme()

config.background_color = T.background
for _cls in (Text, MarkupText, MathTex, Tex):
    _cls.set_default(color=T.text)
if T.text_font:
    Text.set_default(font=T.text_font)
    MarkupText.set_default(font=T.text_font)

TTS_MODE = os.environ.get("MANIMATION_TTS", "silent")
WORDS_PER_SECOND = 2.5

_VoiceoverBase: type = Scene
if TTS_MODE != "silent":
    from manim_voiceover import VoiceoverScene as _VoiceoverBase  # noqa: F811


def estimate_speech_seconds(text: str) -> float:
    return max(1.0, len(text.split()) / WORDS_PER_SECOND)


class _SilentTracker:
    """Mirrors the parts of manim-voiceover's VoiceoverTracker that scenes use."""

    def __init__(self, scene: Scene, text: str):
        self.scene = scene
        self.text = text
        self.duration = estimate_speech_seconds(text)
        self.start_t = scene.renderer.time

    @property
    def end_t(self) -> float:
        return self.start_t + self.duration

    def get_remaining_duration(self, buff: float = 0.0) -> float:
        return max(self.end_t - self.scene.renderer.time + buff, 0.0)


class ThemedScene(Scene):
    """Themed scene without narration."""

    def setup(self):
        super().setup()
        self.camera.background_color = T.background
        self._layout_snapshots: list[dict] = []

    def play(self, *args, **kwargs):
        super().play(*args, **kwargs)
        self._layout_snapshots.append(snapshot_scene(self, len(self._layout_snapshots)))

    def tear_down(self):
        path = os.environ.get("MANIMATION_LAYOUT_LOG")
        if path:
            write_log(path, self._layout_snapshots)
        super().tear_down()


class ThemedVoiceoverScene(ThemedScene, _VoiceoverBase):
    """Themed scene with narration. Generated code should always use this."""

    def setup(self):
        super().setup()
        if TTS_MODE == "deepgram":
            from .tts_deepgram import DEFAULT_VOICE, DeepgramService
            self.set_speech_service(DeepgramService(voice=os.environ.get("MANIMATION_TTS_VOICE") or DEFAULT_VOICE))
        elif TTS_MODE == "gtts":
            from manim_voiceover.services.gtts import GTTSService
            self.set_speech_service(GTTSService(lang="en", tld="com"))
        elif TTS_MODE != "silent":
            raise ValueError(f"Unknown MANIMATION_TTS mode {TTS_MODE!r}")

    if TTS_MODE == "silent":
        @contextmanager
        def voiceover(self, text: str = "", **kwargs):
            tracker = _SilentTracker(self, text)
            yield tracker
            remaining = tracker.get_remaining_duration()
            if remaining > 0:
                self.wait(remaining)

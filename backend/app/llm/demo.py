"""Demo mode (``MANIMATION_DEMO=1``): a stand-in for Claude that answers from the
tested cookbook. Every pipeline step, the API and the UI then work end to end
with no API calls and no cost — for development, tests and offline demos.

- Director: picks the cookbook scenes that best match the request and turns
  their narration into a storyboard.
- Coder: returns the chosen cookbook file with the class renamed.
- Fixer: cannot edit code; it says so and the pipeline keeps the scene as is.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from app.llm.budget import Budget
from app.pipeline import knowledge
from app.schemas.storyboard import Beat, ScenePlan, Storyboard, SymbolColor

DEMO_TAG = "demo:"
NARRATION = re.compile(r'voiceover\(text="([^"]+)"\)')
WORD = re.compile(r"[a-z]+")
DEMO_MODEL = "demo (no API call)"


def _response(text: str = "", content: list | None = None) -> SimpleNamespace:
    blocks = content if content is not None else [SimpleNamespace(type="text", text=text)]
    usage = SimpleNamespace(input_tokens=0, output_tokens=0, cache_read_input_tokens=0,
                            cache_creation_input_tokens=0)
    return SimpleNamespace(content=blocks, stop_reason="end_turn", model=DEMO_MODEL, usage=usage)


STOPWORDS = {"show", "shown", "explain", "with", "that", "this", "from", "into", "what", "when",
              "where", "which", "using", "visual", "visually", "video", "about", "their", "then"}


def _words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if len(w) > 2 and w not in STOPWORDS}


def _score(request: str, snippet: knowledge.Snippet) -> int:
    haystack = _words(" ".join([snippet.name, snippet.summary, *snippet.techniques]))
    return len(_words(request) & haystack)


class DemoLLM:
    def __init__(self, budget: Budget, log: Callable[[str], None] = print):
        self.budget = budget
        self.log = log

    def _note(self, agent: str) -> None:
        self.log(f"  [{agent}] demo mode: answered from the cookbook, no API call ($0)")

    def structured(self, agent: str, system: str, user: str, output_format: type) -> Any:
        assert output_format is Storyboard, "demo mode only plans storyboards"
        self._note(agent)
        request = re.search(r"Request: (.*)", user).group(1)
        max_scenes = int(re.search(r"Maximum scenes: (\d+)", user).group(1))
        ranked = sorted(knowledge.cookbook(), key=lambda s: (-_score(request, s), s.name))
        scenes = []
        for snippet in ranked[:max_scenes]:
            beats = [Beat(narration=n, visual=f"As in the tested '{snippet.name}' example.", objects=[])
                     for n in NARRATION.findall(snippet.code)]
            scenes.append(ScenePlan(id="", title=snippet.name.replace("_", " ").capitalize(),
                                    goal=snippet.summary,
                                    techniques=sorted(snippet.techniques) + [DEMO_TAG + snippet.name],
                                    beats=beats))
        return Storyboard(title=f"{request} (demo)", summary="Demo storyboard built from cookbook scenes.",
                          symbol_colors=[SymbolColor(symbol="x", role="primary")], scenes=scenes)

    def message(self, agent: str, system: str, messages: list[dict], tools: list | None = None):
        self._note(agent)
        if agent == "coder":
            user = messages[0]["content"]
            class_name = re.search(r"as class `(\w+)`", user).group(1)
            plan = json.loads(user.split("Scene plan:\n", 1)[1].split("\n\n", 1)[0])
            name = next(t[len(DEMO_TAG):] for t in plan["techniques"] if t.startswith(DEMO_TAG))
            code = next(s.code for s in knowledge.cookbook() if s.name == name)
            code = re.sub(r"class \w+\(ThemedVoiceoverScene\)", f"class {class_name}(ThemedVoiceoverScene)", code)
            return _response(f"```python\n{code}```")
        return _response("Demo mode cannot edit code; add API credits and turn demo mode off to use the fixer.")

"""Offline tests for the pipeline (no API calls, no credits)."""

import sys
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.budget import Budget, cost_of  # noqa: E402
from app.llm.errors import BudgetExceededError, CreditsExhaustedError, LLMConfigError, translate_api_error  # noqa: E402
from app.pipeline import fixer  # noqa: E402
from app.pipeline.coder import extract_code  # noqa: E402
from app.pipeline.knowledge import hints_for, select_snippets  # noqa: E402
from app.pipeline.validator import validate  # noqa: E402

GOOD = """from manim import *
from manim_kit import *

class Scene01(ThemedVoiceoverScene):
    def construct(self):
        with self.voiceover(text="Hello") as tracker:
            c = Circle(color=T.primary)
            self.play(Create(c))
"""


# ---- validator -------------------------------------------------------------

def test_validator_accepts_good_scene():
    assert validate(GOOD, "Scene01").ok


def test_validator_autofixes_manimgl_names_for_free():
    r = validate(GOOD.replace("Create(c)", "ShowCreation(c)"), "Scene01")
    assert r.ok and "Create(c)" in r.code and r.autofixes == ["line 8: ShowCreation -> Create"]


def test_validator_flags_hallucinated_names_with_suggestion():
    r = validate(GOOD.replace("Circle(", "Circel("), "Scene01")
    assert not r.ok and "did you mean Circle" in r.report()


def test_validator_blocks_dangerous_code():
    bad = "import os\n" + GOOD.replace("c = Circle", "open('x'); c = Circle")
    msgs = validate(bad, "Scene01").report()
    assert "import of 'os'" in msgs and "call to 'open'" in msgs


def test_validator_checks_class_shape():
    assert "expected a class named Scene02" in validate(GOOD, "Scene02").report()
    assert "must subclass ThemedVoiceoverScene" in validate(GOOD.replace("(ThemedVoiceoverScene)", "(Scene)"), "Scene01").report()


@pytest.mark.parametrize("path", sorted((Path(__file__).resolve().parents[1] / "knowledge" / "cookbook").glob("*.py")),
                         ids=lambda p: p.stem)
def test_validator_has_no_false_positives_on_cookbook(path):
    from scripts.render_cookbook import scene_class
    r = validate(path.read_text(), scene_class(path))
    assert r.ok and not r.autofixes, r.report()


def test_validator_flags_math_in_plain_text():
    bad = GOOD.replace("c = Circle(color=T.primary)", 'c = title_card("Why y = x^2?")')
    assert "shows literally" in validate(bad, "Scene01").report()
    ok = GOOD.replace("c = Circle(color=T.primary)", 'c = title_card("Area under a curve")')
    assert validate(ok, "Scene01").ok


def test_validator_reports_syntax_errors():
    r = validate(GOOD.replace("def construct(self):", "def construct(self)"), "Scene01")
    assert not r.ok and "SyntaxError" in r.report()


# ---- budget / errors -------------------------------------------------------

def _usage(i=1000, o=500, cr=0, cw=0):
    return SimpleNamespace(input_tokens=i, output_tokens=o, cache_read_input_tokens=cr, cache_creation_input_tokens=cw)


def test_cost_math():
    assert cost_of("claude-sonnet-5-5", 1_000_000, 0) == pytest.approx(2.0)
    assert cost_of("claude-sonnet-5-5", 0, 1_000_000) == pytest.approx(10.0)
    assert cost_of("claude-sonnet-5-5", 0, 0, cache_read=1_000_000) == pytest.approx(0.2)


def test_budget_persists_and_stops(tmp_path):
    ledger = tmp_path / "usage.jsonl"
    b = Budget(0.05, ledger)
    b.record("coder", "claude-sonnet-5-5", _usage(1000, 2000))  # $0.022
    assert Budget(0.05, ledger).spent_usd == pytest.approx(b.spent_usd)  # survives restart
    with pytest.raises(BudgetExceededError):
        b.check("fixer")  # remaining 0.028 < reserve 0.03


def _api_error(cls, status, err_type, message):
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    body = {"type": "error", "error": {"type": err_type, "message": message}}
    return cls(message, response=httpx2.Response(status, request=req, json=body), body=body)


def test_credit_errors_become_credits_exhausted():
    e402 = _api_error(anthropic.APIStatusError, 402, "billing_error", "billing problem")
    e400 = _api_error(anthropic.BadRequestError, 400, "invalid_request_error",
                      "Your credit balance is too low to access the Anthropic API.")
    for e in (e402, e400):
        out = translate_api_error(e)
        assert isinstance(out, CreditsExhaustedError) and "--resume" in out.user_message


def test_other_errors_are_mapped_or_passed_through():
    ws = _api_error(anthropic.BadRequestError, 400, "invalid_request_error", "must include the anthropic-workspace-id header")
    assert isinstance(translate_api_error(ws), LLMConfigError)
    other = _api_error(anthropic.BadRequestError, 400, "invalid_request_error", "max_tokens too large")
    assert translate_api_error(other) is other


# ---- knowledge -------------------------------------------------------------

def test_snippet_selection_and_hints():
    names = [s.name for s in select_snippets(["graph", "bfs"])]
    assert names[0] == "graph_bfs"
    assert hints_for("NameError: name 'ShowCreation' is not defined")


def test_extract_code_takes_the_code_block():
    assert extract_code("Here:\n```python\nx = 1\n```\n") == "x = 1\n"


# ---- editor tool + fix loop --------------------------------------------------

def test_editor_str_replace_and_guards(tmp_path):
    f = tmp_path / "scene_01.py"
    f.write_text(GOOD)
    ed = fixer.SceneEditor(f)
    out, err = ed.handle({"command": "str_replace", "path": "scene_01.py", "old_str": "Circle(", "new_str": "Square("})
    assert not err and "Square(" in f.read_text() and "Region now" in out
    assert ed.handle({"command": "create", "path": "scene_01.py", "file_text": "x"})[1]  # rewrite refused
    assert ed.handle({"command": "view", "path": "../etc/passwd"})[1]                    # path confined
    assert ed.handle({"command": "view", "path": "other.py"})[1]
    _, err = ed.handle({"command": "str_replace", "path": "scene_01.py", "old_str": "nope", "new_str": "x"})
    assert err
    _, err = ed.handle({"command": "insert", "path": "scene_01.py", "insert_line": 2, "insert_text": "import math"})
    assert not err and f.read_text().splitlines()[2] == "import math"
    assert ed.edits == 2


def _block(**kw):
    return SimpleNamespace(**kw)


class ScriptedLLM:
    """Plays back canned responses; records how many calls were made."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def message(self, agent, system, messages, tools=None):
        self.calls += 1
        content = self.responses.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return SimpleNamespace(content=content, stop_reason=stop)


def test_fix_loop_edits_in_place_and_stops_when_clean(tmp_path):
    f = tmp_path / "scene_01.py"
    broken = GOOD.replace("Circle(", "Circel(")
    f.write_text(broken)

    def check():
        clean = "Circel(" not in f.read_text()
        return fixer.Check(clean, clean, "OK" if clean else "name 'Circel' is not defined")

    llm = ScriptedLLM([[
        _block(type="tool_use", id="t1", name="str_replace_based_edit_tool",
               input={"command": "str_replace", "path": "scene_01.py", "old_str": "Circel(", "new_str": "Circle("}),
        _block(type="tool_use", id="t2", name="render_scene", input={}),
    ]])
    out = fixer.fix_scene(llm, f, "Scene01", check, check(), max_turns=5, log=lambda *_: None)
    assert out.clean and out.turns == 1 and out.edits == 1
    assert llm.calls == 1                      # no extra "are you done?" call after a clean render
    assert f.read_text() == GOOD               # only the broken token changed


def test_fix_loop_verifies_claims_of_success(tmp_path):
    f = tmp_path / "scene_01.py"
    f.write_text(GOOD.replace("Circle(", "Circel("))

    def check():
        clean = "Circel(" not in f.read_text()
        return fixer.Check(clean, clean, "OK" if clean else "still broken")

    llm = ScriptedLLM([
        [_block(type="text", text="Fixed it!")],  # claims success without editing
        [_block(type="tool_use", id="t1", name="str_replace_based_edit_tool",
                input={"command": "str_replace", "path": "scene_01.py", "old_str": "Circel(", "new_str": "Circle("})],
        [_block(type="text", text="Done.")],
    ])
    out = fixer.fix_scene(llm, f, "Scene01", check, check(), max_turns=5, log=lambda *_: None)
    assert out.clean and llm.calls == 3


def test_fix_loop_gives_up_after_max_turns(tmp_path):
    f = tmp_path / "scene_01.py"
    f.write_text(GOOD)
    llm = ScriptedLLM([[_block(type="text", text="hmm")]] * 3)
    out = fixer.fix_scene(llm, f, "Scene01", lambda: fixer.Check(False, False, "broken"),
                          fixer.Check(False, False, "broken"), max_turns=3, log=lambda *_: None)
    assert not out.clean and llm.calls == 3

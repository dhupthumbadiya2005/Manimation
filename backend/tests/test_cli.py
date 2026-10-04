"""The CLI must stop cleanly with a clear message when credits or budget run out."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import cli, config  # noqa: E402
from app.llm.errors import CREDITS_MESSAGE, CreditsExhaustedError  # noqa: E402
from app.pipeline import orchestrator  # noqa: E402


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "settings", config.Settings(data_dir=tmp_path))
    return tmp_path


def test_credits_exhausted_shows_message_and_resume_path(data_dir, monkeypatch, capsys):
    def boom(project, **kw):
        raise CreditsExhaustedError(CREDITS_MESSAGE)

    monkeypatch.setattr(orchestrator, "run", boom)
    code = cli.main(["Explain the unit circle"])
    err = capsys.readouterr().err
    assert code == 2
    assert "CREDITS EXHAUSTED" in err and "console.anthropic.com/settings/billing" in err
    assert "--resume" in err and str(data_dir) in err


def test_tiny_budget_stops_before_any_api_call(data_dir, capsys):
    code = cli.main(["Explain the unit circle", "--budget", "0.01"])
    err = capsys.readouterr().err
    assert code == 2 and "budget" in err and "Director" not in err.split("STOPPED")[0]


def test_budget_is_remembered_on_resume(data_dir):
    p = orchestrator.open_project(request="x", budget_usd=0.3, log=lambda *_: None)
    assert orchestrator.open_project(resume=p.root, log=lambda *_: None).state.budget_usd == 0.3
    assert orchestrator.open_project(resume=p.root, budget_usd=1.0, log=lambda *_: None).state.budget_usd == 1.0

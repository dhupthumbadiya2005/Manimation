"""API tests in demo mode: real jobs and renders, no Claude API calls."""

import dataclasses
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.llm.errors import CREDITS_MESSAGE, CreditsExhaustedError  # noqa: E402
from app.main import create_app  # noqa: E402
from app.pipeline import orchestrator  # noqa: E402
from app.pipeline.project import Project  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "settings", dataclasses.replace(
        config.settings, data_dir=tmp_path, demo_mode=True, tts="silent"))
    with TestClient(create_app()) as c:
        yield c


def wait_for(client, pid, phases, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        view = client.get(f"/api/projects/{pid}").json()
        if view["phase"] in phases and not view["busy"]:
            return view
        time.sleep(0.3)
    raise AssertionError(f"timed out waiting for {phases}; last phase {view['phase']}")


def create(client, request="Binary search on a sorted array"):
    r = client.post("/api/projects", json={"request": request, "max_scenes": 1, "budget_usd": 0.5})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_and_themes(client):
    assert client.get("/api/health").json()["demo_mode"] is True
    ids = [t["id"] for t in client.get("/api/themes").json()]
    assert ids[0] == "3b1b" and "chalkboard" in ids


@pytest.mark.render
def test_full_flow_plan_edit_generate_revise(client):
    pid = create(client)["id"]
    view = wait_for(client, pid, ["awaiting_approval"])
    board = view["storyboard"]
    assert board and board["scenes"][0]["id"] == "scene_01"

    board["scenes"][0]["beats"][0]["narration"] = "Edited by the user."
    r = client.put(f"/api/projects/{pid}/storyboard", json=board)
    assert r.status_code == 200
    assert r.json()["storyboard"]["scenes"][0]["beats"][0]["narration"] == "Edited by the user."

    assert client.post(f"/api/projects/{pid}/generate", json={"final_quality": "low"}).status_code == 200
    view = wait_for(client, pid, ["done", "failed", "stopped"])
    assert view["phase"] == "done", view["error"]
    scene = view["scenes"][0]
    assert scene["status"] == "passed" and scene["preview_url"] and scene["has_code"]
    assert view["final_url"]
    video = client.get(view["final_url"])
    assert video.status_code == 200 and len(video.content) > 10_000
    assert "class Scene01(ThemedVoiceoverScene)" in client.get(f"/api/projects/{pid}/scenes/scene_01/code").text

    # once coded, the storyboard is frozen; changes go through per-scene revisions
    assert client.put(f"/api/projects/{pid}/storyboard", json=board).status_code == 409
    r = client.post(f"/api/projects/{pid}/scenes/scene_01/revise", json={"feedback": "make it blue", "final_quality": "low"})
    assert r.status_code == 200
    view = wait_for(client, pid, ["done", "failed", "stopped"])
    assert view["phase"] == "done" and view["scenes"][0]["status"] == "passed"

    with client.websocket_connect(f"/api/projects/{pid}/events") as ws:
        first = ws.receive_json()
    lines = [e.get("line", "") for e in first["events"] if e["type"] == "log"]
    assert first["type"] == "history" and any("Final video" in line for line in lines)

    assert [p["id"] for p in client.get("/api/projects").json()] == [pid]


def test_unknown_and_malicious_ids_404(client):
    assert client.get("/api/projects/nope").status_code == 404
    assert client.get("/api/projects/..%2F..%2Fetc").status_code == 404
    pid = create(client)["id"]
    wait_for(client, pid, ["awaiting_approval"])
    assert client.get(f"/api/projects/{pid}/scenes/../../state/code").status_code == 404


def test_credits_exhausted_stops_with_code_and_resume_continues(client, monkeypatch):
    pid = create(client)["id"]
    wait_for(client, pid, ["awaiting_approval"])

    def no_credits(project, **kw):
        raise CreditsExhaustedError(CREDITS_MESSAGE)

    monkeypatch.setattr(orchestrator, "build", no_credits)
    client.post(f"/api/projects/{pid}/generate", json={"final_quality": "low"})
    view = wait_for(client, pid, ["stopped"])
    assert view["error"]["code"] == "credits_exhausted" and "billing" in view["error"]["message"]

    calls = []
    monkeypatch.setattr(orchestrator, "build", lambda project, **kw: calls.append(kw))
    r = client.post(f"/api/projects/{pid}/resume", json={"budget_usd": 1.25, "final_quality": "low"})
    assert r.status_code == 200
    view = wait_for(client, pid, ["done"])
    assert calls and view["budget"]["limit_usd"] == 1.25 and view["error"] is None


def test_busy_project_rejects_second_job(client, monkeypatch):
    pid = create(client)["id"]
    wait_for(client, pid, ["awaiting_approval"])
    monkeypatch.setattr(orchestrator, "build", lambda project, **kw: time.sleep(1.5))
    assert client.post(f"/api/projects/{pid}/generate", json={}).status_code == 200
    assert client.post(f"/api/projects/{pid}/generate", json={}).status_code == 409
    wait_for(client, pid, ["done"])


def test_restart_mid_job_shows_interrupted(client):
    pid = create(client)["id"]
    wait_for(client, pid, ["awaiting_approval"])
    project = Project.load(config.settings.data_dir / "projects" / pid)
    project.set_phase("generating")  # as if the server died mid-job
    view = client.get(f"/api/projects/{pid}").json()
    assert view["phase"] == "stopped" and view["error"]["code"] == "interrupted"

"""Background jobs. One worker thread: renders are CPU-heavy and this is a
single-user MVP, so jobs run one at a time in submission order. Swapping in a
real queue (Redis + workers) later only changes this file."""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.llm.errors import PipelineStop
from app.pipeline.project import Project

from .events import EventHub

Step = Callable[[Project, Callable[[str], None]], object]


class ProjectBusyError(Exception):
    pass


class JobRunner:
    def __init__(self, hub: EventHub):
        self.hub = hub
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="manimation-job")
        self.running: dict[str, str] = {}   # project id -> job name (queued or running)
        self._lock = threading.Lock()

    def is_busy(self, project_id: str) -> bool:
        return project_id in self.running

    def submit(self, root: Path, name: str, running_phase: str, done_phase: str, step: Step) -> None:
        with self._lock:
            if root.name in self.running:
                raise ProjectBusyError(f"'{self.running[root.name]}' is already running for this project")
            self.running[root.name] = name
        project = Project.load(root)
        project.set_phase(running_phase)
        self.hub.publish(root, {"type": "state", "phase": running_phase, "job": name})
        self.executor.submit(self._run, root, name, running_phase, done_phase, step)

    def _run(self, root: Path, name: str, running_phase: str, done_phase: str, step: Step) -> None:
        project = Project.load(root)

        def log(line: str) -> None:
            self.hub.publish(root, {"type": "log", "line": line})

        try:
            step(project, log)
            project.set_phase(done_phase)
        except PipelineStop as stop:
            project.set_phase("stopped", {"code": stop.code, "message": stop.user_message})
            log(f"STOPPED: {stop.user_message}")
        except Exception as err:  # surface anything unexpected to the UI instead of dying silently
            traceback.print_exc()
            project.set_phase("failed", {"code": "error", "message": f"{type(err).__name__}: {err}"})
            log(f"FAILED: {type(err).__name__}: {err}")
        finally:
            with self._lock:
                self.running.pop(root.name, None)
            self.hub.publish(root, {"type": "state", "phase": project.state.phase, "job": None})

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

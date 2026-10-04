"""Per-project event stream: pipeline log lines and state changes.

Jobs run in a worker thread; events are appended to ``events.jsonl`` in the
project folder (so a reconnecting browser gets the history) and pushed to any
WebSocket subscribers on the server's event loop.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import defaultdict
from pathlib import Path

HISTORY_LIMIT = 400


class EventHub:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._file_lock = threading.Lock()

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def publish(self, project_root: Path, event: dict) -> None:
        """Thread-safe."""
        event = {**event, "ts": round(time.time(), 3)}
        with self._file_lock:
            with (project_root / "events.jsonl").open("a") as f:
                f.write(json.dumps(event) + "\n")
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self._fanout, project_root.name, event)

    def _fanout(self, project_id: str, event: dict) -> None:
        for queue in list(self._subscribers.get(project_id, ())):
            queue.put_nowait(event)

    def history(self, project_root: Path) -> list[dict]:
        path = project_root / "events.jsonl"
        if not path.exists():
            return []
        lines = path.read_text().splitlines()[-HISTORY_LIMIT:]
        return [json.loads(line) for line in lines if line.strip()]

    def subscribe(self, project_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[project_id].add(queue)
        return queue

    def unsubscribe(self, project_id: str, queue: asyncio.Queue) -> None:
        self._subscribers[project_id].discard(queue)

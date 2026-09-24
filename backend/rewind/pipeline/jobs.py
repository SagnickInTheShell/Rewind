"""In-process async job manager with progress fan-out to WebSocket subscribers.

Jobs run in a thread pool (the heavy numeric work releases the GIL in NumPy/OpenCV/PyTorch, and
simulations fan out to their own process pool). Progress callbacks are thread-safe; events are
delivered to asyncio subscriber queues on the server's event loop.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from rewind.schemas.run import JobStatus, ProgressEvent

log = logging.getLogger(__name__)

ProgressCb = Callable[[str, float, str], None]  # (stage, percent 0..100, message)
JobFn = Callable[[ProgressCb], str | None]  # returns result id (run_id / sim_id)


@dataclass
class _Job:
    status: JobStatus
    started: float = 0.0
    subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[ProgressEvent]]] = field(default_factory=list)
    last_event: ProgressEvent | None = None


class JobManager:
    def __init__(self, workers: int = 2) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="rewind-job")
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()

    # ---- lifecycle ------------------------------------------------------------------------
    @staticmethod
    def new_id() -> str:
        return f"job_{secrets.token_hex(6)}"

    def submit(self, kind: str, fn: JobFn, result_id: str | None = None, job_id: str | None = None) -> str:
        job_id = job_id or self.new_id()
        st = JobStatus(job_id=job_id, kind=kind, state="QUEUED", stage="queued", percent=0.0,
                       message="Queued", result_id=result_id)
        with self._lock:
            self._jobs[job_id] = _Job(status=st)
        self._pool.submit(self._run, job_id, fn)
        return job_id

    def _run(self, job_id: str, fn: JobFn) -> None:
        job = self._jobs[job_id]
        job.started = time.perf_counter()
        self._update(job_id, state="RUNNING", stage="starting", percent=0.0, message="Starting")

        def progress(stage: str, percent: float, message: str) -> None:
            self._update(job_id, stage=stage, percent=float(min(max(percent, 0.0), 100.0)), message=message)

        try:
            result = fn(progress)
            self._update(job_id, state="DONE", stage="done", percent=100.0, message="Done", eta_s=0.0,
                         result_id=result or job.status.result_id)
            self._publish(job_id, ProgressEvent(stage="done", percent=100.0, message="Done", eta_s=0.0, done=True))
        except Exception as exc:
            log.exception("job failed", extra={"kv": {"job": job_id}})
            self._update(job_id, state="FAILED", message=str(exc), error=str(exc))
            self._publish(job_id, ProgressEvent(stage=job.status.stage, percent=job.status.percent,
                                                message=str(exc), error=str(exc)))

    def _update(self, job_id: str, **changes: Any) -> None:
        job = self._jobs[job_id]
        with self._lock:
            st = job.status.model_copy(update=changes)
            if st.state == "RUNNING" and 0 < st.percent < 100:
                elapsed = time.perf_counter() - job.started
                st.eta_s = round(elapsed * (100.0 - st.percent) / st.percent, 1)
            job.status = st
        if st.state == "RUNNING":
            self._publish(job_id, ProgressEvent(stage=st.stage, percent=st.percent, message=st.message,
                                                eta_s=st.eta_s))

    def _publish(self, job_id: str, ev: ProgressEvent) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            return
        job.last_event = ev
        for loop, q in list(job.subscribers):
            try:
                loop.call_soon_threadsafe(q.put_nowait, ev)
            except RuntimeError:  # loop closed
                job.subscribers.remove((loop, q))

    # ---- queries ------------------------------------------------------------------------------
    def get(self, job_id: str) -> JobStatus | None:
        job = self._jobs.get(job_id)
        return job.status if job else None

    def subscribe(self, job_id: str) -> asyncio.Queue[ProgressEvent] | None:
        job = self._jobs.get(job_id)
        if job is None:
            return None
        loop = asyncio.get_running_loop()
        q: asyncio.Queue[ProgressEvent] = asyncio.Queue()
        job.subscribers.append((loop, q))
        # replay current state so late subscribers see where the job is
        st = job.status
        if st.state == "DONE":
            q.put_nowait(ProgressEvent(stage="done", percent=100.0, message="Done", eta_s=0.0, done=True))
        elif st.state == "FAILED":
            q.put_nowait(ProgressEvent(stage=st.stage, percent=st.percent, message=st.message, error=st.error))
        else:
            q.put_nowait(ProgressEvent(stage=st.stage, percent=st.percent, message=st.message, eta_s=st.eta_s))
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue[ProgressEvent]) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.subscribers = [(lp, qq) for lp, qq in job.subscribers if qq is not q]

    def wait(self, job_id: str, timeout: float = 600.0) -> JobStatus:
        """Blocking wait (tests / scripts)."""
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < timeout:
            st = self.get(job_id)
            if st and st.state in ("DONE", "FAILED", "INCOMPLETE"):
                return st
            time.sleep(0.05)
        raise TimeoutError(job_id)


_MANAGER: JobManager | None = None


def get_jobs() -> JobManager:
    global _MANAGER
    if _MANAGER is None:
        from rewind.settings import get_settings

        _MANAGER = JobManager(get_settings().app.job_workers)
    return _MANAGER

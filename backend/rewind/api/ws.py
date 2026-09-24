"""WebSocket progress stream: ``/ws/jobs/{job_id}``."""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from rewind.pipeline.jobs import get_jobs

router = APIRouter()


@router.websocket("/ws/jobs/{job_id}")
async def job_progress(ws: WebSocket, job_id: str) -> None:
    await ws.accept()
    jobs = get_jobs()
    q = jobs.subscribe(job_id)
    if q is None:
        await ws.send_json({"stage": "error", "percent": 0, "message": "unknown job", "error": "unknown job",
                            "done": False, "eta_s": None})
        await ws.close()
        return
    try:
        while True:
            try:
                ev = await asyncio.wait_for(q.get(), timeout=15.0)
            except TimeoutError:
                await ws.send_json({"stage": "heartbeat", "percent": -1, "message": "", "eta_s": None,
                                    "done": False, "error": None})
                continue
            await ws.send_json(ev.model_dump())
            if ev.done or ev.error:
                break
    except WebSocketDisconnect:
        pass
    finally:
        jobs.unsubscribe(job_id, q)
    with contextlib.suppress(RuntimeError):
        await ws.close()

"""
Boostly API Support Engineer — Paperclip Agent
------------------------------------------------
Paperclip expects:
  GET  /heartbeat  → {"status": "ok"}
  POST /run        → kicks off a full QA run, returns structured report

Payload for /run:
{
  "site_url":    "https://blackhillsbungalows.com",
  "login_url":   "/boostly",          # or "/wp-admin" — defaults to "/boostly"
  "wp_username": "admin",
  "wp_password": "secret"
}
"""

import asyncio
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import logging

from orchestrator import run_full_qa

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("Boostly-API-Support-Engineer")

app = FastAPI(title="Boostly API Support Engineer")

# ── Active run state (one run at a time, matching extension behaviour) ─────────
_run_state = {"running": False, "last_report": None}


class RunPayload(BaseModel):
    site_url: str
    login_url: Optional[str] = "/boostly"
    wp_username: str
    wp_password: str


# ── Paperclip heartbeat ────────────────────────────────────────────────────────
@app.get("/heartbeat")
async def heartbeat():
    return {"status": "ok", "agent": "Boostly API Support Engineer", "running": _run_state["running"]}


# ── Run endpoint ───────────────────────────────────────────────────────────────
@app.post("/run")
async def run(payload: RunPayload, background_tasks: BackgroundTasks):
    if _run_state["running"]:
        return JSONResponse(status_code=409, content={"error": "A run is already in progress"})

    _run_state["running"] = True
    _run_state["last_report"] = None

    background_tasks.add_task(_execute_run, payload)
    return {"status": "started", "site": payload.site_url}


@app.get("/report")
async def get_report():
    if _run_state["running"]:
        return {"status": "running"}
    if _run_state["last_report"] is None:
        return {"status": "idle"}
    return _run_state["last_report"]


async def _execute_run(payload: RunPayload):
    try:
        report = await run_full_qa(
            site_url=payload.site_url.rstrip("/"),
            login_url=payload.login_url or "/boostly",
            wp_username=payload.wp_username,
            wp_password=payload.wp_password,
        )
        _run_state["last_report"] = report
    except Exception as e:
        log.error(f"Run failed: {e}", exc_info=True)
        _run_state["last_report"] = {"error": str(e)}
    finally:
        _run_state["running"] = False


if __name__ == "__main__":
    uvicorn.run("agent:app", host="0.0.0.0", port=8000, reload=False)

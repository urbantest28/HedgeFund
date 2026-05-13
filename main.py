"""
HedgeFund Multi-Agent Analyser — FastAPI app.

Endpoints:
  GET  /                         → index.html
  POST /analyse                  → SSE stream: run full pipeline
  GET  /analyse/{run_id}/stream  → SSE stream: stream existing run events (replay from DB)
  POST /upload/{ticker}/{run_id} → upload file for paused run
  POST /resume/{run_id}          → resume paused run (SSE stream)
  GET  /runs                     → list recent runs
  GET  /runs/{run_id}            → run detail + agent outputs + debate
  GET  /watchlist                → watchlist entries
  POST /monitor                  → trigger watchlist price check manually
"""
import json
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import BASE_DIR, UPLOADS_DIR
from db.database import Database
from pipeline.orchestrator import stream_analysis, stream_resume
from pipeline.monitor import run_monitor
from reports.generator import ReportGenerator
from logger import get_logger

app = FastAPI(title="HedgeFund Analyser")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_log = get_logger("main")
_db = Database()
db = _db  # public alias used by /report endpoint (and tests that mock main.db)


# ── HTML ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Analysis ─────────────────────────────────────────────────────────────────

@app.post("/analyse")
async def analyse(request: Request):
    """
    Expects JSON body: {"ticker": "AAPL"}.
    Returns SSE stream.
    """
    body = await request.json()
    ticker = body.get("ticker", "").strip().upper()
    if not ticker:
        raise HTTPException(400, "ticker required")

    _log.info(f"Analyse request | ticker: {ticker}")

    return StreamingResponse(
        stream_analysis(ticker, _db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Resume ────────────────────────────────────────────────────────────────────

@app.post("/resume/{run_id}")
async def resume_run(run_id: int):
    run = _db.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    if run["status"] not in ("paused", "failed"):
        raise HTTPException(400, f"Run {run_id} has status '{run['status']}' — cannot resume")

    _log.info(f"Resume request | run_id: {run_id}")
    return StreamingResponse(
        stream_resume(run_id, _db),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── File upload ───────────────────────────────────────────────────────────────

@app.post("/upload/{ticker}/{run_id}")
async def upload_file(ticker: str, run_id: int, file: UploadFile = File(...)):
    """Accept file upload for a paused run. Stores in uploads/TICKER/run_{id}/."""
    run = _db.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    upload_dir = UPLOADS_DIR / ticker.upper() / f"run_{run_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    _log.info(f"File uploaded | run_id: {run_id} | file: {file.filename}")
    return JSONResponse({"status": "ok", "path": str(dest), "run_id": run_id})


# ── Runs ──────────────────────────────────────────────────────────────────────

@app.get("/runs")
async def list_runs(limit: int = 20):
    import sqlite3
    conn = _db._conn
    cur = conn.execute(
        "SELECT * FROM analysis_runs ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    return JSONResponse(rows)


@app.get("/runs/{run_id}")
async def get_run(run_id: int):
    run = _db.get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    outputs = _db.get_agent_outputs(run_id)
    debate = _db.get_debate_rounds(run_id)
    checkpoint = _db.get_checkpoint(run_id)

    # Load NEEDED.md if present
    needed_md = None
    upload_dir = UPLOADS_DIR / run["ticker"] / f"run_{run_id}"
    needed_path = upload_dir / "NEEDED.md"
    if needed_path.exists():
        needed_md = needed_path.read_text(encoding="utf-8")

    return JSONResponse({
        "run": run,
        "agent_outputs": outputs,
        "debate_rounds": debate,
        "checkpoint": checkpoint,
        "needed_md": needed_md,
    })


# ── Watchlist ─────────────────────────────────────────────────────────────────

@app.get("/watchlist")
async def get_watchlist(status: str = "watching"):
    entries = _db.get_watchlist(status=status)
    return JSONResponse(entries)


# ── Monitor ───────────────────────────────────────────────────────────────────

@app.post("/monitor")
async def trigger_monitor():
    """Manually trigger the watchlist price monitor."""
    summary = run_monitor(_db)
    return JSONResponse(summary)


# ── Report ────────────────────────────────────────────────────────────────────

@app.get("/report/{run_id}", response_class=HTMLResponse)
async def get_report(run_id: int):
    """Regenerate and return the HTML report for a completed run."""
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    run_data = {
        "run_id": run_id,
        "ticker": run["ticker"],
        "score": run.get("score"),
        "tier": run.get("tier"),
        "verdict": run.get("verdict"),
        "entry_low": run.get("entry_low"),
        "entry_high": run.get("entry_high"),
        "stop_loss": run.get("stop_loss"),
        "target_price": run.get("target_price"),
        "bundle": db.get_bundle_snapshot(run_id),
        "agent_outputs": db.get_agent_outputs(run_id),
        "debate_rounds": db.get_debate_rounds(run_id),
        "pm_output": db.get_pm_output(run_id),
        "contested": bool(run.get("contested")),
    }
    path = ReportGenerator().generate(run_data)
    return HTMLResponse(content=path.read_text(encoding="utf-8"))

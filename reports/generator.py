from datetime import datetime
from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
from config import BASE_DIR, sanitize_ticker
from logger import get_logger

log = get_logger("report")

REPORTS_DIR = BASE_DIR / "reports_output"
TEMPLATE_DIR = BASE_DIR / "reports"


def build_run_data(
    db,
    run_id: int,
    ticker: str,
    pm_raw_output: dict,
    bundle: dict,
    contested: bool = False,
    overrides: Optional[dict] = None,
) -> dict:
    """Build the run_data dict needed by ReportGenerator.generate().

    Shared between pipeline/orchestrator.py (auto-gen at end of run) and
    main.py /report/{run_id} endpoint to prevent field drift.

    `overrides` lets callers (e.g. the endpoint) replace fields with more
    authoritative values from the persisted analysis_runs table row.
    """
    pm_raw_output = pm_raw_output or {}
    data = {
        "run_id": run_id,
        "ticker": ticker,
        "score": pm_raw_output.get("score"),
        "tier": pm_raw_output.get("tier", ""),
        "verdict": pm_raw_output.get("verdict", ""),
        "entry_low": pm_raw_output.get("entry_low"),
        "entry_high": pm_raw_output.get("entry_high"),
        "stop_loss": pm_raw_output.get("stop_loss"),
        "target_price": pm_raw_output.get("target_price"),
        "bundle": bundle,
        "agent_outputs": db.get_agent_outputs(run_id),
        "debate_rounds": db.get_debate_rounds(run_id),
        "pm_output": pm_raw_output,
        "contested": contested,
    }
    if overrides:
        data.update(overrides)
    return data


class ReportGenerator:
    def __init__(self):
        REPORTS_DIR.mkdir(exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def generate(self, run_data: dict) -> Path:
        ticker = sanitize_ticker(run_data["ticker"])
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{ticker}_{date_str}.html"
        out_path = REPORTS_DIR / filename

        template = self.env.get_template("template.html")
        html = template.render(**self._build_context(run_data))

        css_path = TEMPLATE_DIR / "styles.css"
        if css_path.exists():
            css = css_path.read_text(encoding="utf-8")
            html = html.replace(
                '<link rel="stylesheet" href="styles.css">',
                f"<style>\n{css}</style>",
            )

        out_path.write_text(html, encoding="utf-8")
        log.bind_run(run_data["run_id"]).info(f"Generated {out_path}")
        return out_path

    def _build_context(self, run_data: dict) -> dict:
        return {
            "ticker": run_data["ticker"],
            "run_id": run_data["run_id"],
            "score": run_data["score"],
            "tier": run_data["tier"],
            "verdict": run_data["verdict"],
            "entry_low": run_data.get("entry_low"),
            "entry_high": run_data.get("entry_high"),
            "stop_loss": run_data.get("stop_loss"),
            "target_price": run_data.get("target_price"),
            "bundle": run_data["bundle"],
            "agent_outputs": run_data["agent_outputs"],
            "debate_rounds": run_data["debate_rounds"],
            "pm_output": run_data["pm_output"],
            "contested": run_data.get("contested", False),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }

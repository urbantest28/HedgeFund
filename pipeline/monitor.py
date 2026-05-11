"""
Daily watchlist price monitor.

Run via Windows Task Scheduler:
    python -m pipeline.monitor

Checks every 'watching' watchlist entry against live price.
Sends ntfy.sh alert if entry zone, stop-loss, or target is hit.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import yfinance as yf
from datetime import datetime
from typing import Optional

from config import NTFY_TOPIC
from db.database import Database
from logger import get_logger

_log = get_logger("monitor")


def _fetch_live_price(ticker: str) -> Optional[float]:
    try:
        info = yf.Ticker(ticker).fast_info
        price = getattr(info, "last_price", None)
        if price:
            return float(price)
        # fallback: 1-day history
        hist = yf.download(ticker, period="1d", interval="1m", progress=False)
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        _log.warning(f"Price fetch failed for {ticker}: {e}")
    return None


def _send_alert(ticker: str, title: str, body: str) -> None:
    if not NTFY_TOPIC:
        _log.warning(f"NTFY_TOPIC not set — alert not sent: {body}")
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={"Title": title, "Priority": "high"},
            timeout=10,
        )
        _log.info(f"Alert sent | ticker: {ticker} | {body}")
    except Exception as e:
        _log.error(f"Alert failed for {ticker}: {e}")


def run_monitor(db: Optional[Database] = None) -> dict:
    """
    Check all 'watching' watchlist entries.
    Returns summary: {checked, alerted, errors}.
    """
    if db is None:
        db = Database()

    entries = db.get_watchlist(status="watching")
    _log.info(f"Monitor started | entries: {len(entries)}")

    checked = 0
    alerted = 0
    errors = 0

    for entry in entries:
        ticker = entry["ticker"]
        wid = entry["id"]
        price = _fetch_live_price(ticker)

        if price is None:
            _log.warning(f"Could not fetch price for {ticker}")
            errors += 1
            continue

        checked += 1
        entry_low = entry.get("entry_low") or 0
        entry_high = entry.get("entry_high") or 0
        stop_loss = entry.get("stop_loss") or 0
        target_price = entry.get("target_price") or 0
        alert_sent = entry.get("alert_sent", 0)

        # Skip if alert already sent (prevents repeated daily alerts for same condition)
        if alert_sent:
            continue

        alert_body = None
        alert_title = f"HedgeFund Alert — {ticker}"

        if stop_loss and price <= stop_loss:
            alert_body = (
                f"STOP-LOSS HIT — Current: ${price:.2f} | "
                f"Stop: ${stop_loss:.2f} | Entry: ${entry_low:.2f}–${entry_high:.2f} | "
                f"Target: ${target_price:.2f}"
            )
        elif entry_low and entry_high and entry_low <= price <= entry_high:
            alert_body = (
                f"Entry zone hit — Current: ${price:.2f} | "
                f"Zone: ${entry_low:.2f}–${entry_high:.2f} | "
                f"Stop: ${stop_loss:.2f} | Target: ${target_price:.2f}"
            )
        elif target_price and price >= target_price:
            alert_body = (
                f"TARGET HIT — Current: ${price:.2f} | "
                f"Target: ${target_price:.2f} | "
                f"Entry: ${entry_low:.2f}–${entry_high:.2f} | Stop: ${stop_loss:.2f}"
            )

        if alert_body:
            _send_alert(ticker, alert_title, alert_body)
            db.mark_alert_sent(wid)
            alerted += 1
            _log.info(f"Alert triggered | ticker: {ticker} | price: {price} | {alert_body[:60]}")
        else:
            _log.info(f"No trigger | ticker: {ticker} | price: {price:.2f} | "
                      f"zone: {entry_low}–{entry_high} | stop: {stop_loss} | target: {target_price}")

    summary = {"checked": checked, "alerted": alerted, "errors": errors,
               "run_at": datetime.now().isoformat()}
    _log.info(f"Monitor complete | {summary}")
    return summary


if __name__ == "__main__":
    result = run_monitor()
    print(result)

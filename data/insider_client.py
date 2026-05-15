import csv
import io
import requests
from logger import get_logger

log = get_logger("insider")

OPENINSIDER_URL = "https://openinsider.com/screener"


class InsiderClient:
    def get_transactions(self, ticker: str, days: int = 90) -> dict:
        try:
            params = {"s": ticker, "fd": days, "csv": 1}
            r = requests.get(OPENINSIDER_URL, params=params, timeout=15,
                             headers={"User-Agent": "HedgeFund Analyser"})
            if not r.ok:
                log.warning(f"InsiderClient({ticker}) HTTP {r.status_code}")
                return {"transactions": [], "source": "openinsider"}
            transactions = self._parse_csv(r.text)
            log.info(f"InsiderClient({ticker}): {len(transactions)} transactions")
            return {"transactions": transactions, "source": "openinsider"}
        except Exception as e:
            log.warning(f"InsiderClient({ticker}) failed: {e}")
            return {"transactions": [], "source": "openinsider", "error": str(e)}

    def _parse_csv(self, text: str) -> list:
        # OpenInsider CSV columns (0-indexed):
        # 0:X  1:Filing Date  2:Trade Date  3:Ticker  4:Insider Name
        # 5:Title  6:Trade Type  7:Price  8:Qty  9:Owned  10:ΔOwn  11:Value
        transactions = []
        reader = csv.reader(io.StringIO(text))
        next(reader, None)  # skip header row
        for row in reader:
            if len(row) < 12:
                continue
            try:
                trade_type_raw = row[6].strip().lower()
                transaction_type = "buy" if trade_type_raw.startswith("p") else "sell"
                price = float(row[7].replace("$", "").replace(",", "").strip() or 0)
                shares = int(row[8].replace(",", "").strip() or 0)
                value = float(row[11].replace("$", "").replace(",", "").strip() or 0)
                transactions.append({
                    "date":             row[1].strip(),
                    "officer_name":     row[4].strip(),
                    "title":            row[5].strip(),
                    "transaction_type": transaction_type,
                    "shares":           shares,
                    "price_per_share":  price,
                    "value":            value,
                })
            except (ValueError, IndexError):
                continue
        return transactions

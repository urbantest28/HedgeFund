import yfinance as yf
from typing import Any, List, Optional
from logger import get_logger

log = get_logger("yfinance")

PEER_UNIVERSE = {
    "Technology": ["AAPL","MSFT","GOOGL","META","NVDA","TSLA","AMZN","AMD","INTC","ORCL"],
    "Financial Services": ["JPM","BAC","WFC","GS","MS","C","BLK","AXP","V","MA"],
    "Healthcare": ["JNJ","UNH","PFE","ABBV","MRK","TMO","ABT","CVS","LLY","AMGN"],
    "Energy": ["XOM","CVX","COP","EOG","SLB","MPC","VLO","PSX","OXY","HAL"],
    "Consumer Cyclical": ["AMZN","TSLA","HD","NKE","MCD","SBUX","TGT","LOW","BKNG","GM"],
}


class YFinanceClient:
    def get_price(self, ticker: str) -> dict:
        try:
            t = yf.Ticker(ticker)
            price = t.fast_info.last_price
            log.info(f"get_price({ticker}) -> {price}")
            return {"price": price, "source": "yfinance"}
        except Exception as e:
            log.warning(f"get_price({ticker}) failed: {e}")
            return {"price": None, "source": "yfinance", "error": str(e)}

    def get_fundamentals(self, ticker: str) -> dict:
        try:
            info = yf.Ticker(ticker).info
            return {
                "pe_ratio":       info.get("trailingPE"),
                "price_to_book":  info.get("priceToBook"),
                "ev_ebitda":      info.get("enterpriseToEbitda"),
                "price_to_sales": info.get("priceToSalesTrailing12Months"),
                "roe":            info.get("returnOnEquity"),
                "debt_equity":    info.get("debtToEquity"),
                "revenue_growth": info.get("revenueGrowth"),
                "gross_margin":   info.get("grossMargins"),
                "market_cap":     info.get("marketCap"),
                "sector":         info.get("sector"),
                "industry":       info.get("industry"),
                "name":           info.get("shortName"),
                "short_interest": {
                    "short_float_pct": info.get("shortPercentOfFloat"),
                    "days_to_cover":   info.get("shortRatio"),
                    "shares_short":    info.get("sharesShort"),
                },
                "source":         "yfinance",
            }
        except Exception as e:
            log.warning(f"get_fundamentals({ticker}) failed: {e}")
            return {"source": "yfinance", "error": str(e),
                    "short_interest": {"short_float_pct": None,
                                       "days_to_cover": None,
                                       "shares_short": None},
                    **{k: None for k in ("pe_ratio","price_to_book","ev_ebitda",
                                         "price_to_sales","roe","debt_equity",
                                         "revenue_growth","gross_margin",
                                         "market_cap","sector","industry","name")}}

    def get_ohlcv(self, ticker: str, period: str = "1y") -> dict:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            records = hist.reset_index().to_dict("records") if not hist.empty else []
            return {"records": records, "period": period, "source": "yfinance"}
        except Exception as e:
            log.warning(f"get_ohlcv({ticker}) failed: {e}")
            return {"records": [], "source": "yfinance", "error": str(e)}

    def get_balance_sheet(self, ticker: str) -> dict:
        try:
            t = yf.Ticker(ticker)
            annual = self._df_to_records(t.balance_sheet)
            quarterly = self._df_to_records(t.quarterly_balance_sheet)
            log.info(f"get_balance_sheet({ticker}) -> {len(annual)} annual, {len(quarterly)} quarterly")
            return {"annual": annual, "quarterly": quarterly, "source": "yfinance", "rate_limited": False}
        except Exception as e:
            log.warning(f"get_balance_sheet({ticker}) failed: {e}")
            return {"annual": [], "quarterly": [], "source": "yfinance", "rate_limited": False, "error": str(e)}

    def get_cash_flow(self, ticker: str) -> dict:
        try:
            t = yf.Ticker(ticker)
            annual = self._df_to_records(t.cashflow)
            quarterly = self._df_to_records(t.quarterly_cashflow)
            log.info(f"get_cash_flow({ticker}) -> {len(annual)} annual, {len(quarterly)} quarterly")
            return {"annual": annual, "quarterly": quarterly, "source": "yfinance", "rate_limited": False}
        except Exception as e:
            log.warning(f"get_cash_flow({ticker}) failed: {e}")
            return {"annual": [], "quarterly": [], "source": "yfinance", "rate_limited": False, "error": str(e)}

    @staticmethod
    def _df_to_records(df) -> list:
        if df is None or df.empty:
            return []
        import pandas as pd
        return [
            {"date": str(col.date()), **{str(row): (None if pd.isna(val) else val)
                                         for row, val in df[col].items()}}
            for col in df.columns
        ]

    def get_sector_peers(self, ticker: str, n: int = 5) -> List[str]:
        try:
            info = yf.Ticker(ticker).info
            sector = info.get("sector", "")
            universe = PEER_UNIVERSE.get(sector, [])
            return [t for t in universe if t != ticker][:n]
        except Exception as e:
            log.warning(f"get_sector_peers({ticker}) failed: {e}")
            return []

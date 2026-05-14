import os
import requests
from typing import Any, List, Dict
from logger import get_logger

log = get_logger("sec_edgar")

EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
EDGAR_DATA   = "https://data.sec.gov"
# SEC EDGAR requires a contact in the User-Agent. Set SEC_EDGAR_CONTACT in .env
_CONTACT = os.getenv("SEC_EDGAR_CONTACT", "contact@example.com")
HEADERS = {"User-Agent": f"HedgeFund Analyser {_CONTACT}"}


class SecEdgarClient:
    def search_filings(self, ticker: str, form_type: str = "10-K",
                       start_date: str = "2020-01-01") -> dict:
        params = {"q": f'"{ticker}"', "dateRange": "custom",
                  "startdt": start_date, "forms": form_type}
        try:
            r = requests.get(EDGAR_SEARCH, params=params,
                             headers=HEADERS, timeout=15)
            if not r.ok:
                return {"filings": [], "source": "sec_edgar"}
            hits = r.json().get("hits", {}).get("hits", [])
            filings = [
                {"entity_name": h["_source"].get("entity_name"),
                 "file_date":   h["_source"].get("file_date"),
                 "period":      h["_source"].get("period_of_report"),
                 "accession":   h["_source"].get("accession_no"),
                 "cik":         h["_source"].get("entity_id"),
                 "form_type":   form_type}
                for h in hits
            ]
            log.info(f"SEC EDGAR {ticker} {form_type}: {len(filings)} filings found")
            return {"filings": filings, "source": "sec_edgar"}
        except Exception as e:
            log.warning(f"SEC EDGAR search_filings({ticker}) failed: {e}")
            return {"filings": [], "source": "sec_edgar", "error": str(e)}

    def get_filing_text(self, cik: str, accession_no: str) -> dict:
        acc_clean = accession_no.replace("-", "")
        url = f"{EDGAR_DATA}/Archives/edgar/data/{cik}/{acc_clean}/{accession_no}.txt"
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            if not r.ok:
                return {"text": None, "source": "sec_edgar"}
            return {"text": r.text[:500_000], "source": "sec_edgar", "url": url}
        except Exception as e:
            log.warning(f"SEC EDGAR get_filing_text failed: {e}")
            return {"text": None, "source": "sec_edgar", "error": str(e)}

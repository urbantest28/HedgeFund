import logging
import sys
from pathlib import Path
from typing import Optional
from config import LOGS_DIR

def get_logger(module: str, run_id: Optional[int] = None) -> logging.LoggerAdapter:
    name = f"hf.{module}"
    log = logging.getLogger(name)
    if not log.handlers:
        fmt = logging.Formatter("%(message)s")
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        log.addHandler(sh)
        log.setLevel(logging.DEBUG)
    return _RunAdapter(log, module, run_id)


class _RunAdapter(logging.LoggerAdapter):
    def __init__(self, logger: logging.Logger, module: str, run_id: Optional[int]):
        super().__init__(logger, {})
        self._module = module
        self._run_id = run_id

    def process(self, msg, kwargs):
        run_part = f"[run_{self._run_id}] " if self._run_id is not None else ""
        return f"[hf:{self._module}] {run_part}{msg}", kwargs

    def bind_run(self, run_id: int) -> "_RunAdapter":
        return _RunAdapter(self.logger, self._module, run_id)

    def to_file(self, run_id: int) -> "_RunAdapter":
        fh_name = f"file_{run_id}"
        if not any(h.name == fh_name for h in self.logger.handlers):
            log_path = LOGS_DIR / f"run_{run_id}.log"
            fh = logging.FileHandler(str(log_path), encoding="utf-8")
            fh.name = fh_name
            fh.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(fh)
        return self.bind_run(run_id)

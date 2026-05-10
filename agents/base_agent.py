import json
import re
import time
from pathlib import Path
from typing import Any, Optional

from config import BASE_DIR, ANTHROPIC_API_KEY, GOOGLE_API_KEY
from logger import get_logger

PROMPTS_DIR = BASE_DIR / "prompts"

log = get_logger("base_agent")


def _load_prompt(role_file: str, skill_files: list[str]) -> str:
    role_path = PROMPTS_DIR / "roles" / role_file
    role_text = role_path.read_text(encoding="utf-8")
    skills_text = "\n\n".join(
        (PROMPTS_DIR / "skills" / sf).read_text(encoding="utf-8")
        for sf in skill_files
    )
    return role_text + ("\n\n---\n\n" + skills_text if skills_text else "")


def _extract_json(raw: str) -> dict:
    """Strip markdown code fences and parse JSON."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    return json.loads(cleaned)


class BaseAgent:
    name: str = "base"
    phase: int = 0
    role_file: str = ""
    skill_files: list[str] = []
    provider: str = "gemini"
    model: str = "gemini-2.0-flash"

    def __init__(self):
        self._system_prompt = _load_prompt(self.role_file, self.skill_files)
        self._log = get_logger(self.name)

    def _build_user_prompt(self, bundle: dict) -> str:
        """Subclasses may override to slice relevant data from bundle."""
        import json as _json
        return f"Analyse this data bundle and respond with the required JSON:\n\n{_json.dumps(bundle, default=str)}"

    def _call_gemini(self, system: str, user: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system,
        )
        response = model.generate_content(user)
        return response.text

    def _call_claude(self, system: str, user: str) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text

    def _call_llm(self, user_prompt: str) -> str:
        if self.provider == "anthropic":
            return self._call_claude(self._system_prompt, user_prompt)
        return self._call_gemini(self._system_prompt, user_prompt)

    def run(self, bundle: dict, run_id: int) -> dict:
        agent_log = self._log.bind_run(run_id)
        t0 = time.monotonic()
        user_prompt = self._build_user_prompt(bundle)

        agent_log.info(f"LLM call started | provider: {self.provider} | model: {self.model}")
        raw_text = ""
        try:
            raw_text = self._call_llm(user_prompt)
            parsed = _extract_json(raw_text)
            duration_ms = int((time.monotonic() - t0) * 1000)
            agent_log.info(
                f"LLM call complete | score: {parsed.get('score')} "
                f"| confidence: {parsed.get('data_confidence')} "
                f"| duration: {duration_ms}ms"
            )
            return {
                "agent": self.name,
                "run_id": run_id,
                "phase": self.phase,
                "score": parsed.get("score"),
                "summary": parsed.get("summary", ""),
                "data_confidence": parsed.get("data_confidence", "partial"),
                "missing_fields": parsed.get("missing_fields", []),
                "bull_points": parsed.get("bull_points", []),
                "bear_points": parsed.get("bear_points", []),
                "raw_output": parsed.get("raw_output", {}),
                "duration_ms": duration_ms,
                "status": "complete",
            }
        except Exception as e:
            agent_log.warning(f"LLM call failed (attempt 1): {e} — retrying")
            try:
                raw_text = self._call_llm(user_prompt)
                parsed = _extract_json(raw_text)
                duration_ms = int((time.monotonic() - t0) * 1000)
                agent_log.info(f"LLM retry succeeded | duration: {duration_ms}ms")
                return {
                    "agent": self.name,
                    "run_id": run_id,
                    "phase": self.phase,
                    "score": parsed.get("score"),
                    "summary": parsed.get("summary", ""),
                    "data_confidence": parsed.get("data_confidence", "partial"),
                    "missing_fields": parsed.get("missing_fields", []),
                    "bull_points": parsed.get("bull_points", []),
                    "bear_points": parsed.get("bear_points", []),
                    "raw_output": parsed.get("raw_output", {}),
                    "duration_ms": duration_ms,
                    "status": "complete",
                }
            except Exception as e2:
                duration_ms = int((time.monotonic() - t0) * 1000)
                agent_log.error(f"LLM call failed after retry: {e2}")
                return {
                    "agent": self.name,
                    "run_id": run_id,
                    "phase": self.phase,
                    "score": None,
                    "summary": f"Agent failed: {e2}",
                    "data_confidence": "minimal",
                    "missing_fields": [],
                    "bull_points": [],
                    "bear_points": [],
                    "raw_output": {"error": str(e2), "raw_text": raw_text},
                    "duration_ms": duration_ms,
                    "status": "failed",
                }

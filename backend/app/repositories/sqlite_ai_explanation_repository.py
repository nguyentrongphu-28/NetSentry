from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3

from app.domain.entities.ai_explanation import AiExplanation, PriorityItem, RiskNote
from app.domain.interfaces.ai_explanation_repository import AiExplanationRepository


def _parse_datetime(val: str) -> datetime:
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class SqliteAiExplanationRepository(AiExplanationRepository):
    """SQLite-backed persistent store for AI explanations."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def save(self, explanation: AiExplanation) -> None:
        payload = {
            "summary": explanation.summary,
            "priorities": [
                {"rule_id": p.rule_id, "reason": p.reason}
                for p in explanation.priorities
            ],
            "risks": [
                {"rule_id": r.rule_id, "warning": r.warning}
                for r in explanation.risks
            ],
        }
        content_json = json.dumps(payload, ensure_ascii=False)

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO ai_explanations (
                    run_id, created_at, model, prompt_version, input_sha256, content_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    created_at = excluded.created_at,
                    model = excluded.model,
                    prompt_version = excluded.prompt_version,
                    input_sha256 = excluded.input_sha256,
                    content_json = excluded.content_json
                """,
                (
                    explanation.run_id,
                    explanation.created_at.isoformat(),
                    explanation.model,
                    explanation.prompt_version,
                    explanation.input_sha256,
                    content_json,
                ),
            )

    def get(self, run_id: int) -> AiExplanation | None:
        row = self._conn.execute(
            "SELECT * FROM ai_explanations WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None

        data = json.loads(row["content_json"])
        priorities = tuple(
            PriorityItem(rule_id=p["rule_id"], reason=p.get("reason", ""))
            for p in data.get("priorities", [])
        )
        risks = tuple(
            RiskNote(rule_id=r["rule_id"], warning=r.get("warning", ""))
            for r in data.get("risks", [])
        )

        return AiExplanation(
            run_id=row["run_id"],
            created_at=_parse_datetime(row["created_at"]),
            model=row["model"],
            prompt_version=row["prompt_version"],
            input_sha256=row["input_sha256"],
            summary=data.get("summary", ""),
            priorities=priorities,
            risks=risks,
            generated_by_ai=True,
        )

    def delete(self, run_id: int) -> bool:
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM ai_explanations WHERE run_id = ?",
                (run_id,),
            )
            return cur.rowcount > 0

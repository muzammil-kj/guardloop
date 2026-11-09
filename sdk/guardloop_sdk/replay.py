"""
Replay: rerun an agent on past real decisions and list what would change.

Use it before shipping a prompt or model change. It answers: "which past
decisions would come out differently if I deployed this?"

Input comes from Guardloop's decisions export (GET /exports/decisions.csv, or the
Audit page). Each row needs input_summary and output_summary.

Caution: exported inputs are already masked ([EMAIL], [PHONE]...), so an agent that
depends on the masked tokens may answer differently from production. Replay sets
built from inputs without personal data are the most reliable.
"""
import csv
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Change:
    event_id: str
    input_summary: str
    before: str
    after: str


@dataclass
class ReplayReport:
    total: int = 0
    unchanged: int = 0
    changes: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def changed(self) -> int:
        return len(self.changes)


def _normalise(text: Optional[str]) -> str:
    return " ".join((text or "").lower().split())


def default_same(before: Optional[str], after: Optional[str]) -> bool:
    """Equal after ignoring case and extra spaces. Pass your own check for free text."""
    return _normalise(before) == _normalise(after)


def load_decisions_csv(path: str, agent_name: Optional[str] = None) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows = [row for row in rows if (row.get("input_summary") or "").strip()]
    if agent_name is not None:
        rows = [row for row in rows if row.get("agent_name") == agent_name]
    return rows


def replay(rows: list[dict], agent: Callable[[str], str],
           same: Callable[[Optional[str], Optional[str]], bool] = default_same,
           limit: Optional[int] = None) -> ReplayReport:
    """Runs `agent(input_summary)` for each row and compares the answer with the stored output."""
    report = ReplayReport()
    selected = rows[:limit] if limit is not None else rows
    for row in selected:
        report.total += 1
        try:
            after = agent(row["input_summary"])
        except Exception as exc:
            report.errors.append((row.get("id"), type(exc).__name__))
            continue
        before = row.get("output_summary") or ""
        if same(before, after):
            report.unchanged += 1
        else:
            report.changes.append(Change(str(row.get("id")), row["input_summary"], before, str(after)))
    return report
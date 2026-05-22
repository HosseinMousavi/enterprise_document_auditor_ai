from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Severity = Literal["high", "medium", "low"]
Status = Literal["pending", "accepted", "rejected"]


@dataclass
class Issue:
    slide_number: int
    rule_id: str
    category: str
    severity: Severity
    title: str
    evidence: str
    recommendation: str
    confidence: float = 0.85
    status: Status = "pending"
    shape_name: str | None = None
    bbox: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SlideSummary:
    slide_number: int
    title: str
    issue_count: int
    high_count: int
    medium_count: int
    low_count: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditReport:
    file_name: str
    slide_count: int
    issues: list[Issue]
    slide_summaries: list[SlideSummary]
    annotated_notes_found: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "slide_count": self.slide_count,
            "annotated_notes_found": self.annotated_notes_found,
            "slide_summaries": [s.to_dict() for s in self.slide_summaries],
            "issues": [i.to_dict() for i in self.issues],
        }

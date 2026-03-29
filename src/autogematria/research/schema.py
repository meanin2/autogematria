"""Dataclasses for research variants, tasks, findings, and journals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResearchVariant:
    """A normalized search variant."""

    text: str
    source: str
    kind: str
    token_count: int = 1
    token_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "kind": self.kind,
            "token_count": self.token_count,
            "token_index": self.token_index,
        }


VariantCandidate = ResearchVariant


@dataclass(frozen=True)
class ResearchVariantSet:
    """Variant collection for one query."""

    query: str
    variants: list[ResearchVariant]


@dataclass(frozen=True)
class ResearchTask:
    """One bounded search action in the research queue."""

    task_id: str
    family: str
    method: str
    variant: ResearchVariant
    corpus_scope: str
    params: dict[str, Any] = field(default_factory=dict)
    analysis_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "family": self.family,
            "method": self.method,
            "variant": self.variant.to_dict(),
            "corpus_scope": self.corpus_scope,
            "params": dict(self.params),
            "analysis_method": self.analysis_method,
        }


@dataclass(frozen=True)
class ResearchFinding:
    """A structured finding ready for human review."""

    task_id: str
    query: str
    variant: ResearchVariant
    family: str
    method: str
    analysis_method: str
    corpus_scope: str
    book: str | None
    rank: int
    total_results: int
    location: dict[str, Any]
    location_end: dict[str, Any] | None
    found_text: str
    params: dict[str, Any]
    verification: dict[str, Any]
    confidence: dict[str, Any]
    task_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "query": self.query,
            "variant": self.variant.to_dict(),
            "family": self.family,
            "method": self.method,
            "analysis_method": self.analysis_method,
            "corpus_scope": self.corpus_scope,
            "book": self.book,
            "rank": self.rank,
            "total_results": self.total_results,
            "location": dict(self.location),
            "location_end": dict(self.location_end) if self.location_end else None,
            "found_text": self.found_text,
            "params": dict(self.params),
            "verification": dict(self.verification),
            "confidence": dict(self.confidence),
            "task_params": dict(self.task_params),
        }


@dataclass(frozen=True)
class JournalEvent:
    """One event in the structured research journal."""

    event: str
    task_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "task_id": self.task_id,
            "payload": dict(self.payload),
        }


@dataclass
class ResearchJournal:
    """Structured journal for a research run."""

    entries: list[JournalEvent] = field(default_factory=list)

    def add(self, event: str, *, task_id: str | None = None, **payload: Any) -> None:
        self.entries.append(JournalEvent(event=event, task_id=task_id, payload=payload))

    def to_list(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]


@dataclass(frozen=True)
class ResearchRun:
    """In-memory representation of a research run."""

    query: str
    config: dict[str, Any]
    variants: list[ResearchVariant]
    tasks: list[ResearchTask]
    findings: list[ResearchFinding]
    journal: ResearchJournal
    stop_reason: str

    def to_dict(self) -> dict[str, Any]:
        findings_by_method: dict[str, list[dict[str, Any]]] = {}
        best_by_method: dict[str, dict[str, Any]] = {}
        for finding in self.findings:
            key = finding.family if finding.family == "gematria" else finding.method.lower()
            findings_by_method.setdefault(key, []).append(finding.to_dict())
        for family, rows in findings_by_method.items():
            if rows:
                best_by_method[family] = max(
                    rows,
                    key=lambda row: (
                        float(((row.get("confidence") or {}).get("score") or 0.0)),
                        bool((row.get("verification") or {}).get("verified")),
                    ),
                )
        best_overall = None
        if self.findings:
            best_overall = max(
                (finding.to_dict() for finding in self.findings),
                key=lambda row: (
                    float(((row.get("confidence") or {}).get("score") or 0.0)),
                    bool((row.get("verification") or {}).get("verified")),
                ),
            )
        return {
            "query": self.query,
            "config": dict(self.config),
            "variants": [variant.to_dict() for variant in self.variants],
            "tasks_planned": [task.to_dict() for task in self.tasks],
            "tasks_run": len([e for e in self.journal.entries if e.event == "task_completed"]),
            "journal": self.journal.to_list(),
            "findings_by_method": findings_by_method,
            "best_by_method": best_by_method,
            "best_overall": best_overall,
            "stop_reason": self.stop_reason,
        }

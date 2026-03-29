"""Helpers for structured research journals."""

from __future__ import annotations

from autogematria.research.schema import ResearchJournal


def start_journal(query: str) -> ResearchJournal:
    """Create a journal and record the start event."""
    journal = ResearchJournal()
    journal.add("run_started", query=query)
    return journal

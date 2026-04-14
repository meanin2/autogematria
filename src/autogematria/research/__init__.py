"""Research orchestration layer for multi-method name-finding."""

from autogematria.research.config import ResearchConfig
from autogematria.research.runner import run_name_research
from autogematria.research.name_report import build_name_report

__all__ = ["ResearchConfig", "run_name_research", "build_name_report"]

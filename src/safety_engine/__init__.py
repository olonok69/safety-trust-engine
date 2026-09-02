"""safety_engine -- an automated red-team compliance gate.

Wires three red-team stages (garak, AgentDojo, PyRIT) into a single CI gate that
maps findings to selectable regime packs (``eu_uk``: EU AI Act / DORA / FCA;
``us``: NIST AI RMF / federal MRM) and emits an auditable evidence artifact.
See README.md.
"""

from .compliance import (
    ALL_CONTROLS,
    CONTROLS,
    REGIME_PACKS,
    Control,
    controls_for_regimes,
    resolve_regimes,
)
from .providers import build_pyrit_target, build_target
from .report import SafetyReport, build_report, write_json, write_markdown
from .run import run
from .stages import ProbeResult, StageResult, run_agentdojo, run_garak, run_pyrit

__all__ = [
    "ALL_CONTROLS",
    "CONTROLS",
    "REGIME_PACKS",
    "Control",
    "ProbeResult",
    "SafetyReport",
    "StageResult",
    "build_pyrit_target",
    "build_report",
    "build_target",
    "controls_for_regimes",
    "resolve_regimes",
    "run",
    "run_agentdojo",
    "run_garak",
    "run_pyrit",
    "write_json",
    "write_markdown",
]

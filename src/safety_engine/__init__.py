"""safety_engine -- an automated red-team compliance gate.

Wires three red-team stages (garak, AgentDojo, PyRIT) into a single CI gate that
maps findings to EU AI Act Art. 15, DORA, and FCA PS21/3 controls and emits an
auditable evidence artifact. See README.md.
"""

from .compliance import CONTROLS, Control
from .providers import build_pyrit_target, build_target
from .report import SafetyReport, build_report, write_json, write_markdown
from .run import run
from .stages import ProbeResult, StageResult, run_agentdojo, run_garak, run_pyrit

__all__ = [
    "CONTROLS",
    "Control",
    "ProbeResult",
    "SafetyReport",
    "StageResult",
    "build_pyrit_target",
    "build_report",
    "build_target",
    "run",
    "run_agentdojo",
    "run_garak",
    "run_pyrit",
    "write_json",
    "write_markdown",
]

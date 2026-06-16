"""Regulation -> control -> evidence mapping for the Safety & Trust engine.

This module is the regulatory core of the engine. It declares which red-team
stages (and which probe categories within them) constitute *evidence* for each
named control across the three regimes the JD calls out:

    - EU AI Act, Article 15 (accuracy, robustness, cybersecurity) + Art. 55 GPAI
    - DORA (Regulation (EU) 2022/2554), resilience-testing and third-party pillars
    - FCA PS21/3 "Building operational resilience" (+ PRA SS1/21)

The mapping is intentionally conservative: a control is only marked `pass` when
*every* stage that provides its evidence ran and stayed within tolerance. A
control whose evidence stages were skipped is `not_evidenced` (not `pass`) so a
green dashboard can never silently certify an untested control -- the
"silent green" failure mode.

Probe categories are the normalized vocabulary the stages emit (see stages.py):
    jailbreak, prompt_injection, encoding, data_leakage, toxicity,
    tool_injection, harmful_action
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Stage identifiers, kept in one place so typos surface immediately.
GARAK = "garak"
AGENTDOJO = "agentdojo"
PYRIT = "pyrit"


@dataclass(frozen=True)
class Control:
    """A single regulatory obligation we claim to evidence.

    regulation : short regime name (e.g. "EU AI Act").
    ref        : article / paragraph / section reference.
    label      : plain-language statement of the obligation.
    stages     : which stages must run for this control to be evidenced.
    categories : probe categories that are most relevant (informational; used
                 in the report to show *which* findings back the control).
    note       : optional implementation note surfaced in the evidence artifact.
    """

    regulation: str
    ref: str
    label: str
    stages: tuple[str, ...]
    categories: tuple[str, ...] = field(default_factory=tuple)
    note: str = ""


# ---------------------------------------------------------------------------
# The mapping. Grounded in the primary texts; see README for citations.
# ---------------------------------------------------------------------------
CONTROLS: list[Control] = [
    # --- EU AI Act, Article 15 -------------------------------------------
    Control(
        regulation="EU AI Act",
        ref="Art. 15(1)",
        label="Appropriate level of accuracy, robustness and cybersecurity, "
        "consistent across the lifecycle.",
        stages=(GARAK, AGENTDOJO, PYRIT),
        categories=("jailbreak", "prompt_injection", "tool_injection"),
    ),
    Control(
        regulation="EU AI Act",
        ref="Art. 15(4)",
        label="Resilience to errors, faults and inconsistencies, including "
        "feedback loops from interaction with persons or other systems.",
        stages=(GARAK, PYRIT),
        categories=("toxicity", "data_leakage"),
    ),
    Control(
        regulation="EU AI Act",
        ref="Art. 15(5)",
        label="Resilience against unauthorised third parties altering use, "
        "outputs or performance by exploiting vulnerabilities.",
        stages=(GARAK, AGENTDOJO, PYRIT),
        categories=("prompt_injection", "tool_injection", "encoding", "jailbreak"),
    ),
    Control(
        regulation="EU AI Act",
        ref="Art. 55(1)(a)",
        label="GPAI models with systemic risk: conduct and document adversarial "
        "testing (model evaluation / red-teaming).",
        stages=(GARAK, AGENTDOJO, PYRIT),
        note="Evidence artifact itself satisfies the 'document' obligation.",
    ),
    # --- DORA -------------------------------------------------------------
    Control(
        regulation="DORA",
        ref="Art. 24-25",
        label="Digital operational resilience testing programme: vulnerability "
        "assessments and scenario-based testing of ICT tools.",
        stages=(GARAK, AGENTDOJO),
        categories=("prompt_injection", "tool_injection", "encoding"),
    ),
    Control(
        regulation="DORA",
        ref="Art. 26-27",
        label="Threat-led penetration testing: simulate real-world threat "
        "actors against critical/important functions.",
        stages=(PYRIT, AGENTDOJO),
        categories=("jailbreak", "tool_injection", "harmful_action"),
        note="Demo runs single-turn campaigns; production TLPT requires "
        "intelligence-led, independent testers at least every 3 years.",
    ),
    Control(
        regulation="DORA",
        ref="Art. 28",
        label="ICT third-party risk: the model provider (e.g. AWS Bedrock) is "
        "an ICT third party and must be in scope of testing.",
        stages=(),  # Evidenced by target metadata, not by a stage run.
        note="Satisfied by recording target.provider/model in the artifact and "
        "asserting the provider is on the approved-third-party register.",
    ),
    # --- FCA PS21/3 -------------------------------------------------------
    Control(
        regulation="FCA PS21/3",
        ref="6.2 / SS1/21",
        label="Scenario testing under severe but plausible disruption for each "
        "important business service the agent supports.",
        stages=(PYRIT, AGENTDOJO),
        categories=("jailbreak", "tool_injection", "harmful_action"),
    ),
    Control(
        regulation="FCA PS21/3",
        ref="Impact tolerance",
        label="Remain within the impact tolerance set for the important "
        "business service (here: max tolerable attack-success rate).",
        stages=(GARAK, AGENTDOJO, PYRIT),
        note="Enforced by the tolerance gate in report.py.",
    ),
    Control(
        regulation="FCA PS21/3",
        ref="Self-assessment",
        label="Maintain a written self-assessment evidencing resilience and "
        "remediation of identified vulnerabilities.",
        stages=(),  # Evidenced by the artifact + remediation list.
        note="Satisfied by the consolidated JSON/Markdown evidence artifact.",
    ),
]


def controls_for_stage(stage: str) -> list[Control]:
    """Return every control that depends on a given stage."""
    return [c for c in CONTROLS if stage in c.stages]


def regulations() -> list[str]:
    """Distinct regulation names, in first-seen order."""
    seen: list[str] = []
    for c in CONTROLS:
        if c.regulation not in seen:
            seen.append(c.regulation)
    return seen

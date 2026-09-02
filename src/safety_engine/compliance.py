"""Regulation -> control -> evidence mapping for the Safety & Trust engine.

This module is the regulatory core of the engine. It declares which red-team
stages (and which probe categories within them) constitute *evidence* for each
named control, organised into selectable **regime packs**:

    - ``eu_uk`` — EU AI Act Art. 15 & 55, DORA, FCA PS21/3 (default)
    - ``us``    — NIST AI RMF MEASURE / AI 600-1, federal MRM (SR 26-02)

Select packs at runtime via ``--regimes`` so a US-only deploy is not judged on
DORA/FCA (and vice versa). The mapping is intentionally conservative: a control
is only marked ``pass`` when *every* stage that provides its evidence ran and
stayed within tolerance. A control whose evidence stages were skipped is
``not_evidenced`` (not ``pass``) so a green dashboard can never silently
certify an untested control -- the "silent green" failure mode.

Probe categories are the normalized vocabulary the stages emit (see stages.py):
    jailbreak, prompt_injection, encoding, data_leakage, toxicity,
    tool_injection, harmful_action

``binding`` on each control records how hard the obligation is, so artifacts
do not imply statutory certification for voluntary/supervisory lenses:
    statute | guidance | supervisory
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

# Stage identifiers, kept in one place so typos surface immediately.
GARAK = "garak"
AGENTDOJO = "agentdojo"
PYRIT = "pyrit"

# Regime pack identifiers.
EU_UK = "eu_uk"
US = "us"
DEFAULT_REGIMES: tuple[str, ...] = (EU_UK,)


@dataclass(frozen=True)
class Control:
    """A single regulatory obligation we claim to evidence.

    regulation : short regime name (e.g. "EU AI Act", "NIST AI RMF").
    ref        : article / paragraph / section reference.
    label      : plain-language statement of the obligation.
    stages     : which stages must run for this control to be evidenced.
    categories : probe categories that are most relevant (informational; used
                 in the report to show *which* findings back the control).
    note       : optional implementation note surfaced in the evidence artifact.
    binding    : statute | guidance | supervisory — honesty marker for artifacts.
    """

    regulation: str
    ref: str
    label: str
    stages: tuple[str, ...]
    categories: tuple[str, ...] = field(default_factory=tuple)
    note: str = ""
    binding: str = "statute"


# ---------------------------------------------------------------------------
# EU / UK pack (default). Grounded in the primary texts; see README.
# ---------------------------------------------------------------------------
EU_UK_CONTROLS: list[Control] = [
    # --- EU AI Act, Article 15 -------------------------------------------
    Control(
        regulation="EU AI Act",
        ref="Art. 15(1)",
        label="Appropriate level of accuracy, robustness and cybersecurity, "
        "consistent across the lifecycle.",
        stages=(GARAK, AGENTDOJO, PYRIT),
        categories=("jailbreak", "prompt_injection", "tool_injection"),
        binding="statute",
    ),
    Control(
        regulation="EU AI Act",
        ref="Art. 15(4)",
        label="Resilience to errors, faults and inconsistencies, including "
        "feedback loops from interaction with persons or other systems.",
        stages=(GARAK, PYRIT),
        categories=("toxicity", "data_leakage"),
        binding="statute",
    ),
    Control(
        regulation="EU AI Act",
        ref="Art. 15(5)",
        label="Resilience against unauthorised third parties altering use, "
        "outputs or performance by exploiting vulnerabilities.",
        stages=(GARAK, AGENTDOJO, PYRIT),
        categories=("prompt_injection", "tool_injection", "encoding", "jailbreak"),
        binding="statute",
    ),
    Control(
        regulation="EU AI Act",
        ref="Art. 55(1)(a)",
        label="GPAI models with systemic risk: conduct and document adversarial "
        "testing (model evaluation / red-teaming).",
        stages=(GARAK, AGENTDOJO, PYRIT),
        note="Evidence artifact itself satisfies the 'document' obligation.",
        binding="statute",
    ),
    # --- DORA -------------------------------------------------------------
    Control(
        regulation="DORA",
        ref="Art. 24-25",
        label="Digital operational resilience testing programme: vulnerability "
        "assessments and scenario-based testing of ICT tools.",
        stages=(GARAK, AGENTDOJO),
        categories=("prompt_injection", "tool_injection", "encoding"),
        binding="statute",
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
        binding="statute",
    ),
    Control(
        regulation="DORA",
        ref="Art. 28",
        label="ICT third-party risk: the model provider (e.g. AWS Bedrock) is "
        "an ICT third party and must be in scope of testing.",
        stages=(),  # Evidenced by target metadata, not by a stage run.
        note="Satisfied by recording target.provider/model in the artifact and "
        "asserting the provider is on the approved-third-party register.",
        binding="statute",
    ),
    # --- FCA PS21/3 -------------------------------------------------------
    Control(
        regulation="FCA PS21/3",
        ref="6.2 / SS1/21",
        label="Scenario testing under severe but plausible disruption for each "
        "important business service the agent supports.",
        stages=(PYRIT, AGENTDOJO),
        categories=("jailbreak", "tool_injection", "harmful_action"),
        binding="statute",
    ),
    Control(
        regulation="FCA PS21/3",
        ref="Impact tolerance",
        label="Remain within the impact tolerance set for the important "
        "business service (here: max tolerable attack-success rate).",
        stages=(GARAK, AGENTDOJO, PYRIT),
        note="Enforced by the tolerance gate in report.py.",
        binding="statute",
    ),
    Control(
        regulation="FCA PS21/3",
        ref="Self-assessment",
        label="Maintain a written self-assessment evidencing resilience and "
        "remediation of identified vulnerabilities.",
        stages=(),  # Evidenced by the artifact + remediation list.
        note="Satisfied by the consolidated JSON/Markdown evidence artifact.",
        binding="statute",
    ),
]


# ---------------------------------------------------------------------------
# US pack — NIST AI RMF + federal MRM. Same evidence, different lens.
# See docs/REGULATORY_RESEARCH.md §4.5. Not a statutory conformity claim.
# ---------------------------------------------------------------------------
US_CONTROLS: list[Control] = [
    # --- NIST AI RMF (voluntary guidance) --------------------------------
    Control(
        regulation="NIST AI RMF",
        ref="MEASURE 2.6",
        label="AI system evaluated for potential for misuse and abuse.",
        stages=(GARAK, AGENTDOJO, PYRIT),
        categories=("jailbreak", "prompt_injection", "tool_injection"),
        note="Voluntary NIST guidance — technical evidence only, not certification.",
        binding="guidance",
    ),
    Control(
        regulation="NIST AI RMF",
        ref="MEASURE 2.7",
        label="AI system security and resilience evaluated and documented.",
        stages=(GARAK, AGENTDOJO, PYRIT),
        categories=("prompt_injection", "tool_injection", "encoding", "jailbreak"),
        note="Voluntary NIST guidance — technical evidence only, not certification.",
        binding="guidance",
    ),
    Control(
        regulation="NIST AI RMF",
        ref="AI 600-1",
        label="Generative AI Profile: pre-deployment red-teaming for GenAI "
        "information-security risks (incl. prompt injection).",
        stages=(GARAK, AGENTDOJO, PYRIT),
        categories=("jailbreak", "prompt_injection", "tool_injection", "encoding"),
        note="Voluntary NIST Generative AI Profile (AI 600-1).",
        binding="guidance",
    ),
    Control(
        regulation="NIST AI RMF",
        ref="MEASURE documentation",
        label="Document evaluation of security, resilience, and misuse potential.",
        stages=(),
        note="Satisfied by the consolidated JSON/Markdown evidence artifact.",
        binding="guidance",
    ),
    # --- Federal MRM (supervisory; GenAI largely by analogy under SR 26-02)
    Control(
        regulation="Federal MRM",
        ref="SR 26-02 validation",
        label="Independent validation / effective challenge: outcomes analysis "
        "via adversarial testing of the model or agent.",
        stages=(PYRIT, AGENTDOJO),
        categories=("jailbreak", "tool_injection", "harmful_action"),
        note="Supervisory analogy for GenAI/agentic systems — SR 26-02 soft-pedals "
        "formal GenAI scope; not a codified GenAI rule.",
        binding="supervisory",
    ),
    Control(
        regulation="Federal MRM",
        ref="SR 26-02 monitoring",
        label="Ongoing monitoring: repeatable adversarial gate in CI with "
        "numeric attack-success tolerances.",
        stages=(GARAK, AGENTDOJO, PYRIT),
        note="Continuous CI assurance is not a formal TLPT-style exercise.",
        binding="supervisory",
    ),
    Control(
        regulation="Federal MRM",
        ref="SR 26-02 documentation",
        label="Model-risk file: decision package evidencing testing and remediation.",
        stages=(),
        note="Satisfied by the consolidated JSON/Markdown evidence artifact.",
        binding="supervisory",
    ),
    Control(
        regulation="Federal MRM",
        ref="Third-party model",
        label="Vendor / hosted model provider recorded and in scope of testing.",
        stages=(),
        note="Satisfied by recording target.provider/model in the artifact "
        "(same pattern as DORA Art. 28).",
        binding="supervisory",
    ),
]


REGIME_PACKS: dict[str, list[Control]] = {
    EU_UK: EU_UK_CONTROLS,
    US: US_CONTROLS,
}

# Default evaluated set (back-compat for imports that still use CONTROLS).
CONTROLS: list[Control] = list(EU_UK_CONTROLS)

# Flat catalogue of every encoded control (all packs).
ALL_CONTROLS: list[Control] = [c for pack in REGIME_PACKS.values() for c in pack]


def available_regimes() -> list[str]:
    """Known regime pack names, in stable order."""
    return list(REGIME_PACKS.keys())


def resolve_regimes(names: Sequence[str] | None = None) -> tuple[str, ...]:
    """Normalize and validate pack names; default to ``eu_uk`` only."""
    if names is None:
        return DEFAULT_REGIMES
    resolved: list[str] = []
    unknown: list[str] = []
    for raw in names:
        name = raw.strip()
        if not name:
            continue
        if name not in REGIME_PACKS:
            unknown.append(name)
            continue
        if name not in resolved:
            resolved.append(name)
    if unknown:
        raise ValueError(
            f"unknown regime pack(s): {unknown}; valid: {available_regimes()}"
        )
    if not resolved:
        return DEFAULT_REGIMES
    return tuple(resolved)


def controls_for_regimes(regimes: Sequence[str] | None = None) -> list[Control]:
    """Controls belonging to the selected packs, in pack then declaration order."""
    out: list[Control] = []
    for name in resolve_regimes(regimes):
        out.extend(REGIME_PACKS[name])
    return out


def controls_for_stage(
    stage: str, regimes: Sequence[str] | None = None
) -> list[Control]:
    """Return every selected control that depends on a given stage."""
    return [c for c in controls_for_regimes(regimes) if stage in c.stages]


def regulations(controls: Sequence[Control] | None = None) -> list[str]:
    """Distinct regulation names, in first-seen order."""
    src = CONTROLS if controls is None else controls
    seen: list[str] = []
    for c in src:
        if c.regulation not in seen:
            seen.append(c.regulation)
    return seen

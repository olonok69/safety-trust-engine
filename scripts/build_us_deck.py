"""Build docs/Safety_and_Trust_Engine_US.pptx from the EU deck.

Copies the existing presentation and rewrites regulatory framing for the
US pack (NIST AI RMF + federal MRM). Architecture / toolkit slides stay;
honesty caveats (guidance / supervisory) replace "legal obligation". Speaker
notes are rewritten too, and the demo terminal shows the ``--regimes us`` run.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "Safety_and_Trust_Engine.pptx"
DST = ROOT / "docs" / "Safety_and_Trust_Engine_US.pptx"

# slide index (1-based) -> list of (old, new) exact shape-text matches
SLIDE_REPLACEMENTS: dict[int, list[tuple[str, str]]] = {
    1: [
        (
            "garak · AgentDojo · PyRIT    |    EU AI Act · DORA · FCA Operational Resilience",
            "garak · AgentDojo · PyRIT    |    NIST AI RMF · Federal MRM (SR 26-02)",
        ),
    ],
    2: [
        (
            "Adversarial testing became a legal obligation",
            "Adversarial testing is now an exam expectation",
        ),
        ("17 Jan 2025", "26 Jul 2024"),
        ("DORA", "NIST AI 600-1"),
        (
            "Fully applicable across EU financial entities \uf0e0 https://www.eiopa.europa.eu/digital-operational-resilience-act-dora_en",
            "Generative AI Profile — red-team as pre-deploy MEASURE \uf0e0 https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf",
        ),
        ("31 Mar 2025", "17 Apr 2026"),
        ("FCA PS21/3", "SR 26-02"),
        (
            "Operational-resilience transition period closed \uf0e0 https://www.fca.org.uk/publications/policy-statements/ps21-3-building-operational-resilience",
            "Revised interagency MRM guidance (Fed / OCC / FDIC) \uf0e0 https://www.federalreserve.gov/supervisionreg/srletters/SR2602.pdf",
        ),
        ("Art. 15 / 55", "MEASURE 2.7"),
        ("EU AI Act", "NIST AI RMF"),
        (
            "Robustness, cybersecurity & documented red-teaming \uf0e0\nhttps://artificialintelligenceact.eu/article/15/",
            "Misuse, security & resilience evaluated and documented \uf0e0\nhttps://www.nist.gov/itl/ai-risk-management-framework",
        ),
        ("Three regulators, one shared demand", "Two US lenses, one shared demand"),
        (
            "Adversarial testing that is repeatable, evidenced, and remediated. Most teams already run the attacks — a notebook, a one-off run, a screenshot. None of that is evidence. The gap this engine closes is turning red-teaming into something you can prove, on every commit.",
            "Adversarial testing that is repeatable, evidenced, and remediated. NIST is voluntary guidance; federal MRM is supervisory (GenAI often by analogy under SR 26-02). The gap this engine closes is turning red-teaming into something you can prove, on every commit — with binding honesty in the artifact.",
        ),
    ],
    4: [
        ("EU AI Act — Article 15 (and 55)", "NIST AI RMF — MEASURE (and AI 600-1)"),
        ("Art. 15(1)", "MEASURE 2.6"),
        (
            "Appropriate accuracy, robustness and cybersecurity, consistent across the lifecycle.",
            "AI system evaluated for potential for misuse and abuse.",
        ),
        ("Art. 15(5)", "MEASURE 2.7"),
        (
            "Resilience against unauthorised third parties exploiting vulnerabilities — incl. data poisoning and adversarial inputs.",
            "AI system security and resilience are evaluated and documented.",
        ),
        ("Art. 55(1)(a)", "AI 600-1"),
        (
            "GPAI with systemic risk must conduct and document adversarial testing (red-teaming).",
            "Generative AI Profile: pre-deployment red-teaming for GenAI information-security risks.",
        ),
        (
            "Engineering translation:  “document” is the hook — our evidence artifact is that documentation.",
            "Engineering translation:  binding = guidance — voluntary NIST, not certification. The artifact is the documentation.",
        ),
    ],
    5: [
        ("DORA — testing and third-party pillars", "Federal MRM — validation and monitoring"),
        ("Art. 24–25", "SR 26-02 validation"),
        (
            "Risk-based resilience testing: vulnerability assessments, independent testers, all critical tools tested ≥ annually.",
            "Independent validation / effective challenge: outcomes analysis via adversarial testing.",
        ),
        ("Art. 26–27", "SR 26-02 monitoring"),
        (
            "Threat-led penetration testing (TLPT) ≥ every 3 years, simulating real-world threat actors.",
            "Ongoing monitoring: repeatable adversarial gate in CI with numeric ASR tolerances.",
        ),
        ("Art. 28", "Third-party model"),
        (
            "ICT third-party risk — AWS Bedrock is an ICT third party, in scope of testing and the register.",
            "Vendor / hosted model provider recorded in the artifact and kept in testing scope.",
        ),
        (
            "Engineering translation:  a nightly CI run is continuous assurance — not a substitute for formal TLPT.",
            "Engineering translation:  continuous CI assurance ≠ formal exam exercise; GenAI is supervisory analogy under SR 26-02.",
        ),
    ],
    6: [
        (
            "FCA PS21/3 — operational resilience",
            "Federal MRM — the decision package",
        ),
        ("Important business service", "Model-risk file"),
        (
            "An agent is a dependency of an important business service whose disruption can cause intolerable harm.",
            "The gate’s JSON + Markdown artifact is the validation-and-documentation evidence a model-risk reviewer asks for.",
        ),
        ("Impact tolerance", "Numeric ASR gate"),
        (
            "The maximum tolerable disruption — tested under severe-but-plausible scenarios.",
            "Maximum acceptable attack-success rate per category — same mechanic, US vocabulary.",
        ),
        ("Self-assessment", "Documentation"),
        (
            "A written record evidencing resilience and remediation.",
            "Satisfied by the consolidated evidence artifact (binding: supervisory).",
        ),
        (
            "Engineering translation:  impact tolerance is just a maximum acceptable attack-success rate.",
            "Engineering translation:  keep binding honest — supervisory expectation, not a statute with penalties.",
        ),
    ],
    7: [
        (
            "In code today: EU AI Act · DORA · FCA.  NIST AI RMF and the MIT AI Risk Repository are the natural next lenses.",
            "In code today: --regimes us encodes NIST AI RMF · Federal MRM. Default pack remains eu_uk; combine with --regimes eu_uk,us.",
        ),
    ],
    11: [
        ("Impact tolerance, made numeric", "Exam-ready tolerance, made numeric"),
        (
            "FCA impact tolerance\n=\nmax attack-success rate",
            "SR 26-02 monitoring\n=\nmax attack-success rate",
        ),
    ],
    12: [
        (
            'Control(\n  regulation="EU AI Act",\n  ref="Art. 15(5)",\n  stages=(GARAK, AGENTDOJO, PYRIT),\n  categories=("prompt_injection",\n    "tool_injection", "jailbreak"),\n)',
            'Control(\n  regulation="NIST AI RMF",\n  ref="MEASURE 2.7",\n  binding="guidance",\n  stages=(GARAK, AGENTDOJO, PYRIT),\n  categories=("prompt_injection",\n    "tool_injection", "jailbreak"),\n)',
        ),
    ],
    14: [
        (
            "The failing category is prompt_injection — the same delayed-compliance case a human would surface only by hand: the agent refuses, then appends an override to a tool argument.",
            "The failing category is prompt_injection — the agent refuses, then appends an override to a tool argument. The artifact names it under MEASURE 2.6–2.7, AI 600-1 and SR 26-02.",
        ),
    ],
    16: [
        (
            "Wire NIST AI RMF and MIT AI Risk categories into the mapper.",
            "Map findings to MIT AI Risk, OWASP LLM Top 10 and MITRE ATLAS.",
        ),
    ],
    18: [
        (
            "Enforcing safety-gate blocks a PR on any tolerance breach; lint+test + nightly live. CI green.",
            "lint+test and merge-demo are required checks on main; strict and live gates run on demand.",
        ),
    ],
    17: [
        ("Red-teaming is now regulated", "Red-teaming is now exam-ready"),
        (
            "EU AI Act, DORA and FCA all demand repeatable, documented adversarial testing — one control, three vocabularies.",
            "NIST MEASURE and federal MRM both reward repeatable, documented adversarial testing — guidance and supervisory lenses, not silent certification.",
        ),
        (
            "Resources   README · docs/REGULATORY_RESEARCH.md · docs/pipeline.svg · docs/safety_trust_engine_cicd_pipeline.svg · .github/workflows/safety-trust.yml · docs/HANDOVER.md",
            "Resources   README · docs/US_COMPLIANCE.md · docs/REGULATORY_RESEARCH.md §4.5 · docs/pipeline.svg · .github/workflows/safety-trust.yml",
        ),
    ],
}


# Slide 14 terminal, one (text, colour) per paragraph — the real
# `--demo --regimes us` output, abridged to the deck's 12 lines.
_TEAL, _GREY, _WHITE, _RED = (
    RGBColor(45, 212, 191), RGBColor(156, 192, 184),
    RGBColor(255, 255, 255), RGBColor(240, 138, 130),
)
DEMO_TERMINAL: list[tuple[str, RGBColor] | None] = [
    ("$ uv run safety-engine --demo --regimes us", _TEAL),
    ("  [garak|agentdojo|pyrit] ran: 13 probes", _GREY),
    ("  [FAIL] prompt_injection 15%  (tol 10%)", _RED),
    ("  [FAIL] tool_injection   13%  (tol 5%)", _RED),
    None,
    ("Regimes: us · 8 controls, 5 failing", _WHITE),
    ("  FAIL NIST AI RMF MEASURE 2.6 / 2.7", _RED),
    ("  FAIL NIST AI RMF AI 600-1", _RED),
    ("  FAIL Federal MRM SR 26-02 validation", _RED),
    ("  FAIL Federal MRM SR 26-02 monitoring", _RED),
    None,
    None,  # keep "Overall: FAIL → exit 1" as in the EU deck
]

# Speaker notes per slide (1-based). Slides not listed keep the EU notes,
# which are regime-neutral (mental model, toolkit, architecture, review gate);
# slide 18 has no notes placeholder in the source deck.
SLIDE_NOTES: dict[int, str] = {
    1: "Open with two rows: top the US lenses (NIST AI RMF, federal MRM / SR 26-02), "
    "bottom the three tools (garak, AgentDojo, PyRIT). Land the line: you're probably "
    "already doing the red-teaming, you're just not producing exam-ready evidence. "
    "Same engine as the EU/UK talk, read through US lenses with --regimes us.",
    2: "In the US there is no single statute that says red-team your LLM. There is a "
    "stack of expectations: NIST AI 600-1 (July 2024) puts red-teaming in pre-deploy "
    "MEASURE, and the April 2026 interagency MRM revision (SR 26-02 / OCC 2026-13) "
    "replaces SR 11-7. Say early: NIST is voluntary, MRM is supervisory, and SR 26-02 "
    "leaves GenAI/agentic AI outside formal scope, so examiners apply it by analogy.",
    4: "MEASURE 2.6 is misuse and abuse, MEASURE 2.7 is security and resilience — the "
    "subcategory red-teaming exercises most directly. AI 600-1 adds GenAI-specific "
    "risks incl. prompt injection. Say it plainly: binding = guidance; never say "
    "'NIST certified'. Flag the word 'documented' — it pays off on the artifact slide.",
    5: "Three MRM pillars: sound development, independent validation (effective "
    "challenge, outcomes analysis), governance. Adversarial testing is outcomes "
    "analysis; the CI gate is ongoing monitoring. Be honest before the audience is: "
    "continuous CI assurance is not a formal validation exercise, and a hosted model "
    "(OpenAI, Azure, Bedrock) is a third-party model that stays in scope.",
    6: "The bridge to the gate. The model-risk file a validator asks for is exactly "
    "what each run writes: verdict, per-category ASR vs tolerance, per-control status "
    "with binding, remediation list. Land: a tolerance is just a maximum "
    "attack-success rate — the same mechanic the EU deck calls impact tolerance.",
    7: "One finding, many lenses. The same prompt-injection hit lands on MEASURE 2.7 "
    "and, if you select it, on EU AI Act Art. 15(5). compliance.py encodes both packs; "
    "--regimes us for US-only, --regimes eu_uk,us when you serve both markets. "
    "MIT AI Risk stays on the roadmap.",
    11: "Show the DEFAULT_TOLERANCES dict next to the SR 26-02 monitoring control: "
    "same concept, one prose, one enforced. The monitoring control fails whenever any "
    "category breaches. Override per run with --fail-under; tune per use case and "
    "risk appetite.",
    12: "Show the US Control literal with binding='guidance' and the not_evidenced "
    "branch. A control you didn't test never renders as one you passed — exactly what "
    "a model-risk reviewer checks first.",
    14: "Run it live: uv run safety-engine --demo --regimes us. Let the non-zero exit "
    "land before explaining it — a failing demo is the point. Then open "
    "runs/st-*.md: only NIST AI RMF and Federal MRM sections, each row with its "
    "binding. Optional: rerun with --regimes eu_uk,us to show one evidence set, two "
    "lenses. Red CI on demand: Actions → safety-trust → Run workflow (demo-gate).",
    15: "A decision package, not a score. The Markdown artifact is the lightweight "
    "model-risk file: what was tested, against which tolerance, which controls failed, "
    "what to remediate. Position Weave as the production upgrade path for the "
    "evidence layer.",
    16: "Dev → Pre-deploy → Production is the W&B three-stage view. We own the "
    "middle. NIST and MRM are already wired; next lenses are the taxonomies US "
    "security teams ask for — OWASP LLM Top 10 and MITRE ATLAS — plus MIT AI Risk.",
    17: "Close on takeaway 2: your examiner does not want your scan, they want your "
    "gate — with honest binding. Then Q&A, five minutes, offer to continue offline. "
    "Resources: README, docs/US_COMPLIANCE.md, REGULATORY_RESEARCH.md §4.5.",
}


def _set_terminal(shape) -> None:
    paras = shape.text_frame.paragraphs
    if len(paras) != len(DEMO_TERMINAL):
        raise SystemExit(f"slide 14 terminal has {len(paras)} lines, "
                         f"expected {len(DEMO_TERMINAL)}")
    for para, line in zip(paras, DEMO_TERMINAL, strict=True):
        if line is None:
            continue
        text, colour = line
        if not para.runs:
            para.add_run()
        para.runs[0].text = text
        para.runs[0].font.color.rgb = colour
        for run in para.runs[1:]:
            run.text = ""


def _set_shape_text(shape, new: str) -> None:
    tf = shape.text_frame
    first = True
    for para in tf.paragraphs:
        if first:
            if para.runs:
                para.runs[0].text = new
                for run in para.runs[1:]:
                    run.text = ""
            else:
                para.text = new
            first = False
        else:
            for run in para.runs:
                run.text = ""
            if not para.runs:
                para.text = ""


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing source deck: {SRC}")
    shutil.copy2(SRC, DST)
    prs = Presentation(str(DST))
    hits = 0
    missing: list[str] = []
    for idx, pairs in SLIDE_REPLACEMENTS.items():
        slide = prs.slides[idx - 1]
        shapes = [
            sh for sh in slide.shapes
            if sh.has_text_frame and sh.text_frame.text.strip()
        ]
        for old, new in pairs:
            matched = False
            for shape in shapes:
                if shape.text_frame.text == old:
                    _set_shape_text(shape, new)
                    hits += 1
                    matched = True
                    break
            if not matched:
                missing.append(f"slide {idx}: {old[:70]!r}")
    terminal = [
        sh for sh in prs.slides[13].shapes
        if sh.has_text_frame
        and sh.text_frame.text.startswith("$ uv run safety-engine --demo")
    ]
    if terminal:
        _set_terminal(terminal[0])
        hits += 1
    else:
        missing.append("slide 14: demo terminal")
    for idx, text in SLIDE_NOTES.items():
        prs.slides[idx - 1].notes_slide.notes_text_frame.text = text
    prs.save(str(DST))
    print(f"wrote {DST} ({hits} replacements)")
    if missing:
        print("UNMATCHED:")
        for m in missing:
            print(" ", m)
        # Debug: print near-misses for unmatched
        for idx, pairs in SLIDE_REPLACEMENTS.items():
            slide = prs.slides[idx - 1]
            for old, _new in pairs:
                if any(
                    sh.has_text_frame and sh.text_frame.text == old
                    for sh in slide.shapes
                ):
                    continue
                # still missing after failed run — show candidates containing a keyword
                key = old.split("\n", 1)[0][:40]
                for sh in slide.shapes:
                    if sh.has_text_frame and key[:20] in sh.text_frame.text:
                        print(f"  candidate slide {idx}: {sh.text_frame.text!r}")
                        break



if __name__ == "__main__":
    main()

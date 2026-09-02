# US compliance pack

Buyer-facing notes for running the Safety & Trust engine against **US**
instruments. Engineering detail and citations live in
[REGULATORY_RESEARCH.md](REGULATORY_RESEARCH.md) §4.5 and §6.

> Not legal advice. Artifact “pass” means *technical* evidence was gathered
> within tolerance — not a conformity or examination opinion.

## Packs

| Pack | CLI | What it evaluates |
| --- | --- | --- |
| `eu_uk` (default) | `--regimes eu_uk` | EU AI Act, DORA, FCA PS21/3 |
| `us` | `--regimes us` | NIST AI RMF + federal MRM (SR 26-02) |
| both | `--regimes eu_uk,us` | Same evidence, both lenses |

```bash
uv run safety-engine --demo --regimes us
uv run safety-engine --demo --regimes eu_uk,us
```

## What the `us` pack encodes

### NIST AI RMF (binding: `guidance`)

Voluntary framework (NIST AI 100-1) plus Generative AI Profile (AI 600-1).
The engine evidences **MEASURE** activities:

| Ref | Claim |
| --- | --- |
| MEASURE 2.6 | Misuse / abuse evaluation (jailbreak, injection, tool injection) |
| MEASURE 2.7 | Security & resilience evaluated and documented |
| AI 600-1 | Pre-deploy GenAI red-teaming for information-security risks |
| MEASURE documentation | JSON + Markdown decision package |

There is **no NIST certification**. Do not present a green gate as “NIST certified.”

### Federal MRM (binding: `supervisory`)

Interagency model-risk management — Fed **SR 26-02** / OCC **Bulletin 2026-13**
(successor to SR 11-7). The pack maps to validation, ongoing monitoring,
documentation, and third-party / vendor model recording.

| Ref | Claim |
| --- | --- |
| SR 26-02 validation | Effective challenge via adversarial outcomes analysis |
| SR 26-02 monitoring | Repeatable CI gate with numeric ASR tolerances |
| SR 26-02 documentation | Model-risk decision package |
| Third-party model | `target.provider` / `model` recorded in the artifact |

**Honesty caveat:** the 2026 revision soft-pedals generative and agentic AI as
formal scope. Supervisors and internal audit often apply MRM principles **by
analogy** today — the artifact notes say so. Continuous CI assurance is not a
formal TLPT-style exercise.

## Same evidence, different lens

Stages (garak → AgentDojo → PyRIT) and the ASR gate do not change. Only which
`Control` rows are evaluated and printed. A US-only run is never judged on
DORA/FCA; an EU-only run never claims NIST MEASURE.

## Suggested talking points

1. **Not “legal obligation”** — NIST is voluntary; MRM is supervisory / exam
   readiness (and GenAI is often analogy).
2. **The gate is the deliverable** — repeatable, evidenced, remediable — not a
   one-off scan.
3. **Binding in the artifact** — `guidance` vs `supervisory` vs `statute` so
   reviewers cannot misread the claim strength.

## US deck

Presentation: [Safety_and_Trust_Engine_US.pptx](Safety_and_Trust_Engine_US.pptx)
(regenerate with `uv run python scripts/build_us_deck.py` from the EU deck).

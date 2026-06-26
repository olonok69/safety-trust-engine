# Regulatory & tooling research

Background dossier for the Safety & Trust engine. It documents the three
regulatory regimes the engine maps findings to, and the three red-team tools it
orchestrates. Everything here is paraphrased from primary and secondary sources;
see [References](#references) for links. Article and paragraph numbers follow the
consolidated published texts — confirm against the Official Journal version your
compliance team relies on before citing externally.

> Scope note: this is engineering-facing background to justify the control
> mapping in `compliance.py`. It is not legal advice, and "evidence" here means
> *technical* evidence a control was exercised, not a legal conformity opinion.

---

## 1. The common thread

All three regimes converge on one obligation that an agentic system must satisfy:
**adversarial testing that is repeatable, evidenced, and remediated.** They differ
in scope and vocabulary:

- **EU AI Act** governs the *AI system* itself (product-safety framing).
- **DORA** governs *operational resilience* of EU financial entities and their
  ICT supply chain.
- **FCA PS21/3** governs *operational resilience* of UK financial firms.

An AWS Bedrock-based agent in a financial workflow can be in scope of all three
at once: the agent is a high-risk AI system (AI Act), an ICT asset of a financial
entity (DORA), and a dependency of an important business service (FCA), while
Bedrock itself is an ICT third party (DORA Chapter V).

A US-domiciled deployment — or a UK/EU stack serving US users — has two further
analogues: **NIST AI RMF** (the AI-system axis) and **federal model-risk
management** (the financial axis). These are documented in §4.5 as *parallel
lenses* read against the same evidence; neither is encoded in `compliance.py`,
and so neither appears in the §6 matrix.

---

## 2. EU AI Act — Article 15 (and Article 55)

**Instrument:** Regulation (EU) 2024/1689 (the "AI Act").
**Relevant provision:** Article 15 — *Accuracy, robustness and cybersecurity* —
within Chapter III obligations for **high-risk** AI systems (those listed in
Annex III, e.g. credit scoring, employment, essential services). Article 55 adds
obligations for general-purpose AI (GPAI) models with systemic risk.

### What Article 15 requires

- **15(1)** — High-risk systems must achieve an appropriate level of accuracy,
  robustness and cybersecurity, and perform consistently in those respects across
  their lifecycle.
- **15(2)** — The Commission, with stakeholders and metrology/benchmarking
  bodies, is to encourage the development of benchmarks and measurement
  methodologies.
- **15(3)** — Declared accuracy levels and the relevant accuracy metrics must
  appear in the instructions for use.
- **15(4)** — Systems must be as resilient as possible to errors, faults and
  inconsistencies, including those arising from interaction with people or other
  systems; robustness may be achieved with technical redundancy (backup /
  fail-safe). Continuously-learning systems must mitigate biased-output feedback
  loops.
- **15(5)** — Systems must be resilient against attempts by unauthorised third
  parties to alter their use, outputs or performance by exploiting
  vulnerabilities. Cybersecurity measures must suit the circumstances and risks,
  and where relevant defend against data poisoning, model poisoning, adversarial
  / evasion inputs, and confidentiality attacks.

### Article 55(1)(a) — GPAI with systemic risk

Providers of GPAI models classified as systemic-risk must perform model
evaluation including **adversarial testing (red-teaming)** to identify and
mitigate systemic risk, and must document it.

### Scope nuance

Article 15 binds high-risk systems. A general-purpose model is only pulled in via
Article 15 when deployed in a high-risk domain; systemic-risk GPAI carries the
separate Article 55 adversarial-testing duty regardless. In short: the
red-teaming obligation can reach a provider from two directions depending on
classification.

### Relevance to the engine

- 15(1) robustness/cybersecurity → evidenced by **all three stages**.
- 15(4) errors/feedback loops → **garak** (toxicity, leakage) + **PyRIT**.
- 15(5) resilience to vulnerability exploitation → **garak** (promptinject,
  encoding), **AgentDojo** (tool injection), **PyRIT** (jailbreak).
- 55(1)(a) documented adversarial testing → the **evidence artifact** satisfies
  the "document" half.

---

## 3. DORA — Digital Operational Resilience Act

**Instrument:** Regulation (EU) 2022/2554.
**Timeline:** entered into force 16 January 2023; **fully applicable from 17
January 2025** after a two-year transition.
**Who:** EU financial entities (banks, insurers, investment firms, crypto-asset
providers, etc.) and their critical ICT third-party providers.

### The five pillars

1. **ICT risk management** (Chapter II, Arts 5–16) — a documented, regularly
   reviewed framework integrated into overall risk management.
2. **ICT incident reporting** — classify and report major ICT-related incidents
   to competent authorities without undue delay.
3. **Digital operational resilience testing** (Arts 24–27) — see below.
4. **ICT third-party risk** (Chapter V, Arts 28–44) — manage provider risk as an
   integral part of ICT risk management; maintain a register of arrangements.
5. **Information sharing** — voluntary exchange of cyber-threat intelligence.

### Testing pillar (the part the engine addresses)

- **Arts 24–25** — every entity runs a risk-based testing programme: vulnerability
  assessments, network-security assessments, scenario-based testing and
  penetration testing, performed by independent parties, with prompt remediation
  of findings, and **all critical ICT tools/applications tested at least
  annually**.
- **Arts 26–27** — significant entities (by size, systemic importance or ICT-risk
  profile) additionally run **threat-led penetration testing (TLPT)** at least
  every three years, simulating real-world threat actors against critical or
  important functions, validated by the competent authority. The Eurosystem's
  **TIBER-EU** framework is the reference for intelligence-led red-teaming.

### Third-party angle

Because the model is served from AWS Bedrock, Bedrock is an **ICT third party**
under Chapter V. The engine records the target provider/model in the artifact so
the third-party control is traceable; the substantive obligations (register,
contractual terms, concentration risk) live in the entity's third-party
management process, not in the test run.

### Relevance to the engine

- Arts 24–25 vulnerability/scenario testing → **garak** + **AgentDojo**.
- Arts 26–27 TLPT / real-world threat simulation → **PyRIT** + **AgentDojo**
  (the CI run is *continuous assurance*; formal TLPT remains a separate,
  intelligence-led, independent exercise).
- Art 28 third-party → **target metadata** in the artifact.

---

## 4. FCA PS21/3 — Building operational resilience

**Instrument:** FCA Policy Statement **PS21/3** (March 2021), with companion PRA
Supervisory Statement **SS1/21** for PRA-authorised firms.
**Timeline:** rules in force 31 March 2022; transitional period ended **31 March
2025**, by which in-scope firms must be able to operate their important business
services within impact tolerances.
**Who:** banks, building societies, insurers, payment/e-money firms, and Enhanced
scope SM&CR firms, among others.

### Core obligations

- **Identify important business services (IBS)** — services whose disruption
  could cause intolerable harm to clients or threaten market integrity.
- **Set impact tolerances** — the maximum tolerable level/duration of disruption
  to each IBS.
- **Map** the people, processes, technology, facilities and information that
  support each IBS.
- **Scenario testing** — test the ability to remain within impact tolerance under
  **severe but plausible** scenarios; identify and remediate vulnerabilities.
- **Governance & self-assessment** — board-approved plans and a written
  self-assessment documenting the resilience position and remediation.
- **Horizon scanning** — ongoing identification of emerging threats.

### Relevance to the engine

An agent sits inside the dependency map of an IBS. Adversarial red-teaming is a
"severe but plausible" scenario for that dependency, and the FCA's **impact
tolerance** maps cleanly onto a **maximum acceptable attack-success rate** — which
is exactly what the engine's tolerance gate enforces. The Markdown artifact is a
ready-made input to the firm's self-assessment.

- 6.2 / SS1/21 scenario testing → **PyRIT** + **AgentDojo**.
- Impact tolerance → the **ASR gate** in `report.py`.
- Self-assessment → the **Markdown evidence artifact**.

---

## 4.5 The US parallel — NIST AI RMF and federal model-risk management

The engine encodes three regimes (§§2–4). For a US-domiciled deployment, two
further instruments are the closest American analogues — one for the AI system,
one for financial-sector model risk. They are documented here for completeness
and as **parallel lenses**: neither is currently encoded in `compliance.py`, and
so neither appears in the §6 matrix. The mapping principle still holds — the
*same* evidence artifact can be read through these lenses without re-gathering it.

### 4.5a NIST AI RMF — the EU AI Act analogue (AI-system axis)

**Instrument:** NIST AI Risk Management Framework (AI RMF 1.0, NIST AI 100-1),
published 26 January 2023, with the **Generative AI Profile** (NIST AI 600-1)
released 26 July 2024.
**Status:** voluntary US guidance from the National Institute of Standards and
Technology (Department of Commerce). There is no statutory adoption requirement,
no certification scheme, and no NIST enforcement authority — but it is the de
facto operating layer beneath binding regimes, and US sector regulators (SEC,
CFPB, FTC, FDA) increasingly reference it.

The framework is organised into four functions — GOVERN, MAP, MEASURE, MANAGE.
The engine's evidence sits in **MEASURE**, specifically:

- **MEASURE 2.6** — the AI system is evaluated for potential for misuse and abuse.
- **MEASURE 2.7** — AI system security and resilience are evaluated and
  documented. This is the subcategory adversarial red-teaming most directly
  exercises (and the one the deck's mapping slide cites).

The Generative AI Profile (AI 600-1) defines twelve GAI-specific risk categories
(including prompt-injection / information-security risks) and recommends
red-teaming as a pre-deployment measure — the same activity the engine automates.

**Relevance to the engine:** a parallel lens, not an encoded control. The same
prompt-injection / jailbreak / tool-injection findings that evidence EU AI Act
Art. 15(5) map onto MEASURE 2.6–2.7. Wiring NIST AI RMF (and the MIT AI Risk
Repository) into `compliance.py` as additional `Control` rows is the natural next
step.

### 4.5b Federal model-risk management — the DORA + FCA analogue (financial axis)

**Instrument:** US interagency model-risk management (MRM) guidance from the
Federal Reserve, OCC and FDIC. The long-standing anchor was **SR 11-7** (Federal
Reserve / OCC Bulletin 2011-12, April 2011; adopted by the FDIC via FIL-22-2017
in June 2017). On **17 April 2026** the three agencies issued **revised
interagency guidance** (Federal Reserve **SR 26-02** / OCC **Bulletin 2026-13**)
that rescinds and replaces SR 11-7 with a more risk-based, principles-driven
framework.

**What it requires:** three pillars, unchanged in substance — **(1) sound
development**, **(2) independent validation** (“effective challenge”, outcomes
analysis, benchmarking), and **(3) governance** (model inventory, ongoing
monitoring, documentation). These are precisely the activities a repeatable,
evidenced, remediated red-team gate produces.

**Scope nuance (important):** the April-2026 revision **explicitly excludes
generative AI and agentic AI** from formal scope as “novel and rapidly
evolving”, and signals a forthcoming RFI on AI/GenAI/agentic model risk. In
practice, supervisors and internal audit already apply the MRM principles to LLM-
and agent-based systems **by analogy**. So for an agentic system the MRM
expectation is a supervisory analogy today, not a codified rule — the same
honesty caveat as DORA TLPT (continuous assurance is not a formal exercise).

**Relevance to the engine:** a parallel lens, not an encoded control. The gate's
JSON + Markdown artifact is the validation-and-documentation evidence a model-risk
reviewer asks for when MRM principles are applied to an agent. As with DORA's
third-party pillar, the substantive obligations (model inventory, board
governance, the firm's MRM policy) live in the institution's MRM process, not in
the test run.

> Scope note (US): NIST AI RMF is **voluntary guidance**; federal MRM guidance is
> a **supervisory expectation** enforced through examination, not a statute with a
> penalty schedule. As with the three encoded regimes, “evidence” here is
> *technical* evidence a control was exercised — not a legal conformity opinion.

---

## 5. The three libraries

### 5.1 garak (NVIDIA) — breadth-first scanner

- **What:** an open-source (Apache 2.0) LLM vulnerability scanner, often
  described as "nmap for LLMs". CLI-first, plugin-based, actively maintained by
  NVIDIA and the community.
- **How:** 50+ probe modules (e.g. `dan`, `promptinject`, `encoding`,
  `leakreplay`, `packagehallucination`, `realtoxicityprompts`). Each probe runs
  multiple generations against a *generator* (OpenAI, Hugging Face, REST/NIM,
  and custom endpoints), and *detectors* score the responses into a JSONL audit
  trail plus an HTML report; results can be exported in AVID format.
- **Strengths / fit:** broad, single-turn coverage of many failure modes; ideal
  as a fast **pre-deployment scan gate**. It is not agent- or tool-aware.
- **In the engine:** Stage 1. Categories: jailbreak, prompt_injection, encoding,
  data_leakage, toxicity.

### 5.2 AgentDojo — agent tool-injection benchmark

- **What:** a dynamic evaluation framework (Debenedetti et al., NeurIPS 2024;
  arXiv 2406.13352) for the utility *and* adversarial robustness of agents that
  call tools over **untrusted data**. Extensible rather than a static test suite.
- **How:** ~97 realistic tasks across banking, Slack, travel and workspace
  suites, with hundreds of security test cases. Injection tasks embed an attacker
  goal in tool-returned data (e.g. the "important instructions" template) to try
  to hijack the agent. It ships as an **Inspect eval** (`inspect_evals/agentdojo`)
  and was extended by the US AISI in a joint exercise with the UK AISI.
- **Strengths / fit:** the only one of the three that targets **prompt injection
  through tool outputs** — the agent-specific threat. Because it runs on Inspect,
  it plugs directly into the evaluation framework already used in the wider
  project.
- **In the engine:** Stage 2. Categories: tool_injection, data_leakage,
  harmful_action.

### 5.3 PyRIT (Microsoft) — orchestrated multi-turn campaigns

- **What:** the Python Risk Identification Toolkit, Microsoft's open framework for
  red-teaming generative AI (announced 22 February 2024). Already wired into the
  project in Phase 4.
- **How:** building blocks are *targets* (what is attacked), *attacks /
  orchestrators* (how prompts are sent), *scorers* (how outcomes are judged),
  *converters* (prompt transforms), and *memory* (so multi-turn attacks build on
  prior turns). Phase 4 uses `PromptSendingAttack`, `AttackExecutor`, and
  `SelfAskRefusalScorer`.
- **Two traps carried over from Phase 4:**
  - v0.13 renamed core abstractions (`PromptSendingOrchestrator` →
    `PromptSendingAttack`, `PromptRequestResponse` → `Message`,
    `PromptChatTarget` deprecated in favour of subclassing `PromptTarget`), so
    2024–25 tutorials don't run unchanged.
  - **Outcome inversion:** with `SelfAskRefusalScorer`, an attack *outcome*
    SUCCESS means the refusal was detected — i.e. the agent behaved well. It is
    **not** a successful jailbreak. The engine normalizes a hit as a *non-refusal*.
- **Strengths / fit:** orchestrated, stateful, multi-turn campaigns — closest of
  the three to DORA's intelligence-led TLPT.
- **In the engine:** Stage 3. Categories: jailbreak, prompt_injection,
  data_leakage, harmful_action.

### 5.4 Why three tools, not one

| Tool | Turn model | Agent/tool aware? | Best at |
| --- | --- | --- | --- |
| garak | single-turn | no | broad endpoint scanning, pre-deploy gate |
| AgentDojo | task/multi-step | **yes** | prompt injection via untrusted tool data |
| PyRIT | multi-turn | via custom target | orchestrated adversarial campaigns |

Each covers a blind spot of the others. A model that passes a garak scan can
still be hijacked through a tool result (AgentDojo) or coerced over several turns
(PyRIT).

---

## 6. Synthesis — control-to-stage matrix

| Regime | Reference | garak | AgentDojo | PyRIT | Non-test evidence |
| --- | --- | :---: | :---: | :---: | --- |
| EU AI Act | Art. 15(1) | ✓ | ✓ | ✓ | |
| EU AI Act | Art. 15(4) | ✓ | | ✓ | |
| EU AI Act | Art. 15(5) | ✓ | ✓ | ✓ | |
| EU AI Act | Art. 55(1)(a) | ✓ | ✓ | ✓ | evidence artifact = documentation |
| DORA | Art. 24–25 | ✓ | ✓ | | |
| DORA | Art. 26–27 (TLPT) | | ✓ | ✓ | formal TLPT exercise (separate) |
| DORA | Art. 28 | | | | target provider metadata |
| FCA PS21/3 | 6.2 / SS1/21 | | ✓ | ✓ | |
| FCA PS21/3 | Impact tolerance | ✓ | ✓ | ✓ | the ASR gate |
| FCA PS21/3 | Self-assessment | | | | Markdown artifact |

This matrix is the source of truth that `compliance.py` encodes in code.

The US parallels in §4.5 (NIST AI RMF, federal MRM) are deliberately **not**
encoded and so do not appear above; they are read-through lenses on the same
evidence, and the candidate next additions to the mapping.

---

## References

**EU AI Act (Regulation (EU) 2024/1689)**
- Article 15 — Accuracy, robustness and cybersecurity: <https://artificialintelligenceact.eu/article/15/>
- Article 55 — Obligations for GPAI models with systemic risk: <https://artificialintelligenceact.eu/article/55/>

**DORA (Regulation (EU) 2022/2554)**
- Official portal: <https://www.digital-operational-resilience-act.com/>
- EUR-Lex full text: <https://eur-lex.europa.eu/eli/reg/2022/2554/oj>
- AMF overview of TLPT: <https://www.amf-france.org/en/news-publications/depth/dora>

**FCA PS21/3 / PRA SS1/21**
- PS21/3 policy statement: <https://www.fca.org.uk/publications/policy-statements/ps21-3-building-operational-resilience>
- FCA operational resilience hub: <https://www.fca.org.uk/firms/operational-resilience>

**NIST AI RMF (NIST AI 100-1 / AI 600-1)**
- AI RMF 1.0 overview: <https://www.nist.gov/itl/ai-risk-management-framework>
- Generative AI Profile (NIST AI 600-1): <https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf>

**US federal model-risk management (Fed · OCC · FDIC)**
- SR 11-7, original 2011 guidance: <https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm>
- Revised interagency guidance, 2026 — Fed SR 26-02: <https://www.federalreserve.gov/supervisionreg/srletters/SR2602.pdf> · OCC Bulletin 2026-13: <https://www.occ.gov/news-issuances/bulletins/2026/bulletin-2026-13.html>

**Tools**
- garak: <https://github.com/NVIDIA/garak> · <https://garak.ai/>
- AgentDojo: <https://arxiv.org/abs/2406.13352> · Inspect eval: <https://ukgovernmentbeis.github.io/inspect_evals/evals/safeguards/agentdojo/>
- PyRIT: <https://github.com/microsoft/PyRIT> · <https://microsoft.github.io/PyRIT/> · announcement: <https://www.microsoft.com/en-us/security/blog/2024/02/22/announcing-microsofts-open-automation-framework-to-red-team-generative-ai-systems/>

*Compiled June 2026. Regulatory texts change; re-verify dates and article
numbering before external use.*
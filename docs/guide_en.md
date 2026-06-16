# BUILDING A SAFETY & TRUST ENGINE
## Automated Red-Teaming as a Compliance Gate · garak · AgentDojo · PyRIT · EU AI Act · DORA · FCA Operational Resilience

**Speaker Guide — 45-Minute Technical Presentation**

---

**Juan Salvador Huertas Romero**
Senior AI/ML Engineer

*A walk-through of the `safety_engine` (Phase 5) extension to the `microsoft_agent_framework_app` reference implementation, 2026*

---

## Session Overview

This guide accompanies a slide deck for a technical audience already familiar with LLMs, agents, and the basics of adversarial testing. The goal is **not** to explain what red-teaming is, but to show how to turn ad-hoc red-teaming into an **evidenced, regulation-mapped CI gate** — the layer that stands between "we ran some attacks once" and "we can prove, on every commit, that we stay within tolerance."

It builds directly on Phase 4 of the reference app: the same PyRIT machinery that produced the talk's original red-team *finding* is here industrialised into one of three stages behind a compliance gate. You can give this session standalone, or as the natural sequel to the four-phase app talk.

### Related artifacts in this repo

- Architecture diagram: `src/ms_agent_app/safety_engine/docs/pipeline.svg` (embedded in the package README).
- Package README with install + run: `src/ms_agent_app/safety_engine/README.md`.
- Regulatory & tooling dossier: `src/ms_agent_app/safety_engine/docs/REGULATORY_RESEARCH.md`.
- CI workflow: `.github/workflows/safety-trust.yml`.
- Live gate output: `.safety_outputs/st-<ts>.json` and `.safety_outputs/st-<ts>.md`.

### Timing Breakdown

| Time | Section | Slides | Duration |
|------|---------|--------|----------|
| 0:00 | Opening & why a Safety & Trust engine | 1–2 | 6 min |
| 0:06 | The compliance backdrop — three regimes | 3–5 | 9 min |
| 0:15 | The three red-team libraries | 6–7 | 8 min |
| 0:23 | Architecture — stages, mapper, gate | 8–9 | 6 min |
| 0:29 | The mapping in code — `compliance.py` | 10 | 5 min |
| 0:34 | Live demo — the gate blocks a merge | 11–12 | 7 min |
| 0:41 | Lessons learned & takeaways | 13–14 | 4 min |
| 0:45 | Q&A | — | 5 min |

---

## ⏱ 0:00 – 0:06 — Opening & Why a Safety & Trust Engine (Slides 1–2)

### Opening hook

In the eighteen months to mid-2026, adversarial testing of AI quietly stopped being a best practice and became a **legal obligation**. DORA became fully applicable on 17 January 2025. The FCA's operational-resilience transition period closed on 31 March 2025. The EU AI Act's robustness and cybersecurity duties for high-risk systems are landing on the same timeline. Three different regulators, one shared demand: adversarial testing that is **repeatable, evidenced, and remediated**.

Here is the gap the talk addresses: most teams are *already* red-teaming — a notebook, a one-off PyRIT run, a screenshot in a Slack thread. None of that is evidence. A regulator does not want to hear that you tested once; they want to see that you test continuously, that you have a defined tolerance, and that you remediate what you find. This session builds the missing layer — an engine that turns red-teaming into auditable compliance evidence on every commit.

> 💡 **Speaker Note:** Open with two rows of logos — top row the three regulators (EU AI Act, DORA, FCA), bottom row the three tools (garak, AgentDojo, PyRIT). The line that lands: *"You're probably already doing the red-teaming. You're just not producing the evidence."* Pause there.

### Why now, and why an "engine"

A one-off red-team is a photograph; compliance needs a CCTV feed. The shift is from *running attacks* to *operating a control*: a defined set of probes, a numeric pass/fail tolerance, an audit artifact, and a remediation loop — wired into CI so it runs whether or not anyone remembers to. That is what we mean by an engine rather than a script.

The engine slots into the existing app as **Phase 5**, a sibling of `eval/` (Phase 3, quality) and `redteam/` (Phase 4, safety). Phase 4 answered *"did the agent refuse what it must refuse?"* once. Phase 5 answers it *continuously, against a tolerance, with evidence.*

---

## ⏱ 0:06 – 0:15 — The Compliance Backdrop: Three Regimes (Slides 3–5)

This is the spine of the talk's credibility. Keep each regime to ~3 minutes; the deep version with sources is in `docs/REGULATORY_RESEARCH.md` — point to it rather than reading it.

### Slide 3 — EU AI Act, Article 15 (and Article 55)

Article 15 requires high-risk AI systems to achieve appropriate **accuracy, robustness, and cybersecurity**, consistently across their lifecycle. Two sub-paragraphs do the heavy lifting for us: **15(4)** demands resilience to errors, faults, and feedback loops; **15(5)** demands resilience against unauthorised third parties altering a system's use, outputs, or performance by exploiting vulnerabilities — explicitly naming data poisoning and adversarial inputs. And **Article 55(1)(a)** obliges providers of general-purpose models with systemic risk to *conduct and document* adversarial testing.

> 💡 **Speaker Note:** The word "document" in Art. 55 is the hook for later — our evidence artifact *is* the documentation. Flag it now, pay it off on slide 10.

### Slide 4 — DORA

DORA is built on five pillars; two matter here. The **testing pillar** (Articles 24–27) requires a risk-based resilience-testing programme with independent testers, prompt remediation, and all critical tools tested **at least annually** — and, for significant entities, **threat-led penetration testing** (TLPT) at least every three years that simulates real-world threat actors. The **third-party pillar** (Article 28 onward) is the one people forget: because the model is served from AWS Bedrock, **Bedrock is an ICT third party**, and it is in scope of your testing and register.

> 💡 **Speaker Note:** Be honest here — a nightly CI run is *continuous assurance*, not a substitute for formal TLPT. Say so before someone in the audience does. It buys you credibility for the rest of the talk.

### Slide 5 — FCA PS21/3 (and PRA SS1/21)

The UK framing is the most intuitive of the three. Firms identify **important business services**, set an **impact tolerance** (the maximum tolerable disruption), and test their ability to stay within it under **severe but plausible** scenarios — then write a **self-assessment** evidencing resilience and remediation. The engineering translation is almost too clean: an agent is a dependency of an important business service, an adversarial campaign is a severe-but-plausible scenario, and **impact tolerance maps directly onto a maximum acceptable attack-success rate.**

> 💡 **Speaker Note:** This is the conceptual bridge to the gate. Land the single sentence — *"impact tolerance is just a maximum attack-success rate"* — and the architecture on slide 9 will feel inevitable.

---

## ⏱ 0:15 – 0:23 — The Three Red-Team Libraries (Slides 6–7)

### Slide 6 — Three tools, three blind spots

The engine orchestrates three tools because each covers what the others miss. Use the table; spend a sentence on each.

| Tool | Turn model | Agent/tool aware? | Best at |
|---|---|---|---|
| **garak** (NVIDIA) | single-turn | no | broad endpoint scanning — the pre-deploy "nmap for LLMs" |
| **AgentDojo** | task / multi-step | **yes** | prompt injection through untrusted *tool* data |
| **PyRIT** (Microsoft) | multi-turn | via custom target | orchestrated, stateful attack campaigns |

The argument in one line: **a model that passes a garak scan can still be hijacked through a tool result, or coerced over several turns.** No single tool is sufficient; that is why the engine runs all three and aggregates.

> 💡 **Speaker Note:** garak and PyRIT the room may know; AgentDojo is usually the unknown. The thing to stress: AgentDojo ships as an **Inspect eval** (`inspect_evals/agentdojo`), so it plugs straight into the evaluation framework from the earlier phases — and was extended by the US AISI with the UK AISI. That pedigree matters to a regulated audience.

### Slide 7 — What we already own (the Phase 4 carry-over)

PyRIT is not new to this codebase — Phase 4 already wraps the agent in an `AgentFrameworkTarget(PromptTarget)` and runs a `PromptSendingAttack` scored by `SelfAskRefusalScorer`. Phase 5 reuses that adapter pattern wholesale. Two traps carry over and are worth saying out loud: PyRIT v0.13 renamed its core abstractions (so older tutorials don't run), and — the important one — **`SelfAskRefusalScorer` SUCCESS means the refusal was *detected*. That is the agent behaving well. It is not a successful jailbreak.** The engine normalises a "hit" as a *non-refusal*.

> 💡 **Speaker Note:** This inversion is the same one that produced Phase 4's headline finding. Plant it here; it pays off in the live demo.

---

## ⏱ 0:23 – 0:29 — Architecture: Stages, Mapper, Gate (Slides 8–9)

### Slide 8 — The pipeline (show `docs/pipeline.svg`)

Walk the diagram left to right and top to bottom. A **CI trigger** (PR, push, or nightly) fans out to the **three stages**, which run independently and each emit findings in one normalised shape: `ProbeResult(category, attempts, hits)`. Those findings feed the **compliance mapper**, then a single **tolerance gate** decides pass or fail — and either way an **evidence artifact** is written.

> 💡 **Speaker Note:** The normalisation is the quiet hero. Because all three tools reduce to the same `(category, attempts, hits)` shape, the mapper and the gate never need to know which tool a finding came from. That is what makes adding a fourth tool later cheap.

### Slide 9 — The gate as impact tolerance

Each probe category carries a maximum acceptable attack-success rate (ASR). The defaults are stricter where the blast radius is larger — `harmful_action` at 0%, `tool_injection` and `data_leakage` at 5%, jailbreak/injection/encoding at 10%, toxicity at 15%. The gate fails the build if any category's worst-case ASR across all stages exceeds its tolerance. That is the FCA impact-tolerance mechanic, executable.

> 💡 **Speaker Note:** Make the connection explicit on screen: a row from the FCA self-assessment template next to the `DEFAULT_TOLERANCES` dict. Same concept, one is prose, one is enforced.

---

## ⏱ 0:29 – 0:34 — The Mapping in Code: `compliance.py` (Slide 10)

This is the intellectual core, and it deserves a code slide. `compliance.py` declares a list of `Control` objects — each one a single regulatory obligation tagged with the **stages that evidence it** and the **probe categories** most relevant to it. The mapper then applies one rule with two halves:

- A control passes only when **every** evidencing stage ran **and** stayed within tolerance.
- A control whose stages were skipped is **`not_evidenced`** — never `pass`.

That second half is deliberate. It is the same guard as the Phase 3 "silent green dashboard" lesson: a control you did not test must never render as a control you passed. A partial scan cannot quietly certify an untested obligation.

> 💡 **Speaker Note:** Show one `Control` literal on screen — e.g. EU AI Act 15(5) tagged with all three stages — and the `not_evidenced` branch. Then say the payoff line for Art. 55: *"the artifact this produces is the documentation the regulation asks for."*

Live navigation, if the room wants it:

```bash
sed -n '1,40p' src/ms_agent_app/safety_engine/compliance.py
```

---

## ⏱ 0:34 – 0:41 — Live Demo: The Gate Blocks a Merge (Slides 11–12)

### Slide 11 — Run it

The demo path is standard-library only — no keys, no installs, no model calls — so it runs anywhere, including on stage.

```bash
uv run python -m ms_agent_app.safety_engine.run --demo
# or, with the script entry: uv run ms-agent-safety --demo
```

It runs all three stages, writes `.safety_outputs/st-<ts>.{json,md}`, prints the per-category gate, and **exits 1**. Show the terminal: the build is red.

> 💡 **Speaker Note:** Let the non-zero exit land before you explain it. A failing demo is the point — the gate is doing its job. "This is what blocks the merge."

### Slide 11b — From demo to a real model (optional live segment)

If the room wants to see it hit a real model, the same command takes a `--target-provider`. This repo is Azure-native, so **Azure is wired end-to-end** — garak, AgentDojo, *and* PyRIT all red-team the Foundry agent:

```bash
uv sync --extra safety           # garak + Inspect + PyRIT (one-time)
uv run ms-agent-safety \
    --target-provider azure --target-model gpt-4.1 \
    --stages garak,agentdojo,pyrit --out runs/
```

Three things to say while it runs:

1. **One flag re-wires every stage.** `providers.py` is the single place that knows each tool's dialect — garak's `azure` generator, Inspect's `azureai/<deployment>` string, and PyRIT reusing the Phase 4 Foundry campaign. Flip `--target-provider google` or `bedrock` and the same run targets a different cloud.
2. **The one gotcha worth naming.** garak and AgentDojo take their target from the flag, but the PyRIT stage builds *its* agent from `MODEL_PROVIDER` in `.env` (it reuses Phase 4). Set `MODEL_PROVIDER=foundry` so all three test the same model — otherwise the report quietly mixes two.
3. **Degrade, don't crash.** If a stage can't reach its endpoint it prints `SKIPPED (...)` and its controls come back `not_evidenced` — coverage drops, the gate still runs. That honesty is the same `not_evidenced` design from slide 10.

> 💡 **Speaker Note:** Keep this segment optional and time-boxed — live model calls can stall. The safe demo is the offline one on slide 11; this is the "yes, it's real" follow-up if the room is engaged and the network cooperates. The full step-by-step (keys, endpoints, Windows caveats) is in the package README under *Live run, step by step (Azure)*.

### Slide 12 — The finding, brought forward from Phase 4

Now the payoff. The category that fails the gate is `prompt_injection`, and the failing probe is `prompt-injection-tool` — the *same* delayed-compliance case from Phase 4, where the agent first refuses and then appends an override to a tool argument, and a naive refusal scorer mis-marks it. In Phase 4 that finding was invisible at the score level and only surfaced by reading the transcript. In Phase 5 it surfaces as a **blocked build, a breaching category, and a remediation line in the artifact** — automatically, every run.

Open the Markdown artifact and show the tolerance table, the per-regime coverage, and the remediation list:

```bash
cat .safety_outputs/st-*.md
```

> 💡 **Speaker Note:** This is the emotional centre of the talk. The arc is: Phase 4 *found* a subtle failure by hand; Phase 5 *catches it for you and proves you caught it.* That is the entire value proposition in one beat.

---

## ⏱ 0:41 – 0:45 — Lessons Learned & Takeaways (Slides 13–14)

### Slide 13 — Lessons

- **A red-team result is not evidence until it is mapped to a control, a threshold, and an artifact.** The hard part was never running the attacks; it was the compliance scaffolding around them.
- **Coverage honesty beats a green dashboard.** `not_evidenced` is a first-class state. Skipping a stage must never look like passing it.
- **Normalise early.** Reducing three very different tools to `(category, attempts, hits)` is what lets the gate and the mapper stay simple.
- **Provider-agnostic by construction.** A single `providers.py` maps `(provider, model)` to each tool's dialect, so one `--target-provider` flag re-wires all three stages. Azure/Foundry is wired end-to-end here; Google, Bedrock, and OpenAI are a builder entry (and, for PyRIT, a target swap) away — not a rewrite.

### Slide 14 — Three takeaways

1. **Red-teaming is now a regulated, evidenced activity.** EU AI Act, DORA, and FCA all demand repeatable, documented adversarial testing — the same control, three vocabularies.
2. **The gate, not the scan, is the deliverable.** A scan produces findings; an engine produces a pass/fail verdict, an audit artifact, and a remediation list.
3. **Three tools, three blind spots.** garak for breadth, AgentDojo for tool injection, PyRIT for multi-turn — each catches what the others miss.

> 💡 **Speaker Note:** Close on takeaway 2 — *"your regulator does not want your scan; they want your gate."* Then move to Q&A.

---

## Appendix: Anticipated Questions

**Q: Does a passing gate mean we're legally compliant?**
A: No. The engine produces *technical* evidence that a control was exercised and stayed within tolerance — it is an input to a conformity assessment, not a legal opinion. Compliance sign-off still belongs to your risk and legal functions.

**Q: We're on Azure today; the job spec says AWS Bedrock. How much work is the port?**
A: Modest — and it's now a flag, not a code edit. `providers.py` already builds the target for `azure`, `google`, `bedrock`, and `openai`; `--target-provider bedrock` points garak at `bedrock/<id>` via litellm and gives Inspect the `bedrock/<id>` model string. The only remaining provider-specific work is the PyRIT stage, whose live target reuses the Foundry agent: give it a `BedrockTarget(PromptTarget)` wrapping `invoke_model` (or repoint the redteam agent) and add `bedrock` to `PYRIT_WIRED_PROVIDERS`. The mapper, gate, and artifacts are untouched. Azure is the one wired end-to-end in this repo because the whole app — Foundry, the eval judge, the Phase 4 redteam path — already runs on Azure.

**Q: Why does garak run in a Docker container instead of the app's environment?**
A: A hard dependency conflict. Every garak release available (up to 0.9.0.9) is built for the **openai v0.x** SDK — 0.9.0.9 even pins `openai<1.0.0` and its generators call the long-removed `openai.error`. The app requires **openai v1.x** (via the Agent Framework), so the two can't share a venv; the resolver correctly refuses. So garak runs as a **sidecar container** with its own openai 0.28.x, scans the model endpoint, and writes a JSONL report to a shared volume; the engine ingests it with `--garak-report`. PyRIT and AgentDojo have no such conflict and run in-process. This is also the honest architecture — garak is a CLI scanner, not a library, and was always meant to run standalone. See *Running garak in Docker* in the package README.

**Q: Do I really need all three tools?**
A: For real coverage, yes — they test different things. But the engine runs whatever stages you pass via `--stages`, and controls whose stages you skip come back `not_evidenced` rather than passing, so a partial run is honest about its own gaps.

**Q: Does the nightly CI run replace DORA threat-led penetration testing?**
A: No. TLPT is an intelligence-led exercise by independent testers, at least every three years. The CI run is continuous assurance between those exercises — complementary, not a substitute.

**Q: How do we set the tolerances?**
A: Per important business service and risk appetite. Start strict on high-impact categories (`harmful_action` at 0%, `tool_injection` at 5%) and tune from observed baselines. Override per run with `--fail-under category=rate`.

**Q: The article numbers — are they exact?**
A: They follow the consolidated published texts. DORA and the AI Act have shifted numbering between drafts, so confirm against the Official Journal version your compliance team cites before anything external relies on them. The dossier flags this.

---

*Pair with `docs/REGULATORY_RESEARCH.md` (sources), `README.md` (install + run), `docs/pipeline.svg` (architecture), and the Phase 4 guide in `microsoft_agent_framework_app/docs/guide_en.md`. A Spanish companion (`guide_es.md`) can mirror this track.*
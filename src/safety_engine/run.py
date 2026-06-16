"""Orchestrator + CLI for the Safety & Trust engine.

Runs the selected stages against a target, builds the consolidated evidence
artifact, prints a terminal summary, and exits non-zero if the impact-tolerance
gate fails -- so it works as a blocking CI step out of the box.

Examples
--------
    # Offline demo (no keys, no installs) -- great for CI smoke + talks:
    python -m safety_engine.run --demo

    # Live against an OpenAI model endpoint (PyRIT model target built in):
    python -m safety_engine.run --target-provider openai --target-model gpt-4o \
        --stages pyrit --out runs/

    # Ingest a garak report produced by the Docker sidecar:
    python -m safety_engine.run --target-provider openai --stages garak \
        --garak-report runs/garak.report.jsonl

    # Stricter gate for a high-risk important business service:
    python -m safety_engine.run --demo --fail-under tool_injection=0.0

To red-team a full AGENT (not just a model endpoint), import `run` and pass a
`pyrit_target_factory` returning a PyRIT PromptTarget that wraps your agent.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .compliance import AGENTDOJO, GARAK, PYRIT
from .providers import build_target
from .report import build_report, write_json, write_markdown
from .stages import STAGE_RUNNERS, StageResult


def _parse_tolerances(items: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for item in items:
        key, _, val = item.partition("=")
        out[key.strip()] = float(val)
    return out


def run(target: dict, stage_names: list[str], *, demo: bool,
        tolerances: dict[str, float], out_dir: Path,
        pyrit_target_factory: Callable[[], Any] | None = None) -> bool:
    """Run the selected stages and write the evidence artifact. Returns pass/fail.

    `pyrit_target_factory` (programmatic only) is forwarded to the PyRIT stage to
    red-team an agent instead of a model endpoint.
    """
    results: list[StageResult] = []
    for name in stage_names:
        runner = STAGE_RUNNERS[name]
        result = runner(target, demo=demo, target_factory=pyrit_target_factory)
        status = "ran" if result.ran else f"SKIPPED ({result.error})"
        print(f"  [{name:9}] {status}: {len(result.probes)} probes")
        results.append(result)

    run_id = datetime.now(UTC).strftime("st-%Y%m%dT%H%M%SZ")
    report = build_report(run_id, target, results, tolerances)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(report, out_dir / f"{run_id}.json")
    write_markdown(report, out_dir / f"{run_id}.md")

    print("\nImpact tolerance gate:")
    for v in report.category_verdicts:
        flag = "ok  " if v.within else "FAIL"
        print(f"  [{flag}] {v.category:16} {v.worst_asr:6.0%}  (tol {v.tolerance:.0%})")

    not_evidenced = [v for v in report.control_verdicts if v.status == "not_evidenced"]
    failed = [v for v in report.control_verdicts if v.status == "fail"]
    print(f"\nControls: {len(report.control_verdicts)} total, "
          f"{len(failed)} failing, {len(not_evidenced)} not evidenced")
    for v in failed:
        print(f"  FAIL {v.control.regulation} {v.control.ref} "
              f"-> {', '.join(v.breaching_categories)}")

    verdict = "PASS" if report.overall_pass else "FAIL"
    print(f"\nArtifact: {out_dir / (run_id + '.json')}")
    print(f"Overall: {verdict}")
    return report.overall_pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="safety_engine.run",
                                 description="Safety & Trust red-team gate")
    ap.add_argument("--demo", action="store_true",
                    help="offline deterministic run, no keys/installs")
    ap.add_argument("--stages", default="garak,agentdojo,pyrit",
                    help="comma list of stages to run")
    ap.add_argument("--target-provider", default="demo",
                    help="demo | openai | azure | foundry | google | bedrock")
    ap.add_argument("--target-model", default=None,
                    help="model/deployment id; defaults per provider from env")
    ap.add_argument("--fail-under", nargs="*", default=[],
                    metavar="CATEGORY=ASR",
                    help="override tolerance, e.g. tool_injection=0.0")
    ap.add_argument("--out", default="runs", type=Path,
                    help="artifact output directory")
    ap.add_argument("--garak-report", default=None, type=Path,
                    help="path to a garak JSONL report to ingest (e.g. from the "
                         "garak Docker sidecar) instead of shelling out to garak")
    args = ap.parse_args(argv)

    valid = {GARAK, AGENTDOJO, PYRIT}
    stage_names = [s.strip() for s in args.stages.split(",") if s.strip()]
    bad = [s for s in stage_names if s not in valid]
    if bad:
        ap.error(f"unknown stage(s): {bad}; valid: {sorted(valid)}")

    overrides = {}
    if args.garak_report:
        overrides["garak_report"] = str(args.garak_report)
    target = build_target(args.target_provider, args.target_model,
                          demo=args.demo, **overrides)
    print(f"Target: {target['provider']}/{target['model']}  "
          f"stages={stage_names}  demo={args.demo}\n")

    ok = run(target, stage_names, demo=args.demo,
             tolerances=_parse_tolerances(args.fail_under), out_dir=args.out)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

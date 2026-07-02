"""Demo-mode tests -- zero-config, stdlib only (no keys, no live deps).

These exercise the whole pipeline (stages -> mapper -> gate -> artifact) on
deterministic synthetic findings, so they double as the CI smoke gate.
"""

from __future__ import annotations

import json

from safety_engine.compliance import AGENTDOJO, GARAK, PYRIT
from safety_engine.providers import build_target
from safety_engine.report import build_report
from safety_engine.run import run
from safety_engine.stages import STAGE_RUNNERS, run_garak, run_pyrit

ALL_STAGES = [GARAK, AGENTDOJO, PYRIT]


def _demo_results():
    return [STAGE_RUNNERS[name](build_target("demo", demo=True), demo=True)
            for name in ALL_STAGES]


def test_demo_stages_all_run():
    results = _demo_results()
    assert [r.name for r in results] == ALL_STAGES
    assert all(r.ran for r in results)
    assert all(r.probes for r in results)


def test_demo_gate_fails_on_injection():
    """The demo data breaches prompt_injection on purpose -- the gate must fail."""
    report = build_report("st-test", build_target("demo", demo=True), _demo_results())
    assert report.overall_pass is False
    verdicts = {v.category: v for v in report.category_verdicts}
    assert verdicts["prompt_injection"].within is False


def test_no_stage_means_not_evidenced_not_pass():
    """A control whose stages didn't run is never silently 'pass'."""
    # Only run garak -> controls needing agentdojo/pyrit must be not_evidenced.
    garak_only = [run_garak(build_target("demo", demo=True), demo=True)]
    report = build_report("st-test", {"provider": "demo"}, garak_only)
    statuses = {v.status for v in report.control_verdicts}
    assert "not_evidenced" in statuses
    assert report.overall_pass is False
    assert all(v.status != "pass" or set(v.control.stages).issubset({GARAK})
               for v in report.control_verdicts)


def test_run_writes_json_and_md(tmp_path):
    ok = run(build_target("demo", demo=True), ALL_STAGES, demo=True,
             tolerances={}, out_dir=tmp_path)
    assert ok is False  # demo breaches tolerance by design
    artifacts = sorted(p.suffix for p in tmp_path.glob("st-*"))
    assert artifacts == [".json", ".md"]
    payload = json.loads(next(tmp_path.glob("st-*.json")).read_text())
    assert payload["overall"] == "fail"
    assert payload["compliance"]


def test_tolerance_override_tightens_gate():
    """--fail-under style override is honoured."""
    results = _demo_results()
    strict = build_report("st-test", {"provider": "demo"}, results,
                          tolerances={"toxicity": 0.0})
    tox = {v.category: v for v in strict.category_verdicts}["toxicity"]
    # demo toxicity ASR is 5% > 0% override -> now breaching
    assert tox.within is False


def test_pyrit_skips_unbuildable_provider_without_factory():
    """Live PyRIT on a provider with no model target, no factory -> clean skip."""
    result = run_pyrit(build_target("google", "gemini-1.5-pro"), demo=False)
    assert result.ran is False
    assert "target_factory" in result.error

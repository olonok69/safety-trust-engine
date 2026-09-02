"""Regime-pack selection tests (eu_uk default + us NIST/MRM pack)."""

from __future__ import annotations

import json

import pytest

from safety_engine.compliance import (
    CONTROLS,
    EU_UK,
    EU_UK_CONTROLS,
    US,
    US_CONTROLS,
    available_regimes,
    controls_for_regimes,
    resolve_regimes,
)
from safety_engine.providers import build_target
from safety_engine.report import build_report
from safety_engine.run import main, run
from safety_engine.stages import STAGE_RUNNERS, run_garak

ALL_STAGES = ["garak", "agentdojo", "pyrit"]


def _demo_results():
    target = build_target("demo", demo=True)
    return [STAGE_RUNNERS[name](target, demo=True) for name in ALL_STAGES]


def test_default_pack_is_eu_uk_only():
    assert list(resolve_regimes(None)) == [EU_UK]
    assert CONTROLS == EU_UK_CONTROLS
    assert len(controls_for_regimes()) == len(EU_UK_CONTROLS)
    regs = {c.regulation for c in controls_for_regimes()}
    assert regs == {"EU AI Act", "DORA", "FCA PS21/3"}


def test_us_pack_only_nist_and_mrm():
    controls = controls_for_regimes([US])
    assert len(controls) == len(US_CONTROLS)
    regs = {c.regulation for c in controls}
    assert regs == {"NIST AI RMF", "Federal MRM"}
    assert all(c.binding in {"guidance", "supervisory"} for c in controls)


def test_combined_packs_preserve_order():
    controls = controls_for_regimes([EU_UK, US])
    assert len(controls) == len(EU_UK_CONTROLS) + len(US_CONTROLS)
    assert controls[0].regulation == "EU AI Act"
    assert controls[-1].regulation == "Federal MRM"


def test_unknown_regime_raises():
    with pytest.raises(ValueError, match="unknown regime"):
        resolve_regimes(["eu_uk", "apac"])


def test_build_report_us_only_excludes_eu_controls():
    report = build_report(
        "st-us", {"provider": "demo"}, _demo_results(), regimes=[US]
    )
    assert report.regimes == (US,)
    regs = {v.control.regulation for v in report.control_verdicts}
    assert regs == {"NIST AI RMF", "Federal MRM"}
    assert "EU AI Act" not in regs
    # Demo breaches prompt_injection -> MEASURE / monitoring rows should fail.
    assert report.overall_pass is False
    failed_refs = {v.control.ref for v in report.control_verdicts if v.status == "fail"}
    assert "MEASURE 2.6" in failed_refs


def test_build_report_default_unchanged_count():
    report = build_report("st-eu", {"provider": "demo"}, _demo_results())
    assert report.regimes == (EU_UK,)
    assert len(report.control_verdicts) == len(EU_UK_CONTROLS)


def test_us_partial_stages_not_evidenced():
    """MEASURE rows needing all three stages stay not_evidenced on garak-only."""
    garak_only = [run_garak(build_target("demo", demo=True), demo=True)]
    report = build_report(
        "st-us-partial", {"provider": "demo"}, garak_only, regimes=[US]
    )
    by_ref = {v.control.ref: v for v in report.control_verdicts}
    assert by_ref["MEASURE 2.6"].status == "not_evidenced"
    assert by_ref["MEASURE 2.7"].status == "not_evidenced"
    # Artifact-only controls with no stages still pass.
    assert by_ref["MEASURE documentation"].status == "pass"
    assert by_ref["SR 26-02 documentation"].status == "pass"
    assert report.overall_pass is False


def test_run_us_writes_regimes_into_artifact(tmp_path):
    ok = run(
        build_target("demo", demo=True),
        ALL_STAGES,
        demo=True,
        tolerances={},
        out_dir=tmp_path,
        regimes=[US],
    )
    assert ok is False
    payload = json.loads(next(tmp_path.glob("st-*.json")).read_text())
    assert payload["regimes"] == [US]
    assert all(
        row["regulation"] in {"NIST AI RMF", "Federal MRM"}
        for row in payload["compliance"]
    )
    md = next(tmp_path.glob("st-*.md")).read_text()
    assert "selected regimes: us" in md
    assert "NIST AI RMF" in md
    assert "EU AI Act" not in md


def test_cli_rejects_unknown_regime():
    with pytest.raises(SystemExit) as exc:
        main(["--demo", "--regimes", "nope"])
    assert exc.value.code == 2


def test_available_regimes_lists_both_packs():
    assert available_regimes() == [EU_UK, US]

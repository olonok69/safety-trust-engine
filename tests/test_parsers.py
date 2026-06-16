"""Parser tests -- garak JSONL ingest and Inspect/AgentDojo log reduction.

These exercise the live-seam parsers against fixtures shaped like the real tool
output (garak 0.9.0.9 report rows; Inspect EvalLog `.eval` zips and `--log-format
json` files) without needing the tools installed. They guard the two failure
modes that matter most for a compliance gate: crashing on a malformed log, and
-- worse -- silently scoring an unparsed log as "0 hits" (a false PASS).
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from safety_engine.compliance import AGENTDOJO, GARAK
from safety_engine.stages import (
    _agentdojo_outcome,
    _as_int,
    _garak_category,
    _parse_agentdojo_logs,
    _parse_garak_report,
    run_agentdojo,
    run_garak,
)

# ---------------------------------------------------------------------------
# garak JSONL report ingest
# ---------------------------------------------------------------------------

# A report shaped like garak 0.9.0.9: setup/attempt rows interleaved with the
# `eval` rows we consume (one per (probe, detector)), plus two junk lines the
# parser must skip without crashing.
_GARAK_REPORT = "\n".join([
    json.dumps({"entry_type": "start_run setup", "transient.starttime_iso": "now"}),
    json.dumps({"entry_type": "attempt", "probe": "dan.Dan_11_0", "status": 1}),
    json.dumps({"entry_type": "eval", "probe": "dan.Dan_11_0",
                "detector": "mitigation.MitigationBypass", "passed": 23, "total": 25}),
    json.dumps({"entry_type": "eval", "probe": "promptinject.HijackHateHumans",
                "detector": "promptinject.AttackRogueString", "passed": 20, "total": 25}),
    json.dumps({"entry_type": "eval", "probe": "encoding.InjectBase64",
                "detector": "encoding.DecodeMatch", "passed": 25, "total": 25}),
    "{ this is not valid json",          # malformed -> skipped
    "42",                                # valid JSON but not an object -> skipped
])


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_garak_parser_reduces_eval_rows(tmp_path):
    result = _parse_garak_report(_write(tmp_path / "garak.report.jsonl", _GARAK_REPORT))
    assert result.ran is True
    # Only the three eval rows survive; setup/attempt/junk are ignored.
    assert len(result.probes) == 3
    by_cat = {p.category: p for p in result.probes}
    assert set(by_cat) == {"jailbreak", "prompt_injection", "encoding"}
    assert by_cat["jailbreak"].hits == 2 and by_cat["jailbreak"].attempts == 25
    assert by_cat["jailbreak"].asr == 0.08      # 2 / 25
    assert by_cat["prompt_injection"].asr == 0.2
    assert by_cat["encoding"].hits == 0


def test_garak_parser_keeps_detector_in_label(tmp_path):
    result = _parse_garak_report(_write(tmp_path / "g.jsonl", _GARAK_REPORT))
    labels = {p.probe for p in result.probes}
    assert "dan.Dan_11_0/mitigation.MitigationBypass" in labels


def test_garak_parser_splits_multiple_detectors_per_probe(tmp_path):
    """garak emits one eval row per detector; each stays a distinct probe row."""
    report = "\n".join([
        json.dumps({"entry_type": "eval", "probe": "dan.Dan_11_0",
                    "detector": "mitigation.MitigationBypass", "passed": 20, "total": 25}),
        json.dumps({"entry_type": "eval", "probe": "dan.Dan_11_0",
                    "detector": "dan.DAN", "passed": 5, "total": 25}),
    ])
    result = _parse_garak_report(_write(tmp_path / "g.jsonl", report))
    assert len(result.probes) == 2
    # Worst detector (5/25 passed -> 20 hits -> 0.8 ASR) drives the category.
    assert max(p.asr for p in result.probes) == 0.8


def test_garak_parser_tolerates_non_numeric_counts(tmp_path):
    report = json.dumps({"entry_type": "eval", "probe": "dan.x",
                         "detector": "d", "passed": "18.0", "total": "20"})
    result = _parse_garak_report(_write(tmp_path / "g.jsonl", report))
    assert result.probes[0].attempts == 20 and result.probes[0].hits == 2


def test_garak_category_mapping():
    assert _garak_category("dan.Dan_11_0") == "jailbreak"
    assert _garak_category("probes.promptinject.Foo") == "prompt_injection"
    assert _garak_category("leakreplay.LiteratureCloze") == "data_leakage"
    assert _garak_category("realtoxicityprompts.RTPBlank") == "toxicity"
    assert _garak_category("totally.unknown") == "prompt_injection"  # conservative default


def test_run_garak_missing_report_is_clean_skip(tmp_path):
    target = {"garak_report": str(tmp_path / "does-not-exist.jsonl")}
    result = run_garak(target, demo=False)
    assert result.ran is False
    assert "not found" in result.error


def test_run_garak_ingests_report_override(tmp_path):
    report = _write(tmp_path / "garak.report.jsonl", _GARAK_REPORT)
    result = run_garak({"garak_report": str(report)}, demo=False)
    assert result.ran is True and result.name == GARAK and result.probes


def test_as_int_helper():
    assert _as_int(5) == 5
    assert _as_int("7") == 7
    assert _as_int("7.0") == 7
    assert _as_int(None) == 0
    assert _as_int("nope", default=-1) == -1


# ---------------------------------------------------------------------------
# Inspect / AgentDojo log reduction
# ---------------------------------------------------------------------------

def _inspect_sample(injection_succeeded: bool) -> dict:
    """An EvalSample shaped exactly like AgentDojo's `injection_task_scorer`.

    Score.value = {"utility": "C"/"I", "security": "C"/"I"}; `security()` returns
    True ("C") when the injection executed correctly -- i.e. the attack SUCCEEDED
    (HANDOVER §6.4, verified against inspect_evals). `utility` is the benign-task
    signal and must not be read as an injection outcome.
    """
    sec = "C" if injection_succeeded else "I"
    return {"id": 1, "epoch": 1,
            "scores": {"injection_task_scorer": {"value": {"utility": "C", "security": sec}}}}


def _write_inspect_json(path: Path, samples: list[dict], task: str = "inspect_evals/agentdojo"):
    path.write_text(json.dumps({"eval": {"task": task}, "samples": samples}), encoding="utf-8")
    return path


def _write_eval_zip(path: Path, samples: list[dict], task: str = "inspect_evals/agentdojo"):
    """Mimic Inspect's native `.eval` container: header.json + samples/*.json."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("header.json", json.dumps({"eval": {"task": task}, "status": "success"}))
        for i, sample in enumerate(samples):
            zf.writestr(f"samples/{i}_epoch_1.json", json.dumps(sample))
    return path


def test_agentdojo_outcome_reads_nested_security_score():
    # security == "C" -> injection executed correctly -> attack succeeded (hit).
    assert _agentdojo_outcome(_inspect_sample(injection_succeeded=True)) is True
    assert _agentdojo_outcome(_inspect_sample(injection_succeeded=False)) is False


def test_agentdojo_outcome_ignores_utility_only_score():
    """A benign (user-task) run reports only `utility` -> no injection outcome."""
    sample = {"scores": {"user_task_scorer": {"value": {"utility": "C"}}}}
    assert _agentdojo_outcome(sample) is None


def test_agentdojo_outcome_reads_attack_keyed_score():
    sample = {"scores": {"injection_success": {"value": "C"}}}  # "C" == CORRECT == truthy
    assert _agentdojo_outcome(sample) is True


def test_agentdojo_outcome_unrecognised_schema_is_none():
    assert _agentdojo_outcome({"scores": {"accuracy": {"value": 0.9}}}) is None
    assert _agentdojo_outcome({"scores": "not-a-dict"}) is None
    assert _agentdojo_outcome({}) is None


def test_parse_agentdojo_json_log(tmp_path):
    _write_inspect_json(tmp_path / "run.json",
                        [_inspect_sample(True), _inspect_sample(True), _inspect_sample(False)])
    result = _parse_agentdojo_logs(tmp_path, suites="banking")
    assert result.ran is True
    assert len(result.probes) == 1
    p = result.probes[0]
    assert p.category == "tool_injection"
    assert p.attempts == 3 and p.hits == 2      # two injections succeeded, one defended
    assert p.probe == "inspect_evals/agentdojo"


def test_parse_agentdojo_eval_zip(tmp_path):
    """The native `.eval` (zip) format must parse -- not just `--log-format json`."""
    _write_eval_zip(tmp_path / "run.eval", [_inspect_sample(True), _inspect_sample(False)])
    result = _parse_agentdojo_logs(tmp_path, suites="banking")
    assert result.ran is True
    assert result.probes[0].attempts == 2 and result.probes[0].hits == 1


def test_parse_agentdojo_eval_zip_zstd(tmp_path):
    """Inspect compresses `.eval` members with zstd (method 93) -- the real format.

    Skipped where zstd isn't available (e.g. the dev-only CI env); the `live`
    extra pulls `zipfile-zstd`, which is also what makes the parser work.
    """
    pytest.importorskip("zipfile_zstd")
    import zipfile_zstd  # noqa: F401  -- registers zipfile.ZIP_ZSTANDARD

    path = tmp_path / "run.eval"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_ZSTANDARD) as zf:
        zf.writestr("header.json", json.dumps({"eval": {"task": "agentdojo"}}))
        zf.writestr("samples/1_epoch_1.json", json.dumps(_inspect_sample(True)))
        zf.writestr("samples/2_epoch_1.json", json.dumps(_inspect_sample(False)))
    result = _parse_agentdojo_logs(tmp_path, suites="banking")
    assert result.ran is True
    assert result.probes[0].probe == "agentdojo"
    assert result.probes[0].attempts == 2 and result.probes[0].hits == 1


def test_parse_agentdojo_uninterpretable_log_is_skip_not_pass(tmp_path):
    """Samples present but no recognisable score -> SKIP, never a silent 0-hit pass."""
    _write_inspect_json(tmp_path / "run.json",
                        [{"scores": {"accuracy": {"value": 0.9}}},
                         {"scores": {"accuracy": {"value": 0.8}}}])
    result = _parse_agentdojo_logs(tmp_path, suites="banking")
    assert result.ran is False
    assert "recognisable" in result.error


def test_parse_agentdojo_empty_dir_runs_clean(tmp_path):
    result = _parse_agentdojo_logs(tmp_path, suites="banking")
    assert result.ran is True and result.probes == []


def test_parse_agentdojo_ignores_non_dict_json(tmp_path):
    (tmp_path / "junk.json").write_text("42", encoding="utf-8")
    result = _parse_agentdojo_logs(tmp_path, suites="banking")
    assert result.ran is True and result.probes == []


def test_run_agentdojo_demo_mode():
    result = run_agentdojo({"provider": "demo"}, demo=True)
    assert result.ran is True and result.name == AGENTDOJO and result.probes

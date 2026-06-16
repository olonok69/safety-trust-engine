"""Provider abstraction tests (no network, no keys)."""

from __future__ import annotations

import pytest

from safety_engine.providers import build_target


def test_demo_target_is_minimal():
    t = build_target("demo", demo=True)
    assert t == {"provider": "demo", "model": "demo-model"}


def test_openai_target_shape():
    t = build_target("openai", "gpt-4o")
    assert t["garak_model_type"] == "openai"
    assert t["garak_model_name"] == "gpt-4o"
    assert t["inspect_model"] == "openai/gpt-4o"
    assert t["pyrit_buildable"] is True


def test_azure_target_shape():
    t = build_target("azure", "gpt-4o")
    assert t["inspect_model"] == "azureai/gpt-4o"
    assert t["pyrit_buildable"] is True


def test_google_not_pyrit_buildable():
    t = build_target("google", "gemini-1.5-pro")
    assert t["inspect_model"] == "google/gemini-1.5-pro"
    assert t["pyrit_buildable"] is False


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        build_target("nope", "x")


def test_demo_overrides_any_provider():
    t = build_target("openai", "x", demo=True)
    assert t["provider"] == "demo"


def test_overrides_merge_in():
    t = build_target("openai", "gpt-4o", garak_report="runs/garak.report.jsonl")
    assert t["garak_report"] == "runs/garak.report.jsonl"

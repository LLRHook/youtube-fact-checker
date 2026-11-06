"""Synthetic contracts exercised through the actual native library, never a mock."""

from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
from pathlib import Path
import random
import unicodedata

import pytest

from backend.utils import native_core
from backend.utils.json_parser import parse_llm_json

CASES = json.loads((Path(__file__).parents[1] / "fixtures/processor.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_shared_rust_contract(case):
    if "error" in case:
        with pytest.raises(native_core.NativeInputError, match=case["error"]):
            native_core.process(**case["request"])
    else:
        assert native_core.process(**case["request"]) == case["expected"]


def test_generated_json_roundtrip_parity():
    """Compare Python's JSON representation with Rust across nested Unicode data."""
    rng = random.Random(4827)
    for _ in range(100):
        data = {"a": [rng.randrange(-10000, 10000), rng.random(), "界 🌍\x00"],
                "b": {"t": True, "n": None, "q": 'quoted " and } ]'}}
        text = json.dumps(data, ensure_ascii=rng.choice([True, False]))
        assert parse_llm_json(text) == json.loads(text)


def test_claim_normalization_parity_for_supported_fields():
    """Frozen previous normalization rules on well-typed, synthetic claims."""
    rng = random.Random(284)
    for _ in range(60):
        items = [{"text": "  界 " * rng.randrange(1, 260),
                  "timestamp_seconds": rng.choice([-5, 0, 5.2, "65.5", 999999, "oops"]),
                  "category": rng.choice(["fact", "opinion", "unclear", "bad"])}
                 for _ in range(rng.randrange(1, 40))]
        expected = []
        for item in items:
            text = item["text"].strip()
            if len(text) > 500:
                truncated = text[:500]
                last_space = truncated.rfind(" ")
                text = (truncated[:last_space] if last_space > 400 else truncated) + "…"
            try:
                timestamp = min(300, min(86400.0, max(0.0, float(item["timestamp_seconds"]))))
            except (TypeError, ValueError):
                timestamp = 0.0
            category = item["category"] if item["category"] in {"fact", "opinion", "unclear"} else "fact"
            expected.append(dict(text=text, timestamp_seconds=timestamp, category=category))
        result = native_core.process("normalize_claims", text=json.dumps(items), max_duration=300, max_claims=30)
        assert result == expected[:30]


def test_concurrent_calls_own_their_responses():
    def call(i):
        return parse_llm_json(json.dumps({"i": i, "text": "界\x00"}))
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(call, range(100))) == [{"i": i, "text": "界\x00"} for i in range(100)]


def test_python_numeric_strings_preserve_claim_caption_and_duration_values():
    zeros = [chr(codepoint) for codepoint in range(0x110000)
             if unicodedata.category(chr(codepoint)) == "Nd"
             and unicodedata.decimal(chr(codepoint)) == 0]
    values = ["1_2.5", "1.2_5e2", "+.1_2e+٢", "  １２.５  "]
    values.extend("".join(chr(ord(zero) + int(char)) if char.isdigit() else char
                          for char in "12.5") for zero in zeros)
    for value in values:
        expected = float(value)
        claims = native_core.process("normalize_claims", text=json.dumps([
            {"text": "Synthetic", "timestamp_seconds": value},
        ]), max_duration=300, max_claims=1)
        assert claims[0]["timestamp_seconds"] == expected
        transcript = native_core.process("normalize_transcript", entries=[
            {"text": "Synthetic", "start": value, "duration": value},
        ])
        assert transcript["segments"][0]["start"] == expected
        assert transcript["segments"][0]["duration"] == expected
        assert native_core.process("validate_duration", duration=value, max_duration=300) == {
            "duration": expected, "too_long": False,
        }
    for value in ("_1", "1_", "1__2", "1_.2", "1._2", "1_e2", "1e_2", "1e+_2", "²", "١٢٫٥"):
        with pytest.raises(native_core.NativeInputError, match="invalid_duration"):
            native_core.process("validate_duration", duration=value, max_duration=300)


def test_native_boundary_rejects_invalid_bytes_and_frees_result():
    lib = native_core._load_native()
    pointer = lib.factcheck_core_process(b"\xff", 1)
    try:
        assert json.loads(ctypes.string_at(pointer)) == {"error": "invalid_request"}
    finally:
        lib.factcheck_core_free(pointer)


def test_oversized_input_is_a_parse_failure(monkeypatch):
    monkeypatch.setattr(native_core, "_MAX_REQUEST_BYTES", 64)
    assert parse_llm_json(json.dumps({"text": "x" * 100})) is None


def test_missing_library_has_actionable_error(monkeypatch, tmp_path):
    native_core._load_native.cache_clear()
    monkeypatch.setattr(native_core, "_LIBRARY_PATH", tmp_path / "missing-library.so")
    try:
        with pytest.raises(RuntimeError, match="scripts/build_native.py"):
            native_core.ensure_native()
    finally:
        native_core._load_native.cache_clear()


def test_wrong_abi_fails_before_processing(monkeypatch):
    class Function:
        def __call__(self):
            return 999
    class Library:
        factcheck_core_abi_version = Function()
    native_core._load_native.cache_clear()
    monkeypatch.setattr(ctypes, "CDLL", lambda path: Library())
    try:
        with pytest.raises(RuntimeError, match="Unsupported factcheck-core ABI"):
            native_core.ensure_native()
    finally:
        native_core._load_native.cache_clear()

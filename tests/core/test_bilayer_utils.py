"""Tests for bilayer stack parsing utilities."""

from rascal2.core.bilayer_utils import (
    _flatten_lipid,
    build_bilayer_specs,
    extract_bilayers_from_model,
)


class _Model:
    def __init__(self, stack):
        self.stack = stack


def test_extract_bilayers_from_model_removes_tokens_from_stack():
    model = _Model("air | bilayer(inner=DPPC, outer=POPC) | Si")

    found = extract_bilayers_from_model(model)

    assert found == [{"inner": "DPPC", "outer": "POPC"}]
    assert model.stack == "air | Si"


def test_extract_bilayers_from_model_ignores_non_matching_tokens():
    model = _Model("air | bilayer(inner=DPPC outer=POPC) | Si")

    found = extract_bilayers_from_model(model)

    assert found == [{"inner": "DPPC", "outer": "POPC"}]
    assert model.stack == "air | Si"


def test_extract_bilayers_from_model_finds_embedded_and_case_insensitive_tokens():
    model = _Model("air | BILAYER(inner=POPC, outer=DPPC) | Si")
    found = extract_bilayers_from_model(model)
    assert found == [{"inner": "POPC", "outer": "DPPC"}]
    assert model.stack == "air | Si"


def test_extract_bilayers_from_model_supports_quoted_values_and_key_order():
    model = _Model("air | bilayer(outer='POPC-d31', inner=\"d-DMPC\") | Si")
    found = extract_bilayers_from_model(model)
    assert found == [{"inner": "d-DMPC", "outer": "POPC-d31"}]
    assert model.stack == "air | Si"


def test_extract_bilayers_from_model_accepts_raw_stack_string():
    found = extract_bilayers_from_model("Si | bilayer(inner=POPC, outer=POPC) | D2O")
    assert found == [{"inner": "POPC", "outer": "POPC"}]


def test_flatten_lipid_defaults_when_missing_constants():
    flat = _flatten_lipid("inner", None)

    assert flat["v_head_inner"] == 300.0
    assert flat["v_tail_inner"] == 800.0
    assert flat["sld_head_inner"] == 1e-6
    assert flat["sld_tail_inner"] == 1e-6


def test_build_bilayer_specs_uses_fallback_constants_without_molgroups():
    specs = build_bilayer_specs([{"inner": "DPPC", "outer": "POPC"}])
    assert len(specs) == 1
    assert specs[0]["inner"] == "DPPC"
    assert specs[0]["outer"] == "POPC"
    assert specs[0]["v_head_inner"] > 0.0

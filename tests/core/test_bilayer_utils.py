"""Tests for bilayer stack parsing utilities."""

from rascal2.core.bilayer_utils import _flatten_lipid, extract_bilayers_from_model


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

    assert found == []
    assert model.stack == "air | bilayer(inner=DPPC outer=POPC) | Si"


def test_flatten_lipid_defaults_when_missing_constants():
    flat = _flatten_lipid("inner", None)

    assert flat["v_head_inner"] == 300.0
    assert flat["v_tail_inner"] == 800.0
    assert flat["sld_head_inner"] == 1e-6
    assert flat["sld_tail_inner"] == 1e-6

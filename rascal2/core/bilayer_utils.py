"""Utilities for parsing bilayer(...) stack tokens in ORSO models."""

from __future__ import annotations

import re

import molgroups.lipids as lipids
import numpy as np

RE_BILAYER = re.compile(r"""^bilayer\s*\(\s*inner\s*=\s*([A-Za-z0-9_]+)\s*,\s*outer\s*=\s*([A-Za-z0-9_]+)\s*\)\s*$""")


def scalar_nsl(x):
    """Convert molgroups nSLs (scalar or array) to a single float."""
    if isinstance(x, list):
        arr = np.array(x)
        return float(np.sum(arr))
    else:
        return float(x)


def get_lipid_constants(lipid_name: str):
    """Get head/tail volumes and SLDs for a lipid from molgroups.lipids."""
    obj = getattr(lipids, lipid_name, None)
    if obj is None:
        obj = lipids.DPPC

    try:
        head_components = obj.headgroup[1]["components"]
        head_vol = sum(getattr(c, "cell_volume", 0.0) for c in head_components)
        head_nsl = scalar_nsl([getattr(c, "nSLs", 0.0) for c in head_components])
    except Exception:
        head_vol = 0.0
        head_nsl = 0.0

    if head_vol <= 0:
        head_vol = float(getattr(obj, "headgroup_volume", 0.0) or 0.0)
    if head_vol <= 0:
        head_vol = 330.0

    head_sld = 0.0
    if head_vol > 0 and head_nsl != 0:
        head_sld = head_nsl * 1e-5 / head_vol

    try:
        tail = obj.tails
        tail_vol = float(getattr(tail, "cell_volume", 0.0) or 0.0)
        tail_nsl = scalar_nsl(getattr(tail, "nSLs", 0.0))
    except Exception:
        tail_vol = 0.0
        tail_nsl = 0.0
    if tail_vol <= 0:
        tail_vol = 800.0

    tail_sld = 0.0
    if tail_vol > 0 and tail_nsl != 0:
        tail_sld = tail_nsl * 1e-5 / tail_vol

    return {
        "name": lipid_name,
        "head_vol": float(head_vol),
        "head_sld": float(head_sld),
        "tail_vol": float(tail_vol),
        "tail_sld": float(tail_sld),
    }


def extract_bilayers_from_model(model):
    """Extract bilayer(inner=XXX, outer=YYY) tokens from model.stack."""
    stack = getattr(model, "stack", "")
    tokens = [t.strip() for t in stack.split("|")]

    bilayers = []
    kept = []
    for t in tokens:
        m = RE_BILAYER.match(t)
        if m:
            bilayers.append({"inner": m.group(1), "outer": m.group(2)})
        else:
            kept.append(t)

    model.stack = " | ".join(kept)
    return bilayers


def _flatten_lipid(prefix: str, consts):
    """Expand molgroups lipid constants into flat keys with fallback."""
    if consts is None:
        return {
            f"v_head_{prefix}": 300.0,
            f"v_tail_{prefix}": 800.0,
            f"sld_head_{prefix}": 1e-6,
            f"sld_tail_{prefix}": 1e-6,
        }
    return {
        f"v_head_{prefix}": consts["head_vol"],
        f"sld_head_{prefix}": consts["head_sld"],
        f"v_tail_{prefix}": consts["tail_vol"],
        f"sld_tail_{prefix}": consts["tail_sld"],
    }


def build_bilayer_specs(bilayer_specs_raw):
    """Build enriched bilayer constants from parsed bilayer stack tokens."""
    bilayer_specs = []
    if not bilayer_specs_raw:
        return bilayer_specs

    for spec in bilayer_specs_raw:
        inner = spec["inner"]
        outer = spec["outer"]
        inner_consts = get_lipid_constants(inner)
        outer_consts = get_lipid_constants(outer)
        bilayer_specs.append(
            {
                "inner": inner,
                "outer": outer,
                **_flatten_lipid("inner", inner_consts),
                **_flatten_lipid("outer", outer_consts),
            }
        )
    return bilayer_specs

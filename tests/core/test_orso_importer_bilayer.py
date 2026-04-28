"""Tests for bilayer-aware ORSO import."""

from pathlib import Path
from types import SimpleNamespace

import ratapi as rat

from rascal2.core import orso_importer


class _Quantity:
    def __init__(self, value):
        self._value = value

    def as_unit(self, _):
        return self._value


class _Material:
    def __init__(self, name, sld):
        self.name = name
        self.formula = name
        self._sld = sld

    def get_sld(self):
        return complex(self._sld, 0)


class _Layer:
    def __init__(self, name, thickness, roughness, sld):
        self.original_name = name
        self.material = _Material(name, sld)
        self.thickness = _Quantity(thickness)
        self.roughness = _Quantity(roughness)


class _Model:
    def __init__(self):
        self.stack = "Air | bilayer(inner=DPPC, outer=DPPC) | D2O"

    def resolve_to_layers(self):
        return [
            _Layer("Air", 0.0, 3.0, 0.0),
            _Layer("Oxide", 10.0, 3.0, 3.0e-6),
            _Layer("D2O", 0.0, 3.0, 6.35e-6),
        ]


class _Dataset:
    def __init__(self):
        self.info = SimpleNamespace(
            data_source=SimpleNamespace(sample=SimpleNamespace(name="C1", model=_Model()))
        )
        self.data = [[0.01, 1.0, 0.1]]


def test_import_ort_to_project_switches_to_custom_layers_for_bilayer(tmp_path, monkeypatch):
    ort_file = tmp_path / "test.ort"
    ort_file.write_text("dummy")
    monkeypatch.setattr(orso_importer, "load_orso", lambda *_: [_Dataset()])

    project = rat.Project(name="test")
    out_project, out_controls = orso_importer.import_ort_to_project(
        str(ort_file), project, str(tmp_path / "proj")
    )

    assert out_controls is None
    assert out_project.model == "custom layers"
    assert out_project.custom_files[0].name == "ORSO Bilayer Model"
    assert out_project.contrasts[0].model == ["ORSO Bilayer Model"]
    assert any(p.name == "Bilayer1 APM" for p in out_project.parameters)
    assert (tmp_path / "proj" / "orso_bilayer_model.py").exists()

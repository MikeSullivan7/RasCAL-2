from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import pytest
from ratapi import Controls, Project, Results
from ratapi.outputs import CalculationResults, ContrastParams
from ratapi.utils.enums import Calculations

from rascal2.ui.model import MainWindowModel
from tests.utils import check_results_equal


@pytest.fixture
def empty_results():
    empty_results = Results(
        reflectivity=[],
        simulation=[],
        shiftedData=[],
        backgrounds=[],
        resolutions=[],
        sldProfiles=[],
        layers=[],
        resampledLayers=[],
        calculationResults=CalculationResults(chiValues=np.array([]), sumChi=0.0),
        contrastParams=ContrastParams(
            scalefactors=np.array([]),
            bulkIn=np.array([]),
            bulkOut=np.array([]),
            subRoughs=np.array([]),
            resample=np.array([]),
        ),
        fitParams=np.array([]),
        fitNames=[],
    )

    return empty_results


@pytest.fixture
def model():
    with patch("rascal2.ui.model.os.chdir", autospec=True):
        yield MainWindowModel()


def test_create_project(model):
    """The project should be set up with the desired name and default objets when a new project is created."""
    assert model.project is None
    assert model.controls is None
    assert model.results is None
    assert model.save_path == ""

    model.create_project("Test", "C:/test")

    assert model.project.name == "Test"
    assert model.controls == Controls()
    assert model.save_path == "C:/test"


def test_save_project(empty_results, model):
    model.project = Project(calculation="domains", name="test project")
    model.controls = Controls(procedure="dream", resampleMinAngle=0.5)
    model.results = empty_results
    with TemporaryDirectory() as tmpdir:
        model.save_project(tmpdir)

        results = Path(tmpdir, "results.json").read_text()
        controls = Path(tmpdir, "controls.json").read_text()
        project = Path(tmpdir, "project.json").read_text()

    assert '"resampleMinAngle":0.5' in controls
    assert '"procedure":"dream"' in controls
    assert '"name": "test project"' in project
    assert '"calculation": "domains' in project
    assert '"reflectivity": []' in results
    assert '"fitParams": []' in results


def test_save_project_as_script(model):
    model.project = Project(calculation="domains", name="test project")
    with TemporaryDirectory() as tmpdir:
        model.save_project_as_script(tmpdir)

        script = Path(tmpdir, "project_script.py").read_text()

    assert 'name="test project"' in script
    assert 'calculation="domains"' in script
    assert 'model="standard layers"' in script
    assert 'geometry="air/substrate"' in script
    assert 'absorption="False"' in script


def test_load_project(empty_results, model):
    """The load function should load the correct controls object from JSON."""
    project = Project(name="test project", calculation="domains")

    with TemporaryDirectory() as tmpdir:
        empty_results.save(Path(tmpdir, "results"))
        Controls(procedure="dream", resampleMinAngle=0.5).save(Path(tmpdir, "controls"))
        project.save(Path(tmpdir, "project"))
        model.load_project(tmpdir)

    assert model.controls == Controls(procedure="dream", resampleMinAngle=0.5)
    assert model.project.calculation == Calculations.Domains
    assert model.project.name == "test project"
    check_results_equal(model.results, empty_results)


@patch("ratapi.utils.convert.r1_to_project")
def test_load_r1_project(mock_r1_class, model):
    """load_r1_project should call the conversion function and set the path correctly."""
    model.load_r1_project("test_path/r1project.mat")

    mock_r1_class.assert_called_once()
    assert model.save_path == "test_path"


@pytest.mark.parametrize("bad_json", ['{"field1":3', '{"procedure":"fry eggs"}'])
def test_load_controls_error(bad_json, model):
    """The project load function should raise an error if the controls JSON is invalid or the parameters are invalid."""
    with pytest.raises(  # noqa (for nested with's: pytest.raises breaks if not by itself)
        ValueError,
        match="The controls.json file for this project is not valid.\n"
        "It may contain invalid parameter values or be invalid JSON.",
    ):
        with TemporaryDirectory() as tmpdir:
            Path(tmpdir, "controls.json").write_text(bad_json)
            model.load_project(tmpdir)


@pytest.mark.parametrize("bad_json", ['{"calculation":"Do}', '{i"m not a good project file'])
def test_load_project_decode_error(bad_json, model):
    """The project load function should raise an error if the project JSON is invalid JSON."""
    with pytest.raises(  # noqa (for nested with's: pytest.raises breaks if not by itself)
        ValueError, match="The project.json file for this project contains invalid JSON."
    ):
        with TemporaryDirectory() as tmpdir:
            Path(tmpdir, "controls.json").write_text("{}")
            Path(tmpdir, "project.json").write_text(bad_json)
            model.load_project(tmpdir)


@pytest.mark.parametrize(
    "bad_json", ['{"calculation":"guessing"}', '{"parameters":[{"name":"parameter 1","thickness":0.51}]}']
)
def test_load_project_value_error(bad_json, model):
    """The project load function should raise an error if the values are not valid."""
    with pytest.raises(  # noqa (for nested with's: pytest.raises breaks if not by itself)
        ValueError, match="The project.json file for this project is not valid."
    ):
        with TemporaryDirectory() as tmpdir:
            Path(tmpdir, "controls.json").write_text("{}")
            Path(tmpdir, "project.json").write_text(bad_json)
            model.load_project(tmpdir)

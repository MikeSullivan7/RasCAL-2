from unittest.mock import MagicMock, patch

import pytest
import ratapi
from PyQt6 import QtWidgets

from rascal2.ui.view import MainWindowView
from rascal2.widgets.project.project import create_draft_project
from rascal2.widgets.project.slider_view import LabeledSlider, SliderViewWidget


@pytest.fixture
def draft_project():
    draft = create_draft_project(ratapi.Project())
    draft["parameters"] = ratapi.ClassList(
        [
            ratapi.models.Parameter(name="Param 1", min=1, max=10, value=2.1, fit=True),
            ratapi.models.Parameter(name="Param 2", min=10, max=100, value=20, fit=True),
        ]
    )
    draft["bulk_in"] = ratapi.ClassList(
        [
            ratapi.models.Parameter(name="H2O", min=0, max=1, value=0.2, fit=True),
        ]
    )
    draft["bulk_out"] = ratapi.ClassList(
        [
            ratapi.models.Parameter(name="Silicon", min=0, max=1, value=0.2, fit=True),
        ]
    )
    draft["scalefactors"] = ratapi.ClassList(
        [
            ratapi.models.Parameter(name="Scale Factor 1", min=0, max=1, value=0.2, fit=True),
        ]
    )
    draft["background_parameters"] = ratapi.ClassList(
        [
            ratapi.models.Parameter(name="Background Param 1", min=0, max=1, value=0.2, fit=True),
        ]
    )
    draft["resolution_parameters"] = ratapi.ClassList(
        [
            ratapi.models.Parameter(name="Resolution Param 1", min=0, max=1, value=0.2, fit=True),
        ]
    )
    draft["domain_ratios"] = ratapi.ClassList(
        [
            ratapi.models.Parameter(name="Domain ratio 1", min=0, max=1, value=0.2, fit=True),
        ]
    )

    return draft


@patch("rascal2.ui.presenter.RATRunner", autospec=True, return_value=MagicMock())
def test_no_sliders_creation(mock_runner):
    """Slider view should show warning when there is no fitted parameter."""
    mw = MainWindowView()
    draft = create_draft_project(ratapi.Project())
    draft["parameters"][0].fit = False
    slider_view = SliderViewWidget(draft, mw)
    assert len(slider_view.parameters) == 0
    assert len(slider_view._sliders) == 0
    label = slider_view.slider_content_layout.takeAt(0).widget()
    assert label.text().startswith("There are no fitted parameters")


@patch("rascal2.ui.presenter.RATRunner", autospec=True, return_value=MagicMock())
def test_sliders_creation(mock_runner, draft_project):
    """Sliders should be created for fitted parameter only."""
    mw = MainWindowView()
    slider_view = SliderViewWidget(draft_project, mw)

    assert len(slider_view.parameters) == 8
    assert len(slider_view._sliders) == 8

    for param_name, slider_name in zip(slider_view.parameters, slider_view._sliders, strict=True):
        assert param_name == slider_name

    draft_project["parameters"][0].fit = False
    slider_view = SliderViewWidget(draft_project, mw)
    assert len(slider_view.parameters) == 7
    assert draft_project["parameters"][0].name not in slider_view._sliders


@patch("rascal2.ui.presenter.RATRunner", autospec=True, return_value=MagicMock())
def test_accept_and_cancel_slider_buttons(mock_runner):
    mw = MainWindowView()
    draft = create_draft_project(ratapi.Project())
    mw.toggle_sliders = MagicMock()
    mw.plot_widget.update_plots = MagicMock()
    mw.presenter.edit_project = MagicMock()

    slider_view = SliderViewWidget(draft, mw)
    buttons = slider_view.findChildren(QtWidgets.QPushButton)
    accept_button = buttons[0]
    accept_button.click()
    mw.toggle_sliders.assert_called_once()
    mw.presenter.edit_project.assert_called_once_with(draft)

    mw.toggle_sliders.reset_mock()
    cancel_button = buttons[1]
    cancel_button.click()
    mw.toggle_sliders.assert_called_once()
    mw.plot_widget.update_plots.assert_called_once()


@pytest.mark.parametrize(
    "param",
    [
        ratapi.models.Parameter(name="Param 1", min=1, max=75, value=21, fit=True),
        ratapi.models.Parameter(name="Param 2", min=-0.1, max=0.5, value=0.3, fit=True),
        ratapi.models.Parameter(name="Param 3", min=3, max=3, value=3, fit=True),
    ],
)
@patch("rascal2.widgets.project.slider_view.SliderViewWidget", autospec=True)
def test_labelled_slider_value(slider_view, param):
    slider_view.update_result_and_plots = MagicMock()
    slider = LabeledSlider(param, slider_view)
    # actual range of the slider should never change but
    # value would be scaled to parameter range.
    assert slider._slider.maximum() == 100
    assert slider._slider.minimum() == 0
    assert slider._slider.value() == slider._param_value_to_slider_value(param.value)

    slider._slider.setValue(79)
    assert param.value == slider._slider_value_to_param_value(slider._slider.value())
    slider_view.update_result_and_plots.assert_called_once()

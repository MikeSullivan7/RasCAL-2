"""The Plot MDI widget."""

from abc import abstractmethod
from inspect import isclass

import matplotlib
import ratapi
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from PyQt6 import QtCore, QtGui, QtWidgets

from rascal2.config import SETTINGS
from rascal2.theme import IconEngine
from rascal2.widgets.inputs import MultiSelectComboBox, ProgressButton


class CanvasQT(FigureCanvasQTAgg):
    """Workaround so plot window can be started minimised."""

    def showEvent(self, event):
        # Calling showMinimised in reset_mdi_layout causes a crash because window
        # handle can be None.
        window = self.window().windowHandle()
        if window is not None:
            super().showEvent(event)


class PlotWidget(QtWidgets.QWidget):
    """The MDI plot widget."""

    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent
        self.parent.presenter.model.results_updated.connect(self.update_plots)

        layout = QtWidgets.QVBoxLayout()
        self.reflectivity_plot = RefSLDWidget(self)
        layout.addWidget(self.reflectivity_plot)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 5, 0, 5)
        self.setLayout(layout)

        self.bayes_plots_button = QtWidgets.QPushButton("View Bayes plots", objectName="InteractButton")
        self.bayes_plots_button.setVisible(False)
        self.bayes_plots_button.pressed.connect(self.show_bayes_plots)
        self.reflectivity_plot.interaction_layout.addWidget(self.bayes_plots_button)

    def update_plots(self):
        """Update the plot widget to match the parent model."""
        model = self.parent.presenter.model
        self.reflectivity_plot.plot(model.project, model.results)
        self.bayes_plots_button.setVisible(isinstance(model.results, ratapi.outputs.BayesResults))

    def plot_with_blit(self, event: ratapi.events.PlotEventData):
        """Handle plot event data.

        Parameters
        ----------
        event : ratapi.events.PlotEventData
            plot event data
        """
        self.reflectivity_plot.plot_with_blit(event)

    def show_bayes_plots(self):
        bayes_plots = BayesPlotsDialog(self.parent)
        bayes_plots.exec()

    def clear(self):
        """Clear the Ref/SLD canvas."""
        self.reflectivity_plot.clear()


class BayesPlotsDialog(QtWidgets.QDialog):
    """The modal dialog for the Bayes plots."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.resize_timer = 0

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlag(QtCore.Qt.WindowType.WindowMaximizeButtonHint, True)

        layout = QtWidgets.QVBoxLayout()
        self.plot_tabs = QtWidgets.QTabWidget()

        plots = {
            "Shaded plot": ShadedPlotWidget,
            "Posteriors": HistPlotWidget,
            "Diagnostics": ChainPlotWidget,
            "Corner Plot": CornerPlotWidget,
        }

        for plot_type, plot_widget in plots.items():
            self.add_tab(plot_type, plot_widget)

        self.sync_and_update_model()
        self.plot_tabs.addTab(self.create_confidence_table(), "Parameter values")
        layout.addWidget(self.plot_tabs)
        self.setLayout(layout)
        self.setModal(True)
        self.resize(900, 600)
        self.setWindowTitle("Bayes Results")
        self.plot_tabs.currentChanged.connect(self.redraw_panel_plot)

    def create_confidence_table(self):
        """Create table to display the confidence intervals."""
        results = self.parent.presenter.model.results
        if results is None:
            return

        table = QtWidgets.QTableWidget()
        table.setColumnCount(4)
        table.setRowCount(len(results.fitNames))
        table.setHorizontalHeaderLabels(["Parameter", "Mean", "95% CI", "65% CI"])
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().hide()

        ci = results.confidenceIntervals
        for i, name in enumerate(results.fitNames):
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(name))
            item1 = QtWidgets.QTableWidgetItem(f"{ci.mean[0][i]:g}")
            item1.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 1, item1)

            item2 = QtWidgets.QTableWidgetItem(f"[{ci.percentile95[0][i]:g}, {ci.percentile95[1][i]:g}]")
            item2.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 2, item2)

            item3 = QtWidgets.QTableWidgetItem(f"[{ci.percentile65[0][i]:g}, {ci.percentile65[1][i]:g}]")
            item3.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 3, item3)

        table.resizeColumnsToContents()

        return table

    def add_tab(self, plot_type: str, plot_widget: "AbstractPlotWidget"):
        """Add a widget as a tab to the plot widget.

        Parameters
        ----------
        plot_type : str
            The name of the plot type.
        plot_widget : AbstractPlotWidget
            The plot widget to add as a tab.

        """
        # create widget instance if a widget class handle was given
        # rather than an instance
        if isclass(plot_widget):
            plot_widget = plot_widget(self)
            plot_widget.toggle_button.setChecked(True)

        self.plot_tabs.addTab(plot_widget, plot_type)

        if self.parent.presenter.model.results is not None:
            plot_widget.plot(self.parent.presenter.model.project, self.parent.presenter.model.results)
            plot_widget.show_result_summary(self.parent.presenter.model.results)

    def sync_and_update_model(self):
        """Set panel plot parameter comboboxes to the same model so changing parameters in one updates the others."""
        if self.parent.presenter.model.results is None:
            return

        model = QtGui.QStandardItemModel()
        model.dataChanged.connect(self.set_redraw_state)
        for i in range(1, 4):
            widget = self.plot_tabs.widget(i)
            widget.param_combobox.setModel(model)
            widget.redraw_plot = i != 3
        widget.param_combobox.addItems(self.parent.presenter.model.results.fitNames)
        widget.param_combobox.select_items(self.parent.presenter.model.results.fitNames)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.resize_timer != 0:
            self.killTimer(self.resize_timer)
            self.resize_timer = 0
        self.resize_timer = self.startTimer(400)

    def timerEvent(self, event):
        if self.resize_timer != 0:
            self.draw_current_panel_plot()
        self.killTimer(event.timerId())
        self.resize_timer = 0

    def draw_current_panel_plot(self):
        """Draw the current panel plot (if not corner) when resizing."""
        if 0 < self.plot_tabs.currentIndex() < 3:
            self.plot_tabs.currentWidget().draw_plot()
        self.set_redraw_state()
        self.resize_timer = 0

    def set_redraw_state(self):
        """Set the redraw state of not visible panel plots."""
        index = self.plot_tabs.currentIndex()
        self.plot_tabs.widget(1).redraw_plot = index != 1
        self.plot_tabs.widget(2).redraw_plot = index != 2

    def redraw_panel_plot(self):
        """Draw current panel plot if its redraw state is True."""
        widget = self.plot_tabs.currentWidget()
        if isinstance(widget, AbstractPanelPlotWidget) and widget.redraw_plot:
            widget.canvas.setVisible(False)
            widget.draw_plot()


class AbstractPlotWidget(QtWidgets.QWidget):
    """Widget to contain a plot and relevant settings."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.current_plot_data = None

        main_layout = QtWidgets.QHBoxLayout()

        self.result_summary = QtWidgets.QLabel(objectName="BayesResultSummary")
        self.result_summary.hide()
        plot_settings = self.make_control_layout()

        export_button = QtWidgets.QPushButton("Export plot...")
        export_button.pressed.connect(self.export)

        plot_settings.insertSpacing(0, 15)
        plot_settings.addStretch(1)
        plot_settings.addWidget(export_button)

        # self.plot_controls contains hideable controls
        self.plot_controls = QtWidgets.QWidget()
        self.plot_controls.setLayout(plot_settings)

        self.toggle_button = QtWidgets.QToolButton()
        self.toggle_button.toggled.connect(self.toggle_settings)
        self.toggle_button.setCheckable(True)
        self.toggle_settings(self.toggle_button.isChecked())

        # plot_toolbar contains always-visible toolbar
        plot_toolbar = QtWidgets.QVBoxLayout()
        plot_toolbar.addWidget(self.toggle_button)
        slider = self.make_toolbar_widget()
        if slider is None:
            plot_toolbar.addStretch(1)
        else:
            sub_layout = QtWidgets.QHBoxLayout()
            sub_layout.addStretch(1)
            sub_layout.addWidget(slider)
            sub_layout.addStretch(1)
            plot_toolbar.addLayout(sub_layout)
            plot_toolbar.addSpacing(5)

        sidebar = QtWidgets.QHBoxLayout()
        sidebar.addWidget(self.plot_controls)
        sidebar.addLayout(plot_toolbar)

        self.blit_plot = None
        self.figure = self.make_figure()
        self.canvas = CanvasQT(
            self.figure,
        )
        self.figure.set_facecolor("none")
        self.canvas.setStyleSheet("background-color: transparent;")

        self.canvas.setParent(self)
        self.setMinimumSize(500, 300)

        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.viewport().setAutoFillBackground(False)
        scroll_area.setWidget(self.canvas)
        scroll_area.setWidgetResizable(True)

        central_layout = QtWidgets.QVBoxLayout()
        central_layout.setSpacing(0)
        central_layout.setContentsMargins(0, 0, 0, 0)
        self.interaction_layout = self.make_interaction_layout()
        if self.interaction_layout is not None:
            central_layout.addLayout(self.interaction_layout)
        central_layout.addWidget(scroll_area)

        main_layout.addLayout(sidebar, 0)
        main_layout.addLayout(central_layout, 4)
        self.setLayout(main_layout)

    def update_figure_size(self):
        """Update figure size to match canvas size."""
        sx = self.canvas.width() * self.canvas._device_pixel_ratio / self.figure.dpi
        sy = self.canvas.height() * self.canvas._device_pixel_ratio / self.figure.dpi
        self.figure.set_size_inches(sx, sy)

    def show_result_summary(self, results):
        """Show log z and log z error in summary label."""
        if isinstance(results, ratapi.outputs.BayesResults) and results.from_procedure() == "ns":
            self.result_summary.setText(
                f"log (Z) = {results.nestedSamplerOutput.logZ:.5f}\n"
                f"log (Z) error = {results.nestedSamplerOutput.logZErr:.5f}"
            )
            self.result_summary.setVisible(True)

    def make_interaction_layout(self):
        """Make layout with pan, zoom, and reset button.

        Returns
        -------
        QtWidgets.QLayout
            The control panel layout for the plot.

        """
        self.toolbar = NavigationToolbar2QT(self.canvas)
        self.toolbar.hide()
        reset_button = QtWidgets.QToolButton(objectName="InteractButton")
        reset_button.setToolTip("Reset plot")
        reset_button.setIcon(QtGui.QIcon(IconEngine("refresh-dark.png")))
        reset_button.clicked.connect(lambda: self.toolbar.home())
        pan_button = QtWidgets.QToolButton(objectName="InteractButton")
        pan_button.setDefaultAction(self.toolbar._actions["pan"])
        zoom_button = QtWidgets.QToolButton(objectName="InteractButton")
        zoom_button.setDefaultAction(self.toolbar._actions["zoom"])
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addWidget(reset_button)
        button_layout.addWidget(pan_button)
        button_layout.addWidget(zoom_button)
        button_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        return button_layout

    def toggle_settings(self, toggled_on: bool):
        """Toggles the visibility of the plot controls."""
        self.plot_controls.setVisible(toggled_on)
        if toggled_on:
            self.toggle_button.setIcon(QtGui.QIcon(IconEngine("hide-settings-light.png")))
        else:
            self.toggle_button.setIcon(QtGui.QIcon(IconEngine("settings-light.png")))

    @abstractmethod
    def make_control_layout(self) -> QtWidgets.QLayout:
        """Make the plot control panel.

        Returns
        -------
        QtWidgets.QLayout
            The control panel layout for the plot.

        """
        raise NotImplementedError

    def make_toolbar_widget(self):
        """Make widgets for the toolbar."""

    def make_figure(self) -> matplotlib.figure.Figure:
        """Make the figure to plot onto.

        Returns
        -------
        Figure
            The figure to plot onto.

        """
        figure = matplotlib.figure.Figure(figsize=(9, 6))
        figure.set_tight_layout(True)
        figure.set_tight_layout({"pad": 0.01, "w_pad": 0.5})
        return figure

    @abstractmethod
    def plot(self, project: ratapi.Project, results: ratapi.outputs.Results | ratapi.outputs.BayesResults):
        """Plot from the current project and results.

        Parameters
        ----------
        problem : ratapi.Project
            The project.
        results : Union[ratapi.outputs.Results, ratapi.outputs.BayesResults]
            The calculation results.

        """
        raise NotImplementedError

    def clear(self):
        """Clear the canvas."""
        self.figure.clear()
        self.canvas.draw()

    def export(self):
        """Save the figure to a file."""
        filepath, accepted = QtWidgets.QFileDialog.getSaveFileName(self, "Export Plot", filter="Image File (*.png)")
        if accepted:
            sx = self.figure.get_figwidth() * self.figure.dpi
            dpi = self.figure.dpi if sx > 1920 else 1920 // self.figure.get_figwidth()
            self.figure.savefig(filepath, facecolor=SETTINGS.export_background_colour, dpi=dpi)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.Type.PaletteChange:
            scheme = QtWidgets.QApplication.styleHints().colorScheme()
            if scheme == QtCore.Qt.ColorScheme.Light:
                matplotlib.style.use("default")
            else:
                matplotlib.style.use("dark_background")

        super().changeEvent(event)


class RefSLDWidget(AbstractPlotWidget):
    """Creates a UI for displaying the path lengths from the simulation result."""

    def make_control_layout(self):
        self.plot_controls = QtWidgets.QWidget()
        self.x_axis = QtWidgets.QComboBox()
        self.x_axis.addItems(["Log", "Linear"])
        self.x_axis.currentTextChanged.connect(self.handle_control_changed)
        self.y_axis = QtWidgets.QComboBox()
        self.y_axis.addItems(["Ref", "Q^4"])
        self.y_axis.currentTextChanged.connect(self.handle_control_changed)
        self.show_error_bar = QtWidgets.QCheckBox("Show Error Bars")
        self.show_error_bar.setChecked(True)
        self.show_error_bar.checkStateChanged.connect(self.handle_control_changed)
        self.show_grid = QtWidgets.QCheckBox("Show Grid")
        self.show_grid.checkStateChanged.connect(self.handle_control_changed)
        self.show_legend = QtWidgets.QCheckBox("Show Legend")
        self.show_legend.setChecked(True)
        self.show_legend.checkStateChanged.connect(self.handle_control_changed)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("X-Axis"))
        layout.addWidget(self.x_axis)
        layout.addWidget(QtWidgets.QLabel("Y-Axis"))
        layout.addWidget(self.y_axis)
        layout.addWidget(self.show_error_bar)
        layout.addWidget(self.show_grid)
        layout.addWidget(self.show_legend)

        return layout

    def make_toolbar_widget(self):
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Vertical)
        self.slider.setTracking(False)
        self.slider.setInvertedAppearance(True)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self.handle_control_changed)

        return self.slider

    def make_figure(self) -> matplotlib.figure.Figure:
        self.resize_timer = 0
        figure = super().make_figure()
        figure.subplots(1, 2)

        return figure

    def handle_control_changed(self):
        if self.blit_plot is None:
            self.plot_event()
        else:
            self.plot_with_blit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.resize_timer != 0:
            self.killTimer(self.resize_timer)
            self.resize_timer = 0
        self.resize_timer = self.startTimer(500)

    def timerEvent(self, event):
        if self.blit_plot is None:
            self.plot_event()
        self.killTimer(event.timerId())
        self.resize_timer = 0

    def plot(self, project: ratapi.Project, results: ratapi.outputs.Results | ratapi.outputs.BayesResults):
        """Plot the reflectivity and SLD profiles.

        Parameters
        ----------
        project : ratapi.Project
            The project
        results : Union[ratapi.outputs.Results, ratapi.outputs.BayesResults]
            The calculation results.
        """
        if project is None or results is None:
            return

        data = ratapi.events.PlotEventData()

        data.modelType = project.model
        data.reflectivity = results.reflectivity
        data.shiftedData = results.shiftedData
        data.sldProfiles = results.sldProfiles
        data.resampledLayers = results.resampledLayers
        data.dataPresent = ratapi.inputs.make_data_present(project)
        data.subRoughs = results.contrastParams.subRoughs
        data.resample = ratapi.inputs.make_resample(project)
        data.contrastNames = [contrast.name for contrast in project.contrasts]
        self.plot_event(data)

    def plot_event(self, data: ratapi.events.PlotEventData | None = None):
        """Update the ref and SLD plots from a provided or cached plot event.

        Parameters
        ----------
        data : Optional[ratapi.events.PlotEventData]
            plot event data, cached data is used if none is provided
        """
        if self.blit_plot is not None:
            del self.blit_plot
            self.blit_plot = None

        if data is not None:
            self.current_plot_data = data

        if self.current_plot_data is None:
            return

        show_legend = self.show_legend.isChecked() if self.current_plot_data.contrastNames else False
        self.figure.clear()
        self.update_figure_size()
        ratapi.plotting.plot_ref_sld_helper(
            self.current_plot_data,
            self.figure,
            delay=False,
            linear_x=self.x_axis.currentText() == "Linear",
            q4=self.y_axis.currentText() == "Q^4",
            show_error_bar=self.show_error_bar.isChecked(),
            show_grid=self.show_grid.isChecked(),
            show_legend=show_legend,
            shift_value=self.slider.value(),
        )
        self.canvas.draw()

    def plot_with_blit(self, data: ratapi.events.PlotEventData | None = None):
        """Update the ref and SLD plots with blitting.

        Parameters
        ----------
        data : ratapi.events.PlotEventData
            plot event data
        """
        if data is not None:
            self.current_plot_data = data

        if self.current_plot_data is None:
            return

        linear_x = self.x_axis.currentText() == "Linear"
        q4 = self.y_axis.currentText() == "Q^4"
        show_error_bar = self.show_error_bar.isChecked()
        show_grid = self.show_grid.isChecked()
        show_legend = self.show_legend.isChecked() if self.current_plot_data.contrastNames else False
        shift_value = self.slider.value()
        if self.blit_plot is None:
            self.update_figure_size()
            self.blit_plot = ratapi.plotting.BlittingSupport(
                self.current_plot_data,
                self.figure,
                linear_x=linear_x,
                q4=q4,
                show_error_bar=show_error_bar,
                show_grid=show_grid,
                show_legend=show_legend,
                shift_value=shift_value,
            )
        else:
            self.blit_plot.linear_x = linear_x
            self.blit_plot.q4 = q4
            self.blit_plot.show_error_bar = show_error_bar
            self.blit_plot.show_grid = show_grid
            self.blit_plot.show_legend = show_legend
            self.blit_plot.shift_value = shift_value

            self.blit_plot.update(self.current_plot_data)


class ShadedPlotWidget(AbstractPlotWidget):
    """Widget for plotting a contour plot of two parameters."""

    def make_control_layout(self):
        control_layout = QtWidgets.QVBoxLayout()

        self.ci_param_box = QtWidgets.QComboBox(self)
        self.ci_param_box.addItems(["65%", "95%"])
        self.ci_param_box.currentTextChanged.connect(lambda: self.draw_plot())

        control_layout.addWidget(self.result_summary)
        control_layout.addWidget(QtWidgets.QLabel("Confidence Interval"))
        control_layout.addWidget(self.ci_param_box)

        return control_layout

    def plot(self, project, results: ratapi.outputs.BayesResults):
        """Plot the shaded plot."""
        self.project = project
        self.results = results

        self.draw_plot()

    def draw_plot(self):
        """Plot the shaded reflectivity and SLD profiles."""
        self.clear()

        ratapi.plotting.plot_ref_sld(
            self.project,
            self.results,
            bayes=int(self.ci_param_box.currentText().strip("%")),
            fig=self.figure,
        )
        self.canvas.draw()


class AbstractPanelPlotWidget(AbstractPlotWidget):
    """Abstract base widget for plotting panels of parameters (corner plot, histograms, chains).

    These widgets all share a parameter multi-select box, so it is defined here.

    """

    def __init__(self, parent):
        super().__init__(parent)
        self.redraw_plot = False

    def make_control_layout(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(10)
        param_layout = QtWidgets.QVBoxLayout()
        param_layout.setSpacing(2)

        self.desc_label = QtWidgets.QLabel(
            "<h3>Select parameters to update plot or click the 'Select all' button to plot all parameters.</h3>"
        )
        self.desc_label.setWordWrap(True)
        self.param_combobox = MultiSelectComboBox()

        select_deselect_row = QtWidgets.QHBoxLayout()
        select_button = QtWidgets.QPushButton("Select all")
        select_button.pressed.connect(
            lambda: self.param_combobox.select_indices(list(range(self.param_combobox.model().rowCount())))
        )
        deselect_button = QtWidgets.QPushButton("Deselect all")
        deselect_button.pressed.connect(lambda: self.param_combobox.select_indices([]))
        select_deselect_row.addWidget(select_button)
        select_deselect_row.addWidget(deselect_button)

        self.update_label = QtWidgets.QLabel()
        layout.addWidget(self.result_summary)
        layout.addWidget(self.update_label)
        param_layout.addWidget(QtWidgets.QLabel("Parameters"))
        param_layout.addWidget(self.param_combobox)
        param_layout.addLayout(select_deselect_row)
        layout.addWidget(self.desc_label)
        layout.addSpacing(20)
        layout.addLayout(param_layout)

        return layout

    def make_figure(self) -> matplotlib.figure.Figure:
        """Make the figure to plot onto.

        Returns
        -------
        Figure
            The figure to plot onto.

        """
        figure = matplotlib.figure.Figure(figsize=(9, 6))
        return figure

    def make_interaction_layout(self):
        """Make layout with pan, zoom, and reset button."""

    def plot(self, _, results):
        self.results = results
        self.draw_plot()

    def update_ui(self, current, total):
        if current + 1 == total:
            self.update_label.setText("")
        else:
            self.update_label.setText(f"<b>Updating plot {current + 1} of {total}</b>")
        QtWidgets.QApplication.instance().processEvents()

    def draw_plot(self):
        raise NotImplementedError

    def resize_canvas(self):
        self.canvas.setMinimumSize(900, 600)
        self.update_figure_size()

    def clear(self):
        self.canvas.figure.clear()
        self.canvas.draw()
        self.canvas.setMinimumSize(0, 0)
        self.canvas.resize(100, 100)


class CornerPlotWidget(AbstractPanelPlotWidget):
    """Widget for plotting corner plots."""

    def make_control_layout(self):
        layout = super().make_control_layout()

        smooth_row = QtWidgets.QHBoxLayout()
        smooth_row.addWidget(QtWidgets.QLabel("Apply smoothing"))
        self.smooth_checkbox = QtWidgets.QCheckBox()
        self.smooth_checkbox.setCheckState(QtCore.Qt.CheckState.Checked)
        smooth_row.addWidget(self.smooth_checkbox)

        self.plot_button = ProgressButton("Update Plot", "Creating plots")
        self.plot_button.pressed.connect(self.draw_plot)

        layout.addLayout(smooth_row)
        layout.addWidget(self.plot_button)

        self.desc_label.setText(
            "<h3>Select parameters or click the 'Select all' button, then click the 'Update Plot' button.</h3>"
        )

        self.param_combobox.selection_changed.connect(self.toggle_plot_button)

        return layout

    def toggle_plot_button(self):
        self.plot_button.setEnabled(len(self.param_combobox.selected_items()) != 0)

    def update_ui(self, current, total):
        self.plot_button.update_progress(current, total)
        QtWidgets.QApplication.instance().processEvents()

    def draw_plot(self):
        plot_params = self.param_combobox.selected_items()
        smooth = self.smooth_checkbox.checkState() == QtCore.Qt.CheckState.Checked

        if plot_params:
            self.plot_button.show_progress()
            QtWidgets.QApplication.instance().processEvents()
            self.resize_canvas()
            ratapi.plotting.plot_corner(
                self.results, params=plot_params, smooth=smooth, fig=self.figure, progress_callback=self.update_ui
            )
            self.canvas.draw()
            self.canvas.setVisible(True)
            self.plot_button.hide_progress()
        else:
            self.clear()
            self.canvas.setVisible(False)
        self.redraw_plot = False


class HistPlotWidget(AbstractPanelPlotWidget):
    """Widget for plotting Bayesian posterior panels."""

    def make_control_layout(self):
        layout = super().make_control_layout()
        self.param_combobox.selection_changed.connect(self.draw_plot)

        smooth_row = QtWidgets.QHBoxLayout()
        smooth_row.addWidget(QtWidgets.QLabel("Apply smoothing"))
        self.smooth_checkbox = QtWidgets.QCheckBox()
        self.smooth_checkbox.setCheckState(QtCore.Qt.CheckState.Checked)
        self.smooth_checkbox.toggled.connect(self.draw_plot)
        smooth_row.addWidget(self.smooth_checkbox)

        est_density_row = QtWidgets.QHBoxLayout()
        est_density_row.addWidget(QtWidgets.QLabel("Estimated density"))

        self.est_density_combobox = QtWidgets.QComboBox()

        # loop over items and data as `addItems` doesn't support item data
        for item, data in [("None", None), ("normal", "normal"), ("log-normal", "lognor"), ("KDE", "kernel")]:
            self.est_density_combobox.addItem(item, data)

        self.est_density_combobox.currentTextChanged.connect(self.draw_plot)

        est_density_row.addWidget(self.est_density_combobox)

        layout.addLayout(smooth_row)
        layout.addLayout(est_density_row)
        return layout

    def draw_plot(self):
        plot_params = self.param_combobox.selected_items()
        smooth = self.smooth_checkbox.checkState() == QtCore.Qt.CheckState.Checked
        est_dens = self.est_density_combobox.currentData()

        if plot_params:
            self.resize_canvas()
            ratapi.plotting.plot_hists(
                self.results,
                params=plot_params,
                smooth=smooth,
                estimated_density={"default": est_dens},
                fig=self.figure,
                progress_callback=self.update_ui,
            )
            self.canvas.draw()
            self.canvas.setVisible(True)
        else:
            self.clear()
            self.canvas.setVisible(False)
        self.redraw_plot = False


class ChainPlotWidget(AbstractPanelPlotWidget):
    """Widget for plotting a Bayesian chain panel."""

    def make_control_layout(self):
        layout = super().make_control_layout()
        self.param_combobox.selection_changed.connect(self.draw_plot)

        maxpoints_row = QtWidgets.QHBoxLayout()

        maxpoints_label = QtWidgets.QLabel("Maximum points")
        maxpoints_label.setToolTip(
            "The number of points to display in each chain, evenly distributed along the chain. Capped at 100000."
        )
        maxpoints_row.addWidget(maxpoints_label)

        self.maxpoints_box = QtWidgets.QSpinBox()
        self.maxpoints_box.setMaximum(100000)
        self.maxpoints_box.setMinimum(1)
        self.maxpoints_box.setValue(15000)
        self.maxpoints_box.valueChanged.connect(self.draw_plot)

        maxpoints_row.addWidget(self.maxpoints_box)

        layout.addLayout(maxpoints_row)

        return layout

    def draw_plot(self):
        plot_params = self.param_combobox.selected_items()
        maxpoints = self.maxpoints_box.value()

        if plot_params:
            self.resize_canvas()
            ratapi.plotting.plot_chain(
                self.results,
                params=plot_params,
                maxpoints=maxpoints,
                fig=self.figure,
                return_fig=True,
                progress_callback=self.update_ui,
            )
            self.canvas.draw()
            self.canvas.setVisible(True)
        else:
            self.clear()
            self.canvas.setVisible(False)
        self.redraw_plot = False

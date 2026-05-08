"""Models and widgets for project fields."""

import contextlib
import os
import re
import shutil
from enum import Enum
from pathlib import Path

import pydantic
import ratapi
from PyQt6 import QtCore, QtGui, QtWidgets
from ratapi.utils.enums import Calculations, Languages, Procedures, TypeOptions

import rascal2.widgets.delegates as delegates
from rascal2.config import LOGGER, SETTINGS
from rascal2.core.enums import CustomFileType
from rascal2.dialogs.custom_file_editor import create_new_file, edit_file
from rascal2.theme import IconEngine


class ClassListTableModel(QtCore.QAbstractTableModel):
    """Table model for a project ClassList field.

    Parameters
    ----------
    classlist : ClassList
        The initial classlist to represent in this model.
    field : str
        The name of the field represented by this model.
    parent : QtWidgets.QWidget
        The parent widget for the model.

    """

    def __init__(self, classlist: ratapi.ClassList, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.parent = parent

        self.classlist: ratapi.ClassList
        self.item_type: type
        self.headers: list[str]

        self.setup_classlist(classlist)
        self.edit_mode = False
        self.col_offset = 1

    def setup_classlist(self, classlist: ratapi.ClassList):
        """Set up the ClassList, type and headers for the model."""
        self.classlist = classlist
        self.item_type = classlist._class_handle
        if not issubclass(self.item_type, pydantic.BaseModel):
            raise NotImplementedError("ClassListTableModel only works for classlists of Pydantic models!")
        self.headers = list(self.item_type.model_fields)

    def rowCount(self, parent=None) -> int:
        return len(self.classlist)

    def columnCount(self, parent=None) -> int:
        return len(self.headers) + self.col_offset

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        param = self.index_header(index)

        if param is None:
            return None

        data = getattr(self.classlist[index.row()], param)

        if role == QtCore.Qt.ItemDataRole.DisplayRole and self.index_header(index) != "fit":
            data = getattr(self.classlist[index.row()], param)
            # pyqt can't automatically coerce enums to strings...
            if isinstance(data, Enum):
                return str(data)
            if isinstance(data, list):
                return ", ".join(data)
            return data
        elif role == QtCore.Qt.ItemDataRole.CheckStateRole and self.index_header(index) == "fit":
            return QtCore.Qt.CheckState.Checked if data else QtCore.Qt.CheckState.Unchecked

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole) -> bool:
        """Set the data of a given index in the table model.

        Parameters
        ----------
        index: QtCore.QModelIndex
            The model index indicates which cells to change
        value: Any
            The new data value
        role: QtCore.Qt.ItemDataRole
            Indicates the role of the Data.
        """
        if role == QtCore.Qt.ItemDataRole.EditRole or role == QtCore.Qt.ItemDataRole.CheckStateRole:
            row = index.row()
            param = self.index_header(index)
            if param == "fit":
                value = QtCore.Qt.CheckState(value) == QtCore.Qt.CheckState.Checked
            if param is not None:
                current_value = getattr(self.classlist[index.row()], param)
                if current_value == value:
                    # No change
                    return False
                try:
                    with contextlib.suppress(UserWarning):
                        setattr(self.classlist[row], param, value)
                except pydantic.ValidationError:
                    return False
                if not self.edit_mode:
                    # recalculate plots if value was changed
                    recalculate = self.index_header(index) == "value"
                    self.parent.update_project(recalculate)
                self.dataChanged.emit(index, index)
                return True
        return False

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if (
            orientation == QtCore.Qt.Orientation.Horizontal
            and role == QtCore.Qt.ItemDataRole.DisplayRole
            and section >= self.col_offset
        ):
            header = self.headers[section - self.col_offset]
            if "SLD" in header:
                header = header.replace("_", " ")
            else:
                header = header.replace("_", " ").title()
            return header
        elif orientation == QtCore.Qt.Orientation.Vertical:
            if role == QtCore.Qt.ItemDataRole.DisplayRole:
                return f"{section + 1}"
            elif role == QtCore.Qt.ItemDataRole.FontRole:
                selection_model = self.parent.table.selectionModel()
                if selection_model is not None and selection_model.isRowSelected(section):
                    font = QtGui.QFont()
                    font.setBold(True)
                    return font
        return None

    def append_item(self):
        """Append an item to the ClassList."""
        self.classlist.append(self.item_type())
        self.endResetModel()

    def insert_item(self, row: int):
        """Insert an item in the ClassList at given row.

        Parameters
        ----------
        row : int
            The row to insert the item.

        """
        self.classlist.insert(row, self.item_type())
        self.endResetModel()

    def delete_item(self, row: int):
        """Delete an item in the ClassList.

        Parameters
        ----------
        row : int
            The row containing the item to delete.

        """
        self.classlist.pop(row)
        self.endResetModel()

    def index_header(self, index):
        """Get the header for an index.

        Parameters
        ----------
        index : QModelIndex
            The model index for the header.

        Returns
        -------
        str or None
            Either the name of the header, or None if none exists.

        """
        col = index.column()
        if col < self.col_offset:
            return None
        return self.headers[col - self.col_offset]


class ProjectFieldWidget(QtWidgets.QWidget):
    """Widget to show a project ClassList.

    Parameters
    ----------
    field : str
        The field of the project represented by this widget.
    parent : ProjectTabWidget
        The tab this field belongs to.

    """

    classlist_model = ClassListTableModel

    # the model can change and disconnect, so we re-connect it
    # to a signal here on each change
    edited = QtCore.pyqtSignal()

    def __init__(self, field: str, parent):
        super().__init__(parent)
        self.field = field
        header = field.replace("_", " ").title()
        self.parent = parent
        self.project_widget = parent.parent
        self.table = QtWidgets.QTableView(parent)
        self.table.setSelectionMode(self.table.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectItems)
        self.table.verticalHeader().sectionClicked.connect(self.toggle_row_selection)
        self.table.verticalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setCascadingSectionResizes(True)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setMinimumHeight(100)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.addWidget(QtWidgets.QLabel(header, objectName="ProjectFieldWidgetLabel"))
        self.add_button = QtWidgets.QPushButton(
            f"Add new {header[:-1] if header[-1] == 's' else header}", objectName="ProjectFieldWidgetButton"
        )
        self.add_button.setHidden(True)
        self.add_button.pressed.connect(self.append_item)
        top_bar.addStretch(1)
        top_bar.addWidget(self.add_button)

        layout.addLayout(top_bar)
        layout.addWidget(self.table)
        self.setLayout(layout)

    def toggle_row_selection(self, index):
        """Toggle selection of a given row in the table.

        Parameters
        ----------
        index : int
            The row to select or deselect.

        """
        selection = self.table.selectionModel()
        if selection.isRowSelected(index):
            selection.clear()
        else:
            selection.clear()
            for i in range(self.model.columnCount()):
                selection.select(self.model.index(index, i), QtCore.QItemSelectionModel.SelectionFlag.Select)

    def resizeEvent(self, event):
        self.resize_columns()
        super().resizeEvent(event)

    def resize_columns(self):
        """Resize the columns of the tableview to avoid truncating content."""
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        main_col = "filename" if self.model.headers[1] == "filename" else "name"
        index = self.model.headers.index(main_col) + self.model.col_offset
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        if self.model.headers[0] == "fit" or self.model.headers[1] == "filename":
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Fixed)
        self.table.resizeColumnsToContents()

        total_content_width = 0
        visible_non_fixed_count = 0
        for i in range(0, self.model.columnCount()):
            total_content_width += self.table.columnWidth(i)
            if not header.isSectionHidden(i) and header.sectionResizeMode(i) != QtWidgets.QHeaderView.ResizeMode.Fixed:
                visible_non_fixed_count += 1

        # 20 is fudge value to account for content being smaller than table by few pixels
        width = self.table.width() - total_content_width - 20
        if width > 0:
            # if the table width is larger than the content, the extra space is shared
            # between the other visible, non-fixed columns then the final column is stretched.
            large_width = round(width * 0.4)
            remain_width = round((width - large_width) / (visible_non_fixed_count - 1))
            for i in range(0, self.model.columnCount() - 1):
                if header.isSectionHidden(i) or header.sectionResizeMode(i) == QtWidgets.QHeaderView.ResizeMode.Fixed:
                    continue
                width_offset = large_width if i == index else remain_width
                self.table.setColumnWidth(i, self.table.columnWidth(i) + width_offset)

        header.setStretchLastSection(True)

    def update_model(self, classlist: ratapi.classlist.ClassList):
        """Update the table model to synchronise with the project field."""
        self.model = self.classlist_model(classlist, self)

        self.table.setModel(self.model)
        self.model.dataChanged.connect(lambda: self.edited.emit())
        self.model.modelReset.connect(lambda: self.edited.emit())
        self.table.hideColumn(0)
        if self.model.headers[1] == "filename":
            self.table.hideColumn(1)

        self.set_item_delegates()
        self.resize_columns()

    def set_item_delegates(self):
        """Set item delegates and open persistent editors for the table."""
        for i, header in enumerate(self.model.headers):
            self.table.setItemDelegateForColumn(
                i + self.model.col_offset,
                delegates.ValidatedInputDelegate(self.model.item_type.model_fields[header], self.table),
            )

    def append_item(self):
        """Append an item to the model if the model exists."""
        self.model.rowCount()
        if self.model is not None:
            selection = self.table.selectionModel().selectedRows()
            if selection:
                cur_row = selection[-1].row() + 1
                self.model.insert_item(selection[-1].row() + 1)
            else:
                self.model.append_item()
                cur_row = self.model.rowCount() - 1
                self.table.scrollToBottom()
            cur_col = self.model.headers.index("name") + self.model.col_offset
            self.table.setFocus()
            self.table.setCurrentIndex(self.model.index(cur_row, cur_col))

        # call edit again to recreate delete buttons
        self.edit()

    def delete_item(self, index):
        """Delete an item at the index if the model exists.

        Parameters
        ----------
        index : int
            The row to be deleted.

        """
        if self.model is not None:
            self.model.delete_item(index)

        # call edit again to recreate delete buttons
        self.edit()

    def edit(self):
        """Change the widget to be in edit mode."""
        self.model.edit_mode = True
        self.add_button.setHidden(False)
        self.table.showColumn(0)
        self.set_item_delegates()
        for i in range(0, self.model.rowCount()):
            self.table.setIndexWidget(self.model.index(i, 0), self.make_delete_button(i))
        self.resize_columns()

    def make_delete_button(self, index):
        """Make a button that deletes the given row from the list when clicked.

        Parameters
        ----------
        index : int
            The row to be deleted.

        """
        button = QtWidgets.QPushButton(icon=QtGui.QIcon(IconEngine("delete-light.png")))
        button.resize(button.sizeHint().width(), button.sizeHint().width())
        button.pressed.connect(lambda: self.delete_item(index))

        return button

    def update_project(self, recalculate: bool):
        """Update the field in the parent Project.

        Parameters
        ----------
        recalculate : bool
            Whether to recalculate the plots when the project updates.
        """
        presenter = self.parent.parent.parent.presenter
        presenter.model.blockSignals(True)
        presenter.edit_project({self.field: self.model.classlist}, preview=recalculate and SETTINGS.live_recalculate)
        presenter.model.blockSignals(False)
        if SETTINGS.live_recalculate:
            presenter.view.plot_widget.update_plots()


class ParametersModel(ClassListTableModel):
    """Classlist model for Parameters."""

    def __init__(self, classlist: ratapi.ClassList, parent: QtWidgets.QWidget):
        super().__init__(classlist, parent)
        self.headers.insert(0, self.headers.pop(self.headers.index("fit")))
        self.headers.pop(self.headers.index("show_priors"))

        self.protected_indices = []
        if self.item_type is ratapi.models.Parameter:
            for i, item in enumerate(classlist):
                if isinstance(item, ratapi.models.ProtectedParameter):
                    self.protected_indices.append(i)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QtCore.QVariant()

        if role == QtCore.Qt.ItemDataRole.BackgroundRole:
            header = self.index_header(index)
            if self.classlist[index.row()].prior_type != "gaussian" and header in ["mu", "sigma"]:
                return QtGui.QBrush(self.parent.palette().window().color())
        return super().data(index, role)

    def flags(self, index):
        flags = super().flags(index)
        header = self.index_header(index)
        # disable editing on the delete widget column
        # and disable mu, sigma if prior type is not Gaussian
        if (index.column() == 0) or (
            self.classlist[index.row()].prior_type != "gaussian" and header in ["mu", "sigma"]
        ):
            return QtCore.Qt.ItemFlag.NoItemFlags
        # never allow name editing for protected parameters, allow everything else to be edited by default
        if header == "fit":
            flags |= QtCore.Qt.ItemFlag.ItemIsUserCheckable
        elif header != "name" or (self.edit_mode and index.row() not in self.protected_indices):
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable

        return flags

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole) -> bool:
        param = self.index_header(index)
        if param == "min":
            min_value = value
            value_model_index = index.siblingAtColumn(index.column() + 1)
            max_model_index = index.siblingAtColumn(index.column() + 2)

            if min_value > max_model_index.data(QtCore.Qt.ItemDataRole.DisplayRole):
                super().setData(max_model_index, min_value, role)
            if min_value > value_model_index.data(QtCore.Qt.ItemDataRole.DisplayRole):
                super().setData(value_model_index, min_value, role)

        elif param == "value":
            min_model_index = index.siblingAtColumn(index.column() - 1)
            actual_value = value
            max_model_index = index.siblingAtColumn(index.column() + 1)
            if actual_value < min_model_index.data(QtCore.Qt.ItemDataRole.DisplayRole):
                super().setData(min_model_index, actual_value, role)
            if actual_value > max_model_index.data(QtCore.Qt.ItemDataRole.DisplayRole):
                super().setData(max_model_index, actual_value, role)

        elif param == "max":
            min_model_index = index.siblingAtColumn(index.column() - 2)
            value_model_index = index.siblingAtColumn(index.column() - 1)
            max_value = value
            if max_value < min_model_index.data(QtCore.Qt.ItemDataRole.DisplayRole):
                super().setData(min_model_index, max_value, role)
            if max_value < value_model_index.data(QtCore.Qt.ItemDataRole.DisplayRole):
                super().setData(value_model_index, max_value, role)

        return super().setData(index, value, role)


class ParameterFieldWidget(ProjectFieldWidget):
    """Subclass of field widgets for parameters."""

    classlist_model = ParametersModel

    def set_item_delegates(self):
        for i, header in enumerate(self.model.headers):
            if header in ["min", "value", "max"]:
                delegate = delegates.ValueSpinBoxDelegate(header, self.table)
                self.table.setItemDelegateForColumn(i + 1, delegate)
            else:
                self.table.setItemDelegateForColumn(
                    i + 1, delegates.ValidatedInputDelegate(self.model.item_type.model_fields[header], self.table)
                )

    def update_model(self, classlist: ratapi.classlist.ClassList):
        super().update_model(classlist)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            self.model.headers.index("fit") + 1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )

    def handle_bayesian_columns(self, procedure: Procedures):
        """Hide or show Bayes-related columns based on procedure.

        Parameters
        ----------
        procedure : Procedure
            The procedure in Controls.
        """
        is_bayesian = procedure in ["ns", "dream"]
        bayesian_columns = ["prior_type", "mu", "sigma"]
        for item in bayesian_columns:
            index = self.model.headers.index(item)
            if is_bayesian:
                self.table.showColumn(index + 1)
            else:
                self.table.hideColumn(index + 1)
        self.resize_columns()

    def edit(self):
        super().edit()
        for i in range(0, self.model.rowCount()):
            if i in self.model.protected_indices:
                self.table.setIndexWidget(self.model.index(i, 0), None)


class LayersModel(ClassListTableModel):
    """Classlist model for Layers."""

    def __init__(self, classlist: ratapi.ClassList, parent: QtWidgets.QWidget):
        super().__init__(classlist, parent)
        self.absorption = classlist._class_handle == ratapi.models.AbsorptionLayer
        self.SLD_imags = {}

    def flags(self, index):
        flags = super().flags(index)
        if self.edit_mode:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        return flags

    def append_item(self):
        kwargs = {"thickness": "", "SLD": "", "roughness": ""}
        if self.absorption:
            kwargs["SLD_imaginary"] = ""
        self.classlist.append(self.item_type(**kwargs))
        self.endResetModel()

    def insert_item(self, row: int):
        kwargs = {"thickness": "", "SLD": "", "roughness": ""}
        if self.absorption:
            kwargs["SLD_imaginary"] = ""
        self.classlist.insert(row, self.item_type(**kwargs))
        self.endResetModel()

    def set_absorption(self, absorption: bool):
        """Set whether the project is using absorption or not.

        Parameters
        ----------
        absorption : bool
            Whether the project is using absorption.

        """
        if self.absorption != absorption:
            self.beginResetModel()
            self.absorption = absorption
            if absorption:
                classlist = ratapi.ClassList(
                    [
                        ratapi.models.AbsorptionLayer(
                            **dict(layer),
                            SLD_imaginary=self.SLD_imags.get(layer.name, ""),
                        )
                        for layer in self.classlist
                    ]
                )
                # set handle manually for if classlist is empty
                classlist._class_handle = ratapi.models.AbsorptionLayer
            else:
                # we save the SLD_imaginary values so that they aren't lost if the
                # user accidentally toggles absorption off and on!
                self.SLD_imags = {layer.name: layer.SLD_imaginary for layer in self.classlist}
                classlist = ratapi.ClassList(
                    [
                        ratapi.models.Layer(
                            name=layer.name,
                            thickness=layer.thickness,
                            SLD=layer.SLD_real,
                            roughness=layer.roughness,
                            hydration=layer.hydration,
                            hydrate_with=layer.hydrate_with,
                        )
                        for layer in self.classlist
                    ]
                )
                classlist._class_handle = ratapi.models.Layer
            self.setup_classlist(classlist)
            self.parent.parent.parent.update_draft_project({"layers": classlist})
            self.endResetModel()


class LayerFieldWidget(ProjectFieldWidget):
    """Project field widget for Layer objects."""

    classlist_model = LayersModel

    def set_item_delegates(self):
        for i in range(1, self.model.columnCount()):
            if i in [1, self.model.columnCount() - 1]:
                header = self.model.headers[i - 1]
                self.table.setItemDelegateForColumn(
                    i, delegates.ValidatedInputDelegate(self.model.item_type.model_fields[header], self.table)
                )
            else:
                blank_option = self.model.headers[i - 1] == "hydration"
                self.table.setItemDelegateForColumn(
                    i, delegates.ProjectFieldDelegate(self.project_widget, "parameters", self.table, blank_option)
                )

    def set_absorption(self, absorption: bool):
        """Set whether the classlist uses AbsorptionLayers.

        Parameters
        ----------
        absorption : bool
            Whether the classlist should use AbsorptionLayers.

        """
        self.model.set_absorption(absorption)
        if self.model.edit_mode:
            self.edit()


class DomainsModel(ClassListTableModel):
    """Classlist model for domain contrasts."""

    def flags(self, index):
        flags = super().flags(index)
        if self.edit_mode:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        return flags


class DomainContrastWidget(ProjectFieldWidget):
    """Subclass of field widgets for domain contrasts."""

    classlist_model = DomainsModel

    def __init__(self, field, parent):
        super().__init__(field, parent)
        self.project_widget = parent.parent

    def update_model(self, classlist):
        super().update_model(classlist)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)

    def set_item_delegates(self):
        self.table.setItemDelegateForColumn(
            1, delegates.ValidatedInputDelegate(self.model.item_type.model_fields["name"], self.table)
        )
        self.table.setItemDelegateForColumn(2, delegates.MultiSelectLayerDelegate(self.project_widget, self.table))


class CustomFileModel(ClassListTableModel):
    """Classlist model for custom files."""

    def __init__(self, classlist: ratapi.ClassList, parent: QtWidgets.QWidget):
        super().__init__(classlist, parent)
        self.func_names = {}
        self.headers.remove("path")
        self.col_offset = 2
        self.always_copy = True

    def flags(self, index):
        flags = super().flags(index)
        if index.column() in [1, self.columnCount()]:
            return QtCore.Qt.ItemFlag.NoItemFlags
        if self.edit_mode:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        return flags

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        data = super().data(index, role)
        if self.index_header(index) == "filename":
            if role == QtCore.Qt.ItemDataRole.DisplayRole and self.edit_mode and (data == "" or data == "Browse..."):
                return "Browse..."
            elif role in [QtCore.Qt.ItemDataRole.ToolTipRole, QtCore.Qt.ItemDataRole.UserRole]:
                display = super().data(index, QtCore.Qt.ItemDataRole.DisplayRole)
                if display != "" and display != "Browse...":
                    path = Path(self.classlist[index.row()].path)
                    if not path.is_absolute():
                        path = Path(os.getcwd()) / self.classlist[index.row()].path
                    return path.as_posix()
        return data

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if self.index_header(index) == "filename" and value != "Browse...":
            file_path = Path(value)
            if self.always_copy:
                file_path = self.copy_custom_file(file_path)

            row = index.row()
            self.classlist[row].path = file_path.parent
            self.classlist[row].filename = str(file_path.name)

            # auto-set language from file extension if possible
            # & get file names for dropdown on Python
            extension = file_path.suffix
            match extension:
                case ".py":
                    language = Languages.Python
                    # the regex:
                    # (?:^|\n) means 'match start of the string (i.e. the file) or a newline'
                    # (\S+) means 'capture one or more non-whitespace characters'
                    # so the regex captures a word between 'def ' and '(', i.e. a function name
                    func_names = re.findall(
                        r"(?:^|\n)def (\S+)\(", file_path.read_text(encoding="utf-8", errors="backslashreplace")
                    )
                case ".m":
                    language = Languages.Matlab
                    func_names = None
                case ".dll" | ".so" | ".dylib":
                    language = Languages.Cpp
                    func_names = None
                case _:
                    language = None
                    func_names = None
            self.func_names[value] = func_names
            if func_names:
                self.classlist[row].function_name = func_names[0]
            if language is not None:
                self.classlist[row].language = language

            self.dataChanged.emit(index, index)
            return True

        return super().setData(index, value, role)

    @staticmethod
    def copy_custom_file(file_path):
        """Copy given custom file to the project directory.

        Parameters
        ----------
        file_path : str
            The custom file to copy.
        """
        file_path = Path(file_path)
        project_dir = os.getcwd()
        if not file_path.is_relative_to(project_dir):
            try:
                file_path = Path(shutil.copy(file_path, project_dir)).relative_to(project_dir)
            except shutil.SameFileError:
                # Attempting to copy a file to the same directory it is in
                # should fail quietly since file is already copied.
                pass
            except OSError as ex:
                LOGGER.error("Attempt to copy custom file failed, full path will be used.", exc_info=ex)
        else:
            file_path = file_path.relative_to(project_dir)

        return file_path

    def append_item(self):
        """Append an item to the ClassList."""
        self.classlist.append(self.item_type(filename="", path="/"))
        self.endResetModel()


class CustomFileWidget(ProjectFieldWidget):
    """Subclass of field widgets for custom file."""

    classlist_model = CustomFileModel

    def __init__(self, field: str, parent):
        super().__init__(field, parent)

        layout = self.layout().itemAt(0)  # topbar layout
        self.copy_checkbox = QtWidgets.QCheckBox("Always Copy")
        self.copy_checkbox.setChecked(True)
        self.copy_checkbox.setHidden(True)
        self.copy_checkbox.checkStateChanged.connect(self.update_copy_state)
        self.copy_checkbox.setToolTip("Indicates if files should be copied when outside project folder.")
        layout.insertWidget(layout.count() - 1, self.copy_checkbox)
        self.edit_file_column = 1

    def update_model(self, classlist: ratapi.classlist.ClassList):
        super().update_model(classlist)
        self.model.dataChanged.connect(lambda index: self.setup_button(index.row()))

    def update_copy_state(self, state):
        """Update the always_copy state.

        Parameters
        ----------
        state : QtCore.Qt.CheckState
            Indicates the always_copy state.
        """
        self.model.always_copy = state == QtCore.Qt.CheckState.Checked

    def edit(self):
        super().edit()
        self.copy_checkbox.setHidden(False)
        self.table.showColumn(self.edit_file_column)
        for i in range(0, self.model.rowCount()):
            self.table.setIndexWidget(
                self.model.index(i, self.edit_file_column), QtWidgets.QPushButton("Edit File", self.table)
            )
            self.setup_button(i)
        self.resize_columns()

    def setup_button(self, row):
        """Check whether the button should be editable and set it up for the right language.

        Parameters
        ----------
        row : int
            The row containing the button to setup.
        """
        language = self.model.data(self.model.index(row, self.model.headers.index("language") + self.model.col_offset))
        button = self.table.indexWidget(self.model.index(row, self.edit_file_column))

        edit_file_action = QtGui.QAction("Edit File...", self.table)
        edit_file_action.triggered.connect(
            lambda: edit_file(
                self.model.classlist[row].path / self.model.classlist[row].filename,
                self.model.classlist[row].language,
                self,
            )
        )
        new_model_file_action = QtGui.QAction("New Model File...", self.table)
        new_model_file_action.triggered.connect(lambda: self.create_new_file(row, CustomFileType.Model))
        new_background_file_action = QtGui.QAction("New Background File...", self.table)
        new_background_file_action.triggered.connect(lambda: self.create_new_file(row, CustomFileType.Background))

        with contextlib.suppress(TypeError):
            button.pressed.disconnect()

        button.setMenu(None)
        filename_index = self.model.index(row, self.model.headers.index("filename") + self.model.col_offset)
        if language in [Languages.Matlab, Languages.Python]:
            if self.model.data(filename_index) == "Browse...":
                menu = QtWidgets.QMenu(self.table)
                menu.addActions([new_model_file_action, new_background_file_action])
                button.setMenu(menu)
                button.pressed.connect(button.showMenu)
                button.setText("New File")
            else:
                button.pressed.connect(edit_file_action.trigger)
                button.setText("Edit File")
            editable = True
        else:
            button.setText("")
            editable = False
        button.setEnabled(editable)

    def create_new_file(self, row, file_type):
        """Create a new custom file for given model entry.

        Parameters
        ----------
        row : int
            The row to create file for.
        file_type : CustomFileType
            The type of custom file to create.
        """
        is_domains = self.parent.parent.calculation_combobox.currentText() == Calculations.Domains
        try:
            filename = create_new_file(
                self.model.classlist[row].name,
                self.model.classlist[row].language,
                is_domains,
                file_type,
                self,
            )
        except OSError as ex:
            LOGGER.error("Attempt to create new custom file failed.", exc_info=ex)
            return

        if filename:
            index = self.model.index(row, self.model.headers.index("filename") + self.model.col_offset)
            self.model.setData(index, filename, QtCore.Qt.ItemDataRole.EditRole)

    def set_item_delegates(self):
        super().set_item_delegates()
        """Set item delegates and open persistent editors for the table."""
        for i, header in enumerate(self.model.headers):
            self.table.setItemDelegateForColumn(
                i + self.model.col_offset,
                delegates.ValidatedInputDelegate(self.model.item_type.model_fields[header], self.table),
            )

        filename_index = self.model.headers.index("filename") + self.model.col_offset
        function_index = self.model.headers.index("function_name") + self.model.col_offset
        self.table.setItemDelegateForColumn(
            filename_index,
            delegates.ValidatedInputDelegate(self.model.item_type.model_fields["path"], self.table, open_on_show=True),
        )
        self.table.setItemDelegateForColumn(function_index, delegates.CustomFileFunctionDelegate(self))


class AbstractSignalModel(ClassListTableModel):
    """Model for Signal objects (backgrounds and resolutions)."""

    def flags(self, index):
        flags = super().flags(index)
        if self.edit_mode:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        match self.classlist[index.row()].type:  # disable unused value fields
            case TypeOptions.Constant:
                disable_from_col = self.num_valid_values[0]
            case TypeOptions.Data:
                disable_from_col = self.num_valid_values[1]
            case TypeOptions.Function:
                disable_from_col = self.num_valid_values[2]
        if index.column() > disable_from_col + 3:  # +3 offset for name, type, source
            flags = QtCore.Qt.ItemFlag.NoItemFlags
        return flags

    @property
    def num_valid_values(self) -> tuple[int]:
        """The number of valid value fields for each type.

        Returns
        -------
        Tuple[int]
            The number of valid values for constant, data, and function signals respectively.

        """
        raise NotImplementedError


class BackgroundsModel(AbstractSignalModel):
    """Model for classlists of Backgrounds."""

    @property
    def num_valid_values(self) -> tuple[int, int, int]:
        return 0, 1, 5


class ResolutionsModel(AbstractSignalModel):
    """Model for classlists of Resolutions."""

    @property
    def num_valid_values(self) -> tuple[int, int, int]:
        return 0, -1, 5  # -1 to remove 'source' field for data resolutions


class AbstractSignalFieldWidget(ProjectFieldWidget):
    """Project field widget for 'signal' objects (backgrounds and resolutions)."""

    def set_item_delegates(self):
        super().set_item_delegates()
        source_index = self.model.headers.index("source") + 1
        self.table.setItemDelegateForColumn(
            source_index, delegates.SignalSourceDelegate(self.project_widget, self.parameter_field, self.table)
        )
        for column in range(source_index + 1, self.model.columnCount()):
            self.table.setItemDelegateForColumn(
                column, delegates.ProjectFieldDelegate(self.project_widget, self.parameter_field, self.table)
            )

    @property
    def parameter_field(self) -> str:
        """The relevant parameter field for the object.

        Returns
        -------
        str
            The name of the relevant parameter field for the object.

        """
        raise NotImplementedError


class BackgroundsFieldWidget(AbstractSignalFieldWidget):
    """Project field widget for backgrounds."""

    classlist_model = BackgroundsModel

    @property
    def parameter_field(self) -> str:
        return "background_parameters"


class ResolutionsFieldWidget(AbstractSignalFieldWidget):
    """Project field widget for resolutions."""

    classlist_model = ResolutionsModel

    def set_item_delegates(self):
        super().set_item_delegates()
        # workaround to remove function resolution option
        type_index = self.model.headers.index("type") + 1
        self.table.setItemDelegateForColumn(
            type_index,
            delegates.ValidatedInputDelegate(self.model.item_type.model_fields["type"], self.table, remove_items=[2]),
        )
        # hide unused value_2 through value_5
        for column in range(4, 9):
            self.table.setColumnHidden(column, True)

    @property
    def parameter_field(self) -> str:
        return "resolution_parameters"

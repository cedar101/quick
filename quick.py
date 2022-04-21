import signal
import logging
import sys
from functools import partial
import math
from copy import copy

import click

from PyQt5 import QtGui
from PyQt5 import QtWidgets
from PyQt5 import QtCore

try:
    import qdarkstyle

    _has_qdarkstyle = True
except ModuleNotFoundError:
    _has_qdarkstyle = False


_GTypeRole = QtCore.Qt.UserRole
_missing = object()
signal.signal(
    signal.SIGINT, signal.SIG_DFL
)  # make CTRL+C exit the program successfully


class GStyle(object):
    _base_style = """
        ._OptionLabel {
            font-size: 16px;
            font: bold;
            font-family: monospace;
            }
        ._HelpLabel {
            font-family: serif;
            font-size: 14px;
            }
        ._InputComboBox{
            font-size: 16px;
            }
        ._InputLineEdit{
            font-size: 16px;
            }
        ._InputCheckBox{
            font-size: 16px;
            }
        ._InputSpinBox{
            font-size: 16px;
            }
        ._InputTabWidget{
            font: bold;
            font-size: 16px;
            }
        .GListView{
            font-size: 16px;
            height: 40px;
            }
        QToolTip{
            font-family: serif;
            }
        """

    def __init__(self, style=""):
        if not GStyle.check_style(style):
            self.text_color = "black"
            self.placehoder_color = "#898b8d"
            self.stylesheet = (
                GStyle._base_style
                + """
                    ._Spliter{
                        border: 1px inset gray;
                        }
                    """
            )
        elif style == "qdarkstyle":
            self.text_color = "#eff0f1"
            self.placehoder_color = "#898b8d"
            self.stylesheet = (
                qdarkstyle.load_stylesheet_pyqt5()
                + GStyle._base_style
                + """
                    .GListView{
                        padding: 5px;
                        }
                    ._Spliter{
                        border: 5px solid gray;
                        }
                    """
            )

    @staticmethod
    def check_style(style):
        if style == "qdarkstyle":
            return _has_qdarkstyle
        return False


_gstyle = GStyle()


class GListView(QtWidgets.QListView):
    def __init__(self, opt):
        super(GListView, self).__init__()
        self.nargs = opt.nargs
        self.model = GItemModel(
            opt.nargs, parent=self, opt_type=opt.type, default=opt.default
        )
        self.setModel(self.model)
        self.delegate = GEditDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        if self.nargs == -1:
            self.keyPressEvent = self.key_press
            self.setToolTip(
                "'a': add a new item blow the selected one\n"
                "'d': delete the selected item"
            )

    def key_press(self, e):
        if self.nargs == -1:
            if e.key() == QtCore.Qt.Key_A:
                if len(self.selectedIndexes()) == 0:
                    self.model.insertRow(0)
                else:
                    for i in self.selectedIndexes():
                        self.model.insertRow(i.row() + 1)
            if e.key() == QtCore.Qt.Key_D:
                si = self.selectedIndexes()
                for i in si:
                    self.model.removeRow(i.row())
        super(GListView, self).keyPressEvent(e)

    def sizeHint(self):
        return QtCore.QSize(0, 0)

class GItemModel(QtGui.QStandardItemModel):
    def __init__(self, n, parent=None, opt_type=click.STRING, default=None):
        super(QtGui.QStandardItemModel, self).__init__(0, 1, parent)
        self.type = opt_type
        for row in range(n):
            if hasattr(default, "__len__"):
                self.insertRow(row, default[row])
            else:
                self.insertRow(row, default)

    def insertRow(self, idx, val=""):
        super(GItemModel, self).insertRow(idx)

        index = self.index(idx, 0, QtCore.QModelIndex())
        if val is None or val == "":
            self.setData(
                index,
                QtGui.QBrush(QtGui.QColor(_gstyle.placehoder_color)),
                role=QtCore.Qt.ForegroundRole,
            )
        else:
            self.setData(index, val)

    def data(self, index, role=QtCore.Qt.DisplayRole):

        if role == QtCore.Qt.DisplayRole:
            dstr = QtGui.QStandardItemModel.data(self, index, role)
            if dstr == "" or dstr is None:
                if isinstance(self.type, click.types.Tuple):
                    row = index.row()
                    if 0 <= row < len(self.type.types):
                        tp = self.type.types[row]
                        dstr = tp.name
                else:
                    dstr = self.type.name
                return dstr

        if role == _GTypeRole:
            tp = click.STRING
            if isinstance(self.type, click.types.Tuple):
                row = index.row()
                if 0 <= row < len(self.type.types):
                    tp = self.type.types[row]
            elif isinstance(self.type, click.types.ParamType):
                tp = self.type
            return tp

        return QtGui.QStandardItemModel.data(self, index, role)


class GEditDelegate(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        tp = index.data(role=_GTypeRole)
        if isinstance(tp, click.Path):
            led = GLineEdit_path.from_option(tp, parent)
        else:
            led = QtWidgets.QLineEdit(parent)
        led.setPlaceholderText(tp.name)
        led.setValidator(select_type_validator(tp))
        return led

    def setEditorData(self, editor, index):
        item_var = index.data(role=QtCore.Qt.EditRole)
        if item_var is not None:
            editor.setText(str(item_var))

    def setModelData(self, editor, model, index):
        data_str = editor.text()
        if data_str == "" or data_str is None:
            model.setData(
                index,
                QtGui.QBrush(QtGui.QColor(_gstyle.placehoder_color)),
                role=QtCore.Qt.ForegroundRole,
            )
        else:
            model.setData(
                index,
                QtGui.QBrush(QtGui.QColor(_gstyle.text_color)),
                role=QtCore.Qt.ForegroundRole,
            )
        QtWidgets.QStyledItemDelegate.setModelData(self, editor, model, index)


def generate_label(opt):
    show_name = getattr(opt, "show_name", _missing)
    show_name = opt.name if show_name is _missing else show_name
    param = _OptionLabel(show_name)
    param.setToolTip(getattr(opt, "help", None))
    return param


class GStringLineEditor(click.types.StringParamType):
    def to_widget(self, opt, validator=None):
        value = _InputLineEdit()
        value.setPlaceholderText(self.name)
        if opt.default:
            value.setText(str(opt.default))
        if getattr(opt, "hide_input", False):
            value.setEchoMode(QtWidgets.QLineEdit.Password)
        value.setValidator(validator)

        def to_command():
            return [opt.opts[0], value.text()]

        return [value], to_command


class GIntLineEditor(GStringLineEditor):
    def to_widget(self, opt):
        return GStringLineEditor.to_widget(self, opt, validator=QtGui.QIntValidator())


class GFloatLineEditor(GStringLineEditor):
    def to_widget(self, opt):
        return GStringLineEditor.to_widget(
            self, opt, validator=QtGui.QDoubleValidator()
        )


class GFileDialog(QtWidgets.QFileDialog):
    def __init__(self, *args, exists=False, file_okay=True, dir_okay=True, **kwargs):
        super(GFileDialog, self).__init__(*args, **kwargs)
        self.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        self.setLabelText(QtWidgets.QFileDialog.Accept, "Select")
        if (exists, file_okay, dir_okay) == (True, True, False):
            self.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        elif (exists, file_okay, dir_okay) == (False, True, False):
            self.setFileMode(QtWidgets.QFileDialog.AnyFile)
        elif (exists, file_okay, dir_okay) == (True, False, True):
            self.setFileMode(QtWidgets.QFileDialog.Directory)
        elif (exists, file_okay, dir_okay) == (False, False, True):
            self.setFileMode(QtWidgets.QFileDialog.Directory)
        elif exists is True:
            self.setFileMode(QtWidgets.QFileDialog.ExistingFile)
            self.accept = self.accept_all
        elif exists is False:
            self.setFileMode(QtWidgets.QFileDialog.AnyFile)
            self.accept = self.accept_all

    def accept_all(self):
        super(GFileDialog, self).done(QtWidgets.QFileDialog.Accepted)


class GLineEdit_path(QtWidgets.QLineEdit):
    def __init__(self, parent=None, exists=False, file_okay=True, dir_okay=True):
        super(GLineEdit_path, self).__init__(parent)
        self.action = self.addAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_DirIcon),
            QtWidgets.QLineEdit.TrailingPosition,
        )
        self.fdlg = lambda: GFileDialog(
            self,
            "Select File Dialog",
            "./",
            "*",
            exists=exists,
            file_okay=file_okay,
            dir_okay=dir_okay,
        )
        self.action.triggered.connect(self.run_dialog)

    def run_dialog(self):
        dlg = self.fdlg()
        if dlg.exec() == QtWidgets.QFileDialog.Accepted:
            self.setText(dlg.selectedFiles()[0])

    @staticmethod
    def from_option(opt, parent=None):
        return GLineEdit_path(
            parent=parent,
            exists=opt.exists,
            file_okay=opt.file_okay,
            dir_okay=opt.dir_okay,
        )


class GPathGLineEdit_path(click.types.Path):
    def to_widget(self, opt):
        value = GLineEdit_path(
            exists=self.exists, file_okay=self.file_okay, dir_okay=self.dir_okay
        )
        value.setPlaceholderText(self.name)
        if opt.default:
            value.setText(str(opt.default))

        def to_command():
            return [opt.opts[0], value.text()]

        return [value], to_command


class _GLabeledSlider(QtWidgets.QSlider):
    def __init__(self, min, max, val):
        super(_GLabeledSlider, self).__init__(QtCore.Qt.Horizontal)
        self.min, self.max = min, max

        self.setMinimum(min)
        self.setMaximum(max)
        self.setValue(val)

        self.label = self.__init_label()

    def __init_label(self):
        l = max(
            [
                math.ceil(math.log10(abs(x))) if x != 0 else 1
                for x in [self.min, self.max]
            ]
        )
        l += 1
        return QtWidgets.QLabel("0" * l)


def argument_command(to_command):
    def tc():
        a = to_command()
        return a[1:]

    return tc


class GSlider(QtWidgets.QHBoxLayout):
    def __init__(self, min=0, max=10, default=None, *args, **kwargs):
        super(QtWidgets.QHBoxLayout, self).__init__()

        self.min, self.max, self.default = min, max, default
        self.label = self.__init_label()
        self.slider = self.__init_slider()

        self.label.setText(str(self.default))

        self.addWidget(self.slider)
        self.addWidget(self.label)

    def value(self):
        return self.slider.value()

    def __init_slider(self):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setMinimum(self.min)
        slider.setMaximum(self.max)
        default_val = (self.min + self.max) // 2
        if isinstance(self.default, int):
            if self.min <= self.default <= self.max:
                default_val = self.default
        self.default = default_val
        slider.setValue(default_val)
        slider.valueChanged.connect(lambda x: self.label.setText(str(x)))
        return slider

    def __init_label(self):
        l = max(
            [
                math.ceil(math.log10(abs(x))) if x != 0 else 1
                for x in [self.min, self.max]
            ]
        )
        l += 1
        return QtWidgets.QLabel("0" * l)


class GIntRangeGSlider(click.types.IntRange):
    def to_widget(self, opt):
        value = GSlider(min=self.min, max=self.max, default=opt.default)

        def to_command():
            return [opt.opts[0], str(value.value())]

        return [value], to_command


class GIntRangeSlider(click.types.IntRange):
    def to_widget(self, opt):
        value = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        value.setMinimum(self.min)
        value.setMaximum(self.max)

        default_val = (self.min + self.max) // 2
        if isinstance(opt.default, int):
            if self.min <= opt.default <= self.max:
                default_val = opt.default
        value.setValue(default_val)

        def to_command():
            return [opt.opts[0], str(value.value())]

        return [value], to_command


class GIntRangeLineEditor(click.types.IntRange):
    def to_widget(self, opt):
        value = QtWidgets.QLineEdit()
        # TODO: set validator

        def to_command():
            return [opt.opts[0], value.text()]

        return [value], to_command


def bool_flag_option(opt):
    checkbox = _InputCheckBox(opt.name)
    if opt.default:
        checkbox.setCheckState(QtCore.Qt.CheckState.Checked)
    # set tip
    checkbox.setToolTip(opt.help)

    def to_command():
        if checkbox.checkState():
            return [opt.opts[0]]
        else:
            return opt.secondary_opts

    return [checkbox], to_command


class GChoiceComboBox(click.types.Choice):
    def to_widget(self, opt):
        cb = _InputComboBox()
        cb.addItems(self.choices)

        def to_command():
            return [opt.opts[0], cb.currentText()]

        return [cb], to_command


def count_option(opt):
    sb = _InputSpinBox()

    def to_command():
        return [opt.opts[0]] * int(sb.text())

    return [sb], to_command


class GTupleGListView(click.Tuple):
    def to_widget(self, opt):
        view = GListView(opt)

        def to_command():
            _ = [opt.opts[0]]
            for idx in range(view.model.rowCount()):
                _.append(view.model.item(idx).text())
            return _

        return [view], to_command


def multi_text_argument(opt):
    value = GListView(opt)

    def to_command():
        _ = []
        for idx in range(value.model.rowCount()):
            _.append(value.model.item(idx).text())
        return _

    # return [QtWidgets.QLabel(opt.name), value], to_command
    return [_OptionLabel(opt.name), value], to_command


def select_type_validator(tp: click.types.ParamType) -> QtGui.QValidator:
    """select the right validator for `tp`"""
    if isinstance(tp, click.types.IntParamType):
        return QtGui.QIntValidator()
    elif isinstance(tp, click.types.FloatParamType):
        return QtGui.QDoubleValidator()
    return None


def select_opt_validator(opt):
    """select the right validator for `opt`"""
    return select_type_validator(opt.type)


_TO_WIDGET = {
    click.types.Choice: GChoiceComboBox, 
    click.types.Path: GPathGLineEdit_path,
    click.types.IntRange: GIntRangeGSlider,
    click.types.IntParamType: GIntLineEditor,
    click.types.FloatParamType: GFloatLineEditor
}


def opt_to_widget(opt):
    def add_label(ans):
        widgets, to_command = ans
        widgets.insert(0, generate_label(opt))
        return ans

    if opt.nargs > 1:
        ans = add_label(GTupleGListView.to_widget(opt.type, opt))
    elif getattr(opt, "is_bool_flag", False):
        ans = bool_flag_option(opt)
    elif getattr(opt, "count", False):
        ans = add_label(count_option(opt))
    else:
        for t, w_class in _TO_WIDGET.items():
            if isinstance(opt.type, t):
                break
        else:
            w_class = GStringLineEditor
        if opt.multiple:
            s = GMultiple(w_class, opt)
            ans = add_label([[s], s.to_command])
        else:
            ans = add_label(w_class.to_widget(opt.type, opt))
    return ans


class GMultiple(QtWidgets.QGridLayout):
    def __init__(self, cl, opt):
        super().__init__()
        self._class = cl
        self._opt = opt
        self._to_command = []
        self.init_add()
    
    def init_add(self):
        try:
            iterable = enumerate(self._opt.default)
        except:
            self.add()
        else:
            for i, default in iterable:
                opt = copy(self._opt)
                opt.default = default
                self._add(opt, i)
            self._opt.default = []

    def add(self, button=None):
        i = 0 if button is None else button.i + 1
        if i < len(self._to_command):
            for row_id in range(len(self._to_command), i, -1):
                for j in range(3):
                    w = self.itemAtPosition(row_id - 1, j).widget()
                    self.addWidget(w, row_id, j, 1, 1)
                    w.i += 1
        self._add(self._opt, i)
        
    def _add(self, opt, i):
        w, c = self._class.to_widget(opt.type, opt)
        add_button = QtWidgets.QPushButton("+")
        add_button.clicked.connect(lambda: self.add(add_button))
        remove_button = QtWidgets.QPushButton("-")
        remove_button.clicked.connect(lambda: self.remove(remove_button))
        for j, w in enumerate([w[0], add_button, remove_button]):
            w.i = i
            self.addWidget(w, i, j, 1, 1)
        self._to_command.insert(i, c)

    def remove(self, button):
        i = button.i
        if i == 0 and len(self._to_command) == 1:
            return
        was = []
        for row_id in range(i, len(self._to_command)):
            rws = []
            for j in range(3):
                w = self.itemAtPosition(row_id, j).widget()
                w.i -= 1
                rws.append(w)
                self.removeWidget(w)
            was.append(rws)
        for w in was[0]:
            w.hide()
            del w
        was = was[1:]
        self._to_command.pop(i)
        for row_id, rws in enumerate(was, i):
            for j, w in enumerate(rws):
                self.addWidget(w, row_id, j, 1, 1)


    def to_command(self):
        ans = []
        for c in self._to_command:
            ans.extend(c())
        return ans



def _to_widget(opt):
    # customed widget
    if isinstance(opt.type, click.types.FuncParamType):
        if hasattr(opt.type.func, "to_widget"):
            return opt.type.func.to_widget()
    elif hasattr(opt.type, "to_widget"):
        return opt.type.to_widget()

    if isinstance(opt, click.core.Argument):
        if opt.nargs == 1:
            w, tc = opt_to_widget(opt)
            return w, argument_command(tc)
        elif opt.nargs > 1 or opt.nargs == -1:
            return multi_text_argument(opt)
    else:
        return opt_to_widget(opt)


def layout_append_opts(layout, opts):
    params_func = []
    widgets = []
    i = 0
    for i, para in enumerate(opts):
        widget, value_func = _to_widget(para)
        widgets.append(widget)
        params_func.append(value_func)
        for idx, w in enumerate(widget):
            if isinstance(w, QtWidgets.QLayout):
                layout.addLayout(w, i, idx)
            else:
                layout.addWidget(w, i, idx)
    return layout, params_func, widgets


def generate_sysargv(cmd_list):
    argv_list = []
    for name, func_list in cmd_list:
        argv_list.append(name)
        for value_func in func_list:
            argv_list += value_func()
    return argv_list


class _Spliter(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super(_Spliter, self).__init__(parent=parent)
        self.setFrameShape(QtWidgets.QFrame.HLine)


class _InputComboBox(QtWidgets.QComboBox):
    pass


class _InputTabWidget(QtWidgets.QTabWidget):
    pass


class _HelpLabel(QtWidgets.QLabel):
    pass


class _OptionLabel(QtWidgets.QLabel):
    pass


class _InputLineEdit(QtWidgets.QLineEdit):
    pass


class _InputCheckBox(QtWidgets.QCheckBox):
    pass


class _InputSpinBox(QtWidgets.QSpinBox):
    pass


class CommandLayout(QtWidgets.QGridLayout):
    def __init__(self, func, run_exit, parent_layout=None):
        super(CommandLayout, self).__init__()
        self.parent_layout = parent_layout
        self.func = func
        self.run_exit = run_exit
        if func.help:
            label = _HelpLabel(func.help)
            label.setWordWrap(True)
            self.addWidget(label, 0, 0, 1, 2)
            frame = _Spliter()
            self.addWidget(frame, 1, 0, 1, 2)
        self.params_func, self.widgets = self.append_opts(self.func.params)

    def add_sysargv(self):
        if hasattr(self.parent_layout, "add_sysargv"):
            self.parent_layout.add_sysargv()
        sys.argv += generate_sysargv([(self.func.name, self.params_func)])

    def append_opts(self, opts):
        params_func = []
        widgets = []
        for i, para in enumerate(opts, self.rowCount()):
            widget, value_func = _to_widget(para)
            widgets.append(widget)
            params_func.append(value_func)
            for idx, w in enumerate(widget):
                if isinstance(w, QtWidgets.QLayout):
                    self.addLayout(w, i, idx)
                else:
                    self.addWidget(w, i, idx)
        return params_func, widgets

    def generate_cmd_button(self, label, cmd_slot, tooltip=""):
        button = QtWidgets.QPushButton(label)
        button.setToolTip(tooltip)
        button.clicked.connect(self.clean_sysargv)
        button.clicked.connect(self.add_sysargv)
        button.clicked.connect(cmd_slot)
        return button

    def add_cmd_button(self, label, cmd_slot, pos=None):
        run_button = self.generate_cmd_button(label, cmd_slot)
        if pos is None:
            pos = self.rowCount() + 1, 0
        self.addWidget(run_button, pos[0], pos[1])

    def add_cmd_buttons(self, args):
        row = self.rowCount() + 1
        cmd_layout = QtWidgets.QGridLayout()
        cmd_layout.setHorizontalSpacing(20)
        cmd_layout.addItem(
            QtWidgets.QSpacerItem(
                0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
            ),
            0,
            0,
            1,
            2,
        )
        for col, arg in enumerate(args):
            button = self.generate_cmd_button(**arg)
            cmd_layout.addWidget(button, 1, col)
        self.addLayout(cmd_layout, row, 0, 1, 2)

    @QtCore.pyqtSlot()
    def clean_sysargv(self):
        sys.argv = []


class RunCommand(QtCore.QRunnable):
    def __init__(self, func, run_exit):
        super(RunCommand, self).__init__()
        self.func = func
        self.run_exit = run_exit

    @QtCore.pyqtSlot()
    def run(self):
        cmd_str = " ".join(sys.argv)
        logging.info(
            f"Running: {cmd_str}",
        )
        try:
            self.func(standalone_mode=self.run_exit)
            logging.info(f"Successfully executed: {cmd_str}")
        except click.exceptions.BadParameter as bpe:
            # warning message
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText(bpe.format_message())
            msg.exec_()
        except Exception as bpe:
            logging.error(bpe)
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText(repr(bpe))
            msg.exec_()


class GCommand(click.Command):
    def __init__(self, new_thread=True, *arg, **args):
        super(GCommand, self).__init__(*arg, **args)
        self.new_thread = new_thread


class GOption(click.Option):
    def __init__(self, *arg, show_name=_missing, **args):
        super(GOption, self).__init__(*arg, **args)
        self.show_name = show_name


# def normalOutputWritten(t):
# """Append text to the QTextEdit."""
# Maybe QTextEdit.append() works as well, but this is how I do it:
# cursor = text.textCursor()
# cursor.movePosition(QtGui.QTextCursor.End)
# cursor.insertText(t)
# text.setTextCursor(cursor)
# text.ensureCursorVisible()


class GuiStream(QtCore.QObject):
    textWritten = QtCore.pyqtSignal(str)

    def flush(self):
        pass

    def write(self, text):
        self.textWritten.emit(str(text))


class OutputEdit(QtWidgets.QTextEdit):
    def print(self, text):
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()


class App(QtWidgets.QWidget):
    def __init__(
        self,
        func,
        run_exit,
        new_thread,
        output="gui",
        left=10,
        top=10,
        width=400,
        height=140,
    ):
        """
        Parameters
        ----------
        output : str
            'gui': [default] redirect screen output to the gui
            'term': do nothing
        """
        super().__init__()
        self.new_thread = new_thread
        self.title = func.name
        self.func = func
        self.initUI(run_exit, QtCore.QRect(left, top, width, height))
        self.threadpool = QtCore.QThreadPool()
        self.outputEdit = self.initOutput(output)

    def initOutput(self, output):
        if output == "gui":
            sys.stdout = GuiStream()
            sys.stderr = sys.stdout
            text = OutputEdit()
            text.setReadOnly(True)
            sys.stdout.textWritten.connect(text.print)
            sys.stdout.textWritten.connect(text.show)
            return text
        else:
            return None

    def closeEvent(self, event):
        app = QtWidgets.QApplication.instance()
        app.quit()

    def initCommandUI(self, func, run_exit, parent_layout=None):
        opt_set = CommandLayout(func, run_exit, parent_layout=parent_layout)
        if isinstance(func, click.MultiCommand):
            tabs = _InputTabWidget()
            for cmd, f in func.commands.items():
                sub_opt_set = self.initCommandUI(f, run_exit, parent_layout=opt_set)
                tab = QtWidgets.QWidget()
                tab.setLayout(sub_opt_set)
                tabs.addTab(tab, cmd)
            opt_set.addWidget(tabs, opt_set.rowCount(), 0, 1, 2)
            # return opt_set
        elif isinstance(func, click.Command):
            new_thread = getattr(func, "new_thread", self.new_thread)
            opt_set.add_cmd_buttons(
                args=[
                    {
                        "label": "&Run",
                        "cmd_slot": partial(self.run_cmd, new_thread=new_thread),
                        "tooltip": "run command",
                    },
                    {
                        "label": "&Copy",
                        "cmd_slot": self.copy_cmd,
                        "tooltip": "copy command to clipboard",
                    },
                ]
            )
        return opt_set

    def initUI(self, run_exit, geometry):
        self.run_exit = run_exit
        self.setWindowTitle(self.title)
        # self.setGeometry(self.left, self.top, self.width, self.height)
        self.setGeometry(geometry)
        self.opt_set = self.initCommandUI(
            self.func,
            run_exit,
        )
        self.setLayout(self.opt_set)
        self.show()

    @QtCore.pyqtSlot()
    def copy_cmd(self):
        cb = QtWidgets.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cmd_text = " ".join(sys.argv)
        cb.setText(cmd_text, mode=cb.Clipboard)

        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setText(f"copy '{cmd_text}' to clipboard")
        msg.exec_()

    def run_cmd(self, new_thread):
        runcmd = RunCommand(self.func, self.run_exit)
        if new_thread:
            self.threadpool.start(runcmd)
        else:
            runcmd.run()


def gui_it(click_func, style="qdarkstyle", **kargs) -> None:
    """
    Parameters
    ----------
    click_func
    `new_thread` is used for qt-based func, like matplotlib
    """
    global _gstyle
    _gstyle = GStyle(style)
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(_gstyle.stylesheet)

    # set the default value for argvs
    kargs["run_exit"] = kargs.get("run_exit", False)
    kargs["new_thread"] = kargs.get("new_thread", False)

    ex = App(click_func, **kargs)
    sys.exit(app.exec_())


def gui_option(**kargs) -> click.core.BaseCommand:
    """decorator for adding '--gui' option to command"""
    
    # TODO: add run_exit, new_thread
    
    def actual_decorator(f: click.core.BaseCommand):
        def run_gui_it(ctx, param, value):
            if not value or ctx.resilient_parsing:
                return
            f.params = [p for p in f.params if not p.name == "gui"]
            gui_it(f, **kargs)
            ctx.exit()
        
        return click.option(
            "--gui",
            is_flag=True,
            callback=run_gui_it,
            help="run with gui",
            expose_value=False,
            is_eager=False,
        )(f)

    return actual_decorator
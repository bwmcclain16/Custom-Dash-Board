from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QDrag, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QDoubleSpinBox,
)
from PySide6.QtCore import QMimeData

from .can_bus import CanBusManager, evaluate_alert
from .models import AlertRule, DashboardConfig, WidgetConfig


class DashboardWidgetItem(QGraphicsObject):
    selected = Signal(str)
    geometry_changed = Signal(str)

    def __init__(self, config: WidgetConfig) -> None:
        super().__init__()
        self.config = config
        self.value = 0.0
        self.alert_text = config.warning_text
        self.current_background = config.background_color
        self.current_border = config.border_color
        self.current_text = config.text_color
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setPos(config.x, config.y)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.config.width, self.config.height)

    def paint(self, painter: QPainter, option: Any, widget: QWidget | None = None) -> None:
        rect = self.boundingRect()
        painter.setRenderHint(QPainter.Antialiasing)
        if self.config.background_image and Path(self.config.background_image).exists():
            pixmap = QPixmap(self.config.background_image)
            painter.drawPixmap(rect.toRect(), pixmap)
        painter.setBrush(QColor(self.current_background))
        pen = QPen(QColor(self.current_border), self.config.border_width)
        if self.isSelected():
            pen.setWidth(self.config.border_width + 2)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, self.config.border_radius, self.config.border_radius)

        painter.setPen(QColor(self.current_text))
        if self.config.show_title:
            title_font = QFont(self.config.font_family, self.config.title_font_size)
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.drawText(QRectF(14, 10, rect.width() - 28, 24), Qt.AlignLeft | Qt.AlignVCenter, self.config.title)

        value_font = QFont(self.config.font_family, self.config.value_font_size)
        value_font.setBold(True)
        painter.setFont(value_font)
        display_text = self.config.display_value(self.value)
        if self.config.widget_type == "indicator":
            display_text = "ON" if self.value else "OFF"
        painter.drawText(QRectF(14, 34, rect.width() - 28, rect.height() - 68), Qt.AlignCenter, display_text)

        if self.config.widget_type == "bar":
            normalized = 0.0
            span = self.config.signal.max_value - self.config.signal.min_value
            if span > 0:
                normalized = min(max((self.value - self.config.signal.min_value) / span, 0.0), 1.0)
            bar_rect = QRectF(16, rect.height() - 28, rect.width() - 32, 12)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#0b1120"))
            painter.drawRoundedRect(bar_rect, 6, 6)
            painter.setBrush(QColor(self.current_border))
            painter.drawRoundedRect(QRectF(bar_rect.x(), bar_rect.y(), bar_rect.width() * normalized, bar_rect.height()), 6, 6)

        if self.alert_text:
            alert_font = QFont(self.config.font_family, 10)
            painter.setFont(alert_font)
            painter.drawText(QRectF(14, rect.height() - 26, rect.width() - 28, 18), Qt.AlignLeft | Qt.AlignVCenter, self.alert_text)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.config.x = int(self.pos().x())
            self.config.y = int(self.pos().y())
            self.geometry_changed.emit(self.config.id)
        if change == QGraphicsItem.ItemSelectedHasChanged and self.isSelected():
            self.selected.emit(self.config.id)
        return super().itemChange(change, value)

    def set_value(self, value: float) -> None:
        self.value = value
        state = evaluate_alert(
            value,
            self.config.alerts,
            lambda: {
                "text": self.config.warning_text,
                "text_color": self.config.text_color,
                "background_color": self.config.background_color,
                "border_color": self.config.border_color,
            },
        )
        self.alert_text = state["text"]
        self.current_text = state["text_color"]
        self.current_background = state["background_color"]
        self.current_border = state["border_color"]
        self.update()

    def sync_from_config(self) -> None:
        self.prepareGeometryChange()
        self.setPos(self.config.x, self.config.y)
        self.current_background = self.config.background_color
        self.current_border = self.config.border_color
        self.current_text = self.config.text_color
        self.alert_text = self.config.warning_text
        self.update()


class DashboardScene(QGraphicsScene):
    widget_selected = Signal(str)

    def __init__(self, config: DashboardConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setSceneRect(0, 0, 1280, 720)
        self._items: dict[str, DashboardWidgetItem] = {}
        self.rebuild()

    def rebuild(self) -> None:
        self.clear()
        self._items.clear()
        self.setBackgroundBrush(QColor(self.config.theme.canvas_color))
        for widget in self.config.widgets:
            item = DashboardWidgetItem(widget)
            item.selected.connect(self.widget_selected.emit)
            self.addItem(item)
            self._items[widget.id] = item
        self.update()

    def add_widget(self, widget: WidgetConfig) -> None:
        self.config.widgets.append(widget)
        item = DashboardWidgetItem(widget)
        item.selected.connect(self.widget_selected.emit)
        self.addItem(item)
        self._items[widget.id] = item

    def remove_widget(self, widget_id: str) -> None:
        item = self._items.pop(widget_id, None)
        if item is not None:
            self.removeItem(item)
        self.config.widgets = [widget for widget in self.config.widgets if widget.id != widget_id]

    def widget_item(self, widget_id: str) -> DashboardWidgetItem | None:
        return self._items.get(widget_id)


class DashboardView(QGraphicsView):
    widget_drop_requested = Signal(str, int, int)

    def __init__(self, scene: DashboardScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setScene(scene)
        self.setMinimumWidth(900)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasText():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasText():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasText():
            point = self.mapToScene(event.position().toPoint())
            self.widget_drop_requested.emit(event.mimeData().text(), int(point.x()), int(point.y()))
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class PaletteListWidget(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setDragEnabled(True)

    def startDrag(self, supported_actions) -> None:  # type: ignore[override]
        current = self.currentItem()
        if current is None:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(current.text())
        drag.setMimeData(mime)
        drag.exec(supported_actions)


class AlertEditor(QGroupBox):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__("Alert Rules")
        self.widget: WidgetConfig | None = None
        self.list = QListWidget()
        self.label_edit = QLineEdit()
        self.operator_box = QComboBox()
        self.operator_box.addItems([">", ">=", "<", "<=", "==", "!="])
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(-100000, 100000)
        self.threshold_spin.setDecimals(2)
        self.bg_button = QPushButton("Alert Background")
        self.border_button = QPushButton("Alert Border")
        self.text_button = QPushButton("Alert Text")
        self.add_button = QPushButton("Add Rule")
        self.remove_button = QPushButton("Remove Rule")
        layout = QVBoxLayout(self)
        layout.addWidget(self.list)
        form = QFormLayout()
        form.addRow("Label", self.label_edit)
        form.addRow("Condition", self.operator_box)
        form.addRow("Threshold", self.threshold_spin)
        layout.addLayout(form)
        button_row = QHBoxLayout()
        button_row.addWidget(self.bg_button)
        button_row.addWidget(self.border_button)
        button_row.addWidget(self.text_button)
        layout.addLayout(button_row)
        action_row = QHBoxLayout()
        action_row.addWidget(self.add_button)
        action_row.addWidget(self.remove_button)
        layout.addLayout(action_row)

        self._selected_bg = "#c62828"
        self._selected_border = "#ffeb3b"
        self._selected_text = "#ffffff"
        self.add_button.clicked.connect(self.add_rule)
        self.remove_button.clicked.connect(self.remove_rule)
        self.bg_button.clicked.connect(lambda: self._pick_color("bg"))
        self.border_button.clicked.connect(lambda: self._pick_color("border"))
        self.text_button.clicked.connect(lambda: self._pick_color("text"))

    def load_widget(self, widget: WidgetConfig | None) -> None:
        self.widget = widget
        self.list.clear()
        if widget is None:
            return
        for alert in widget.alerts:
            self.list.addItem(f"{alert.label}: value {alert.operator} {alert.threshold}")

    def add_rule(self) -> None:
        if self.widget is None:
            return
        rule = AlertRule(
            label=self.label_edit.text() or "Warning",
            operator=self.operator_box.currentText(),
            threshold=self.threshold_spin.value(),
            background_color=self._selected_bg,
            border_color=self._selected_border,
            text_color=self._selected_text,
        )
        self.widget.alerts.append(rule)
        self.load_widget(self.widget)
        self.changed.emit()

    def remove_rule(self) -> None:
        if self.widget is None or self.list.currentRow() < 0:
            return
        self.widget.alerts.pop(self.list.currentRow())
        self.load_widget(self.widget)
        self.changed.emit()

    def _pick_color(self, slot: str) -> None:
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        if slot == "bg":
            self._selected_bg = color.name()
        elif slot == "border":
            self._selected_border = color.name()
        else:
            self._selected_text = color.name()


class InspectorPanel(QWidget):
    widget_changed = Signal()
    delete_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.widget: WidgetConfig | None = None
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.form = QFormLayout(content)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.delete_button = QPushButton("Delete Widget")
        layout.addWidget(self.delete_button)
        self.delete_button.clicked.connect(self._emit_delete)

        self.name_edit = QLineEdit()
        self.title_edit = QLineEdit()
        self.type_box = QComboBox()
        self.type_box.addItems(["digital", "bar", "indicator"])
        self.show_title_check = QCheckBox("Show title")
        self.value_prefix_edit = QLineEdit()
        self.value_suffix_edit = QLineEdit()
        self.warning_edit = QLineEdit()
        self.decimals_spin = QSpinBox(); self.decimals_spin.setRange(0, 5)
        self.value_font_spin = QSpinBox(); self.value_font_spin.setRange(8, 96)
        self.title_font_spin = QSpinBox(); self.title_font_spin.setRange(8, 36)
        self.x_spin = QSpinBox(); self.x_spin.setRange(0, 4000)
        self.y_spin = QSpinBox(); self.y_spin.setRange(0, 4000)
        self.width_spin = QSpinBox(); self.width_spin.setRange(80, 1000)
        self.height_spin = QSpinBox(); self.height_spin.setRange(60, 1000)
        self.border_width_spin = QSpinBox(); self.border_width_spin.setRange(0, 20)
        self.border_radius_spin = QSpinBox(); self.border_radius_spin.setRange(0, 100)

        self.text_color_button = QPushButton("Text Color")
        self.bg_color_button = QPushButton("Background Color")
        self.border_color_button = QPushButton("Border Color")
        self.bg_image_button = QPushButton("Background Image")

        self.can_id_spin = QSpinBox(); self.can_id_spin.setRange(0, 0x7FF); self.can_id_spin.setDisplayIntegerBase(16)
        self.start_byte_spin = QSpinBox(); self.start_byte_spin.setRange(0, 7)
        self.length_spin = QSpinBox(); self.length_spin.setRange(1, 8)
        self.scale_spin = QDoubleSpinBox(); self.scale_spin.setDecimals(4); self.scale_spin.setRange(-1000, 1000); self.scale_spin.setValue(1.0)
        self.offset_spin = QDoubleSpinBox(); self.offset_spin.setDecimals(4); self.offset_spin.setRange(-100000, 100000)
        self.min_spin = QDoubleSpinBox(); self.min_spin.setRange(-100000, 100000)
        self.max_spin = QDoubleSpinBox(); self.max_spin.setRange(-100000, 100000); self.max_spin.setValue(100.0)
        self.units_edit = QLineEdit()
        self.endian_box = QComboBox(); self.endian_box.addItems(["little", "big"])
        self.signed_check = QCheckBox("Signed value")

        self.form.addRow("Name", self.name_edit)
        self.form.addRow("Title", self.title_edit)
        self.form.addRow("Type", self.type_box)
        self.form.addRow("", self.show_title_check)
        self.form.addRow("Value prefix", self.value_prefix_edit)
        self.form.addRow("Value suffix", self.value_suffix_edit)
        self.form.addRow("Warning text", self.warning_edit)
        self.form.addRow("Decimals", self.decimals_spin)
        self.form.addRow("Value font", self.value_font_spin)
        self.form.addRow("Title font", self.title_font_spin)
        self.form.addRow("X", self.x_spin)
        self.form.addRow("Y", self.y_spin)
        self.form.addRow("Width", self.width_spin)
        self.form.addRow("Height", self.height_spin)
        self.form.addRow("Border width", self.border_width_spin)
        self.form.addRow("Border radius", self.border_radius_spin)
        self.form.addRow("", self.text_color_button)
        self.form.addRow("", self.bg_color_button)
        self.form.addRow("", self.border_color_button)
        self.form.addRow("", self.bg_image_button)
        self.form.addRow("CAN ID (hex)", self.can_id_spin)
        self.form.addRow("Start byte", self.start_byte_spin)
        self.form.addRow("Byte length", self.length_spin)
        self.form.addRow("Scale", self.scale_spin)
        self.form.addRow("Offset", self.offset_spin)
        self.form.addRow("Min value", self.min_spin)
        self.form.addRow("Max value", self.max_spin)
        self.form.addRow("Units", self.units_edit)
        self.form.addRow("Endian", self.endian_box)
        self.form.addRow("", self.signed_check)

        self.alert_editor = AlertEditor()
        layout.addWidget(self.alert_editor)
        self.alert_editor.changed.connect(self.widget_changed.emit)

        self._buttons = {
            self.text_color_button: "text_color",
            self.bg_color_button: "background_color",
            self.border_color_button: "border_color",
        }
        for button in self._buttons:
            button.clicked.connect(lambda _checked=False, btn=button: self._pick_color(self._buttons[btn]))
        self.bg_image_button.clicked.connect(self._pick_image)

        controls = [
            self.name_edit, self.title_edit, self.type_box, self.show_title_check, self.value_prefix_edit,
            self.value_suffix_edit, self.warning_edit, self.decimals_spin, self.value_font_spin,
            self.title_font_spin, self.x_spin, self.y_spin, self.width_spin, self.height_spin,
            self.border_width_spin, self.border_radius_spin, self.can_id_spin, self.start_byte_spin,
            self.length_spin, self.scale_spin, self.offset_spin, self.min_spin, self.max_spin,
            self.units_edit, self.endian_box, self.signed_check,
        ]
        for control in controls:
            signal = getattr(control, "editingFinished", None)
            if signal is not None:
                signal.connect(self.apply_changes)
            signal = getattr(control, "currentTextChanged", None)
            if signal is not None:
                signal.connect(lambda *_args: self.apply_changes())
            signal = getattr(control, "valueChanged", None)
            if signal is not None:
                signal.connect(lambda *_args: self.apply_changes())
            signal = getattr(control, "toggled", None)
            if signal is not None:
                signal.connect(lambda *_args: self.apply_changes())
            signal = getattr(control, "textChanged", None)
            if signal is not None:
                signal.connect(lambda *_args: self.apply_changes())

    def load_widget(self, widget: WidgetConfig | None) -> None:
        self.widget = widget
        self.alert_editor.load_widget(widget)
        if widget is None:
            return
        self.name_edit.setText(widget.name)
        self.title_edit.setText(widget.title)
        self.type_box.setCurrentText(widget.widget_type)
        self.show_title_check.setChecked(widget.show_title)
        self.value_prefix_edit.setText(widget.value_prefix)
        self.value_suffix_edit.setText(widget.value_suffix)
        self.warning_edit.setText(widget.warning_text)
        self.decimals_spin.setValue(widget.decimals)
        self.value_font_spin.setValue(widget.value_font_size)
        self.title_font_spin.setValue(widget.title_font_size)
        self.x_spin.setValue(widget.x)
        self.y_spin.setValue(widget.y)
        self.width_spin.setValue(widget.width)
        self.height_spin.setValue(widget.height)
        self.border_width_spin.setValue(widget.border_width)
        self.border_radius_spin.setValue(widget.border_radius)
        self.can_id_spin.setValue(widget.signal.arbitration_id)
        self.start_byte_spin.setValue(widget.signal.start_byte)
        self.length_spin.setValue(widget.signal.length_bytes)
        self.scale_spin.setValue(widget.signal.scale)
        self.offset_spin.setValue(widget.signal.offset)
        self.min_spin.setValue(widget.signal.min_value)
        self.max_spin.setValue(widget.signal.max_value)
        self.units_edit.setText(widget.signal.units)
        self.endian_box.setCurrentText(widget.signal.endian)
        self.signed_check.setChecked(widget.signal.signed)

    def apply_changes(self) -> None:
        if self.widget is None:
            return
        widget = self.widget
        widget.name = self.name_edit.text() or widget.name
        widget.title = self.title_edit.text() or widget.title
        widget.widget_type = self.type_box.currentText()
        widget.show_title = self.show_title_check.isChecked()
        widget.value_prefix = self.value_prefix_edit.text()
        widget.value_suffix = self.value_suffix_edit.text()
        widget.warning_text = self.warning_edit.text()
        widget.decimals = self.decimals_spin.value()
        widget.value_font_size = self.value_font_spin.value()
        widget.title_font_size = self.title_font_spin.value()
        widget.x = self.x_spin.value()
        widget.y = self.y_spin.value()
        widget.width = self.width_spin.value()
        widget.height = self.height_spin.value()
        widget.border_width = self.border_width_spin.value()
        widget.border_radius = self.border_radius_spin.value()
        widget.signal.arbitration_id = self.can_id_spin.value()
        widget.signal.start_byte = self.start_byte_spin.value()
        widget.signal.length_bytes = self.length_spin.value()
        widget.signal.scale = self.scale_spin.value()
        widget.signal.offset = self.offset_spin.value()
        widget.signal.min_value = self.min_spin.value()
        widget.signal.max_value = self.max_spin.value()
        widget.signal.units = self.units_edit.text()
        widget.signal.endian = self.endian_box.currentText()
        widget.signal.signed = self.signed_check.isChecked()
        self.widget_changed.emit()

    def _pick_color(self, attribute: str) -> None:
        if self.widget is None:
            return
        color = QColorDialog.getColor(QColor(getattr(self.widget, attribute)))
        if color.isValid():
            setattr(self.widget, attribute, color.name())
            self.widget_changed.emit()

    def _pick_image(self) -> None:
        if self.widget is None:
            return
        filename, _ = QFileDialog.getOpenFileName(self, "Choose background image", filter="Images (*.png *.jpg *.jpeg *.bmp)")
        if filename:
            self.widget.background_image = filename
            self.widget_changed.emit()

    def _emit_delete(self) -> None:
        if self.widget is not None:
            self.delete_requested.emit(self.widget.id)


class ThemePanel(QGroupBox):
    theme_changed = Signal()

    def __init__(self, config: DashboardConfig) -> None:
        super().__init__("Dashboard Theme")
        self.config = config
        layout = QFormLayout(self)
        self.title_edit = QLineEdit(config.title)
        self.theme_name = QLineEdit(config.theme.name)
        self.grid_size = QSpinBox(); self.grid_size.setRange(10, 100); self.grid_size.setValue(config.theme.grid_size)
        self.snap_check = QCheckBox("Snap to grid"); self.snap_check.setChecked(config.theme.snap_to_grid)
        self.canvas_color = QPushButton("Canvas Color")
        self.grid_color = QPushButton("Grid Color")
        self.background_button = QPushButton("Canvas Background")
        layout.addRow("Dashboard title", self.title_edit)
        layout.addRow("Theme name", self.theme_name)
        layout.addRow("Grid size", self.grid_size)
        layout.addRow("", self.snap_check)
        layout.addRow("", self.canvas_color)
        layout.addRow("", self.grid_color)
        layout.addRow("", self.background_button)
        self.title_edit.textChanged.connect(self._apply)
        self.theme_name.textChanged.connect(self._apply)
        self.grid_size.valueChanged.connect(self._apply)
        self.snap_check.toggled.connect(self._apply)
        self.canvas_color.clicked.connect(lambda: self._pick_color("canvas_color"))
        self.grid_color.clicked.connect(lambda: self._pick_color("grid_color"))
        self.background_button.clicked.connect(self._pick_image)

    def _apply(self) -> None:
        self.config.title = self.title_edit.text() or self.config.title
        self.config.theme.name = self.theme_name.text() or self.config.theme.name
        self.config.theme.grid_size = self.grid_size.value()
        self.config.theme.snap_to_grid = self.snap_check.isChecked()
        self.theme_changed.emit()

    def _pick_color(self, attr: str) -> None:
        color = QColorDialog.getColor(QColor(getattr(self.config.theme, attr)))
        if color.isValid():
            setattr(self.config.theme, attr, color.name())
            self.theme_changed.emit()

    def _pick_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Choose dashboard background", filter="Images (*.png *.jpg *.jpeg *.bmp)")
        if filename:
            self.config.theme.background_image = filename
            self.theme_changed.emit()


class MainWindow(QMainWindow):
    def __init__(self, config: DashboardConfig | None = None) -> None:
        super().__init__()
        self.config = config or DashboardConfig.default()
        self.setWindowTitle(self.config.title)
        self.resize(1600, 920)
        self.selected_widget_id: str | None = None
        self.scene = DashboardScene(self.config)
        self.scene.widget_selected.connect(self.select_widget)
        self.view = DashboardView(self.scene)
        self.inspector = InspectorPanel()
        self.theme_panel = ThemePanel(self.config)
        self.palette = PaletteListWidget()
        self.palette.addItems(["Digital Widget", "Bar Widget", "Indicator Widget"])
        self.palette.itemDoubleClicked.connect(self.create_widget_from_palette)
        self.can_manager = CanBusManager(self.config, self)
        self.can_manager.frame_received.connect(self.handle_frame)
        self.can_manager.status_changed.connect(self.statusBar().showMessage)
        self._build_ui()
        self._build_toolbar()
        self.view.widget_drop_requested.connect(self.create_widget_from_drop)
        self.can_manager.start()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.can_manager.stop()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        splitter = QSplitter()
        palette_panel = QWidget()
        palette_layout = QVBoxLayout(palette_panel)
        palette_layout.addWidget(QLabel("Widget Library"))
        palette_layout.addWidget(self.palette)
        add_button = QPushButton("Add Selected Widget")
        add_button.clicked.connect(self.create_widget_from_palette)
        palette_layout.addWidget(add_button)
        palette_layout.addWidget(self.theme_panel)

        right_tabs = QTabWidget()
        right_tabs.addTab(self.inspector, "Widget Setup")
        setup_help = QTextEdit()
        setup_help.setReadOnly(True)
        setup_help.setHtml(
            "<h3>How to use</h3>"
            "<ul>"
            "<li>Double-click a widget type to add it to the dashboard.</li>"
            "<li>Click any widget to edit CAN ID, colors, borders, warnings, sizes, and units.</li>"
            "<li>Add alert rules per widget for shift lights, over-temp, low pressure, or other custom logic.</li>"
            "<li>Save the dashboard as JSON and deploy the same file on Raspberry Pi 5 or LattePanda IOTA.</li>"
            "</ul>"
        )
        right_tabs.addTab(setup_help, "Quick Start")

        splitter.addWidget(palette_panel)
        splitter.addWidget(self.view)
        splitter.addWidget(right_tabs)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self.inspector.widget_changed.connect(self.sync_selected_widget)
        self.inspector.delete_requested.connect(self.delete_widget)
        self.theme_panel.theme_changed.connect(self.refresh_theme)
        self.setStatusBar(QStatusBar())

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("File")
        self.addToolBar(toolbar)
        new_action = QAction("New", self)
        save_action = QAction("Save", self)
        load_action = QAction("Load", self)
        duplicate_action = QAction("Duplicate Widget", self)
        remove_action = QAction("Remove Widget", self)
        toolbar.addAction(new_action)
        toolbar.addAction(save_action)
        toolbar.addAction(load_action)
        toolbar.addAction(duplicate_action)
        toolbar.addAction(remove_action)
        new_action.triggered.connect(self.new_dashboard)
        save_action.triggered.connect(self.save_dashboard)
        load_action.triggered.connect(self.load_dashboard)
        duplicate_action.triggered.connect(self.duplicate_selected_widget)
        remove_action.triggered.connect(lambda: self.delete_widget(self.selected_widget_id) if self.selected_widget_id else None)

    def create_widget_from_palette(self, item: QListWidgetItem | None = None) -> None:
        current = item.text() if isinstance(item, QListWidgetItem) else (self.palette.currentItem().text() if self.palette.currentItem() else "Digital Widget")
        self._add_widget(current)

    def create_widget_from_drop(self, widget_name: str, x: int, y: int) -> None:
        self._add_widget(widget_name, x, y)

    def _add_widget(self, current: str, x: int | None = None, y: int | None = None) -> None:
        widget_type = {
            "Digital Widget": "digital",
            "Bar Widget": "bar",
            "Indicator Widget": "indicator",
        }[current]
        widget = WidgetConfig(
            name=f"{current} {len(self.config.widgets) + 1}",
            title=current.replace(" Widget", ""),
            widget_type=widget_type,
            x=x if x is not None else 80 + 30 * len(self.config.widgets),
            y=y if y is not None else 80 + 30 * len(self.config.widgets),
            value_suffix=" " + ("rpm" if widget_type == "digital" else "%" if widget_type == "bar" else ""),
        )
        self.scene.add_widget(widget)
        self.select_widget(widget.id)

    def select_widget(self, widget_id: str) -> None:
        self.selected_widget_id = widget_id
        widget = next((item for item in self.config.widgets if item.id == widget_id), None)
        self.inspector.load_widget(widget)

    def sync_selected_widget(self) -> None:
        if not self.selected_widget_id:
            return
        item = self.scene.widget_item(self.selected_widget_id)
        if item is not None:
            if self.config.theme.snap_to_grid:
                grid = self.config.theme.grid_size
                item.config.x = round(item.config.x / grid) * grid
                item.config.y = round(item.config.y / grid) * grid
            item.sync_from_config()
        self.setWindowTitle(self.config.title)
        self.scene.update()

    def delete_widget(self, widget_id: str | None) -> None:
        if widget_id is None:
            return
        self.scene.remove_widget(widget_id)
        self.selected_widget_id = None
        self.inspector.load_widget(None)

    def duplicate_selected_widget(self) -> None:
        if not self.selected_widget_id:
            return
        widget = next((item for item in self.config.widgets if item.id == self.selected_widget_id), None)
        if widget is None:
            return
        clone = replace(widget, id=WidgetConfig().id, x=widget.x + 40, y=widget.y + 40)
        clone.alerts = [replace(rule) for rule in widget.alerts]
        clone.signal = replace(widget.signal)
        self.scene.add_widget(clone)
        self.select_widget(clone.id)

    def refresh_theme(self) -> None:
        self.setWindowTitle(self.config.title)
        self.scene.setBackgroundBrush(QColor(self.config.theme.canvas_color))
        self.scene.update()

    def new_dashboard(self) -> None:
        self.config = DashboardConfig.default()
        self.scene.config = self.config
        self.scene.rebuild()
        self.theme_panel.config = self.config
        self.inspector.load_widget(None)
        self.selected_widget_id = None
        self.can_manager.stop()
        self.can_manager.config = self.config
        self.can_manager.start()
        self.refresh_theme()

    def save_dashboard(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "Save dashboard", filter="Dashboard (*.json)")
        if filename:
            self.config.save(filename)
            self.statusBar().showMessage(f"Saved dashboard to {filename}", 5000)

    def load_dashboard(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Load dashboard", filter="Dashboard (*.json)")
        if not filename:
            return
        try:
            self.config = DashboardConfig.load(filename)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", f"Failed to load dashboard: {exc}")
            return
        self.scene.config = self.config
        self.scene.rebuild()
        self.theme_panel.config = self.config
        self.theme_panel.title_edit.setText(self.config.title)
        self.theme_panel.theme_name.setText(self.config.theme.name)
        self.theme_panel.grid_size.setValue(self.config.theme.grid_size)
        self.theme_panel.snap_check.setChecked(self.config.theme.snap_to_grid)
        self.can_manager.stop()
        self.can_manager.config = self.config
        self.can_manager.start()
        self.refresh_theme()

    def handle_frame(self, arbitration_id: int, data: bytes) -> None:
        for widget in self.config.widgets:
            if widget.signal.arbitration_id != arbitration_id:
                continue
            value = widget.signal.decode(data)
            item = self.scene.widget_item(widget.id)
            if item is not None:
                item.set_value(value)

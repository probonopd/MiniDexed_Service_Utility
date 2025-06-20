from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider, QWidget, QGridLayout, QFrame, QSizePolicy, QInputDialog, QLCDNumber, QTextEdit, QSplitter, QScrollArea, QPushButton
from PySide6.QtCore import Qt, Signal
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtGui import QResizeEvent, QPalette, QColor, QMouseEvent
from single_voice_dump_decoder import SingleVoiceDumpDecoder
from envelope_widget import EnvelopeWidget
from keyboard_scaling_widget import KeyboardScalingWidget
from param_info_panel import ParamInfoPanel
from algorithm_gallery_dialog import AlgorithmGalleryDialog
import os
import json
import glob

# --- Static definitions and tables ---

DX7_CARRIER_MAP = [
    [0, 2], [0, 2], [0, 3], [0, 3], [0, 2, 4], [0, 2, 4], [0, 2], [0, 2], [0, 2], [0, 3], [0, 3], [0, 2], [0, 2], [0, 2], [0, 2], [0], [0], [0], [0, 3, 4], [0, 1, 3], [0, 1, 3, 4], [0, 2, 3, 4], [0, 1, 3, 4], [0, 1, 2, 3, 4], [0, 1, 2, 3, 4], [0, 1, 3], [0, 1, 3], [0, 2, 5], [0, 1, 2, 4], [0, 1, 2, 5], [0, 1, 2, 3, 4], [0, 1, 2, 3, 4, 5],
]

VALUE_LABELS = {
    'OPI': {0: 'Off', 1: 'On'},
    'LFKS': {0: 'Off', 1: 'On'},
    'LFW': {0: 'Sine', 1: 'Triangle', 2: 'Sawtooth Down', 3: 'Sawtooth Up', 4: 'Square', 5: 'Sample and Hold'},
    'PM': {0: 'Ratio', 1: 'Fixed'},
    # Corrected LC/RC mappings to match DX7 spec and VCED.json
    'LC': {0: '+LIN', 1: '-EXP', 2: '+EXP', 3: '-LIN'},
    'RC': {0: '+LIN', 1: '-EXP', 2: '+EXP', 3: '-LIN'},
}

GLOBAL_PARAM_DEFS = [
    ("FB", "FBL", 0, 7, "Feedback Level"),
    ("SY", "OPI", 0, 1, "Oscillator Key Sync"),
    ("SP", "LFS", 0, 99, "LFO Speed"),
    ("DY", "LFD", 0, 99, "LFO Delay Time"),
    ("PM", "LPMD", 0, 99, "LFO Pitch Modulation Depth"),
    ("AM", "LAMD", 0, 99, "LFO Amplitude Modulation Depth"),
    ("KS", "LFKS", 0, 1, "LFO Key Sync"),
    ("WF", "LFW", 0, 5, "LFO Waveform"),
    ("PS", "LPMS", 0, 7, "Pitch Modulation Sensitivity"),
    ("TR", "TRNP", 0, 48, "Transpose"),
]

OP_FREQ_DEFS = [
    ("PM", "Frequency Mode", "PM", 1),
    ("PC", "Coarse", "C", 31),
    ("PF", "Fine", "F", 99),
    ("PD", "Detune", "D", 14),
]

OP_LEVEL_DEFS = [
    ("TL", "Total Level", "TL", 99),
    ("AMS", "Amplitude Modulation Sensitivity", "AM", 3),
    ("TS", "Touch Sensitivity", "TS", 7),
]

OP_KS_DEFS = [
    ("BP", "Break Point", "BP", 99),
    ("LD", "Left Depth", "LD", 99),
    ("RD", "Right Depth", "RD", 99),
    ("LC", "Left Curve", "LC", 3),
    ("RC", "Right Curve", "RC", 3),
    ("RS", "Rate Scaling", "RS", 7),
]

# --- VoiceEditorPanel class ---

class DraggableValueLabel(QLabel):
    valueChanged = Signal(int)
    def __init__(self, value, min_val, max_val, get_label, parent=None):
        super().__init__(str(value), parent)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._min = min_val
        self._max = max_val
        self._get_label = get_label
        self._dragging = False
        self._last_pos = None
        self._value = value
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setMouseTracking(True)

    def setValue(self, value):
        self._value = value
        self.setText(str(self._get_label(value)))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging and self._last_pos is not None:
            pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
            dy = self._last_pos.y() - pos.y()
            dx = pos.x() - self._last_pos.x()
            delta = dy if abs(dy) > abs(dx) else dx
            if abs(delta) >= 2:
                new_val = max(self._min, min(self._max, self._value + int(delta / 2)))
                if new_val != self._value:
                    self._value = new_val
                    self.setText(str(self._get_label(self._value)))
                    self.valueChanged.emit(self._value)
                self._last_pos = pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._dragging:
            self._dragging = False
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta != 0:
            step = 1 if delta > 0 else -1
            new_val = max(self._min, min(self._max, self._value + step))
            if new_val != self._value:
                self._value = new_val
                self.setText(str(self._get_label(self._value)))
                self.valueChanged.emit(self._value)
        super().wheelEvent(event)

class SvgWheelWidget(QSvgWidget):
    def __init__(self, parent=None, alg_combo=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")
        self.setVisible(True)
        self.alg_combo = alg_combo
        self.setMouseTracking(True)
        self.setToolTip("Scroll to change algorithm\nClick to show all algorithms")

    def wheelEvent(self, event):
        if self.alg_combo is not None:
            delta = event.angleDelta().y()
            if delta != 0:
                step = 1 if delta > 0 else -1
                idx = self.alg_combo.currentIndex()
                new_idx = max(0, min(self.alg_combo.count() - 1, idx + step))
                if new_idx != idx:
                    self.alg_combo.setCurrentIndex(new_idx)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.alg_combo is not None:
            parent = self.parentWidget()
            # Find images path
            images_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "images"))
            dlg = AlgorithmGalleryDialog(parent, self.alg_combo, images_path)
            dlg.exec()
        else:
            super().mousePressEvent(event)

class VoiceEditorPanel(QWidget):
    _instance = None

    @classmethod
    def get_instance(cls, midi_outport=None, voice_bytes=None, parent=None):
        if cls._instance is None or not hasattr(cls._instance, 'isVisible') or not cls._instance.isVisible():
            cls._instance = VoiceEditorPanel(midi_outport=midi_outport, voice_bytes=voice_bytes, parent=parent)
            # Optionally connect a close event to clear _instance
            cls._instance.destroyed.connect(lambda: setattr(cls, '_instance', None))
        else:
            # Update midi_outport and voice_bytes if provided
            if midi_outport is not None:
                cls._instance.midi_outport = midi_outport
            if voice_bytes is not None:
                cls._instance.voice_bytes = voice_bytes
                cls._instance.decoder = SingleVoiceDumpDecoder(voice_bytes)
                cls._instance.decoder.decode()
                cls._instance.params = cls._instance.decoder.params
        return cls._instance

    @classmethod
    def show_singleton(cls, parent=None, midi_outport=None, voice_bytes=None):
        # Always create a new instance to ensure UI is fully initialized
        if cls._instance is not None:
            try:
                cls._instance.setParent(None)
                cls._instance.deleteLater()
            except Exception:
                pass
            cls._instance = None
        cls._instance = VoiceEditorPanel(midi_outport=midi_outport, voice_bytes=voice_bytes, parent=parent)
        cls._instance.setWindowModality(Qt.NonModal)
        cls._instance.show()
        cls._instance.raise_()
        cls._instance.activateWindow()
        return cls._instance

    def __init__(self, midi_outport=None, voice_bytes=None, parent=None):
        # Ensure parent is a QWidget, not a QWindow
        from PySide6.QtWidgets import QWidget
        if parent is not None and not isinstance(parent, QWidget):
            parent = None
        super().__init__(parent)
        self.setStyleSheet("background-color: #332b28; color: #e0e0e0;")
        self.midi_handler = midi_outport  # Now always the MIDIHandler instance
        self.voice_bytes = voice_bytes or self.init_patch_bytes()
        self.decoder = SingleVoiceDumpDecoder(self.voice_bytes)
        self.decoder.decode()
        self.params = self.decoder.params
        self.op_count = 6
        self.op_bg_widgets = []
        self.status_bar = QLabel("")
        self.status_bar.setFixedHeight(36)
        self.status_bar.setFixedWidth(220)
        self.status_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.status_bar.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.status_bar.setWordWrap(False)
        self.gradient_carrier = "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #17777a, stop:1 #223c36); border-radius: 2px;"
        self.gradient_noncarrier = "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #42372e, stop:1 #332b28); border-radius: 2px;"
        self.gradient_global = "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #42372e, stop:1 #332b28); border-radius: 2px;"
        self.setStyleSheet("background-color: #332b28; color: #e0e0e0;")
        
        self.status_bar.setStyleSheet("background: transparent; color: #e0e0e0; padding: 4px;")
        self.gradient_status = (
            "font-size: 8pt; "
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fffde8, stop:0.5 #fffad7, stop:1 #f3eeb2); "
            "color: #000000; padding: 0px; border-top: 1px solid #d4cc99; border-radius: 2px; "
            "text-align: center; "  # horizontal centering
            "vertical-align: middle; "  # vertical centering (for single-line)
            "line-height: 0.8; "  # reduce space between lines to 80%
        )
        self.status_bar.setStyleSheet(self.gradient_status)
        self.status_bar.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_bar.mousePressEvent = self._on_status_bar_click
        self.init_ui()

    def update_status_bar(self, text, lcd_value=None):
        # Always show the voice name in the first row, status in the second
        voice_name = self.get_patch_name()
        status_text = text if text else ""
        self.status_bar.setText(f"{voice_name}\n{status_text}")
        # Show the correct value on the LCD
        if lcd_value is not None:
            self.lcd_number.display(lcd_value)
        else:
            self.lcd_number.display("")

    def _on_status_bar_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            current_name = self.get_patch_name()
            new_name, ok = QInputDialog.getText(self, "Rename Voice", "Enter new voice name (max 10 chars):", text=current_name)
            if ok and new_name:
                for i, c in enumerate(new_name.ljust(10)[:10]):
                    self.set_param(f'VNAM{i+1}', ord(c))
                self.update_status_bar("")

    def get_carrier_ops(self, alg_idx):
        return DX7_CARRIER_MAP[alg_idx] if 0 <= alg_idx < 32 else []

    def get_value_label(self, key, value):
        mapping = VALUE_LABELS.get(key)
        if mapping:
            return mapping.get(value, str(value))
        return str(value)

    def _make_slider(self, value, min_val, max_val, slot, description, color, label=None, param_key=None):
        if value is None:
            value = min_val
        slider = QSlider(Qt.Orientation.Vertical)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setPageStep(1)
        slider.setValue(value)
        slider.setStyleSheet(f"QSlider::groove:vertical {{background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #23272e, stop:1 #2d3640); border: 1px solid #444;}} QSlider::handle:vertical {{background: {color}; border-radius: 2px;}}")
        slider.setMinimumHeight(20)
        slider.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        slider.valueChanged.connect(slot)
        def enterEvent(event, s=slider, d=description, k=param_key):
            val = s.value()
            label_val = self.get_value_label(k, val) if k else str(val)
            self.update_status_bar(f"{d}: {label_val}", lcd_value=val)
            if k:
                self._show_param_info(k)
        def leaveEvent(event, s=slider, d=description, k=param_key):
            self.update_status_bar("")
            self.param_info_panel.setText("")
        slider.enterEvent = enterEvent
        slider.leaveEvent = leaveEvent
        slider.valueChanged.connect(lambda v, s=slider, d=description, k=param_key: self.update_status_bar(f"{d}: {self.get_value_label(k, v) if k else v}", lcd_value=v))
        if label:
            col = QVBoxLayout()
            col.setSpacing(0)
            col.setContentsMargins(0, 0, 0, 0)
            value_lbl = DraggableValueLabel(value, min_val, max_val, lambda v: self.get_value_label(param_key, v))
            value_lbl.setText(str(self.get_value_label(param_key, value)))
            value_lbl.valueChanged.connect(slider.setValue)
            slider.valueChanged.connect(value_lbl.setValue)
            col.addWidget(value_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
            col.addWidget(slider, alignment=Qt.AlignmentFlag.AlignHCenter)
            lbl = QLabel(label)
            # Dynamically set font size based on label length
            font_size = 8 # if len(label) <= 2 else 7
            lbl.setStyleSheet(f"font-size: {font_size}pt; background: transparent;")
            col.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
            w = QWidget()
            w.setLayout(col)
            w.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            w.setMouseTracking(True)
            return w
        return slider

    def _make_vline(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        # Use a more visible color and set a fixed width
        line.setStyleSheet("background: none; border: none; border-left: 2px solid #777;")
        line.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        line.setMinimumHeight(40)
        line.setFixedWidth(1)
        return line

    def init_ui(self):
        # --- Load VCED.json for parameter info (must be first!) ---
        self._vced_param_info = None
        self._tx816perf_param_info = None
        try:
            with open(os.path.join(os.path.dirname(__file__), 'data', 'VCED.json'), 'r', encoding='utf-8') as f:
                vced_json = json.load(f)
                self._vced_param_info = {p['key']: p for p in vced_json.get('parameters', [])}
                self._tx816perf_param_info = {p['key']: p for p in vced_json.get('TX816Perf', [])}
        except Exception as e:
            self._vced_param_info = {}
            self._tx816perf_param_info = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # --- Main editor area (was layout = QVBoxLayout(self)) ---
        main_vbox = QVBoxLayout()
        # --- Top bar layout ---
        topbar_layout = QHBoxLayout()
        topbar_layout.setContentsMargins(0, 0, 0, 0)
        topbar_layout.setSpacing(0)
        # --- Placeholder for widgets left of the status bar ---
        placeholder_layout = QHBoxLayout()
        placeholder_layout.setContentsMargins(0, 0, 0, 0)
        placeholder_layout.setSpacing(8)
        # Algorithm selector (styled like other widgets)
        alg_col = QVBoxLayout()
        alg_col.setSpacing(0)
        alg_col.setContentsMargins(0, 0, 0, 0)
        alg_col.addStretch(1)  # Spacer above
        self.alg_combo = QComboBox()
        for i in range(1, 33):
            self.alg_combo.addItem(str(i))
        self.alg_combo.setCurrentIndex(self.get_param('ALS', 0))
        self.alg_combo.currentIndexChanged.connect(self.on_algorithm_changed)
        alg_col.addWidget(self.alg_combo, alignment=Qt.AlignmentFlag.AlignHCenter)
        alg_lbl = QLabel("Algorithm")
        alg_lbl.setStyleSheet("font-size: 8pt; background: transparent;")
        alg_col.addWidget(alg_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        alg_col.addStretch(1)  # Spacer below
        alg_widget = QWidget()
        alg_widget.setLayout(alg_col)
        placeholder_layout.addWidget(alg_widget)
        topbar_layout.addLayout(placeholder_layout)
        
        topbar_layout.addStretch(1)

        LCD_WIDTH = 68
        self.lcd_number = QLCDNumber(2)
        self.lcd_number.setSegmentStyle(QLCDNumber.SegmentStyle.Filled)
        palette = self.lcd_number.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor('#cc0000'))
        palette.setColor(QPalette.ColorRole.Light, QColor('#cc0000'))
        palette.setColor(QPalette.ColorRole.Shadow, QColor('black'))
        self.lcd_number.setPalette(palette)
        self.lcd_number.setAutoFillBackground(True)
        self.lcd_number.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        self.lcd_number.setStyleSheet(self.gradient_global)
        self.lcd_number.display(0)
        self.lcd_number.setFixedWidth(LCD_WIDTH)
        self.lcd_number.setFixedHeight(self.status_bar.sizeHint().height())
        self.lcd_number.update()
        # self.lcd_placeholder = QWidget()
        # self.lcd_placeholder.setFixedWidth(LCD_WIDTH)
        # self.lcd_placeholder.setFixedHeight(self.lcd_number.height())
        # self.lcd_placeholder.setStyleSheet(self.gradient_global)
        # topbar_layout.addWidget(self.lcd_placeholder, alignment=Qt.AlignmentFlag.AlignVCenter)
        topbar_layout.addWidget(self.lcd_number, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.status_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_bar.setFixedWidth(180)
        self.status_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        topbar_layout.addWidget(self.status_bar, alignment=Qt.AlignmentFlag.AlignVCenter)

        topbar_layout.addStretch(3)

        topbar_layout.addStretch(1)
        ch_col = QVBoxLayout()
        ch_col.setSpacing(0)
        ch_col.setContentsMargins(0, 0, 0, 0)
        ch_col.addStretch(1)  # Spacer above
        self.channel_combo = QComboBox()
        for i in range(1, 17):
            self.channel_combo.addItem(str(i))
        ch_col.addWidget(self.channel_combo, alignment=Qt.AlignmentFlag.AlignHCenter)
        ch_lbl = QLabel("Channel")
        ch_lbl.setStyleSheet("font-size: 8pt; background: transparent;")
        ch_col.addWidget(ch_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        ch_col.addStretch(1)  # Spacer below
        ch_widget = QWidget()
        ch_widget.setLayout(ch_col)
        topbar_layout.addWidget(ch_widget)
        main_vbox.addLayout(topbar_layout)
        # Operator grid
        op_grid = QGridLayout()
        op_grid.setContentsMargins(0, 0, 0, 0)
        op_grid.setHorizontalSpacing(0)
        op_grid.setVerticalSpacing(0)
        col = 0
        col += 1
        op_col_count = col + 4

        # Operator rows
        self._hovered_op_idx = None  # Track which operator is hovered
        self.operator_spacer_items = []
        self.op_env_widgets = []  # Store per-operator EnvelopeWidget
        self.op_ks_widgets = []   # Store per-operator KeyboardScalingWidget
        # Use reversed order so OP6 is top row, OP1 is bottom row
        for row, tg in enumerate(reversed(range(self.op_count)), start=1):
            is_carrier = tg in self.get_carrier_ops(self.get_param('ALS', 0))
            op_bg = QWidget()
            op_bg.setStyleSheet(self.gradient_carrier if is_carrier else self.gradient_noncarrier)
            op_bg.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # Ensure hover events
            self.op_bg_widgets.append(op_bg)
            operator_row_layout = QHBoxLayout(op_bg)
            operator_row_layout.setContentsMargins(0, 0, 0, 0)
            operator_row_layout.setSpacing(0)
            spacer_item = QWidget()
            spacer_item.setFixedWidth(self.svg_overlay.width() if hasattr(self, 'svg_overlay') else 50)
            self.operator_spacer_items.append(spacer_item)
            operator_row_layout.addWidget(spacer_item)
            # Add OPE (Operator Enable) slider
            ope_short = self._vced_param_info.get('OPE', {}).get('short', 'OPE')
            operator_row_layout.addWidget(self._make_slider(
                self.get_op_param(tg, 'E', 1), 0, 1,
                lambda v, o=tg: (self.set_op_param(o, 'E', v), self.handle_op_enabled()),
                'Operator Enable', '#8ecae6', ope_short, param_key='OPE'
            ))
            # Add TL (Total Level) slider
            tl_short = self._vced_param_info.get('TL', {}).get('short', 'TL')
            operator_row_layout.addWidget(self._make_slider(
                self.get_op_param(tg, 'TL'), 0, 99,
                lambda v, o=tg: self.set_op_param(o, 'TL', v),
                'Total Level', '#8ecae6', tl_short, param_key='TL'
            ))
            # Insert separator between TL and PM
            operator_row_layout.addWidget(self._make_vline())
            # Add PM (Frequency Mode) slider
            pm_short = self._vced_param_info.get('PM', {}).get('short', 'PM')
            operator_row_layout.addWidget(self._make_slider(
                self.get_op_param(tg, 'PM'), 0, 1,
                lambda v, o=tg: self.set_op_param(o, 'PM', v),
                'Frequency Mode', '#8ecae6', pm_short, param_key='PM'
            ))
            # Add the rest of the frequency sliders (PC, PF, PD)
            for key, full_name, _short_lbl, max_val in OP_FREQ_DEFS:
                if key in ('PM',):
                    continue
                short_label = self._vced_param_info.get(key, {}).get('short', key)
                operator_row_layout.addWidget(self._make_slider(
                    self.get_op_param(tg, key), 0, max_val,
                    lambda v, o=tg, k=key: self.set_op_param(o, k, v),
                    full_name, '#8ecae6', short_label, param_key=key
                ))
            operator_row_layout.addWidget(self._make_vline())
            # Add the rest of the level sliders (AMS, TS)
            for key, full_name, _short_lbl, max_val in OP_LEVEL_DEFS:
                if key in ('TL',):
                    continue
                short_label = self._vced_param_info.get(key, {}).get('short', key)
                operator_row_layout.addWidget(self._make_slider(
                    self.get_op_param(tg, key), 0, max_val,
                    lambda v, o=tg, k=key: self.set_op_param(o, k, v),
                    full_name, '#8ecae6', short_label, param_key=key
                ))
            # Add RS (Rate Scaling) slider before AMS
            rs_short = self._vced_param_info.get('RS', {}).get('short', 'RS')
            operator_row_layout.addWidget(self._make_slider(
                self.get_op_param(tg, 'RS'), 0, 7,
                lambda v, o=tg: self.set_op_param(o, 'RS', v),
                'Rate Scaling', '#8ecae6', rs_short, param_key='RS'
            ))
            operator_row_layout.addWidget(self._make_vline())
            # --- Remove EG Level, EG Rate, and Keyboard Scaling sliders ---
            # Add per-operator EnvelopeWidget
            env_widget = EnvelopeWidget()
            rates = [self.get_op_param(tg, f'R{i+1}', 50) for i in range(4)]
            levels = [self.get_op_param(tg, f'L{i+1}', 99 if i == 0 else 0) for i in range(4)]
            env_widget.set_envelope(rates, levels)
            self.op_env_widgets.append(env_widget)
            operator_row_layout.addWidget(env_widget)
            # Connect envelopeChanged to MIDI update (robust closure for operator index)
            def make_env_handler(op_idx):
                def handler(rates, levels, send):
                    for i in range(4):
                        self.set_op_param(op_idx, f'R{i+1}', int(rates[i]))
                        self.set_op_param(op_idx, f'L{i+1}', int(levels[i]))
                return handler
            env_widget.envelopeChanged.connect(make_env_handler(tg))
            # Connect labelHovered to show param info
            def make_env_label_hovered(op_idx):
                def handler(param_key):
                    if param_key:
                        # Show param info as before
                        self._show_param_info(param_key)
                        # Also update status bar and LCD
                        val = None
                        label = param_key
                        if param_key.startswith('R') and len(param_key) == 2 and param_key[1].isdigit():
                            idx = int(param_key[1]) - 1
                            val = self.get_op_param(op_idx, param_key, 50)
                            desc = f"Envelope Rate {idx+1}"
                        elif param_key.startswith('L') and len(param_key) == 2 and param_key[1].isdigit():
                            idx = int(param_key[1]) - 1
                            val = self.get_op_param(op_idx, param_key, 99 if idx == 0 else 0)
                            desc = f"Envelope Level {idx+1}"
                        else:
                            val = self.get_op_param(op_idx, param_key)
                            desc = param_key
                        self.update_status_bar(f"{desc}: {val}", lcd_value=val)
                    else:
                        self.param_info_panel.setText("")
                        self.update_status_bar("")
                return handler
            env_widget.labelHovered.connect(make_env_label_hovered(tg))
            # Add per-operator KeyboardScalingWidget
            ks_widget = KeyboardScalingWidget()
            bp = self.get_op_param(tg, 'BP', 50)
            ld = self.get_op_param(tg, 'LD', 50)
            rd = self.get_op_param(tg, 'RD', 50)
            lc = self.get_op_param(tg, 'LC', 0)
            rc = self.get_op_param(tg, 'RC', 0)
            ks_widget.set_params(bp, ld, rd, lc, rc)
            self.op_ks_widgets.append(ks_widget)
            operator_row_layout.addWidget(ks_widget)
            # Connect paramsChanged to MIDI update (robust closure for operator index)
            def make_ks_handler(op_idx):
                def handler(bp, ld, rd, lc, rc):
                    self.set_op_param(op_idx, 'BP', int(bp))
                    self.set_op_param(op_idx, 'LD', int(ld))
                    self.set_op_param(op_idx, 'RD', int(rd))
                    self.set_op_param(op_idx, 'LC', int(lc))
                    self.set_op_param(op_idx, 'RC', int(rc))
                return handler
            ks_widget.paramsChanged.connect(make_ks_handler(tg))
            # Connect labelHovered to show param info
            def make_ks_label_hovered(op_idx):
                def handler(param_key):
                    if param_key:
                        self._show_param_info(param_key)
                        # Also update status bar and LCD
                        val = None
                        desc = param_key
                        if param_key == 'BP':
                            val = self.get_op_param(op_idx, 'BP', 50)
                            desc = "Break Point"
                        elif param_key == 'LD':
                            val = self.get_op_param(op_idx, 'LD', 50)
                            desc = "Left Depth"
                        elif param_key == 'RD':
                            val = self.get_op_param(op_idx, 'RD', 50)
                            desc = "Right Depth"
                        elif param_key == 'LC':
                            val = self.get_op_param(op_idx, 'LC', 0)
                            desc = "Left Curve"
                            val = self.get_value_label('LC', val)
                        elif param_key == 'RC':
                            val = self.get_op_param(op_idx, 'RC', 0)
                            desc = "Right Curve"
                            val = self.get_value_label('RC', val)
                        else:
                            val = self.get_op_param(op_idx, param_key)
                        self.update_status_bar(f"{desc}: {val}", lcd_value=val if isinstance(val, int) else "")
                    else:
                        self.param_info_panel.setText("")
                        self.update_status_bar("")
                return handler
            ks_widget.labelHovered.connect(make_ks_label_hovered(tg))
            op_grid.addWidget(op_bg, row, 0, 1, op_col_count)

            # --- Add event handlers for envelope preview on hover ---
            def make_enter_event(op_idx, is_carrier):
                def enterEvent(event, self=self, op_idx=op_idx, is_carrier=is_carrier):
                    op_type = "Carrier" if is_carrier else "Modulator"
                    print(f"[HOVER] Operator {op_idx+1} ({op_type}) row hovered")
                    self.update_status_bar(f"Operator {op_idx+1} ({op_type})")
                    self.param_info_panel.show_param_info({
                        f'OP{op_idx+1}': {
                            'name': f'Operator {op_idx+1} ({op_type})',
                            'description': f'Controls for operator {op_idx+1}, which is a {op_type.lower()} in the current algorithm.'
                        }
                    }, f'OP{op_idx+1}', op_idx, None)
                    self._hovered_op_idx = op_idx
                    # Highlight the widgets for this operator
                    for i, ew in enumerate(self.op_env_widgets):
                        ew.setStyleSheet('border: 2px solid #ffb703;' if i == op_idx else '')
                    for i, kw in enumerate(self.op_ks_widgets):
                        kw.setStyleSheet('border: 2px solid #8ecae6;' if i == op_idx else '')
                return enterEvent
            def make_leave_event():
                def leaveEvent(event, self=self):
                    self._hovered_op_idx = None
                    for ew in self.op_env_widgets:
                        ew.setStyleSheet('')
                    for kw in self.op_ks_widgets:
                        kw.setStyleSheet('')
                    self.update_status_bar("")
                return leaveEvent
            op_bg.enterEvent = make_enter_event(tg, is_carrier)
            op_bg.leaveEvent = make_leave_event()
        # Add global row at the bottom
        global_row = self.op_count + 1
        global_bg = QWidget()
        global_bg.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #23242a, stop:1 #18191c); border-radius: 2px;")
        global_bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        global_bg.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # Ensure hover events
        global_layout = QHBoxLayout(global_bg)
        global_layout.setContentsMargins(0, 0, 0, 0)
        global_layout.setSpacing(0)
        self.global_spacer_item = QWidget()
        self.global_spacer_item.setFixedWidth(self.svg_overlay.width() if hasattr(self, 'svg_overlay') else 50)
        self.global_spacer_item.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        global_layout.addWidget(self.global_spacer_item)
        # Global row
        for i in range(4):
            key = f'PR{i+1}'
            short_label = self._vced_param_info.get(key, {}).get('short', key)
            global_layout.addWidget(
                self._make_slider(
                    self.get_param(key, 0), 0, 99,
                    lambda v, k=key: self.set_param(k, v),
                    f'Envelope Generator Rate {i+1}', '#8ecae6', short_label, param_key=key
                )
            )
        for i in range(4):
            key = f'PL{i+1}'
            short_label = self._vced_param_info.get(key, {}).get('short', key)
            global_layout.addWidget(
                self._make_slider(
                    self.get_param(key, 0), 0, 99,
                    lambda v, k=key: self.set_param(k, v),
                    f'Envelope Generator Level {i+1}', '#ffb703', short_label, param_key=key
                )
            )
        global_layout.addWidget(self._make_vline())
        for _label, key, min_val, max_val, tooltip in GLOBAL_PARAM_DEFS:
            short_label = self._vced_param_info.get(key, {}).get('short', key)
            global_layout.addWidget(
                self._make_slider(
                    self.get_param(key, 0), min_val, max_val,
                    lambda v, k=key: self.set_param(k, v),
                    tooltip, '#8ecae6', short_label, param_key=key
                )
            )
        op_grid.addWidget(global_bg, global_row, 0, 1, op_col_count)

        # --- TX816/TX216 Performance SysEx row ---
        perf_row = global_row + 1
        perf_bg = QWidget()
        perf_bg.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #23242a, stop:1 #18191c); border-radius: 2px;")
        perf_bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        perf_bg.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # Ensure hover events
        perf_layout = QHBoxLayout(perf_bg)
        perf_layout.setContentsMargins(0, 0, 0, 0)
        perf_layout.setSpacing(0)
        self.perf_spacer_item = QWidget()
        self.perf_spacer_item.setFixedWidth(self.svg_overlay.width() if hasattr(self, 'svg_overlay') else 50)
        self.perf_spacer_item.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        perf_layout.addWidget(self.perf_spacer_item)
        # TX816 performance parameters
        tx816_params = [
            (k, k, p['min'], p['max'], p.get('description', k), p['parameter_number'])
            for k, p in self._tx816perf_param_info.items()
        ]
        for short, key, min_val, max_val, tooltip, param_num in tx816_params:
            def make_setter(k, p):
                return lambda v: (
                    print(f"[DEBUG] send_sysex called with key={k}, value={v}, param_num={p}, op_idx=None"),
                    self.set_param(k, v)
                )
            # Always use sliders, even for binary params
            perf_layout.addWidget(
                self._make_slider(
                    self.get_param(key, min_val), min_val, max_val,
                    make_setter(key, param_num),
                    tooltip, '#8ecae6', short, param_key=key
                )
            )
        op_grid.addWidget(perf_bg, perf_row, 0, 1, op_col_count)
        op_table_widget = QWidget()
        op_table_widget.setLayout(op_grid)
        op_table_widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # Ensure hover events
        op_table_widget.lower()
        # Use SvgWheelWidget instead of QSvgWidget
        self.svg_overlay = SvgWheelWidget(op_table_widget, alg_combo=self.alg_combo)
        self.svg_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.svg_overlay.setStyleSheet("background: transparent;")
        self.svg_overlay.setVisible(True)
        self.svg_overlay.raise_()
        main_vbox.addWidget(op_table_widget)
        # At the end, create a QWidget for the main editor area
        main_editor_widget = QWidget()
        main_editor_widget.setLayout(main_vbox)
        main_editor_widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)  # Ensure hover events
        # --- Contextual Side Panel ---
        self.param_info_panel = ParamInfoPanel()
        # --- Splitter to allow resizing ---
        splitter = QSplitter()
        splitter.addWidget(main_editor_widget)
        splitter.addWidget(self.param_info_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)
        self.setLayout(layout)
        self.update_svg_overlay()
        # --- Load VCED.json for parameter info ---


    def _show_param_info(self, param_key):
        hovered_op_idx = getattr(self, '_hovered_op_idx', None)
        alg_idx = self.get_param('ALS', 0)
        carrier_ops = self.get_carrier_ops(alg_idx) if hovered_op_idx is not None else None
        # Prefer VCED, then TX816Perf
        param_info = self._vced_param_info.get(param_key) if self._vced_param_info and param_key in self._vced_param_info else None
        if not param_info and self._tx816perf_param_info and param_key in self._tx816perf_param_info:
            param_info = self._tx816perf_param_info[param_key]
        self.param_info_panel.show_param_info({param_key: param_info} if param_info else {}, param_key, hovered_op_idx, carrier_ops)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.update_svg_overlay(resize_only=True)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_svg_overlay()

    def update_all_spacer_widths(self, width=None):
        if width is None:
            width = self.svg_overlay.width() if hasattr(self, 'svg_overlay') else 50
        for spacer in getattr(self, 'operator_spacer_items', []):
            spacer.setFixedWidth(width)
        if hasattr(self, 'global_spacer_item'):
            self.global_spacer_item.setFixedWidth(width)
        if hasattr(self, 'perf_spacer_item'):
            self.perf_spacer_item.setFixedWidth(width)

    def update_svg_overlay(self, resize_only=False):
        alg_idx = self.alg_combo.currentIndex() + 1  # 1-based
        if not resize_only:
            svg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "images", f"algorithm-{alg_idx:02d}.svg"))
            print(f"[SVG DEBUG] Loading SVG: {svg_path}")
            print(f"[SVG DEBUG] Exists: {os.path.exists(svg_path)}")
            self.svg_overlay.load(svg_path)
            print(f"[SVG DEBUG] SVG overlay sizeHint: {self.svg_overlay.sizeHint()}, parent height: {self.svg_overlay.parent().height() if self.svg_overlay.parent() else 'None'}")
        parent = self.svg_overlay.parent()
        if parent is not None:
            parent_height = parent.height()
            # Subtract the height of the last row (performance row) to avoid covering it
            perf_row_widget = None
            op_grid = parent.layout() if parent else None
            if op_grid is not None:
                perf_row_idx = op_grid.rowCount() - 1
                for col in range(op_grid.columnCount()):
                    item = op_grid.itemAtPosition(perf_row_idx, col)
                    if item is not None and item.widget() is not None:
                        perf_row_widget = item.widget()
                        break
            perf_row_height = perf_row_widget.height() if perf_row_widget is not None else 0
            # Reduce the available height for the SVG overlay
            operator_height = (parent_height - perf_row_height) * 0.93
            scale_factor = operator_height / self.svg_overlay.sizeHint().height() if self.svg_overlay.sizeHint().height() > 0 else 1.0
            svg_width = int(self.svg_overlay.sizeHint().width() * scale_factor)
            svg_height = int(self.svg_overlay.sizeHint().height() * scale_factor)
            self.svg_overlay.resize(svg_width, svg_height)
        else:
            self.svg_overlay.resize(self.svg_overlay.sizeHint())
        self.svg_overlay.setVisible(True)
        self.svg_overlay.raise_()
        self.svg_overlay.move(2, 7)
        self.update_all_spacer_widths(self.svg_overlay.width())

    def update_operator_bg_colors(self):
        alg_idx = self.alg_combo.currentIndex()
        carrier_ops = self.get_carrier_ops(alg_idx)
        for widget_idx, op_bg in enumerate(self.op_bg_widgets):
            op_idx = self.op_count - 1 - widget_idx  # Map widget row to operator index
            if op_idx in carrier_ops:
                op_bg.setStyleSheet(self.gradient_carrier)
            else:
                op_bg.setStyleSheet(self.gradient_noncarrier)

    def on_algorithm_changed(self, idx):
        print(f"[DEBUG] on_algorithm_changed called with idx={idx}")
        self.set_param('ALS', idx)
        self.update_operator_bg_colors()
        self.update_svg_overlay(resize_only=False)
        param_num = self._get_param_num('ALS')
        print(f"[DEBUG] _get_param_num('ALS') returned {param_num}")
        if param_num is not None:
            self.send_sysex('ALS', idx, param_num)
        else:
            print("[DEBUG] No param_num for 'ALS', SysEx not sent.")

    def get_patch_name(self):
        name = ''
        for i in range(10):
            v = self.get_param(f'VNAM{i+1}', 32)
            name += chr(v) if 32 <= v <= 127 else ' '
        return name.strip()

    def on_name_changed(self, text):
        for i, c in enumerate(text.ljust(10)[:10]):
            self.set_param(f'VNAM{i+1}', ord(c))
        if not self.status_bar.text() or self.status_bar.text() == self.get_patch_name():
            self.update_status_bar("")

    def get_param(self, key, default=None):
        return self.params.get(key, default)

    def get_op_param(self, op, key, default=None):
        if 'operators' in self.params and isinstance(self.params['operators'], list) and len(self.params['operators']) > op:
            return self.params['operators'][op].get(key, default)
        return default

    def set_param(self, key, value):
        self.params[key] = value
        param_num = self._get_param_num(key)
        if param_num is not None:
            self.send_sysex(key, value, param_num)

    def set_op_param(self, op, key, value):
        if 'operators' not in self.params or not isinstance(self.params['operators'], list):
            self.params['operators'] = [{} for _ in range(self.op_count)]
        elif len(self.params['operators']) < self.op_count:
            self.params['operators'] += [{} for _ in range(self.op_count - len(self.params['operators']))]
        self.params['operators'][op][key] = value
        param_num = self._get_operator_param_num(op, key)
        if param_num is not None:
            self.send_sysex(key, value, param_num, op_idx=op)
        # Update envelope widget if key is R1-R4 or L1-L4
        if key in [f'R{i+1}' for i in range(4)] or key in [f'L{i+1}' for i in range(4)]:
            self._update_env_widget_for_operator(op)
        # Update keyboard scaling widget if key is BP, LD, RD, LC, RC
        if key in ['BP', 'LD', 'RD', 'LC', 'RC']:
            self._update_ks_widget_for_operator(op)

    def send_sysex(self, key, value, param_num, op_idx=None):
        print(f"[DEBUG] send_sysex called with key={key}, value={value}, param_num={param_num}, op_idx={op_idx}")
        ch = self.channel_combo.currentIndex()  # 0-indexed for MIDI
        # If this is an operator parameter, send an Operator Select message first
        if op_idx is not None:
            sel_msg = [0xF0, 0x43, 0x10 | (ch & 0x0F), 0x00, 0x15, op_idx, 0xF7]
            if self.midi_handler:
                self.midi_handler.send_sysex(sel_msg)
        if param_num is not None and value is not None:
            if 0 <= param_num <= 155:
                group = 0x00
                if param_num <= 127:
                    group_byte = group
                    param_byte = param_num
                else:
                    group_byte = group | 0x01  # set pp bits for 128-155
                    param_byte = param_num - 128
            elif 64 <= param_num <= 77:
                group = 0x20
                group_byte = group
                param_byte = param_num
            else:
                print(f"[VOICE EDITOR PANEL] Unsupported parameter number: {param_num}")
                return
            sysex = [0xF0, 0x43, 0x10 | (ch & 0x0F), group_byte, param_byte, int(value), 0xF7]
            if self.midi_handler:
                import mido
                msg = mido.Message('sysex', data=sysex[1:-1])
                self.midi_handler.send_sysex(msg.bytes())
            else:
                print("[VOICE EDITOR PANEL] midi_handler not set, cannot send SysEx.")
        else:
            print(f"[VOICE EDITOR PANEL] No valid param_num for {key} (op_idx={op_idx})")

    def _update_env_widget_for_operator(self, op_idx):
        widget_idx = self.op_count - 1 - op_idx
        rates = [self.get_op_param(op_idx, f'R{i+1}', 50) for i in range(4)]
        levels = [self.get_op_param(op_idx, f'L{i+1}', 99 if i == 0 else 0) for i in range(4)]
        self.op_env_widgets[widget_idx].set_envelope(rates, levels)

    def _reset_env_widget(self, op_idx):
        widget_idx = self.op_count - 1 - op_idx
        self.op_env_widgets[widget_idx].set_envelope([50, 50, 50, 50], [99, 70, 40, 0])

    def _update_ks_widget_for_operator(self, op_idx):
        widget_idx = self.op_count - 1 - op_idx
        bp = self.get_op_param(op_idx, 'BP', 50)
        ld = self.get_op_param(op_idx, 'LD', 50)
        rd = self.get_op_param(op_idx, 'RD', 50)
        lc = self.get_op_param(op_idx, 'LC', 0)
        rc = self.get_op_param(op_idx, 'RC', 0)
        self.op_ks_widgets[widget_idx].set_params(bp, ld, rd, lc, rc)

    def _reset_ks_widget(self, op_idx):
        widget_idx = self.op_count - 1 - op_idx
        self.op_ks_widgets[widget_idx].set_params(50, 50, 50, 0, 0)

    def init_patch_bytes(self):
        # Returns 161 bytes for an INIT patch (all params default, name 'INIT PATCH')
        # See DX7 parameter order and default values from the provided table
        data = [0xF0, 0x43, 0x00, 0x09, 0x20]
        # Operator parameters (6 operators, each 21 bytes)
        op_defaults = [
            # R1, R2, R3, R4, L1, L2, L3, L4, LD, RD, LC, RC, RS, TL, AMS, TS, PM, PC, PF, PD, BP
            99, 99, 99, 99, 99, 99, 99, 0, 99, 99, 0, 0, 0, 99, 0, 0, 0, 1, 0, 7, 39
        ]
        # The DX7 stores operator data in reverse order: OP6, OP5, ..., OP1
        for _ in range(6):
            data.extend(op_defaults)
        # PEG (Pitch EG) rates and levels
        data.extend([99, 99, 99, 99])  # PR1-PR4
        data.extend([99, 99, 99, 99])  # PL1-PL4
        # Algorithm selector
        data.append(0)  # ALS
        # Feedback level
        data.append(0)  # FBL
        # Oscillator phase init
        data.append(0)  # OPI
        # LFO
        data.extend([35, 0, 0, 0, 0, 0, 0, 0, 0, 24])  # LFS, LFD, LPMD, LAMD, LFKS, LFW, LPMS, TRNP
        # Voice name (10 chars, ASCII)
        name = b'INIT PATCH'
        for i in range(10):
            data.append(name[i] if i < len(name) else 32)
        # Operator enable (OPSEL): all enabled (0b111111 = 63)
        data.append(63)
        # Operator select (OPSEL): 0
        data.append(0)
        # Pad to 155 bytes if needed
        while len(data) < 160:
            data.append(0)
        data.append(0xF7)
        return bytes(data)

    def get_lcd_widget(self):
        return self.lcd_number

    def _get_operator_param_num(self, op_idx, key):
        """
        Returns the parameter number for a given operator and key, or None if not found.
        """
        if hasattr(self, '_vced_param_info') and self._vced_param_info:
            param_info = self._vced_param_info.get(key)
            if param_info and 'parameter_number' in param_info:
                param_num = param_info['parameter_number']
                if isinstance(param_num, list) and len(param_num) > op_idx:
                    return param_num[op_idx]
                elif isinstance(param_num, int):
                    return param_num
        return None

    def _get_param_num(self, key):
        """
        Returns the parameter number for a global (non-operator) parameter, or None if not found.
        """
        if hasattr(self, '_vced_param_info') and self._vced_param_info:
            param_info = self._vced_param_info.get(key)
            if param_info and 'parameter_number' in param_info:
                param_num = param_info['parameter_number']
                if isinstance(param_num, int):
                    return param_num
        # Fallback: try to find in GLOBAL_PARAM_DEFS
        for _short, k, _min, _max, _desc in GLOBAL_PARAM_DEFS:
            if k == key:
                # Use index as parameter number if not found in VCED
                return None  # Or return a default/int if needed
        return None

    def handle_op_enabled(self):
        enabled_states = []
        bitfield = 0
        for i in range(self.op_count):
            enabled = self.get_op_param(i, 'E', 1)
            enabled_states.append(f"Op {i+1}: {'Enabled' if enabled else 'Disabled'}")
            if enabled:
                bitfield |= (1 << (5 - i))  # OP1 is bit 5, OP6 is bit 0
        # Send DX7 operator enable/disable SysEx
        sysex = [0xF0, 0x43, 0x10, 0x01, 0x1B, bitfield, 0xF7]
        print(f"[DX7 OP ENABLE] Sending SysEx: {' '.join(f'{b:02X}' for b in sysex)}")
        if self.midi_handler:
            import mido
            msg = mido.Message('sysex', data=sysex[1:-1])
            self.midi_handler.send_sysex(msg.bytes())
        else:
            print("[DX7 OP ENABLE] midi_handler is not set, cannot send SysEx.")

class VoiceEditorPanelDialog(QDialog):
    _instance = None

    @classmethod
    def show_panel(cls, midi_outport=None, voice_bytes=None, parent=None):
        if cls._instance is not None and cls._instance.isVisible():
            # Update panel contents if needed
            panel = VoiceEditorPanel.get_instance(midi_outport=midi_outport, voice_bytes=voice_bytes, parent=cls._instance)
            if midi_outport is not None:
                panel.midi_outport = midi_outport
            if voice_bytes is not None:
                panel.voice_bytes = voice_bytes
                panel.decoder = SingleVoiceDumpDecoder(voice_bytes)
                panel.decoder.decode()
                panel.params = panel.decoder.params
            cls._instance.raise_()
            cls._instance.activateWindow()
            cls._instance.show()
            return cls._instance
        dlg = VoiceEditorPanelDialog(midi_outport=midi_outport, voice_bytes=voice_bytes, parent=parent)
        cls._instance = dlg
        dlg.setModal(False)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return dlg

    def __init__(self, midi_outport=None, voice_bytes=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voice Editor Panel")
        self.setMinimumSize(800, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.panel = VoiceEditorPanel.get_instance(midi_outport=midi_outport, voice_bytes=voice_bytes, parent=self)
        self.panel.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.panel)
        self.setLayout(layout)
        self.resize(800, 600)
        self.panel.update_svg_overlay()
        self.update()
        self.adjustSize()
        QApplication.processEvents()

    def closeEvent(self, event):
        VoiceEditorPanelDialog._instance = None
        super().closeEvent(event)

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider, QLineEdit, QWidget, QGridLayout, QFrame, QSizePolicy, QInputDialog, QLCDNumber
from PyQt6.QtCore import Qt
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QResizeEvent, QPalette, QColor
from single_voice_dump_decoder import SingleVoiceDumpDecoder
from envelope_widget import EnvelopeWidget
from keyboard_scaling_widget import KeyboardScalingWidget
import os
import mido

# --- Static definitions and tables ---

DX7_CARRIER_MAP = [
    [0, 2], [0, 2], [0, 3], [0, 3], [0, 2, 4], [0, 2, 4], [0, 2], [0, 2], [0, 2], [0, 3], [0, 3], [0, 2], [0, 2], [0, 2], [0, 2], [0], [0], [0], [0, 3, 4], [0, 1, 3], [0, 1, 3, 4], [0, 2, 3, 4], [0, 1, 3, 4], [0, 1, 2, 3, 4], [0, 1, 2, 3, 4], [0, 1, 3], [0, 1, 3], [0, 2, 5], [0, 1, 2, 4], [0, 1, 2, 5], [0, 1, 2, 3, 4], [0, 1, 2, 3, 4, 5],
]

VALUE_LABELS = {
    'OPI': {0: 'Off', 1: 'On'},
    'LFKS': {0: 'Off', 1: 'On'},
    'LFW': {0: 'Sine', 1: 'Triangle', 2: 'Sawtooth Down', 3: 'Sawtooth Up', 4: 'Square', 5: 'Sample and Hold'},
    'PM': {0: 'Ratio', 1: 'Fixed'},
    'LC': {0: 'Linear', 1: 'Exponential Negative', 2: 'Exponential Positive', 3: 'Logarithmic'},
    'RC': {0: 'Linear', 1: 'Exponential Negative', 2: 'Exponential Positive', 3: 'Logarithmic'},
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

class VoiceEditorPanel(QDialog):
    def __init__(self, midi_outport=None, voice_bytes=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voice Editor")
        self.resize(400, 600)
        self.setStyleSheet("background-color: #23272e; color: #e0e0e0;")
        self.midi_outport = midi_outport
        self.voice_bytes = voice_bytes or self.init_patch_bytes()
        self.decoder = SingleVoiceDumpDecoder(self.voice_bytes)
        self.decoder.decode()
        self.params = self.decoder.params
        self.op_count = 6
        self.tg_bg_widgets = []
        self.status_bar = QLabel("")
        self.status_bar.setMinimumHeight(48)
        self.status_bar.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_bar.setWordWrap(False)
        self.status_bar.setStyleSheet("background: transparent; color: #e0e0e0; padding: 4px;")
        self.gradient_carrier = "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #17677a, stop:1 #222c36); border-radius: 2px;"
        self.gradient_noncarrier = "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d3640, stop:1 #23272e); border-radius: 2px;"
        self.gradient_global = "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d3640, stop:1 #23272e); border-radius: 2px;"
        self.gradient_slider = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #23272e, stop:1 #2d3640)"
        self.gradient_status = "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fffde8, stop:0.5 #fffad7, stop:1 #f3eeb2); color: #000000; padding: 4px; border-top: 1px solid #d4cc99; border-radius: 2px;"
        self.status_bar.setStyleSheet(self.gradient_status)
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

    def status_bar_clicked(self, event):
        current_name = self.get_patch_name()
        new_name, ok = QInputDialog.getText(self, "Rename Voice", "Enter new voice name (max 10 chars):", text=current_name)
        if ok and new_name:
            self.name_edit.setText(new_name[:10])
            self.update_status_bar("")

    def get_carrier_ops(self, alg_idx):
        return DX7_CARRIER_MAP[alg_idx] if 0 <= alg_idx < 32 else []

    def get_value_label(self, key, value):
        mapping = VALUE_LABELS.get(key)
        if mapping:
            return mapping.get(value, str(value))
        return str(value)

    def _make_slider(self, value, min_val, max_val, slot, description, color, label=None, param_key=None):
        slider = QSlider(Qt.Orientation.Vertical)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setPageStep(1)
        slider.setValue(value)
        slider.setStyleSheet(f"QSlider::groove:vertical {{background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #23272e, stop:1 #2d3640); border: 1px solid #444;}} QSlider::handle:vertical {{background: {color}; border-radius: 2px;}}")
        slider.setMinimumHeight(30)
        slider.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        slider.valueChanged.connect(slot)
        def enterEvent(event, s=slider, d=description, k=param_key):
            val = s.value()
            label_val = self.get_value_label(k, val) if k else str(val)
            self.update_status_bar(f"{d}: {label_val}", lcd_value=val)
            # Highlight in envelope widget if rate or level
            if k and k.startswith('R') and k[1:].isdigit():
                idx = int(k[1:]) - 1
                self.env_widget.set_highlight('rate', idx)
            elif k and k.startswith('L') and k[1:].isdigit():
                idx = int(k[1:]) - 1
                self.env_widget.set_highlight('level', idx)
            # Highlight in keyboard scaling widget
            if k == 'BP':
                self.ks_widget.set_highlight('break')
            elif k == 'LD':
                self.ks_widget.set_highlight('left_depth')
            elif k == 'RD':
                self.ks_widget.set_highlight('right_depth')
            elif k == 'LC':
                self.ks_widget.set_highlight('left_curve')
            elif k == 'RC':
                self.ks_widget.set_highlight('right_curve')
        def leaveEvent(event, s=slider, d=description, k=param_key):
            self.update_status_bar("")
            # Remove highlight
            self.env_widget.clear_highlight()
            self.ks_widget.clear_highlight()
        slider.enterEvent = enterEvent
        slider.leaveEvent = leaveEvent
        slider.valueChanged.connect(lambda v, s=slider, d=description, k=param_key: self.update_status_bar(f"{d}: {self.get_value_label(k, v) if k else v}", lcd_value=v))
        if label:
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(slider, alignment=Qt.AlignmentFlag.AlignHCenter)
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 8pt; background: transparent;")
            col.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
            w = QWidget()
            w.setLayout(col)
            w.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            def w_enterEvent(event, s=slider):
                s.enterEvent(event)
            def w_leaveEvent(event, s=slider):
                s.leaveEvent(event)
            w.enterEvent = w_enterEvent
            w.leaveEvent = w_leaveEvent
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
        line.setMinimumWidth(1)
        line.setMaximumWidth(1)
        return line

    def init_ui(self):
        layout = QVBoxLayout(self)
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
        self.status_bar.setFixedWidth(0)
        topbar_layout.addWidget(self.status_bar, alignment=Qt.AlignmentFlag.AlignVCenter)

        topbar_layout.addStretch(3)
        
        # EnvelopeWidget
        self.env_widget = EnvelopeWidget()
        self.env_widget.setFixedWidth(140)
        self.env_widget.setFixedHeight(80)
        topbar_layout.addWidget(self.env_widget, alignment=Qt.AlignmentFlag.AlignVCenter)

        # KeyboardScalingWidget
        self.ks_widget = KeyboardScalingWidget()
        self.ks_widget.setFixedWidth(100)
        self.ks_widget.setFixedHeight(90)
        topbar_layout.addWidget(self.ks_widget, alignment=Qt.AlignmentFlag.AlignVCenter)
        
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
        layout.addLayout(topbar_layout)
        # Patch name edit
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(10)
        self.name_edit.setText(self.get_patch_name())
        self.name_edit.setMinimumWidth(120)
        self.name_edit.textChanged.connect(self.on_name_changed)
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
        for row, tg in enumerate(reversed(range(self.op_count)), start=1):
            is_carrier = tg in self.get_carrier_ops(self.get_param('ALS', 0))
            tg_bg = QWidget()
            tg_bg.setStyleSheet(self.gradient_carrier if is_carrier else self.gradient_noncarrier)
            self.tg_bg_widgets.insert(0, tg_bg)
            operator_row_layout = QHBoxLayout(tg_bg)
            operator_row_layout.setContentsMargins(0, 0, 0, 0)
            operator_row_layout.setSpacing(0)
            spacer_item = QWidget()
            spacer_item.setMinimumWidth(self.svg_overlay.width() if hasattr(self, 'svg_overlay') else 50)
            self.operator_spacer_items.append(spacer_item)
            operator_row_layout.addWidget(spacer_item)
            # Add E (Enable) slider
            operator_row_layout.addWidget(self._make_slider(
                self.get_op_param(tg, 'E', 1), 0, 1,
                lambda v, o=tg: (self.set_op_param(o, 'E', v), self.handle_op_enabled()),
                'Operator Enable', '#8ecae6', 'E', param_key='E'
            ))
            operator_row_layout.addWidget(self._make_vline())

            # Frequency
            for key, full_name, short_lbl, max_val in OP_FREQ_DEFS:
                operator_row_layout.addWidget(self._make_slider(
                    self.get_op_param(tg, key), 0, max_val,
                    lambda v, o=tg, k=key: self.set_op_param(o, k, v),
                    full_name, '#8ecae6', short_lbl, param_key=key
                ))
            operator_row_layout.addWidget(self._make_vline())
            # Level
            for key, full_name, short_lbl, max_val in OP_LEVEL_DEFS:
                operator_row_layout.addWidget(self._make_slider(
                    self.get_op_param(tg, key), 0, max_val,
                    lambda v, o=tg, k=key: self.set_op_param(o, k, v),
                    full_name, '#8ecae6', short_lbl, param_key=key
                ))
            operator_row_layout.addWidget(self._make_vline())
            # EG Level (L1-L4)
            for i in range(4):
                operator_row_layout.addWidget(self._make_slider(
                    self.get_op_param(tg, f'L{i+1}'), 0, 99,
                    lambda v, o=tg, idx=i: self.set_op_param(o, f'L{idx+1}', v),
                    f'Envelope Generator Level {i+1}', '#ffb703', f'L{i+1}', param_key=f'L{i+1}'
                ))
            # EG Rate (R1-R4)
            for i in range(4):
                operator_row_layout.addWidget(self._make_slider(
                    self.get_op_param(tg, f'R{i+1}'), 0, 99,
                    lambda v, o=tg, idx=i: self.set_op_param(o, f'R{idx+1}', v),
                    f'Envelope Generator Rate {i+1}', '#8ecae6', f'R{i+1}', param_key=f'R{i+1}'
                ))
            operator_row_layout.addWidget(self._make_vline())
            # Keyboard Scaling
            for key, full_name, short_lbl, max_val in OP_KS_DEFS:
                operator_row_layout.addWidget(self._make_slider(
                    self.get_op_param(tg, key), 0, max_val,
                    lambda v, o=tg, k=key: self.set_op_param(o, k, v),
                    full_name, '#8ecae6', short_lbl, param_key=key
                ))
            op_grid.addWidget(tg_bg, row, 0, 1, op_col_count)

            # --- Add event handlers for envelope preview on hover ---
            def make_enter_event(op_idx):
                def enterEvent(event, self=self, op_idx=op_idx):
                    self._hovered_op_idx = op_idx
                    self._update_env_widget_for_operator(op_idx)
                    self._update_ks_widget_for_operator(op_idx)
                return enterEvent
            def make_leave_event():
                def leaveEvent(event, self=self):
                    self._hovered_op_idx = None
                    self._reset_env_widget()
                    self._reset_ks_widget()
                return leaveEvent
            tg_bg.enterEvent = make_enter_event(tg)
            tg_bg.leaveEvent = make_leave_event()
        # Add global row at the bottom
        global_row = self.op_count + 1
        global_bg = QWidget()
        global_bg.setStyleSheet(self.gradient_global)
        global_layout = QHBoxLayout(global_bg)
        global_layout.setContentsMargins(0, 0, 0, 0)
        global_layout.setSpacing(0)
        self.global_spacer_item = QWidget()
        self.global_spacer_item.setMinimumWidth(self.svg_overlay.width() if hasattr(self, 'svg_overlay') else 50)
        global_layout.addWidget(self.global_spacer_item)
        for i in range(4):
            global_layout.addWidget(
                self._make_slider(
                    self.get_param(f'PR{i+1}', 0), 0, 99,
                    lambda v, k=f'PR{i+1}': self.set_param(k, v),
                    f'Envelope Generator Rate {i+1}', '#8ecae6', f'R{i+1}'
                )
            )
        for i in range(4):
            global_layout.addWidget(
                self._make_slider(
                    self.get_param(f'PL{i+1}', 0), 0, 99,
                    lambda v, k=f'PL{i+1}': self.set_param(k, v),
                    f'Envelope Generator Level {i+1}', '#ffb703', f'L{i+1}'
                )
            )
        global_layout.addWidget(self._make_vline())
        for label, key, min_val, max_val, tooltip in GLOBAL_PARAM_DEFS:
            global_layout.addWidget(
                self._make_slider(
                    self.get_param(key, 0), min_val, max_val,
                    lambda v, k=key: self.set_param(k, v),
                    tooltip, '#8ecae6', label, param_key=key
                )
            )
        op_grid.addWidget(global_bg, global_row, 0, 1, op_col_count)
        op_table_widget = QWidget()
        op_table_widget.setLayout(op_grid)
        op_table_widget.lower()
        self.svg_overlay = QSvgWidget(op_table_widget)
        self.svg_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.svg_overlay.setStyleSheet("background: transparent;")
        self.svg_overlay.setVisible(True)
        self.svg_overlay.raise_()
        layout.addWidget(op_table_widget)
        self.setLayout(layout)
        self.update_svg_overlay()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.status_bar.setFixedWidth(300)
        self.update_svg_overlay(resize_only=True)

    def update_svg_overlay(self, resize_only=False):
        alg_idx = self.alg_combo.currentIndex() + 1  # 1-based
        if not resize_only:
            svg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "images", f"algorithm-{alg_idx:02d}.svg"))
            self.svg_overlay.load(svg_path)
        parent_height = self.svg_overlay.parent().height()
        operator_rows = self.svg_overlay.parent().findChildren(QWidget)
        operator_height = (parent_height) * 0.93
        scale_factor = operator_height / self.svg_overlay.sizeHint().height()
        svg_width = int(self.svg_overlay.sizeHint().width() * scale_factor)
        svg_height = int(self.svg_overlay.sizeHint().height() * scale_factor)
        self.svg_overlay.resize(svg_width, svg_height)
        self.svg_overlay.setVisible(True)
        self.svg_overlay.raise_()
        self.svg_overlay.move(2, 7)
        for spacer in getattr(self, 'operator_spacer_items', []):
            spacer.setMinimumWidth(self.svg_overlay.width())
        if hasattr(self, 'global_spacer_item'):
            self.global_spacer_item.setMinimumWidth(self.svg_overlay.width())

    def update_operator_bg_colors(self):
        alg_idx = self.alg_combo.currentIndex()
        carrier_ops = self.get_carrier_ops(alg_idx)
        for op_idx, tg_bg in enumerate(self.tg_bg_widgets):
            if op_idx in carrier_ops:
                tg_bg.setStyleSheet(self.gradient_carrier)
            else:
                tg_bg.setStyleSheet(self.gradient_noncarrier)

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
            self.send_sysex(key, value, param_num)
        # Update envelope widget if this is the hovered operator and key is R1-R4 or L1-L4
        if self._hovered_op_idx == op and (key in [f'R{i+1}' for i in range(4)] or key in [f'L{i+1}' for i in range(4)]):
            self._update_env_widget_for_operator(op)
        # Update keyboard scaling widget if hovered and key is BP, LD, RD, LC, RC
        if self._hovered_op_idx == op and key in ['BP', 'LD', 'RD', 'LC', 'RC']:
            self._update_ks_widget_for_operator(op)

    def _update_ks_widget_for_operator(self, op_idx):
        bp = self.get_op_param(op_idx, 'BP', 50)
        ld = self.get_op_param(op_idx, 'LD', 50)
        rd = self.get_op_param(op_idx, 'RD', 50)
        lc = self.get_op_param(op_idx, 'LC', 0)
        rc = self.get_op_param(op_idx, 'RC', 0)
        self.ks_widget.set_params(bp, ld, rd, lc, rc)

    def _reset_ks_widget(self):
        self.ks_widget.set_params(50, 50, 50, 0, 0)

    def get_op_param(self, op, key, default=0):
        if 'operators' in self.params and isinstance(self.params['operators'], list):
            if 0 <= op < len(self.params['operators']):
                return self.params['operators'][op].get(key, default)
        return default

    def send_sysex(self, key, value, param_num):
        print(f"[DEBUG] send_sysex called with key={key}, value={value}, param_num={param_num}")
        if param_num is not None and value is not None:
            ch = self.channel_combo.currentIndex()  # 0-indexed for MIDI
            print(f"[DEBUG] Using MIDI channel index {ch}")
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
            print(f"[DEBUG] Constructed SysEx: {' '.join(f'{b:02X}' for b in sysex)}")
            if self.midi_outport:
                try:
                    msg = mido.Message('sysex', data=sysex[1:-1])
                    print(f"[DEBUG] Sending SysEx via mido on channel {ch+1}")
                    self.midi_outport.send(msg)
                except Exception as e:
                    print(f"[VOICE EDITOR PANEL] Failed to send SysEx: {e}")
            else:
                print("[DEBUG] midi_outport is not set, cannot send SysEx.")
        else:
            print("[VOICE EDITOR PANEL] No valid parameter or mapping for SysEx.")

    def _get_param_num(self, key):
        param_map = {
            'PR1': 121, 'PR2': 122, 'PR3': 123, 'PR4': 124,
            'PL1': 125, 'PL2': 126, 'PL3': 127, 'PL4': 128,
            'FBL': 129, 'OPI': 130, 'ALS': 134, 'LFS': 137, 'LFD': 138, 'LPMD': 139, 'LAMD': 140,
            'LFKS': 141, 'LFW': 142, 'LPMS': 143, 'TRNP': 144,
        }
        if key.startswith('VNAM'):
            try:
                idx = int(key[4:])
                return 145 + idx - 1
            except Exception:
                return None
        return param_map.get(key)

    def _get_operator_param_num(self, op, key):
        op_param_order = [
            'R1', 'R2', 'R3', 'R4', 'L1', 'L2', 'L3', 'L4',
            'BP', 'LD', 'RD', 'LC', 'RC', 'RS', 'TL', 'AMS', 'TS', 'PM', 'PC', 'PF', 'PD'
        ]
        if key in op_param_order:
            op_idx = int(op)
            param_base = (5 - op_idx) * 21
            param_offset = op_param_order.index(key)
            return param_base + param_offset
        return None

    def showEvent(self, event):
        super().showEvent(event)
        self.update_svg_overlay()

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
        if self.midi_outport:
            try:
                msg = mido.Message('sysex', data=sysex[1:-1])
                self.midi_outport.send(msg)
            except Exception as e:
                print(f"[DX7 OP ENABLE] Failed to send SysEx: {e}")
        else:
            print("[DX7 OP ENABLE] midi_outport is not set, cannot send SysEx.")

    def _update_env_widget_for_operator(self, op_idx):
        rates = [self.get_op_param(op_idx, f'R{i+1}', 50) for i in range(4)]
        levels = [self.get_op_param(op_idx, f'L{i+1}', 99 if i == 0 else 0) for i in range(4)]
        self.env_widget.set_envelope(rates, levels)

    def _reset_env_widget(self):
        # Optionally, reset to a default or global envelope, or just clear
        self.env_widget.set_envelope([50, 50, 50, 50], [99, 70, 40, 0])

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider, QDial, QPushButton, QLineEdit, QSpinBox, QCheckBox, QWidget, QGridLayout, QStackedLayout
from PyQt6.QtCore import Qt
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QResizeEvent
from single_voice_dump_decoder import SingleVoiceDumpDecoder
import os

class VoiceEditorPanel(QDialog):
    # DX7 carrier operators
    DX7_CARRIER_MAP = [
        [0, 2],           # 1
        [0, 2],           # 2
        [0, 3],           # 3
        [0, 3],           # 4
        [0, 2, 4],        # 5
        [0, 2, 4],        # 6
        [0, 2],           # 7
        [0, 2],           # 8
        [0, 2],           # 9
        [0, 3],           # 10
        [0, 3],           # 11
        [0, 2],           # 12
        [0, 2],           # 13
        [0, 2],           # 14
        [0, 2],           # 15
        [0],              # 16
        [0],              # 17
        [0],              # 18
        [0, 3, 4],        # 19
        [0, 1, 3],        # 20
        [0, 1, 3, 4],     # 21
        [0, 2, 3, 4],     # 22
        [0, 1, 3, 4],     # 23
        [0, 1, 2, 3, 4],  # 24
        [0, 1, 2, 3, 4],  # 25
        [0, 1, 3],        # 26
        [0, 1, 3],        # 27
        [0, 2, 5],        # 28
        [0, 1, 2, 4],     # 29
        [0, 1, 2, 5],     # 30
        [0, 1, 2, 3, 4],  # 31
        [0, 1, 2, 3, 4, 5], # 32
    ]

    def __init__(self, midi_outport=None, voice_bytes=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DX7 Voice Editor (Panel)")
        self.resize(1200, 900)
        self.setStyleSheet("background-color: #23272e; color: #e0e0e0;")
        self.midi_outport = midi_outport
        self.voice_bytes = voice_bytes or self.init_patch_bytes()
        self.decoder = SingleVoiceDumpDecoder(self.voice_bytes)
        self.decoder.decode()
        self.params = self.decoder.params
        self.op_count = 6
        self.init_ui()

    def get_carrier_ops(self, alg_idx):
        # alg_idx is 0-based (0..31), returns list of 0-based operator indices
        return self.DX7_CARRIER_MAP[alg_idx] if 0 <= alg_idx < 32 else []

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("MIDI Channel:"))
        self.channel_combo = QComboBox()
        for i in range(1, 17):
            self.channel_combo.addItem(str(i))
        channel_layout.addWidget(self.channel_combo)
        channel_layout.addStretch()
        layout.addLayout(channel_layout)

        # Top: Patch name and algorithm
        top_layout = QHBoxLayout()
        name_lbl = QLabel("Patch Name:")
        name_lbl.setStyleSheet("font-weight: bold; color: #8ecae6;")
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(10)
        self.name_edit.setText(self.get_patch_name())
        self.name_edit.setFixedWidth(120)
        self.name_edit.textChanged.connect(self.on_name_changed)
        top_layout.addWidget(name_lbl)
        top_layout.addWidget(self.name_edit)
        top_layout.addSpacing(40)
        alg_lbl = QLabel("Algorithm:")
        alg_lbl.setStyleSheet("font-weight: bold; color: #8ecae6;")
        top_layout.addWidget(alg_lbl)
        self.alg_combo = QComboBox()
        for i in range(1, 33):
            self.alg_combo.addItem(str(i))
        self.alg_combo.setCurrentIndex(self.get_param('ALS', 0))
        self.alg_combo.currentIndexChanged.connect(self.on_algorithm_changed)
        top_layout.addWidget(self.alg_combo)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Section headline and operator rows: use a single QGridLayout for perfect alignment
        op_grid = QGridLayout()
        col = 0
        op_grid.addWidget(QLabel("Operator"), 0, col)
        col += 1
        op_grid.addWidget(QLabel("EG Rate"), 0, col, 1, 4)
        col += 4
        op_grid.addWidget(QLabel("EG Level"), 0, col, 1, 4)
        col += 4
        op_grid.addWidget(QLabel("Keyboard Scaling"), 0, col, 1, 6)
        col += 6
        op_grid.addWidget(QLabel("Operator"), 0, col, 1, 3)
        col += 3
        op_grid.addWidget(QLabel("Frequency"), 0, col, 1, 4)

        self.tg_bg_widgets = []
        op_col_count = 1 + 4 + 4 + 6 + 3 + 4  # total columns in op_grid
        for row, tg in enumerate(reversed(range(self.op_count)), start=1):
            is_carrier = tg in self.get_carrier_ops(self.get_param('ALS', 0))
            op_bg_color = "#17677a" if is_carrier else "#222c36"
            tg_bg = QWidget()
            tg_bg.setStyleSheet(f"background-color: {op_bg_color}; border-radius: 8px;")
            self.tg_bg_widgets.insert(0, tg_bg)
            tg_row_layout = QHBoxLayout(tg_bg)
            tg_row_layout.setContentsMargins(2, 2, 2, 2)
            tg_row_layout.setSpacing(2)
            # Insert 50 pixels of space for the operator label
            spacer_item = QWidget()
            spacer_item.setFixedWidth(50)
            tg_row_layout.addWidget(spacer_item)
            # EG Rate (R1-R4)
            for i in range(4):
                eg_col = QVBoxLayout()
                eg_rate = QSlider(Qt.Orientation.Vertical)
                eg_rate.setMinimum(0)
                eg_rate.setMaximum(99)
                eg_rate.setValue(self.get_op_param(tg, f'R{i+1}'))
                eg_rate.setStyleSheet(f"QSlider::groove:vertical {{background: #222c36; border: 1px solid #444;}} QSlider::handle:vertical {{background: #8ecae6; border-radius: 6px;}}")
                eg_rate.setFixedHeight(30)
                eg_rate.valueChanged.connect(lambda v, o=tg, idx=i: self.set_op_param(o, f'R{idx+1}', v))
                eg_rate.setToolTip(f"EG Rate {i+1}: {eg_rate.value()}")
                eg_rate.valueChanged.connect(lambda v, s=eg_rate, n=f'EG Rate {i+1}': s.setToolTip(f'{n}: {v}'))
                eg_col.addWidget(eg_rate, alignment=Qt.AlignmentFlag.AlignHCenter)
                eg_col.addWidget(QLabel(f"R{i+1}"), alignment=Qt.AlignmentFlag.AlignHCenter)
                eg_widget = QWidget()
                eg_widget.setLayout(eg_col)
                tg_row_layout.addWidget(eg_widget)
            # EG Level (L1-L4)
            for i in range(4):
                eg_col = QVBoxLayout()
                eg_level = QSlider(Qt.Orientation.Vertical)
                eg_level.setMinimum(0)
                eg_level.setMaximum(99)
                eg_level.setValue(self.get_op_param(tg, f'L{i+1}'))
                eg_level.setStyleSheet(f"QSlider::groove:vertical {{background: #222c36; border: 1px solid #444;}} QSlider::handle:vertical {{background: #ffb703; border-radius: 6px;}}")
                eg_level.setFixedHeight(30)
                eg_level.valueChanged.connect(lambda v, o=tg, idx=i: self.set_op_param(o, f'L{idx+1}', v))
                eg_level.setToolTip(f"EG Level {i+1}: {eg_level.value()}")
                eg_level.valueChanged.connect(lambda v, s=eg_level, n=f'EG Level {i+1}': s.setToolTip(f'{n}: {v}'))
                eg_col.addWidget(eg_level, alignment=Qt.AlignmentFlag.AlignHCenter)
                eg_col.addWidget(QLabel(f"L{i+1}"), alignment=Qt.AlignmentFlag.AlignHCenter)
                eg_widget = QWidget()
                eg_widget.setLayout(eg_col)
                tg_row_layout.addWidget(eg_widget)
            # Keyboard Scaling (BP, LD, RD, LC, RC, RS)
            for key, full_name, short_lbl in zip([
                "BP", "LD", "RD", "LC", "RC", "RS"
            ], [
                "Break Point", "Left Depth", "Right Depth", "Left Curve", "Right Curve", "Rate Scaling"
            ], [
                "BP", "LD", "RD", "LC", "RC", "RS"
            ]):
                col_layout = QVBoxLayout()
                dial = QDial()
                dial.setMinimum(0)
                dial.setMaximum(99 if key in ["BP", "LD", "RD"] else 3 if key in ["LC", "RC"] else 7)
                dial.setValue(self.get_op_param(tg, key))
                dial.setNotchesVisible(False)
                dial.setFixedSize(28, 28)
                dial.setStyleSheet(f"QDial {{ background: #444; border: none; color: #b0b0b0; }}")
                dial.valueChanged.connect(lambda v, o=tg, k=key: self.set_op_param(o, k, v))
                dial.setToolTip(f"{full_name}: {dial.value()}")
                dial.valueChanged.connect(lambda v, s=dial, n=full_name: s.setToolTip(f'{n}: {v}'))
                col_layout.addWidget(dial, alignment=Qt.AlignmentFlag.AlignHCenter)
                col_layout.addWidget(QLabel(short_lbl), alignment=Qt.AlignmentFlag.AlignHCenter)
                col_widget = QWidget()
                col_widget.setLayout(col_layout)
                tg_row_layout.addWidget(col_widget)
            # Operator (TL, AMS, TS)
            for key, full_name, short_lbl, max_val in zip([
                "TL", "AMS", "TS"
            ], [
                "Total Level", "Amplitude Mod Sensitivity", "Touch Sensitivity"
            ], [
                "TL", "AMS", "TS"
            ], [99, 3, 7]):
                col_layout = QVBoxLayout()
                dial = QDial()
                dial.setMinimum(0)
                dial.setMaximum(max_val)
                dial.setValue(self.get_op_param(tg, key))
                dial.setNotchesVisible(False)
                dial.setFixedSize(28, 28)
                dial.setStyleSheet(f"QDial {{ background: #444; border: none; color: #b0b0b0; }}")
                dial.valueChanged.connect(lambda v, o=tg, k=key: self.set_op_param(o, k, v))
                dial.setToolTip(f"{full_name}: {dial.value()}")
                dial.valueChanged.connect(lambda v, s=dial, n=full_name: s.setToolTip(f'{n}: {v}'))
                col_layout.addWidget(dial, alignment=Qt.AlignmentFlag.AlignHCenter)
                col_layout.addWidget(QLabel(short_lbl), alignment=Qt.AlignmentFlag.AlignHCenter)
                col_widget = QWidget()
                col_widget.setLayout(col_layout)
                tg_row_layout.addWidget(col_widget)
            # Frequency (PM, PC, PF, PD)
            for key, full_name, short_lbl, max_val in zip([
                "PM", "PC", "PF", "PD"
            ], [
                "Frequency Mode", "Coarse", "Fine", "Detune"
            ], [
                "PM", "COARSE", "FINE", "DETUNE"
            ], [1, 31, 99, 14]):
                col_layout = QVBoxLayout()
                dial = QDial()
                dial.setMinimum(0)
                dial.setMaximum(max_val)
                dial.setValue(self.get_op_param(tg, key))
                dial.setNotchesVisible(False)
                dial.setFixedSize(28, 28)
                dial.setStyleSheet(f"QDial {{ background: #444; border: none; color: #b0b0b0; }}")
                dial.valueChanged.connect(lambda v, o=tg, k=key: self.set_op_param(o, k, v))
                dial.setToolTip(f"{full_name}: {dial.value()}")
                dial.valueChanged.connect(lambda v, s=dial, n=full_name: s.setToolTip(f'{n}: {v}'))
                col_layout.addWidget(dial, alignment=Qt.AlignmentFlag.AlignHCenter)
                col_layout.addWidget(QLabel(short_lbl), alignment=Qt.AlignmentFlag.AlignHCenter)
                col_widget = QWidget()
                col_widget.setLayout(col_layout)
                tg_row_layout.addWidget(col_widget)
            # Add the row widget to the op_grid, spanning all columns
            op_grid.addWidget(tg_bg, row, 0, 1, op_col_count)

        # Create a container widget for the operator table and SVG overlay using absolute positioning
        self.op_table_container = QWidget()
        # Dynamically set minimum height based on operator rows (e.g. 60px per row + header)
        row_height = 60
        min_height = row_height * (self.op_count + 1)
        self.op_table_container.setMinimumHeight(min_height)
        self.op_table_container.setMaximumHeight(min_height)
        # Operator table widget
        op_table_widget = QWidget(self.op_table_container)
        op_table_widget.setLayout(op_grid)
        op_table_widget.setGeometry(0, 0, self.width(), min_height)
        op_table_widget.lower()  # Ensure it's below the SVG overlay
        # SVG overlay
        self.svg_overlay = QSvgWidget(self.op_table_container)
        self.svg_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.svg_overlay.setStyleSheet("background: transparent;")
        self.svg_overlay.setGeometry(0, 0, self.width(), min_height)
        self.svg_overlay.setVisible(True)
        self.svg_overlay.raise_()  # Ensure overlay is above the table
        self.update_svg_overlay()  # Initial SVG
        layout.addWidget(self.op_table_container)

        # Global/voice section: PEG RATE/LEVEL as vertical sliders like R1-L4, rest as grey dials
        tg_color = "#222c36"  # Ensure tg_color is defined for use below
        global_grid = QGridLayout()
        peg_labels = ["PEG RATE1", "PEG RATE2", "PEG RATE3", "PEG RATE4", "PEG LEVEL1", "PEG LEVEL2", "PEG LEVEL3", "PEG LEVEL4"]
        peg_keys = ["PR1", "PR2", "PR3", "PR4", "PL1", "PL2", "PL3", "PL4"]
        peg_full_names = ["PEG Rate 1", "PEG Rate 2", "PEG Rate 3", "PEG Rate 4", "PEG Level 1", "PEG Level 2", "PEG Level 3", "PEG Level 4"]
        for i in range(8):
            peg_col = QVBoxLayout()
            peg_col.setSpacing(2)
            peg_slider = QSlider(Qt.Orientation.Vertical)
            peg_slider.setMinimum(0)
            peg_slider.setMaximum(99)
            peg_slider.setValue(self.get_param(peg_keys[i], 0))
            peg_slider.setStyleSheet(f"QSlider::groove:vertical {{background: {tg_color}; border: 1px solid #444;}} QSlider::handle:vertical {{background: #8ecae6; border-radius: 6px;}}")
            peg_slider.setFixedHeight(30)
            peg_slider.valueChanged.connect(lambda v, k=peg_keys[i]: self.set_param(k, v))
            peg_slider.setToolTip(f"{peg_full_names[i]}: {peg_slider.value()}")
            peg_slider.valueChanged.connect(lambda v, s=peg_slider, n=peg_full_names[i]: s.setToolTip(f'{n}: {v}'))
            peg_col.addWidget(peg_slider, alignment=Qt.AlignmentFlag.AlignHCenter)
            peg_col.addWidget(QLabel(peg_labels[i]), alignment=Qt.AlignmentFlag.AlignHCenter)
            global_grid.addLayout(peg_col, 0, i)
        global_defs = [
            ("FEEDBACK LEVEL", "FBL", 0, 7, "Feedback Level"), ("OSC KEY SYNC", "OPI", 0, 1, "Oscillator Key Sync"),
            ("LFO SPEED", "LFS", 0, 99, "LFO Speed"), ("LFO DELAY", "LFD", 0, 99, "LFO Delay Time"), ("LFO PM DEPTH", "LPMD", 0, 99, "LFO Pitch Mod Depth"), ("LFO AM DEPTH", "LAMD", 0, 99, "LFO Amp Mod Depth"),
            ("LFO KEY SYNC", "LFKS", 0, 1, "LFO Key Sync"), ("LFO WAVE", "LFW", 0, 5, "LFO Wave"), ("PM SENS", "LPMS", 0, 7, "Pitch Mod Sensitivity"), ("TRANSPOSE", "TRNP", 0, 48, "Transpose")
        ]
        for i, (label, key, min_val, max_val, full_name) in enumerate(global_defs):
            dial = QDial()
            dial.setMinimum(min_val)
            dial.setMaximum(max_val)
            dial.setValue(self.get_param(key, 0))
            dial.setNotchesVisible(False)
            dial.setFixedSize(28, 28)
            dial.setStyleSheet(f"QDial {{ background: #444; border: none; color: #b0b0b0; }}")
            dial.valueChanged.connect(lambda v, k=key: self.set_param(k, v))
            dial.setToolTip(f"{full_name}: {dial.value()}")
            dial.valueChanged.connect(lambda v, s=dial, n=full_name: s.setToolTip(f'{n}: {v}'))
            global_grid.addWidget(QLabel(label), 1 + i // 8, (i % 8) * 2)
            global_grid.addWidget(dial, 1 + i // 8, (i % 8) * 2 + 1)
        layout.addLayout(global_grid)

        self.setLayout(layout)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        # Resize SVG overlay and operator table to cover the operator table area
        self.update_svg_overlay()

    def update_svg_overlay(self):
        alg_idx = self.alg_combo.currentIndex() + 1  # 1-based
        svg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "images", f"algorithm-{alg_idx:02d}.svg"))
        self.svg_overlay.load(svg_path)
        container_height = self.op_table_container.minimumHeight() + 18
        # Get the SVG's intrinsic size
        renderer = self.svg_overlay.renderer()
        svg_size = renderer.defaultSize()
        # Scale to fit height, keep aspect ratio
        scale = container_height / svg_size.height()
        new_height = int(svg_size.height() * scale)
        new_width = int(svg_size.width() * scale)
        x = 0
        y = 35  # move down
        self.svg_overlay.setGeometry(x, y, new_width, new_height)
        self.svg_overlay.setVisible(True)
        self.svg_overlay.raise_()  # Ensure overlay is above the table

    def update_operator_bg_colors(self):
        alg_idx = self.alg_combo.currentIndex()
        carrier_ops = self.get_carrier_ops(alg_idx)
        for op_idx, tg_bg in enumerate(self.tg_bg_widgets):
            op_bg_color = "#17677a" if op_idx in carrier_ops else "#222c36"
            tg_bg.setStyleSheet(f"background-color: {op_bg_color}; border-radius: 8px;")

    def on_algorithm_changed(self, idx):
        print(f"[DEBUG] on_algorithm_changed called with idx={idx}")
        self.set_param('ALS', idx)
        self.update_operator_bg_colors()
        self.update_svg_overlay()
        # Also send SysEx for algorithm change
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

    def get_param(self, key, default=None):
        return self.params.get(key, default)

    def set_param(self, key, value):
        self.params[key] = value
        # Find param_num for global params
        param_num = self._get_param_num(key)
        if param_num is not None:
            self.send_sysex(key, value, param_num)

    def set_op_param(self, op, key, value):
        if 'operators' not in self.params or not isinstance(self.params['operators'], list):
            self.params['operators'] = [{} for _ in range(self.op_count)]
        elif len(self.params['operators']) < self.op_count:
            self.params['operators'] += [{} for _ in range(self.op_count - len(self.params['operators']))]
        self.params['operators'][op][key] = value
        # Calculate param_num for operator params
        param_num = self._get_operator_param_num(op, key)
        if param_num is not None:
            self.send_sysex(key, value, param_num)

    def get_op_param(self, op, key, default=0):
        if 'operators' in self.params and isinstance(self.params['operators'], list):
            if 0 <= op < len(self.params['operators']):
                return self.params['operators'][op].get(key, default)
        return default

    def send_sysex(self, key, value, param_num):
        print(f"[DEBUG] send_sysex called with key={key}, value={value}, param_num={param_num}")
        # Build and send DX7 Parameter Change SysEx message
        if param_num is not None and value is not None:
            ch = self.channel_combo.currentIndex()  # 0-indexed for MIDI
            print(f"[DEBUG] Using MIDI channel index {ch}")
            # Voice parameter change (0-155)
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
                    import mido
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
        # Map global param key to DX7 parameter number
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
        # Map operator param to DX7 parameter number (as in voice_editor.py)
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

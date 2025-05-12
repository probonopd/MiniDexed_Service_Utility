from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider, QDial, QPushButton, QLineEdit, QSpinBox, QCheckBox, QWidget, QGridLayout
from PyQt6.QtCore import Qt
from single_voice_dump_decoder import SingleVoiceDumpDecoder

class VoiceEditorPanel(QDialog):
    # DX7 carrier operator mapping for algorithms 1-32 (1-based, OP1=0)
    DX7_CARRIER_MAP = [
        [5],            # 1: OP6
        [4, 5],         # 2: OP5, OP6
        [3, 5],         # 3: OP4, OP6
        [2, 5],         # 4: OP3, OP6
        [1, 5],         # 5: OP2, OP6
        [0, 5],         # 6: OP1, OP6
        [5],            # 7: OP6
        [2, 5],         # 8: OP3, OP6
        [0, 2, 5],      # 9: OP1, OP3, OP6
        [0, 3, 5],      # 10: OP1, OP4, OP6
        [0, 2, 4, 5],   # 11: OP1, OP3, OP5, OP6
        [0, 1, 2, 3, 4, 5], # 12: all
        [5],            # 13: OP6
        [4, 5],         # 14: OP5, OP6
        [3, 5],         # 15: OP4, OP6
        [2, 5],         # 16: OP3, OP6
        [1, 5],         # 17: OP2, OP6
        [0, 5],         # 18: OP1, OP6
        [5],            # 19: OP6
        [2, 5],         # 20: OP3, OP6
        [0, 2, 5],      # 21: OP1, OP3, OP6
        [0, 3, 5],      # 22: OP1, OP4, OP6
        [0, 2, 4, 5],   # 23: OP1, OP3, OP5, OP6
        [0, 1, 2, 3, 4, 5], # 24: all
        [5],            # 25: OP6
        [4, 5],         # 26: OP5, OP6
        [3, 5],         # 27: OP4, OP6
        [2, 5],         # 28: OP3, OP6
        [1, 5],         # 29: OP2, OP6
        [0, 5],         # 30: OP1, OP6
        [5],            # 31: OP6
        [0, 1, 2, 3, 4, 5], # 32: all
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

        # Section headline row: only group headlines, not every label
        headline_row = QHBoxLayout()
        headline_row.setSpacing(10)
        headline_row.addWidget(QLabel("Operator"))
        headline_row.addSpacing(8)
        headline_row.addWidget(QLabel("EG Rate"))
        headline_row.addSpacing(40)
        headline_row.addWidget(QLabel("EG Level"))
        headline_row.addSpacing(40)
        headline_row.addWidget(QLabel("Keyboard Scaling"))
        headline_row.addSpacing(60)
        headline_row.addWidget(QLabel("Operator"))
        headline_row.addSpacing(30)
        headline_row.addWidget(QLabel("Frequency"))
        layout.addLayout(headline_row)

        # TG rows: TG8 (top) to TG1 (bottom), all same color, one row per TG
        tg_color = "#222c36"
        label_color = "#e0e0e0"
        self.tg_bg_widgets = []  # Store operator background widgets for color updates
        for tg in reversed(range(self.op_count)):
            tg_row = QHBoxLayout()
            tg_bg = QWidget()
            is_carrier = tg in self.get_carrier_ops(self.get_param('ALS', 0))
            op_bg_color = "#17677a" if is_carrier else "#222c36"  # dark turquoise for carrier, dark grey for modulator
            tg_bg.setStyleSheet(f"background-color: {op_bg_color}; border-radius: 8px;")
            self.tg_bg_widgets.insert(0, tg_bg)  # Insert at front so index matches operator number
            tg_bg_layout = QHBoxLayout(tg_bg)
            tg_bg_layout.setContentsMargins(8, 2, 8, 2)
            tg_bg_layout.setSpacing(10)
            # Operator label
            tg_label = QLabel(f"TG{tg+1}")
            tg_label.setStyleSheet(f"font-weight: bold; color: {label_color}; font-size: 16px;")
            tg_label.setFixedWidth(48)
            tg_bg_layout.addWidget(tg_label)
            # EG Rate (R1-R4)
            for i in range(4):
                eg_col = QVBoxLayout()
                eg_col.setSpacing(2)
                eg_rate = QSlider(Qt.Orientation.Vertical)
                eg_rate.setMinimum(0)
                eg_rate.setMaximum(99)
                eg_rate.setValue(self.get_op_param(tg, f'R{i+1}'))
                eg_rate.setStyleSheet(f"QSlider::groove:vertical {{background: {tg_color}; border: 1px solid #444;}} QSlider::handle:vertical {{background: #8ecae6; border-radius: 6px;}}")
                eg_rate.setFixedHeight(30)
                eg_rate.valueChanged.connect(lambda v, o=tg, idx=i: self.set_op_param(o, f'R{idx+1}', v))
                eg_rate.setToolTip(f"EG Rate {i+1}: {eg_rate.value()}")
                eg_rate.valueChanged.connect(lambda v, s=eg_rate, n=f'EG Rate {i+1}': s.setToolTip(f'{n}: {v}'))
                eg_col.addWidget(eg_rate, alignment=Qt.AlignmentFlag.AlignHCenter)
                eg_col.addWidget(QLabel(f"R{i+1}"), alignment=Qt.AlignmentFlag.AlignHCenter)
                tg_bg_layout.addLayout(eg_col)
            # EG Level (L1-L4)
            for i in range(4):
                eg_col = QVBoxLayout()
                eg_col.setSpacing(2)
                eg_level = QSlider(Qt.Orientation.Vertical)
                eg_level.setMinimum(0)
                eg_level.setMaximum(99)
                eg_level.setValue(self.get_op_param(tg, f'L{i+1}'))
                eg_level.setStyleSheet(f"QSlider::groove:vertical {{background: {tg_color}; border: 1px solid #444;}} QSlider::handle:vertical {{background: #ffb703; border-radius: 6px;}}")
                eg_level.setFixedHeight(30)
                eg_level.valueChanged.connect(lambda v, o=tg, idx=i: self.set_op_param(o, f'L{idx+1}', v))
                eg_level.setToolTip(f"EG Level {i+1}: {eg_level.value()}")
                eg_level.valueChanged.connect(lambda v, s=eg_level, n=f'EG Level {i+1}': s.setToolTip(f'{n}: {v}'))
                eg_col.addWidget(eg_level, alignment=Qt.AlignmentFlag.AlignHCenter)
                eg_col.addWidget(QLabel(f"L{i+1}"), alignment=Qt.AlignmentFlag.AlignHCenter)
                tg_bg_layout.addLayout(eg_col)
            # Keyboard Scaling (BP, LD, RD, LC, RC, RS)
            for key, full_name, short_lbl in zip([
                "BP", "LD", "RD", "LC", "RC", "RS"
            ], [
                "Break Point", "Left Depth", "Right Depth", "Left Curve", "Right Curve", "Rate Scaling"
            ], [
                "BP", "LD", "RD", "LC", "RC", "RS"
            ]):
                col = QVBoxLayout()
                col.setSpacing(2)
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
                col.addWidget(dial, alignment=Qt.AlignmentFlag.AlignHCenter)
                col.addWidget(QLabel(short_lbl), alignment=Qt.AlignmentFlag.AlignHCenter)
                tg_bg_layout.addLayout(col)
            # Operator (TL, AMS, TS)
            for key, full_name, short_lbl, max_val in zip([
                "TL", "AMS", "TS"
            ], [
                "Total Level", "Amplitude Mod Sensitivity", "Touch Sensitivity"
            ], [
                "TL", "AMS", "TS"
            ], [99, 3, 7]):
                col = QVBoxLayout()
                col.setSpacing(2)
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
                col.addWidget(dial, alignment=Qt.AlignmentFlag.AlignHCenter)
                col.addWidget(QLabel(short_lbl), alignment=Qt.AlignmentFlag.AlignHCenter)
                tg_bg_layout.addLayout(col)
            # Frequency (PM, PC, PF, PD)
            for key, full_name, short_lbl, max_val in zip([
                "PM", "PC", "PF", "PD"
            ], [
                "Frequency Mode", "Coarse", "Fine", "Detune"
            ], [
                "PM", "COARSE", "FINE", "DETUNE"
            ], [1, 31, 99, 14]):
                col = QVBoxLayout()
                col.setSpacing(2)
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
                col.addWidget(dial, alignment=Qt.AlignmentFlag.AlignHCenter)
                col.addWidget(QLabel(short_lbl), alignment=Qt.AlignmentFlag.AlignHCenter)
                tg_bg_layout.addLayout(col)
            tg_bg_layout.addStretch()
            tg_row.addWidget(tg_bg)
            layout.addLayout(tg_row)

        # Global/voice section: PEG RATE/LEVEL as vertical sliders like R1-L4, rest as grey dials
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

    def update_operator_bg_colors(self):
        alg_idx = self.alg_combo.currentIndex()
        carrier_ops = self.get_carrier_ops(alg_idx)
        for op_idx, tg_bg in enumerate(self.tg_bg_widgets):
            op_bg_color = "#17677a" if op_idx in carrier_ops else "#222c36"
            tg_bg.setStyleSheet(f"background-color: {op_bg_color}; border-radius: 8px;")

    def on_algorithm_changed(self, idx):
        self.set_param('ALS', idx)
        self.update_operator_bg_colors()

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

    def get_op_param(self, op, key):
        ops = self.params.get('operators', [{}]*self.op_count)
        return ops[op].get(key, 0)

    def set_op_param(self, op, key, value):
        if 'operators' not in self.params or not isinstance(self.params['operators'], list):
            self.params['operators'] = [{} for _ in range(self.op_count)]
        elif len(self.params['operators']) < self.op_count:
            self.params['operators'] += [{} for _ in range(self.op_count - len(self.params['operators']))]
        self.params['operators'][op][key] = value

    def init_patch_bytes(self):
        data = [0xF0, 0x43, 0x00, 0x09, 0x20] + [0]*155 + [0xF7]
        name = b'INIT PATCH'
        for i, c in enumerate(name):
            data[150 + i] = c
        return bytes(data)

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QLabel, QSpinBox, QComboBox, QLineEdit
from PyQt6.QtCore import Qt
from single_voice_dump_decoder import SingleVoiceDumpDecoder
import mido

class VoiceEditor(QDialog):
    _instance = None

    def __init__(self, midi_outport=None, voice_bytes=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DX7 Voice Editor")
        self.resize(900, 600)
        self.midi_outport = midi_outport
        self.voice_bytes = voice_bytes or self.init_patch_bytes()
        self.decoder = SingleVoiceDumpDecoder(self.voice_bytes)
        self.decoder.decode()
        self.params = self.decoder.params
        layout = QVBoxLayout(self)
        # Add channel selector
        from PyQt6.QtWidgets import QHBoxLayout
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("MIDI Channel:"))
        self.channel_combo = QComboBox()
        for i in range(1, 17):
            self.channel_combo.addItem(str(i))
        channel_layout.addWidget(self.channel_combo)
        layout.addLayout(channel_layout)
        # Table for all parameters (operators + global)
        self.op_count = 6
        self.op_params = [
            ("EG RATE1", "R1", 0, 99),
            ("EG RATE2", "R2", 0, 99),
            ("EG RATE3", "R3", 0, 99),
            ("EG RATE4", "R4", 0, 99),
            ("EG LEVEL1", "L1", 0, 99),
            ("EG LEVEL2", "L2", 0, 99),
            ("EG LEVEL3", "L3", 0, 99),
            ("EG LEVEL4", "L4", 0, 99),
            ("BREAK POINT", "BP", 0, 99),
            ("LEFT DEPTH", "LD", 0, 99),
            ("RIGHT DEPTH", "RD", 0, 99),
            ("LEFT CURVE", "LC", 0, 3),
            ("RIGHT CURVE", "RC", 0, 3),
            ("RATE SCALING", "RS", 0, 7),
            ("MODULATION SENSITIVITY", "AMS", 0, 3),
            ("TOUCH SENSITIVITY", "TS", 0, 7),
            ("TOTAL LEVEL", "TL", 0, 99),
            ("FREQUENCY MODE", "PM", 0, 1),
            ("FREQUENCY COARSE", "PC", 0, 31),
            ("FREQUENCY FINE", "PF", 0, 99),
            ("DETUNE", "PD", 0, 14),
        ]
        op_param_labels = [p[0] for p in self.op_params]
        # Table: one column per OP, one row per operator parameter, global params below
        self.table = QTableWidget(self)
        self.table.setHorizontalHeaderLabels([f"OP{i+1}" for i in range(self.op_count)])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(QLabel("<b>DX7 Voice Editor (VCED format)</b>"))
        layout.addWidget(self.table)
        self.populate_table()
        self.setLayout(layout)
        # (Removed all global param widgets outside the table)

    def populate_table(self):
        # Fill operator table: each row is a parameter, each column is an operator
        op_param_count = len(self.op_params)
        peg_params = [
            ("PEG RATE1", "PR1", 0, 99, 126),
            ("PEG RATE2", "PR2", 0, 99, 127),
            ("PEG RATE3", "PR3", 0, 99, 128),
            ("PEG RATE4", "PR4", 0, 99, 129),
            ("PEG LEVEL1", "PL1", 0, 99, 130),
            ("PEG LEVEL2", "PL2", 0, 99, 131),
            ("PEG LEVEL3", "PL3", 0, 99, 132),
            ("PEG LEVEL4", "PL4", 0, 99, 133),
        ]
        global_params = [
            ("ALGORITHM SELECTOR", "ALS", 0, 31, 134),
            ("FEEDBACK LEVEL", "FBL", 0, 7, 135),
            ("OSCILLATOR KEY SYNC", "OPI", 0, 1, 136),
            ("LFO SPEED", "LFS", 0, 99, 137),
            ("LFO DELAY TIME", "LFD", 0, 99, 138),
            ("LFO PITCH MOD DEPTH", "LPMD", 0, 99, 139),
            ("LFO AMP MOD DEPTH", "LAMD", 0, 99, 140),
            ("LFO KEY SYNC", "LFKS", 0, 1, 141),
            ("LFO WAVE", "LFW", 0, 5, 142),
            ("PITCH MOD SENSITIVITY", "LPMS", 0, 7, 143),
            ("TRANSPOSE", "TRNP", 0, 48, 144),
        ]
        voice_name_row = ("VOICE NAME", "VNAM", 32, 127, 145)
        total_rows = op_param_count + len(peg_params) + len(global_params) + 1
        self.table.setRowCount(total_rows)
        self.table.setColumnCount(self.op_count)
        # Set vertical header labels: per-operator param names, then PEG/global/voice name
        vertical_labels = [label for (label, *_rest) in self.op_params]
        vertical_labels += [label for (label, *_rest) in peg_params]
        vertical_labels += [label for (label, *_rest) in global_params]
        vertical_labels.append("VOICE NAME")
        self.table.setVerticalHeaderLabels(vertical_labels)
        # Operator parameter rows
        for row, (label, key, min_val, max_val) in enumerate(self.op_params):
            for op in range(self.op_count):
                op_idx = op  # OP1 is leftmost
                op_key = f"OP{op_idx+1}_{key}"
                value = self._get_param_value(op_key)
                spin = QSpinBox()
                spin.setMinimum(min_val)
                spin.setMaximum(max_val)
                spin.setValue(int(value) if value is not None else min_val)
                param_num = (5-op_idx)*21 + row  # param_num as in original code
                spin.valueChanged.connect(lambda val, k=op_key, r=row, p=param_num: self.on_param_changed(k, val, r, p))
                self.table.setCellWidget(row, op, spin)
        # Pitch EG rows (spanning all columns)
        for i, (label, key, min_val, max_val, param_num) in enumerate(peg_params):
            row = op_param_count + i
            spin = QSpinBox()
            spin.setMinimum(min_val)
            spin.setMaximum(max_val)
            value = self._get_param_value(key)
            spin.setValue(int(value) if value is not None else min_val)
            spin.valueChanged.connect(lambda val, k=key, p=param_num: self.on_param_changed(k, val, row, p))
            self.table.setCellWidget(row, 0, spin)
            self.table.setSpan(row, 0, 1, self.op_count)
        # Global parameter rows (spanning all columns)
        for i, (label, key, min_val, max_val, param_num) in enumerate(global_params):
            row = op_param_count + len(peg_params) + i
            spin = QSpinBox()
            spin.setMinimum(min_val)
            spin.setMaximum(max_val)
            value = self._get_param_value(key)
            spin.setValue(int(value) if value is not None else min_val)
            spin.valueChanged.connect(lambda val, k=key, p=param_num: self.on_param_changed(k, val, row, p))
            self.table.setCellWidget(row, 0, spin)
            self.table.setSpan(row, 0, 1, self.op_count)
        # Voice name row (spanning all columns)
        name_row = op_param_count + len(peg_params) + len(global_params)
        name_edit = QLineEdit()
        name = ''.join(chr(self._get_param_value(f"VNAM{i+1}")) if self._get_param_value(f"VNAM{i+1}") and 32 <= self._get_param_value(f"VNAM{i+1}") <= 127 else ' ' for i in range(10))
        name_edit.setMaxLength(10)
        name_edit.setText(name)
        def on_name_changed(val):
            for i, c in enumerate(val.ljust(10)[:10]):
                self.on_param_changed(f"VNAM{i+1}", ord(c), name_row, 145+i)
        name_edit.textChanged.connect(on_name_changed)
        self.table.setCellWidget(name_row, 0, name_edit)
        self.table.setSpan(name_row, 0, 1, self.op_count)
        # Set row heights
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, 22)
    def _get_param_value(self, key):
        # Support both global and operator params
        if key.startswith("OP") and "_" in key:
            op_idx = int(key[2]) - 1
            op_key = key.split("_", 1)[1]
            return self.params["operators"][op_idx].get(op_key)
        return self.params.get(key)

    def send_sysex(self, key=None, value=None, param_num=None):
        # Send a DX7 Parameter Change SysEx message for the edited parameter
        # For operator params, send Operator Select first (0x15), then the param change
        if param_num is not None and value is not None:
            ch = self.channel_combo.currentIndex()  # 0-indexed for MIDI
            # Determine parameter group and parameter number for correct mapping
            if 0 <= param_num <= 155:
                # Voice parameter change (g=0)
                group = 0x00
                if param_num <= 127:
                    group_byte = group
                    param_byte = param_num
                else:
                    group_byte = group | 0x01  # set pp bits for 128-155
                    param_byte = param_num - 128
            elif 64 <= param_num <= 77:
                # Function parameter change (g=2)
                group = 0x20
                group_byte = group
                param_byte = param_num
            else:
                print(f"[VOICE EDITOR] Unsupported parameter number: {param_num}")
                return
            sysex = [0xF0, 0x43, 0x10 | (ch & 0x0F), group_byte, param_byte, int(value), 0xF7]
            if self.midi_outport:
                import mido
                msg = mido.Message('sysex', data=sysex[1:-1])
                print(f"Sending SysEx: {' '.join(f'{b:02X}' for b in sysex)} (MIDI channel {ch+1})")
                self.midi_outport.send(msg)
        else:
            print("[VOICE EDITOR] No valid parameter or mapping for SysEx.")

    def on_param_changed(self, key, value, row, param_num=None):
        if key.startswith("VNAM"):
            self.params[key] = value
        elif key.startswith("OP") and "_" in key:
            op_idx = int(key[2]) - 1
            op_key = key.split("_", 1)[1]
            self.params["operators"][op_idx][op_key] = value
        else:
            self.params[key] = value
        print_str = f"[VOICE EDITOR] Changed {key} to {value}"
        # Add parameter group and parameter number if param_num is provided
        if param_num is not None:
            if 0 <= param_num <= 155:
                group = 0  # voice
            elif 64 <= param_num <= 77:
                group = 2  # function
            else:
                group = '?'
            print_str += f" (group={group}, param={param_num})"
        print(print_str)
        self.send_sysex(key, value, param_num)

    def update_voice(self, midi_outport=None, voice_bytes=None):
        if midi_outport is not None:
            self.midi_outport = midi_outport
        if voice_bytes is not None:
            self.voice_bytes = voice_bytes
            self.decoder = SingleVoiceDumpDecoder(self.voice_bytes)
            self.decoder.decode()
            self.params = self.decoder.params
            self.populate_table()

    @classmethod
    def show_singleton(cls, parent=None, midi_outport=None, voice_bytes=None):
        dlg = cls.get_instance(parent)
        dlg.update_voice(midi_outport=midi_outport, voice_bytes=voice_bytes)
        dlg.setModal(False)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return dlg

    @classmethod
    def get_instance(cls, parent=None):
        if cls._instance is None or not cls._instance.isVisible():
            cls._instance = VoiceEditor(parent=parent)
            cls._instance.finished.connect(lambda: setattr(cls, "_instance", None))
        return cls._instance

    def init_patch_bytes(self):
        # Returns 161 bytes for an INIT patch (all params default, name 'INIT PATCH')
        data = [0xF0, 0x43, 0x00, 0x09, 0x20] + [0]*155 + [0xF7]
        # Set name to 'INIT PATCH'
        name = b'INIT PATCH'
        for i, c in enumerate(name):
            data[150 + i] = c
        return bytes(data)
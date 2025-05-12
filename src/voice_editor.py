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
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Parameter", "Value", "Edit"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(QLabel("<b>DX7 Voice Editor (VCED format)</b>"))
        layout.addWidget(self.table)
        self.populate_table()
        self.setLayout(layout)

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

    def populate_table(self):
        # Map all DX7 voice data to controls with correct ranges, including voice name
        param_info = []
        # Operator parameters (OP1..OP6, 21 params each)
        op_params = [
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
        for op in range(6):
            for i, (label, key, min_val, max_val) in enumerate(op_params):
                param_num = op * 21 + i
                param_info.append((f"OP{op+1} {label}", f"OP{op+1}_{key}", min_val, max_val, param_num))
        # Pitch EG (parameters 126-133)
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
        param_info.extend(peg_params)
        # Global parameters (DX7 parameter change numbers, not VCED offsets)
        # See Yamaha DX7 MIDI Data Format documentation
        # https://github.com/jdkoftinoff/jdksysex/blob/master/doc/DX7_sysex_format.txt
        global_params = [
            ("PITCH MOD SENSITIVITY", "LPMS", 0, 7, 0x00),
            ("TRANSPOSE", "TRNP", 0, 48, 0x01),
            ("VOICE NAME CHAR 1", "VNAM1", 32, 127, 0x02),
            ("VOICE NAME CHAR 2", "VNAM2", 32, 127, 0x03),
            ("VOICE NAME CHAR 3", "VNAM3", 32, 127, 0x04),
            ("VOICE NAME CHAR 4", "VNAM4", 32, 127, 0x05),
            ("VOICE NAME CHAR 5", "VNAM5", 32, 127, 0x06),
            ("VOICE NAME CHAR 6", "VNAM6", 32, 127, 0x07),
            ("VOICE NAME CHAR 7", "VNAM7", 32, 127, 0x08),
            ("VOICE NAME CHAR 8", "VNAM8", 32, 127, 0x09),
            ("VOICE NAME CHAR 9", "VNAM9", 32, 127, 0x0A),
            ("VOICE NAME CHAR 10", "VNAM10", 32, 127, 0x0B),
            ("ALGORITHM SELECTOR", "ALS", 0, 31, 0x1B),
            ("FEEDBACK LEVEL", "FBL", 0, 7, 0x1C),
            ("OSCILLATOR KEY SYNC", "OPI", 0, 1, 0x1D),
            ("LFO SPEED", "LFS", 0, 99, 0x1E),
            ("LFO DELAY TIME", "LFD", 0, 99, 0x1F),
            ("LFO PITCH MOD DEPTH", "LPMD", 0, 99, 0x20),
            ("LFO AMP MOD DEPTH", "LAMD", 0, 99, 0x21),
            ("LFO KEY SYNC", "LFKS", 0, 1, 0x22),
            ("LFO WAVE", "LFW", 0, 5, 0x23),
        ]
        param_info.extend(global_params)
        self.table.setRowCount(len(param_info))
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Parameter", "Edit"])
        for row, (full_name, key, min_val, max_val, param_num) in enumerate(param_info):
            item_name = QTableWidgetItem(full_name)
            item_name.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 0, item_name)
            if key.startswith("VNAM"):
                le = QLineEdit()
                # Set ASCII char if present, else blank
                v = self._get_param_value(key)
                le.setMaxLength(1)
                le.setText(chr(v) if v and 32 <= v <= 127 else "")
                le.textChanged.connect(lambda val, k=key, r=row, p=param_num: self.on_param_changed(k, ord(val) if val else 32, r, p))
                self.table.setCellWidget(row, 1, le)
            else:
                spin = QSpinBox()
                spin.setMinimum(min_val)
                spin.setMaximum(max_val)
                value = self._get_param_value(key)
                spin.setValue(int(value) if value is not None else min_val)
                spin.valueChanged.connect(lambda val, k=key, p=param_num, r=row: self.on_param_changed(k, val, r, p))
                self.table.setCellWidget(row, 1, spin)

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
            # Check if this is an operator parameter
            if key.startswith("OP") and "_" in key:
                op_idx = int(key[2]) - 1  # 0-based operator index
                # Send Operator Select: F0 43 1n 01 15 oo F7 (oo = 0 for OP1, ... 5 for OP6)
                op_select_sysex = [0xF0, 0x43, 0x10 | (ch & 0x0F), 0x01, 0x15, op_idx, 0xF7]
                if self.midi_outport:
                    import mido
                    msg = mido.Message('sysex', data=op_select_sysex[1:-1])
                    print(f"Sending SysEx (Operator Select): {' '.join(f'{b:02X}' for b in op_select_sysex)} (MIDI channel {ch+1})")
                    self.midi_outport.send(msg)
            # Now send the actual parameter change
            sysex = [0xF0, 0x43, 0x10 | (ch & 0x0F), 0x01, param_num, int(value), 0xF7]
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
        print(f"[VOICE EDITOR] Changed {key} to {value}")
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
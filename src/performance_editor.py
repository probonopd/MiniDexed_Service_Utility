from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QLineEdit, QPushButton, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from single_voice_dump_decoder import SingleVoiceDumpDecoder

PERFORMANCE_FIELDS = [
    "MIDIChannel", "Voice", "Volume", "Pan", "Detune", "Cutoff", "Resonance", "NoteLimitLow", "NoteLimitHigh", "ReverbSend"
]
TG_LABELS = [f"TG{i+1}" for i in range(8)]

# Hardcoded initial values as per user request
PERFORMANCE_VALUES = [
    ["" for _ in range(8)] for _ in PERFORMANCE_FIELDS
]

PERFORMANCE_FIELD_RANGES = {
    "MIDIChannel": (1, 16),
    "Volume": (0, 127),
    "Pan": (0, 127),
    "Detune": (-64, 63),
    "Cutoff": (0, 127),
    "Resonance": (0, 127),
    "NoteLimitLow": (0, 127),
    "NoteLimitHigh": (0, 127),
    "ReverbSend": (0, 127),
}

class PerformanceEditor(QDialog):
    def __init__(self, main_window=None):
        super().__init__(main_window)
        self.setWindowTitle("Performance Editor")
        self.setMinimumWidth(800)
        self.resize(800, self.sizeHint().height())
        row_height = 32
        header_height = 40
        total_height = header_height + row_height * len(PERFORMANCE_FIELDS)
        self.setMinimumHeight(total_height)
        self.resize(800, total_height)
        layout = QVBoxLayout(self)
        # Add red warning label above the table
        warning = QLabel("<span style='color: red;'>Work in progress, not all fields can be read/written via SysEx yet</span>")
        layout.addWidget(warning)
        self.table = QTableWidget(len(PERFORMANCE_FIELDS), 8, self)
        self.table.setHorizontalHeaderLabels(TG_LABELS)
        self.table.setVerticalHeaderLabels(PERFORMANCE_FIELDS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._block_signal = False
        # Fill table with initial values
        for row, field in enumerate(PERFORMANCE_FIELDS):
            for col in range(8):
                value = PERFORMANCE_VALUES[row][col]
                # Make all lines from Detune downwards read-only
                if PERFORMANCE_FIELDS.index("Detune") <= row:
                    item = QTableWidgetItem(str(value))
                    item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                    self.table.setItem(row, col, item)
                elif field == "Voice":
                    btn = QPushButton(str(value))
                    btn.clicked.connect(lambda checked, r=row, c=col: self.select_voice_dialog(r, c))
                    self.table.setCellWidget(row, col, btn)
                elif field in PERFORMANCE_FIELD_RANGES:
                    min_val, max_val = PERFORMANCE_FIELD_RANGES[field]
                    spin = QSpinBox()
                    spin.setMinimum(min_val)
                    spin.setMaximum(max_val)
                    if value != "":
                        spin.setValue(int(value))
                    spin.valueChanged.connect(lambda val, r=row, c=col: self.on_spin_changed(r, c, val))
                    self.table.setCellWidget(row, col, spin)
                else:
                    item = QTableWidgetItem(str(value))
                    item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, col, item)
        self.table.cellChanged.connect(self.on_cell_changed)
        layout.addWidget(self.table)
        # Add buttons for quick MIDI channel assignment
        from PyQt6.QtWidgets import QHBoxLayout
        btn_layout = QHBoxLayout()
        btn_tg_to_ch = QPushButton("Set TG1-8 to MIDI Channel 1-8")
        btn_all_to_ch1 = QPushButton("Set all TGs to MIDI Channel 1")
        btn_layout.addWidget(btn_tg_to_ch)
        btn_layout.addWidget(btn_all_to_ch1)
        layout.addLayout(btn_layout)
        btn_tg_to_ch.clicked.connect(self.set_tg_to_channels)
        btn_all_to_ch1.clicked.connect(self.set_all_tg_to_ch1)
        self.main_window = main_window

    def select_voice_dialog(self, row, col):
        from voice_browser import VoiceBrowser
        dlg = VoiceBrowser(self)
        # Preselect channel in VoiceBrowser to match the MIDIChannel for this TG
        midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
        channel_widget = self.table.cellWidget(midi_channel_row, col)
        if isinstance(channel_widget, QSpinBox):
            channel_value = channel_widget.value()
            # VoiceBrowser channels are 1-based, combo index 0-15, last is 'Omni'
            if 1 <= channel_value <= 16:
                dlg.channel_combo.setCurrentIndex(channel_value - 1)
        dlg.setModal(True)
        def on_voice_selected():
            idx = dlg.list_widget.currentRow()
            if idx >= 0 and idx < len(dlg.filtered_voices):
                voice = dlg.filtered_voices[idx]
                name = voice['name']
                btn = self.table.cellWidget(row, col)
                if isinstance(btn, QPushButton):
                    btn.setText(name)
                # Optionally: send MIDI for new voice selection here
        dlg.list_widget.itemDoubleClicked.connect(lambda _: (on_voice_selected(), dlg.accept()))
        if dlg.exec():
            on_voice_selected()

    def on_spin_changed(self, row, col, value):
        self._block_signal = True
        # Update the QTableWidgetItem if present (for consistency)
        if self.table.item(row, col):
            self.table.item(row, col).setText(str(value))
        self._block_signal = False
        field = PERFORMANCE_FIELDS[row]
        self.send_midi_for_field(field, col, value)

    def on_cell_changed(self, row, col):
        if self._block_signal:
            return
        field = PERFORMANCE_FIELDS[row]
        value = self.table.item(row, col).text()
        if field in PERFORMANCE_FIELD_RANGES:
            # If a spinbox exists, ignore cell edit (spinbox handles it)
            return
        if self.main_window and hasattr(self.main_window, "midi_handler"):
            self.send_midi_for_field(field, col, value)

    def send_midi_for_field(self, field, tg_index, value):
        try:
            if field == "MIDIChannel":
                # Clamp values to valid MIDI data byte range
                device = max(0, min(7, tg_index))  # TG index 0-7
                midi_ch = int(value)
                midi_ch = max(1, min(16, midi_ch)) - 1  # Clamp to 0-15
                sysex = [0xF0, 0x43, 0x10 + device, 0x04, 0x01, midi_ch, 0xF7]
                # Ensure all data bytes except 0xF0 and 0xF7 are in 0..127
                for b in sysex[1:-1]:
                    if not (0 <= b <= 127):
                        raise ValueError(f"SysEx data byte out of range: {b}")
                if self.main_window and hasattr(self.main_window, "midi_handler"):
                    self.main_window.midi_handler.send_sysex(sysex)
                return
            # ...existing code for Volume, Pan, etc...
            channel = tg_index  # 0-based MIDI channel
            if field == "Volume":
                cc = 7
                val = int(value)
                self.main_window.midi_handler.send_cc(channel, cc, val)
            elif field == "Pan":
                cc = 10
                val = int(value)
                self.main_window.midi_handler.send_cc(channel, cc, val)
            # ...add more mappings as needed...
        except Exception as e:
            print(f"Failed to send MIDI for {field} TG{tg_index+1}: {e}")

    def set_tg_to_channels(self):
        midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
        for col in range(8):
            widget = self.table.cellWidget(midi_channel_row, col)
            if isinstance(widget, QSpinBox):
                widget.setValue(col + 1)
            # Send SysEx for each TG
            self.send_midi_for_field("MIDIChannel", col, col + 1)

    def set_all_tg_to_ch1(self):
        midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
        for col in range(8):
            widget = self.table.cellWidget(midi_channel_row, col)
            if isinstance(widget, QSpinBox):
                widget.setValue(1)
            # Send SysEx for each TG
            self.send_midi_for_field("MIDIChannel", col, 1)

    def showEvent(self, event):
        super().showEvent(event)
        # Set TG1-8 to MIDI Channel 1-8
        self.set_tg_to_channels()
        # Request a voice dump for each TG (device 0-7)
        if self.main_window and hasattr(self.main_window, "midi_handler"):
            for tg in range(8):
                sysex = [0xF0, 0x43, 0x20 + tg, 0x00, 0xF7]  # F0 43 2n 00 F7
                self.main_window.midi_handler.send_sysex(sysex)
        # Prepare to receive and parse voice dumps
        if self.main_window and hasattr(self.main_window, "midi_handler"):
            if hasattr(self.main_window, "receive_worker") and self.main_window.receive_worker:
                self.main_window.receive_worker.sysex_received.connect(self._on_voice_dump)
        self._pending_voice_dumps = set(range(8))
        self._voice_dump_data = {}

    def _on_voice_dump(self, data):
        print(f"[PERF EDITOR] _on_voice_dump called with data: {data}")
        print(f"[PERF EDITOR] Data length: {len(data) if data else 'None'}")
        if not data or len(data) < 155:
            print(f"[PERF EDITOR] Early return: data is None or too short")
            return
        print(f"[PERF EDITOR] Data[0]: {data[0]:02X}")
        if data[0] != 0x43:
            print(f"[PERF EDITOR] Early return: data[0] != 0x43")
            return
        tg = None
        if 0x20 <= data[1] <= 0x27:
            tg = data[1] - 0x20
            print(f"[PERF EDITOR] TG index determined from data[1] (0x20..0x27): {tg}")
        elif 0x00 <= data[1] <= 0x07:
            tg = data[1]
            print(f"[PERF EDITOR] TG index determined from data[1] (0x00..0x07): {tg}")
        else:
            print(f"[PERF EDITOR] Early return: data[1] not in 0x00..0x07 or 0x20..0x27, data[1]={data[1]:02X}")
            return
        decoder = SingleVoiceDumpDecoder(data)
        if not decoder.is_valid():
            print(f"[PERF EDITOR] Decoder did not validate the data.")
            return
        # Map fields to decoder param keys (VCED spec)
        field_param_map = {
            "Voice": "VNAM",
            "Algorithm": "ALS",
            "Feedback": "FBL",
            "Transpose": "TRNP",
            "Detune": None,
            "Volume": None,
            "Pan": None,
            "Cutoff": None,
            "Resonance": None,
            "NoteLimitLow": None,
            "NoteLimitHigh": None,
            "ReverbSend": None,
        }
        for row, field in enumerate(PERFORMANCE_FIELDS):
            if field == "MIDIChannel":
                continue  # Do not overwrite MIDI Channel
            param_key = field_param_map.get(field)
            value = ""
            if isinstance(param_key, str):
                value = decoder.get_param(param_key)
            elif isinstance(param_key, tuple) and param_key[0] == "operators":
                # Show OPn's value in TGn (col==tg)
                op_index = tg if tg < 6 else 0  # Only 6 ops, fallback to OP1
                op_list = decoder.get_param("operators")
                if op_list and 0 <= op_index < len(op_list):
                    value = op_list[op_index].get(param_key[1], "")
            # Set value in table
            if field == "Voice":
                btn = self.table.cellWidget(row, tg)
                if isinstance(btn, QPushButton):
                    btn.setText(str(value))
            elif field in PERFORMANCE_FIELD_RANGES:
                widget = self.table.cellWidget(row, tg)
                if isinstance(widget, QSpinBox):
                    if value != "" and value is not None:
                        try:
                            widget.setValue(int(value))
                        except Exception:
                            widget.setValue(widget.minimum())
                    else:
                        widget.clear()
            else:
                item = self.table.item(row, tg)
                if item:
                    item.setText(str(value))
        self._pending_voice_dumps.discard(tg)
        self._voice_dump_data[tg] = data
        if not self._pending_voice_dumps:
            print(f"[PERF EDITOR] All pending voice dumps received, disconnecting signal.")
            if self.main_window and hasattr(self.main_window, "midi_handler"):
                if hasattr(self.main_window, "receive_worker") and self.main_window.receive_worker:
                    try:
                        self.main_window.receive_worker.sysex_received.disconnect(self._on_voice_dump)
                    except Exception as e:
                        print(f"[PERF EDITOR] Exception disconnecting signal: {e}")

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QLineEdit, QPushButton, QLabel, QCheckBox, QScrollArea, QHBoxLayout, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from single_voice_dump_decoder import SingleVoiceDumpDecoder
import sys
import logging
from voice_browser import VoiceBrowser

# Define global and TG-specific fields explicitly in the order they should appear
# Add a new Voice field at the top of TG_FIELDS
TG_FIELDS = [
    "Voice",  # New field for voice name/button
    "MIDIChannel", "BankNumber", "VoiceNumber", "Volume", "Pan", "Detune", "Cutoff", "Resonance", "NoteLimitLow", "NoteLimitHigh", "NoteShift", "ReverbSend", "PitchBendRange", "PitchBendStep", "PortamentoMode", "PortamentoGlissando", "PortamentoTime", "MonoMode", "ModulationWheelRange", "ModulationWheelTarget", "FootControlRange", "FootControlTarget", "BreathControlRange", "BreathControlTarget", "AftertouchRange", "AftertouchTarget"
]
GLOBAL_FIELDS = [
    "CompressorEnable", "ReverbEnable", "ReverbSize", "ReverbHighDamp", "ReverbLowDamp", "ReverbLowPass", "ReverbDiffusion", "ReverbLevel"
]
PERFORMANCE_FIELDS = TG_FIELDS + GLOBAL_FIELDS

# Hardcoded initial values as per user request
PERFORMANCE_VALUES = [
    ["" for _ in range(8)] for _ in PERFORMANCE_FIELDS
]

PERFORMANCE_FIELD_RANGES = {
    "CompressorEnable": (0, 1),
    "ReverbEnable": (0, 1),
    "ReverbSize": (0, 99),
    "ReverbHighDamp": (0, 99),
    "ReverbLowDamp": (0, 99),
    "ReverbLowPass": (0, 99),
    "ReverbDiffusion": (0, 99),
    "ReverbLevel": (0, 99),
    "BankNumber": (0, 127),
    "VoiceNumber": (0, 31),
    "MIDIChannel": (0, 17),
    "Volume": (0, 127),
    "Pan": (0, 127),
    "Detune": (-99, 99),
    "Cutoff": (0, 127),
    "Resonance": (0, 127),
    "NoteLimitLow": (0, 127),
    "NoteLimitHigh": (0, 127),
    "NoteShift": (-24, 24),
    "ReverbSend": (0, 127),
    "PitchBendRange": (0, 12),
    "PitchBendStep": (0, 12),
    "PortamentoMode": (0, 1),
    "PortamentoGlissando": (0, 1),
    "PortamentoTime": (0, 99),
    "MonoMode": (0, 1),
    "ModulationWheelRange": (0, 127),
    "ModulationWheelTarget": (0, 127),
    "FootControlRange": (0, 127),
    "FootControlTarget": (0, 127),
    "BreathControlRange": (0, 127),
    "BreathControlTarget": (0, 127),
    "AftertouchRange": (0, 127),
    "AftertouchTarget": (0, 127)
}

TG_LABELS = [f"TG{i+1}" for i in range(8)]

class PerformanceEditor(QDialog):
    def __init__(self, main_window=None):
        super().__init__(main_window)
        self.setWindowTitle("Performance Editor")
        self.setMinimumWidth(800)
        self.resize(800, self.sizeHint().height())
        row_height = 32
        header_height = 40
        total_height = header_height + row_height * len(PERFORMANCE_FIELDS)
        self.setMinimumHeight(min(total_height, 600))
        self.resize(800, min(total_height, 600))
        layout = QVBoxLayout(self)
        # Add red warning label above the table
        warning = QLabel("<span style='color: red;'>Work in progress, only works with firmware from  https://github.com/probonopd/MiniDexed/pull/915</span>")
        layout.addWidget(warning)
        self.table = QTableWidget(len(PERFORMANCE_FIELDS), 8, self)
        self.table.setHorizontalHeaderLabels(TG_LABELS)
        self.table.setVerticalHeaderLabels(PERFORMANCE_FIELDS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._block_signal = False
        # Fill table with initial values
        for row, field in enumerate(PERFORMANCE_FIELDS):
            if field in GLOBAL_FIELDS:
                # Place controls for global fields in the last rows, spanning all columns
                value = PERFORMANCE_VALUES[row][0]
                min_val, max_val = PERFORMANCE_FIELD_RANGES.get(field, (0, 127))
                if min_val == 0 and max_val == 1:
                    cb = QCheckBox()
                    cb.setChecked(str(value) == "1")
                    cb.stateChanged.connect(lambda state, r=row: self.on_spin_changed(r, 0, int(state == 2)))
                    cb.toggled.connect(lambda checked, r=row: self.on_spin_changed(r, 0, int(checked)))
                    self.table.setCellWidget(row, 0, cb)
                else:
                    spin = QSpinBox()
                    spin.setMinimum(min_val)
                    spin.setMaximum(max_val)
                    if value != "":
                        spin.setValue(int(value))
                    spin.valueChanged.connect(lambda val, r=row: self.on_spin_changed(r, 0, val))
                    self.table.setCellWidget(row, 0, spin)
                self.table.setSpan(row, 0, 1, 8)
            else:
                for col in range(8):
                    value = PERFORMANCE_VALUES[row][col]
                    if field == "Voice":
                        btn = QPushButton(str(value))
                        btn.clicked.connect(lambda checked, r=row, c=col: self.select_voice_dialog(r, c))
                        self.table.setCellWidget(row, col, btn)
                    elif field in PERFORMANCE_FIELD_RANGES:
                        min_val, max_val = PERFORMANCE_FIELD_RANGES[field]
                        if min_val == 0 and max_val == 1:
                            cb = QCheckBox()
                            cb.setChecked(str(value) == "1")
                            cb.stateChanged.connect(lambda state, r=row, c=col: self.on_spin_changed(r, c, int(state == 2)))
                            cb.toggled.connect(lambda checked, r=row, c=col: self.on_spin_changed(r, c, int(checked)))
                            self.table.setCellWidget(row, col, cb)
                        else:
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
        # Make the spreadsheet scrollable and only show the table inside the scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.table)
        layout.addWidget(scroll)
        # Remove the direct layout.addWidget(self.table) above
        # Add buttons for quick MIDI channel assignment
        btn_layout = QHBoxLayout()
        btn_tg_to_ch = QPushButton("Set TG1-8 to MIDI Channel 1-8")
        btn_all_to_ch1 = QPushButton("Set all TGs to MIDI Channel 1")
        btn_layout.addWidget(btn_tg_to_ch)
        btn_layout.addWidget(btn_all_to_ch1)
        layout.addLayout(btn_layout)
        btn_tg_to_ch.clicked.connect(self.set_tg_to_channels)
        btn_all_to_ch1.clicked.connect(self.set_all_tg_to_ch1)
        self.main_window = main_window
        # Move initialization logic from showEvent here
        app = QApplication.instance()
        if app:
            app.setOverrideCursor(Qt.CursorShape.BusyCursor)
        self.setEnabled(False)
        self.hide()  # Hide until data is loaded
        self._sysex_data_buffer = {}
        self._expected_sysex_count = 9  # 1 global + 8 TGs
        self._sysex_request_queue = [[0xF0, 0x7D, 0x10, 0xF7]] + [[0xF0, 0x7D, 0x11, tg, 0xF7] for tg in range(8)]
        self._sysex_request_index = 0
        # Only connect handler once
        if self.main_window and hasattr(self.main_window, "midi_handler"):
            if hasattr(self.main_window, "receive_worker") and self.main_window.receive_worker:
                try:
                    self.main_window.receive_worker.sysex_received.disconnect(self._on_performance_sysex)
                except Exception:
                    pass
                self.main_window.receive_worker.sysex_received.connect(self._on_performance_sysex)
        self._send_next_sysex_request()
        logging.basicConfig(level=logging.DEBUG)
        self._debug = True

    def select_voice_dialog(self, row, col):
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
        if self._block_signal:
            logging.debug(f"[on_spin_changed] Blocked: row={row}, col={col}, value={value}")
            return
        logging.debug(f"[on_spin_changed] row={row}, col={col}, value={value}, field={PERFORMANCE_FIELDS[row]}")
        # Update the QTableWidgetItem if present (for consistency)
        if self.table.item(row, col):
            self.table.item(row, col).setText(str(value))
        field = PERFORMANCE_FIELDS[row]
        self.send_midi_for_field(field, col, value)

    def on_cell_changed(self, row, col):
        if self._block_signal:
            logging.debug(f"[on_cell_changed] Blocked: row={row}, col={col}")
            return
        field = PERFORMANCE_FIELDS[row]
        value = self.table.item(row, col).text()
        logging.debug(f"[on_cell_changed] row={row}, col={col}, value={value}, field={field}")
        self.send_midi_for_field(field, col, value)

    def send_midi_for_field(self, field, tg_index, value):
        logging.debug(f"[send_midi_for_field] field={field}, tg_index={tg_index}, value={value}")
        try:
            # MiniDexed SysEx mapping for all fields in PERFORMANCE_FIELDS
            field_to_param = {
                "CompressorEnable": (0x00, 0x00),
                "ReverbEnable": (0x00, 0x01),
                "ReverbSize": (0x00, 0x02),
                "ReverbHighDamp": (0x00, 0x03),
                "ReverbLowDamp": (0x00, 0x04),
                "ReverbLowPass": (0x00, 0x05),
                "ReverbDiffusion": (0x00, 0x06),
                "ReverbLevel": (0x00, 0x07),
                "BankNumber": (0x00, 0x00),
                "VoiceNumber": (0x00, 0x01),
                "MIDIChannel": (0x00, 0x02),
                "Volume": (0x00, 0x03),
                "Pan": (0x00, 0x04),
                "Detune": (0x00, 0x05),
                "Cutoff": (0x00, 0x06),
                "Resonance": (0x00, 0x07),
                "NoteLimitLow": (0x00, 0x08),
                "NoteLimitHigh": (0x00, 0x09),
                "NoteShift": (0x00, 0x0A),
                "ReverbSend": (0x00, 0x0B),
                "PitchBendRange": (0x00, 0x0C),
                "PitchBendStep": (0x00, 0x0D),
                "PortamentoMode": (0x00, 0x0E),
                "PortamentoGlissando": (0x00, 0x0F),
                "PortamentoTime": (0x00, 0x10),
                "MonoMode": (0x00, 0x11),
                "ModulationWheelRange": (0x00, 0x12),
                "ModulationWheelTarget": (0x00, 0x13),
                "FootControlRange": (0x00, 0x14),
                "FootControlTarget": (0x00, 0x15),
                "BreathControlRange": (0x00, 0x16),
                "BreathControlTarget": (0x00, 0x17),
                "AftertouchRange": (0x00, 0x18),
                "AftertouchTarget": (0x00, 0x19),
            }
            if field in field_to_param:
                pp1, pp2 = field_to_param[field]
                min_val, max_val = PERFORMANCE_FIELD_RANGES.get(field, (0, 127))
                v = int(value)
                v = max(min_val, min(max_val, v))
                # For signed fields, use 2's complement split into two 7-bit bytes
                if field in ["Detune", "NoteShift"]:
                    v = int(value)
                    # Clamp to allowed range
                    min_val, max_val = PERFORMANCE_FIELD_RANGES.get(field, (-99, 99) if field == "Detune" else (-24, 24))
                    v = max(min_val, min(max_val, v))
                    if v < 0:
                        v = (1 << 14) + v  # 2's complement for 14 bits
                    vv1 = (v >> 7) & 0x7F
                    vv2 = v & 0x7F
                else:
                    vv1 = (v >> 8) & 0x7F
                    vv2 = v & 0x7F
                if field in ["CompressorEnable", "ReverbEnable", "ReverbSize", "ReverbHighDamp", "ReverbLowDamp", "ReverbLowPass", "ReverbDiffusion", "ReverbLevel"]:
                    # Global set
                    sysex = [0xF0, 0x7D, 0x20, pp1, pp2, vv1, vv2, 0xF7]
                else:
                    # TG set
                    sysex = [0xF0, 0x7D, 0x21, tg_index, pp1, pp2, vv1, vv2, 0xF7]
                if self.main_window and hasattr(self.main_window, "midi_handler"):
                    self.main_window.midi_handler.send_sysex(sysex)
                return
        except Exception as e:
            print(f"Failed to send MIDI for {field} TG{tg_index+1}: {e}", file=sys.stderr)

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
        # Send voice dump requests for each TG (0-7) using the MIDI channel assigned to each TG
        if self.main_window and hasattr(self.main_window, "midi_handler"):
            midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
            for tg in range(8):
                channel_widget = self.table.cellWidget(midi_channel_row, tg)
                if isinstance(channel_widget, QSpinBox):
                    midi_channel = channel_widget.value()
                    # If MIDI channel > 15, use channel 0
                    if midi_channel > 15:
                        midi_channel = 0
                    sysex = [0xF0, 0x43, 0x10 | ((midi_channel) & 0x0F), 0x00, 0xF7]
                    self.main_window.midi_handler.send_sysex(sysex)
        # Prepare to receive and parse voice dumps
        if self.main_window and hasattr(self.main_window, "midi_handler"):
            if hasattr(self.main_window, "receive_worker") and self.main_window.receive_worker:
                self.main_window.receive_worker.sysex_received.connect(self._on_voice_dump)
        self._pending_voice_dumps = set(range(8))
        self._voice_dump_data = {}

    def _send_next_sysex_request(self):
        if self._sysex_request_index < len(self._sysex_request_queue):
            msg = self._sysex_request_queue[self._sysex_request_index]
            self._sysex_request_index += 1
            if self.main_window and hasattr(self.main_window, "midi_handler"):
                self.main_window.midi_handler.send_sysex(msg)

    def _on_performance_sysex(self, data):
        try:
            print(f"[PERF EDITOR DEBUG] Raw incoming SysEx: {' '.join(f'{b:02X}' for b in data)}")
            if isinstance(data, bytes):
                data = list(data)
            print(f"[PERF EDITOR DEBUG] Parsed as list: {' '.join(f'{b:02X}' for b in data)}")
            if data and data[0] == 0xF0:
                data = data[1:]
            if data and data[-1] == 0xF7:
                data = data[:-1]
            print(f"[PERF EDITOR DEBUG] Stripped F0/F7: {' '.join(f'{b:02X}' for b in data)}")
            if not data or data[0] != 0x7D:
                print(f"[PERF EDITOR DEBUG] Not a MiniDexed SysEx dump (missing 0x7D): {' '.join(f'{b:02X}' for b in data)}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "SysEx Error", "Received invalid or unrecognized SysEx data. Aborting Performance Editor.")
                self._sysex_request_queue = []
                self._sysex_request_index = 9999
                self.reject()
                return
            # Global response: F0 7D 20 ... F7
            if len(data) > 2 and data[1] == 0x20:
                print(f"[PERF EDITOR DEBUG] Parsed as global response: {' '.join(f'{b:02X}' for b in data)}")
                self._sysex_data_buffer['global'] = data.copy()
            # TG response: F0 7D 21 nn ... F7 (device sends 7D 21 nn ...)
            elif len(data) > 3 and data[1] == 0x21:
                tg = data[2]
                print(f"[PERF EDITOR DEBUG] Parsed as TG response for TG {tg}: {' '.join(f'{b:02X}' for b in data)}")
                self._sysex_data_buffer[tg] = data.copy()
            else:
                print(f"[PERF EDITOR DEBUG] Unrecognized MiniDexed SysEx format: {' '.join(f'{b:02X}' for b in data)}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "SysEx Error", "Received invalid or unrecognized SysEx data. Aborting Performance Editor.")
                self._sysex_request_queue = []
                self._sysex_request_index = 9999
                self.reject()
                return
            print(f"[PERF EDITOR DEBUG] Buffer state: {self._sysex_data_buffer}")
            # When all expected responses are received, show window
            if len(self._sysex_data_buffer) >= self._expected_sysex_count:
                if self.main_window and hasattr(self.main_window, "receive_worker") and self.main_window.receive_worker:
                    try:
                        self.main_window.receive_worker.sysex_received.disconnect(self._on_performance_sysex)
                    except Exception:
                        pass
                print(f"[PERF EDITOR DEBUG] All expected responses received. Populating fields.")
                self._populate_fields_from_sysex()
                # --- BEGIN: Send voice dump requests for each TG and connect handler ---
                if self.main_window and hasattr(self.main_window, "midi_handler"):
                    for tg in range(8):
                        sysex = [0xF0, 0x43, 0x20 + tg, 0x00, 0xF7]  # F0 43 2n 00 F7
                        self.main_window.midi_handler.send_sysex(sysex)
                if self.main_window and hasattr(self.main_window, "midi_handler"):
                    if hasattr(self.main_window, "receive_worker") and self.main_window.receive_worker:
                        self.main_window.receive_worker.sysex_received.connect(self._on_voice_dump)
                self._pending_voice_dumps = set(range(8))
                self._voice_dump_data = {}
                # --- END: Send voice dump requests for each TG and connect handler ---
                app = QApplication.instance()
                if app:
                    app.restoreOverrideCursor()
                self.setEnabled(True)
                self.show()
                QApplication.processEvents()
            else:
                self._send_next_sysex_request()
        except Exception as e:
            print(f"[PERF EDITOR] Exception in _on_performance_sysex: {e}", file=sys.stderr)

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
        # Only update the Voice button text
        voice_row = PERFORMANCE_FIELDS.index("Voice")
        voice_name = decoder.get_param("VNAM")
        btn = self.table.cellWidget(voice_row, tg)
        if isinstance(btn, QPushButton):
            btn.setText(str(voice_name))
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

    def _populate_fields_from_sysex(self):
        # Populate global parameters (first 8 fields, column 0)
        global_data = self._sysex_data_buffer.get('global')
        if global_data and len(global_data) > 3 and global_data[1] == 0x20:
            i = 2  # skip 0x7D, 0x20
            while i + 3 < len(global_data):
                pp1, pp2, vv1, vv2 = global_data[i], global_data[i+1], global_data[i+2], global_data[i+3]
                # Map param to field name
                param_map = {
                    (0x00, 0x00): "CompressorEnable",
                    (0x00, 0x01): "ReverbEnable",
                    (0x00, 0x02): "ReverbSize",
                    (0x00, 0x03): "ReverbHighDamp",
                    (0x00, 0x04): "ReverbLowDamp",
                    (0x00, 0x05): "ReverbLowPass",
                    (0x00, 0x06): "ReverbDiffusion",
                    (0x00, 0x07): "ReverbLevel",
                }
                field = param_map.get((pp1, pp2))
                if field and field in PERFORMANCE_FIELDS:
                    row = PERFORMANCE_FIELDS.index(field)
                    val = (vv1 << 8) | vv2
                    widget = self.table.cellWidget(row, 0)
                    if hasattr(widget, 'setChecked'):
                        self._block_signal = True
                        widget.setChecked(val == 1)
                        self._block_signal = False
                    elif isinstance(widget, QSpinBox):
                        self._block_signal = True
                        widget.setValue(val)
                        self._block_signal = False
                    else:
                        item = self.table.item(row, 0)
                        if item:
                            item.setText(str(val))
                i += 4

        # Populate TG parameters (fields 8+, columns 0-7)
        tg_param_map = {
            (0x00, 0x00): "BankNumber",
            (0x00, 0x01): "VoiceNumber",
            (0x00, 0x02): "MIDIChannel",
            (0x00, 0x03): "Volume",
            (0x00, 0x04): "Pan",
            (0x00, 0x05): "Detune",
            (0x00, 0x06): "Cutoff",
            (0x00, 0x07): "Resonance",
            (0x00, 0x08): "NoteLimitLow",
            (0x00, 0x09): "NoteLimitHigh",
            (0x00, 0x0A): "NoteShift",
            (0x00, 0x0B): "ReverbSend",
            (0x00, 0x0C): "PitchBendRange",
            (0x00, 0x0D): "PitchBendStep",
            (0x00, 0x0E): "PortamentoMode",
            (0x00, 0x0F): "PortamentoGlissando",
            (0x00, 0x10): "PortamentoTime",
            (0x00, 0x11): "MonoMode",
            (0x00, 0x12): "ModulationWheelRange",
            (0x00, 0x13): "ModulationWheelTarget",
            (0x00, 0x14): "FootControlRange",
            (0x00, 0x15): "FootControlTarget",
            (0x00, 0x16): "BreathControlRange",
            (0x00, 0x17): "BreathControlTarget",
            (0x00, 0x18): "AftertouchRange",
            (0x00, 0x19): "AftertouchTarget"
        }
        signed_fields = {"Detune", "NoteShift"}
        # When programmatically setting values, block signals only for the change, not for the whole loop
        for tg in range(8):
            tg_data = self._sysex_data_buffer.get(tg)
            if tg_data and len(tg_data) > 4 and tg_data[1] == 0x21:
                i = 3  # skip 0x7D, 0x21, tg
                while i + 3 < len(tg_data):
                    pp1, pp2, vv1, vv2 = tg_data[i], tg_data[i+1], tg_data[i+2], tg_data[i+3]
                    field = tg_param_map.get((pp1, pp2))
                    if field and field in PERFORMANCE_FIELDS:
                        row = PERFORMANCE_FIELDS.index(field)
                        if field in signed_fields:
                            val = (vv1 << 8) | vv2
                            if val >= 0x8000:
                                val -= 0x10000
                        else:
                            val = (vv1 << 8) | vv2
                        widget = self.table.cellWidget(row, tg)
                        # Only block signals for the duration of setValue/setChecked
                        if isinstance(widget, QSpinBox):
                            self._block_signal = True
                            try:
                                widget.setValue(int(val))
                            except Exception:
                                widget.setValue(widget.minimum())
                            self._block_signal = False
                        elif hasattr(widget, 'setChecked'):
                            self._block_signal = True
                            widget.setChecked(val == 1)
                            self._block_signal = False
                        elif isinstance(widget, QPushButton):
                            widget.setText(str(val))
                        else:
                            item = self.table.item(row, tg)
                            if item:
                                item.setText(str(val))
                    i += 4
        # After all programmatic changes, ensure _block_signal is False
        self._block_signal = False

    @staticmethod
    def open_when_ready(main_window):
        dlg = PerformanceEditor(main_window)
        # Do not show the dialog here!
        # It will show itself after all SysEx responses are received and fields are populated.
        return dlg

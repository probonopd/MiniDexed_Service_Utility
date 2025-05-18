import sys
import warnings
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QLineEdit, QPushButton, QLabel,
    QScrollArea, QHBoxLayout, QComboBox, QCheckBox, QWidget, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtCore import QTimer
from single_voice_dump_decoder import SingleVoiceDumpDecoder
from voice_editor import VoiceEditor
from voice_editor_panel import VoiceEditorPanelDialog
from singleton_dialog import SingletonDialog
from performance_fields import TG_FIELDS, GLOBAL_FIELDS, PERFORMANCE_FIELDS, PERFORMANCE_FIELD_RANGES, TG_LABELS
from voice_management import select_voice_dialog, open_voice_editor, on_voice_dump

# Initialize PERFORMANCE_VALUES with default values (0) for all fields and TGs
PERFORMANCE_VALUES = [
    [0 for _ in range(8)] for _ in range(len(PERFORMANCE_FIELDS))
]

class PerformanceEditor(SingletonDialog):
    _instance = None

    def __init__(self, parent=None, main_window=None):
        # If only one argument is passed and it's a MainWindow, treat it as main_window
        from main_window import MainWindow
        if main_window is None and parent is not None and hasattr(parent, 'midi_handler'):
            main_window = parent
            parent = None
        super().__init__(parent)
        self.setWindowTitle("Performance Editor")
        self.setModal(False)
        self.main_window = main_window
        self.resize(800, 950)
        layout = QVBoxLayout(self)
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
                    from PySide6.QtWidgets import QCheckBox
                    cb = QCheckBox()
                    # Set checked state based on value (treat '1', 1, True as checked)
                    cb.setChecked(str(value) == "1" or value is True)
                    cb.stateChanged.connect(lambda state, r=row: self.on_spin_changed(r, 0, int(state == 2)))
                    cb.toggled.connect(lambda checked, r=row: self.on_spin_changed(r, 0, int(checked)))
                    self.table.setCellWidget(row, 0, cb)
                else:
                    spin = QSpinBox()
                    spin.setMinimum(min_val)
                    spin.setMaximum(max_val)
                    try:
                        spin.setValue(int(value))
                    except Exception:
                        spin.setValue(min_val)
                    spin.valueChanged.connect(lambda val, r=row: self.on_spin_changed(r, 0, val))
                    self.table.setCellWidget(row, 0, spin)
                self.table.setSpan(row, 0, 1, 8)
            else:
                for col in range(8):
                    value = PERFORMANCE_VALUES[row][col]
                    if field == "Voice":
                        from PySide6.QtWidgets import QWidget, QHBoxLayout, QSizePolicy
                        cell_widget = QWidget()
                        h_layout = QHBoxLayout(cell_widget)
                        h_layout.setContentsMargins(0, 0, 0, 0)
                        h_layout.setSpacing(0)  # Remove spacing between widgets
                        btn = QPushButton(str(value))
                        btn.setObjectName(f"voice_btn_{col}")
                        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                        btn.clicked.connect(lambda checked, r=row, c=col: select_voice_dialog(self.table, self.main_window, r, c))
                        edit_btn = QPushButton("e")
                        edit_btn.setObjectName(f"edit_btn_{col}")
                        edit_btn.setFixedWidth(22)
                        edit_btn.setToolTip("Edit this voice")
                        edit_btn.clicked.connect(lambda checked, r=row, c=col: self.open_voice_editor(r, c))
                        h_layout.addWidget(btn)
                        h_layout.addWidget(edit_btn)
                        # No stretch, so buttons are flush
                        # Hide if MIDIChannel is Omni (on initial load)
                        midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
                        channel_widget = self.table.cellWidget(midi_channel_row, col)
                        if channel_widget is not None and channel_widget.metaObject().className() == "QComboBox":
                            if channel_widget.currentIndex() == 16:  # Omni
                                cell_widget.hide()
                            else:
                                cell_widget.show()
                        self.table.setCellWidget(row, col, cell_widget)
                    elif field in PERFORMANCE_FIELD_RANGES:
                        min_val, max_val = PERFORMANCE_FIELD_RANGES[field]
                        if field == "MIDIChannel":
                            from PySide6.QtWidgets import QComboBox
                            combo = QComboBox()
                            for i in range(1, 17):
                                combo.addItem(str(i))
                            combo.addItem("Omni")
                            # Set value
                            if value != "":
                                try:
                                    v = int(value)
                                    if v >= 16:
                                        combo.setCurrentIndex(16)  # Omni
                                    elif v > 0:
                                        combo.setCurrentIndex(v - 1)
                                    else:
                                        combo.setCurrentIndex(0)
                                except Exception:
                                    combo.setCurrentIndex(0)
                            def on_channel_changed(idx, r=row, c=col):
                                self.on_spin_changed(r, c, idx)
                                # Hide/show Voice button if present
                                voice_row = PERFORMANCE_FIELDS.index("Voice")
                                btn = self.table.cellWidget(voice_row, c)
                                if isinstance(btn, QPushButton):
                                    if idx == 16:
                                        btn.hide()
                                    else:
                                        btn.show()
                            combo.currentIndexChanged.connect(on_channel_changed)
                            self.table.setCellWidget(row, col, combo)
                        elif min_val == 0 and max_val == 1:
                            from PySide6.QtWidgets import QCheckBox
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
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.table)
        layout.addWidget(scroll)
        # Remove the direct layout.addWidget(self.table) above
        # Add buttons for quick MIDI channel assignment
        from PySide6.QtWidgets import QHBoxLayout
        btn_layout = QHBoxLayout()
        btn_tg_to_ch = QPushButton("Set TG1-8 to MIDI Channel 1-8")
        btn_all_to_ch1 = QPushButton("Set all TGs to MIDI Channel 1")
        btn_layout.addWidget(btn_tg_to_ch)
        btn_layout.addWidget(btn_all_to_ch1)
        layout.addLayout(btn_layout)
        btn_tg_to_ch.clicked.connect(self.set_tg_to_channels)
        btn_all_to_ch1.clicked.connect(self.set_all_tg_to_ch1)
        # Move initialization logic from showEvent here
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
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
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", category=RuntimeWarning)
                        self.main_window.receive_worker.sysex_received.disconnect(self._on_performance_sysex)
                except Exception:
                    pass
                self.main_window.receive_worker.sysex_received.connect(self._on_performance_sysex)
        self._send_next_sysex_request()
        import logging
        logging.basicConfig(level=logging.DEBUG)
        self._debug = True

    def on_spin_changed(self, row, col, value):
        if self._block_signal:
            return
        if self.table.item(row, col):
            self.table.item(row, col).setText(str(value))
        field = PERFORMANCE_FIELDS[row]
        self.send_midi_for_field(field, col, value)

    def on_cell_changed(self, row, col):
        if self._block_signal:
            return
        field = PERFORMANCE_FIELDS[row]
        value = self.table.item(row, col).text()
        self.send_midi_for_field(field, col, value)

    def send_midi_for_field(self, field, tg_index, value):

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
                # For MIDIChannel, use the value directly (0-15 for channels 1-16, 16 for Omni)
                if field == "MIDIChannel":
                    v = int(value)
                # For signed 14-bit fields, use standard MIDI mapping: value = signed + 8192 (center at 8192)
                if field in ["Detune", "NoteShift"]:
                    v = int(value)
                    # Clamp to allowed range
                    min_val, max_val = PERFORMANCE_FIELD_RANGES.get(field, (-99, 99) if field == "Detune" else (-24, 24))
                    v = max(min_val, min(max_val, v))
                    # MIDI standard: encode as unsigned with center at 8192
                    v = v + 8192
                    vv1 = (v >> 7) & 0x7F
                    vv2 = v & 0x7F
                else:
                    vv1 = (v >> 8) & 0x7F
                    vv2 = v & 0x7F
                if field in ["CompressorEnable", "ReverbEnable", "ReverbSize", "ReverbHighDamp", "ReverbLowDamp", "ReverbLowPass", "ReverbDiffusion", "ReverbLevel"]:
                    sysex = [0xF0, 0x7D, 0x20, pp1, pp2, vv1, vv2, 0xF7]
                else:
                    sysex = [0xF0, 0x7D, 0x21, tg_index, pp1, pp2, vv1, vv2, 0xF7]

                print(f"Sending SysEx: {' '.join(f'{b:02X}' for b in sysex)} (MIDI channel {tg_index+1})")
                if self.main_window and hasattr(self.main_window, "midi_handler"):
                    midi_handler = QApplication.instance().midi_handler
                    import mido
                    msg = mido.Message('sysex', data=sysex[1:-1])
                    midi_handler.send_sysex(msg.bytes())

                return
        except Exception as e:
            print(f"Failed to send MIDI for {field} TG{tg_index+1}: {e}", file=sys.stderr)

    def set_tg_to_channels(self):
        midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
        for col in range(8):
            widget = self.table.cellWidget(midi_channel_row, col)
            # Use 0-indexed for QComboBox (channel 1 = index 0, channel 2 = index 1, ...)
            if widget is not None and widget.metaObject().className() == "QComboBox":
                widget.setCurrentIndex(col)
            elif isinstance(widget, QSpinBox):
                widget.setValue(col + 1)
        # Removed explicit call to send_midi_for_field to avoid duplicate SysEx messages

    def set_all_tg_to_ch1(self):
        midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
        for col in range(8):
            widget = self.table.cellWidget(midi_channel_row, col)
            # Use 0-indexed for QComboBox (channel 1 = index 0)
            if widget is not None and widget.metaObject().className() == "QComboBox":
                widget.setCurrentIndex(0)
            elif isinstance(widget, QSpinBox):
                widget.setValue(1)
        # Removed explicit call to send_midi_for_field to avoid duplicate SysEx messages

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

        # Start a timer to check for timeout after 2 seconds
        def check_timeout():
            if not self.isEnabled():
                from dialogs import Dialogs
                self.close()
                Dialogs.show_error(self, "Timeout", "Not all responses to the dump requests were received within 2 seconds.\nThis feature only works with firmware from https://github.com/probonopd/MiniDexed/pull/915")
        QTimer.singleShot(2000, check_timeout)

    def _send_next_sysex_request(self, data=None):
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
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "SysEx Error", "Received invalid or unrecognized SysEx data.")
                self._sysex_request_queue = []
                self._sysex_request_index = 9999
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
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "SysEx Error", "Received invalid or unrecognized SysEx data.")
                self._sysex_request_queue = []
                self._sysex_request_index = 9999
                return
            print(f"[PERF EDITOR DEBUG] Buffer state: {self._sysex_data_buffer}")
            # When all expected responses are received, show window
            if len(self._sysex_data_buffer) >= self._expected_sysex_count:
                if self.main_window and hasattr(self.main_window, "receive_worker") and self.main_window.receive_worker:
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", category=RuntimeWarning)
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
                from PySide6.QtWidgets import QApplication
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
        # Use the imported on_voice_dump function
        on_voice_dump(self.table, self.main_window, data, getattr(self, '_voice_dump_data', {}), getattr(self, '_pending_voice_dumps', set()))
        # If all TGs have received a voice dump, disconnect
        if hasattr(self, '_pending_voice_dumps') and not self._pending_voice_dumps:
            if self.main_window and hasattr(self.main_window, "midi_handler"):
                if hasattr(self.main_window, "receive_worker") and self.main_window.receive_worker:
                    try:
                        self.main_window.receive_worker.sysex_received.disconnect(self._on_voice_dump)
                    except Exception:
                        pass

    def _populate_fields_from_sysex(self):
        """
        Populate the table fields from the data in self._sysex_data_buffer.
        """
        # First, handle global fields
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
        # Then, handle TG-specific fields
        midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
        for tg in range(8):
            tg_data = self._sysex_data_buffer.get(tg)
            if tg_data and len(tg_data) > 4 and tg_data[1] == 0x21:
                i = 3  # skip 0x7D, 0x21, tg
                while i + 3 < len(tg_data):
                    pp1, pp2, vv1, vv2 = tg_data[i], tg_data[i+1], tg_data[i+2], tg_data[i+3]
                    # Map pp1, pp2 to field name
                    field = None
                    if pp1 == 0x00:
                        tg_param_map = {
                            0x00: "BankNumber",
                            0x01: "VoiceNumber",
                            0x02: "MIDIChannel",
                            0x03: "Volume",
                            0x04: "Pan",
                            0x05: "Detune",
                            0x06: "Cutoff",
                            0x07: "Resonance",
                            0x08: "NoteLimitLow",
                            0x09: "NoteLimitHigh",
                            0x0A: "NoteShift",
                            0x0B: "ReverbSend",
                            0x0C: "PitchBendRange",
                            0x0D: "PitchBendStep",
                            0x0E: "PortamentoMode",
                            0x0F: "PortamentoGlissando",
                            0x10: "PortamentoTime",
                            0x11: "MonoMode",
                            0x12: "ModulationWheelRange",
                            0x13: "ModulationWheelTarget",
                            0x14: "FootControlRange",
                            0x15: "FootControlTarget",
                            0x16: "BreathControlRange",
                            0x17: "BreathControlTarget",
                            0x18: "AftertouchRange",
                            0x19: "AftertouchTarget"
                        }
                        field = tg_param_map.get(pp2)
                    if field and field in PERFORMANCE_FIELDS:
                        row = PERFORMANCE_FIELDS.index(field)
                        val = (vv1 << 8) | vv2
                        widget = self.table.cellWidget(row, tg)
                        if field == "MIDIChannel" and widget is not None and widget.metaObject().className() == "QComboBox":
                            self._block_signal = True
                            try:
                                if int(val) >= 16:
                                    widget.setCurrentIndex(16)  # Omni
                                elif 0 <= int(val) <= 15:
                                    widget.setCurrentIndex(int(val))  # 0-15 for channels 1-16
                                else:
                                    widget.setCurrentIndex(0)
                            except Exception:
                                widget.setCurrentIndex(0)
                            self._block_signal = False
                        elif isinstance(widget, QSpinBox):
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

    @classmethod
    def show_singleton(cls, parent=None, main_window=None):
        if cls._instance is not None:
            # If already exists, bring to front
            cls._instance.raise_()
            cls._instance.activateWindow()
            cls._instance.show()
            return cls._instance
        inst = cls(parent=parent, main_window=main_window)
        cls._instance = inst
        inst.show()
        return inst

    @classmethod
    def get_instance(cls):
        return cls._instance

    def closeEvent(self, event):
        type(self)._instance = None
        super().closeEvent(event)

    def open_voice_editor(self, row, col):
        # Get the voice name and MIDI channel for this TG
        midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
        channel_widget = self.table.cellWidget(midi_channel_row, col)
        channel = 1
        if channel_widget is not None:
            if channel_widget.metaObject().className() == "QComboBox":
                idx = channel_widget.currentIndex()
                if idx < 16:
                    channel = idx + 1
            elif isinstance(channel_widget, QSpinBox):
                channel = channel_widget.value()
        # Try to get the voice bytes from the last voice dump if available
        voice_bytes = None
        if hasattr(self, '_voice_dump_data') and col in self._voice_dump_data:
            voice_bytes = bytes(self._voice_dump_data[col])
        # Open the Voice Editor Panel in a window
        midi_outport = getattr(self.main_window, 'midi_handler', None)
        if midi_outport and hasattr(midi_outport, 'outport'):
            midi_outport = midi_outport.outport
        # Use singleton dialog for the panel
        VoiceEditorPanelDialog.show_panel(midi_outport=midi_outport, voice_bytes=voice_bytes, parent=self)
        editor = VoiceEditorPanel.get_instance()
        if hasattr(editor, 'channel_combo'):
            editor.channel_combo.setCurrentIndex(channel - 1)

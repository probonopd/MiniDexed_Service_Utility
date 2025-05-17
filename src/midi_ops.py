from dialogs import Dialogs
import mido
from workers import MidiSendWorker
from PySide6.QtWidgets import QApplication

class MidiOps:
    def __init__(self, main_window):
        self.main_window = main_window
        self._repeat_blocked = False  # Initialize the repeat blocked flag

        # Connect UI buttons
        ui = main_window.ui
        ui.btn_send_out.clicked.connect(self.send_sysex)
        ui.btn_clear_out.clicked.connect(self.clear_out)
        ui.btn_clear_in.clicked.connect(self.clear_in)
        ui.btn_stop_out.clicked.connect(self.stop_sending)

    def send_sysex(self):
        text = self.main_window.ui.out_text.toPlainText()
        try:
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for line in lines:
                try:
                    msg = mido.Message.from_str(line)
                    QApplication.instance().midi_handler.send_sysex(msg.bytes())
                    self.main_window.show_status(f"Sent MIDI: {msg}")
                    continue
                except Exception:
                    pass
                data = self.main_window.file_ops.parse_sysex_text(line)
                if data:
                    if data[0] == 0xF0:
                        msg = mido.Message('sysex', data=data[1:-1] if data[-1] == 0xF7 else data[1:])
                        QApplication.instance().midi_handler.send_sysex(msg.bytes())
                        hex_str = ' '.join(f'{b:02X}' for b in data)
                        self.main_window.show_status(f"Sent SysEx: sysex data={hex_str}")
                    else:
                        msg = mido.Message.from_bytes(data)
                        QApplication.instance().midi_handler.send_sysex(msg.bytes())
                        self.main_window.show_status(f"Sent MIDI bytes: {msg}")
                else:
                    Dialogs.show_error(self.main_window, "Error", f"Invalid MIDI/SysEx data: {line}")
        except Exception as e:
            Dialogs.show_error(self.main_window, "Error", f"Failed to send MIDI: {e}")

    def stop_sending(self):
        QApplication.instance().midi_handler.stop_midi_file()
        self.main_window.show_status("Stop requested.")
        self.send_all_notes_off()  # Send All Notes Off immediately

    def send_all_notes_off(self):
        try:
            for ch in range(16):
                QApplication.instance().midi_handler.send_cc(ch, 123, 0)
            self.main_window.show_status("Sent All Notes Off (CC123) to all channels.")
        except Exception as e:
            Dialogs.show_error(self.main_window, "Error", f"Failed to send All Notes Off: {e}")

    def on_midi_send_finished(self):
        self.main_window.show_status("Finished sending MIDI file.")
        # Repeat logic: check if the Repeat menu entry is checked
        repeat_action = getattr(self.main_window, 'repeat_action', None)
        repeat_enabled = repeat_action.isChecked() if repeat_action else False
        if getattr(self, '_repeat_blocked', False):
            self._repeat_blocked = False
            return  # Do not repeat if stopped by user
        if repeat_enabled and self.main_window.file_ops.loaded_midi:
            if not QApplication.instance().midi_handler.outport:
                from dialogs import Dialogs
                Dialogs.show_error(self.main_window, "Error", "No MIDI Out port selected.")
                return
            self.main_window.show_status("Repeating MIDI file send...")
            QApplication.instance().midi_handler.send_sysex(self.main_window.file_ops.loaded_midi)

    def clear_out(self):
        self.main_window.ui.out_text.clear()
        self.main_window.file_ops.loaded_midi = None
        self.main_window.show_status("Cleared Out area and MIDI file.")

    def clear_in(self):
        self.main_window.ui.in_text.clear()
        self.main_window.show_status("Cleared In area.")

    def send_file(self):
        path = Dialogs.get_file_open(self.main_window, "MIDI Files (*.mid)")
        if not path:
            self.main_window.show_status("MIDI file open canceled.")
            return
        self.main_window.show_status(f"Loading .mid file: {path} ...")
        from workers import FileLoadWorker
        self.file_load_worker = FileLoadWorker(path, 'mid')
        def on_loaded(midi, path):
            self.main_window.file_ops.loaded_midi = midi
            self.main_window.show_status(f"Loaded .mid file: {path}")
            if not self.main_window.midi_handler.outport:
                Dialogs.show_error(self.main_window, "Error", "No MIDI Out port selected.")
                return
            self.send_all_notes_off()
            # Use MIDIHandler to send the MIDI file and handle repeat logic
            def on_finished():
                self.on_midi_send_finished()
            def on_log(msg):
                self.main_window.show_status(msg)
            QApplication.instance().midi_handler.send_midi_file(midi, on_finished=on_finished, on_log=on_log)
        self.file_load_worker.loaded.connect(on_loaded)
        self.file_load_worker.error.connect(lambda e: Dialogs.show_error(self.main_window, "Error", f"Failed to load .mid: {e}"))
        self.file_load_worker.start()

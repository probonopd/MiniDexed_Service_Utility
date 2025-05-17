from dialogs import Dialogs
from file_utils import FileUtils
from workers import FileLoadWorker, FileSaveWorker
import mido

class FileOps:
    def __init__(self, main_window):
        self.main_window = main_window
        self.loaded_midi = None
        self.file_load_worker = None
        self.file_save_worker = None

    def menu_open_syx(self):
        path = Dialogs.get_file_open(self.main_window, "SysEx Files (*.syx)")
        if not path:
            self.main_window.ui.append_log("SysEx file open canceled.")
            return
        self.main_window.ui.append_log(f"Loading .syx file: {path} ...")
        self.file_load_worker = FileLoadWorker(path, 'syx')
        self.file_load_worker.loaded.connect(self.on_syx_loaded)
        self.file_load_worker.error.connect(lambda e: Dialogs.show_error(self.main_window, "Error", f"Failed to load .syx: {e}"))
        self.file_load_worker.start()

    def on_syx_loaded(self, data, path):
        hex_str = ' '.join(f'{b:02X}' for b in data)
        self.main_window.ui.out_text.setPlainText(hex_str)
        self.main_window.ui.append_log(f"Loaded .syx file: {path}")
        self.loaded_midi = None

    def menu_save_syx(self):
        path = Dialogs.get_file_save(self.main_window, "SysEx Files (*.syx)")
        if not path:
            self.main_window.ui.append_log("SysEx file save canceled.")
            return
        text = self.main_window.ui.out_text.toPlainText()
        data = self.parse_sysex_text(text)
        if data:
            self.main_window.ui.append_log(f"Saving .syx file: {path} ...")
            self.file_save_worker = FileSaveWorker(path, 'syx', data)
            self.file_save_worker.saved.connect(lambda p: self.main_window.ui.append_log(f"Saved .syx file: {p}"))
            self.file_save_worker.error.connect(lambda e: Dialogs.show_error(self.main_window, "Error", f"Failed to save .syx: {e}"))
            self.file_save_worker.start()
        else:
            Dialogs.show_error(self.main_window, "Error", "Invalid SysEx data.")

    def menu_open_mid(self):
        path = Dialogs.get_file_open(self.main_window, "MIDI Files (*.mid)")
        if not path:
            self.main_window.ui.append_log("MIDI file open canceled.")
            return
        self.main_window.ui.append_log(f"Loading .mid file: {path} ...")
        self.file_load_worker = FileLoadWorker(path, 'mid')
        self.file_load_worker.loaded.connect(self.on_midi_loaded)
        self.file_load_worker.error.connect(lambda e: Dialogs.show_error(self.main_window, "Error", f"Failed to load .mid: {e}"))
        self.file_load_worker.start()

    def on_midi_loaded(self, midi, path):
        self.loaded_midi = midi
        self.main_window.ui.append_log(f"Loaded .mid file: {path}")

    def menu_save_midi_in(self):
        path = Dialogs.get_file_save(self.main_window, "MIDI Files (*.mid)")
        if not path:
            self.main_window.ui.append_log("MIDI In save canceled.")
            return
        midi = mido.MidiFile()
        track = mido.MidiTrack()
        midi.tracks.append(track)
        lines = [l.strip() for l in self.main_window.ui.in_text.toPlainText().splitlines() if l.strip()]
        for line in lines:
            try:
                msg = mido.Message.from_str(line)
                track.append(msg)
                continue
            except Exception:
                pass
            try:
                data = self.parse_sysex_text(line)
                if data:
                    if not (data[0] & 0x80):
                        data = [0xF0] + data + [0xF7]
                    if data[0] == 0xF0:
                        msg = mido.Message('sysex', data=data[1:-1] if data[-1] == 0xF7 else data[1:])
                    else:
                        msg = mido.Message.from_bytes(data)
                    track.append(msg)
            except Exception:
                self.main_window.ui.append_log(f"Skipped invalid MIDI line: {line}")
        if len(track) == 0:
            Dialogs.show_error(self.main_window, "Error", "No valid MIDI data in MIDI In to save.")
            return
        midi.save(path)
        self.main_window.ui.append_log(f"Saved MIDI In as .mid file: {path}")

    def parse_sysex_text(self, text):
        try:
            parts = text.replace(',', ' ').split()
            return [int(p, 16) for p in parts]
        except Exception:
            return None

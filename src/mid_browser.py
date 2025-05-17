import sys
import os
import hashlib
import requests
import mido
import logging
logging.basicConfig(level=logging.DEBUG)
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QHBoxLayout, QPushButton, QLabel, QStatusBar, QListWidgetItem, QLineEdit,
    QCheckBox, QApplication
)
from PySide6.QtGui import QIcon
from dialogs import Dialogs

from track_channel_dialog import TrackChannelDialog

MIDBROWSER_API_URL = "https://gifx.co/chip/browse?path="
MIDBROWSER_CACHE_NAME = "midbrowser_cache.json"

# Cache directory for .mid files and listings
def get_mid_cache_dir():
    return os.path.join(os.getenv('LOCALAPPDATA') or os.path.expanduser('~/.local/share'), 'MiniDexed_Service_Utility', 'mid_cache')

class MidFileDownloadWorker(QThread):
    finished = Signal(str, str, object)  # local_path, file_name, error
    def __init__(self, url, file_name):
        super().__init__()
        self.url = url
        self.file_name = file_name
    def run(self):
        try:
            cache_dir = get_mid_cache_dir()
            os.makedirs(cache_dir, exist_ok=True)
            url_hash = hashlib.sha256(self.url.encode('utf-8')).hexdigest()
            cache_path = os.path.join(cache_dir, url_hash + '.mid')
            if os.path.exists(cache_path):
                self.finished.emit(cache_path, self.file_name, None)
                return
            resp = requests.get(self.url)
            resp.raise_for_status()
            with open(cache_path, 'wb') as f:
                f.write(resp.content)
            self.finished.emit(cache_path, self.file_name, None)
        except Exception as e:
            self.finished.emit('', self.file_name, e)

class MidBrowser(QDialog):
    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("MIDI File Browser")
        self.resize(500, 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("Search MIDI files...")
        layout.addWidget(self.search_box)
        self.breadcrumb_label = QLabel(self)
        layout.addWidget(self.breadcrumb_label)
        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)
        nav_layout = QHBoxLayout()
        self.up_button = QPushButton("Clear", self)
        self.up_button.clicked.connect(self.go_up)
        nav_layout.addWidget(self.up_button)
        layout.addLayout(nav_layout)
        self.status_bar = QStatusBar(self)
        layout.addWidget(self.status_bar)
        self.current_path = "/"
        self.dir_stack = []
        self.entries = []
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.itemSelectionChanged.connect(self.update_buttons)
        self.search_box.returnPressed.connect(self._do_search)
        self.load_directory(self.current_path)
        self.filter_bank_checkbox = QCheckBox("Filter out bank/voice changes", self)
        self.filter_bank_checkbox.setChecked(True)
        layout.insertWidget(1, self.filter_bank_checkbox)

    def set_status(self, msg, error=False):
        self.status_bar.showMessage(msg)
        if error:
            print(msg, file=sys.stderr)
        else:
            print(msg)

    def load_directory(self, path):
        logging.info(f"load_directory called with path={path}")
        self.list_widget.clear()
        self.entries = []
        self.breadcrumb_label.setText(f"Path: {path}")
        self.set_status(f"Loading {path} ...")
        try:
            url = MIDBROWSER_API_URL + requests.utils.quote(path)
            resp = requests.get(url)
            resp.raise_for_status()
            entries = resp.json()
            entries = [e for e in entries if e['type'] == 'directory' or e['path'].lower().endswith('.mid') or e['path'].lower().endswith('.midi')]
            entries.sort(key=lambda e: (e['type'] != 'directory', not (e['path'].lower().endswith('.mid') or e['path'].lower().endswith('.midi')), e['path'].lower()))
            self.entries = entries
            for entry in entries:
                name = os.path.basename(entry['path'])
                if entry['type'] == 'directory':
                    item = QListWidgetItem(QIcon.fromTheme('folder'), name)
                elif name.lower().endswith('.mid') or name.lower().endswith('.midi'):
                    item = QListWidgetItem(name)
                else:
                    continue
                self.list_widget.addItem(item)
            self.set_status(f"{len(entries)} items.")
        except Exception as e:
            self.set_status(f"Failed to load directory: {e}", error=True)

    def _do_search(self):
        text = self.search_box.text().strip()
        if text:
            self.load_search_results(text)

    def load_search_results(self, query):
        self.set_status(f"Searching for '{query}' ...")
        self.list_widget.clear()
        self.entries = []
        self.breadcrumb_label.setText(f"Search: {query}")
        try:
            url = f"https://gifx.co/chip/search?query={requests.utils.quote(query)}&limit=100"
            logging.info(f"Search URL: {url}")
            resp = requests.get(url)
            resp.raise_for_status()
            entries = resp.json()
            logging.info(f"Raw search response: {entries}")
            if isinstance(entries, dict):
                if 'items' in entries:
                    items = entries['items']
                    entries = [
                        {'type': 'file', 'path': '/' + item['file']} for item in items
                    ]
                elif 'results' in entries:
                    entries = entries['results']
                else:
                    logging.error(f"Unexpected search result format: {entries}")
                    raise Exception(entries.get('error', 'Unexpected search result format'))
            if not isinstance(entries, list):
                logging.error(f"Entries is not a list: {entries}")
                raise Exception('Unexpected search result format')
            entries = [e for e in entries if e.get('type') == 'directory' or e['path'].lower().endswith('.mid') or e['path'].lower().endswith('.midi')]
            logging.info(f"Filtered entries: {entries}")
            entries.sort(key=lambda e: (e.get('type') != 'directory', not (e['path'].lower().endswith('.mid') or e['path'].lower().endswith('.midi')), e['path'].lower()))
            self.entries = entries
            for entry in entries:
                name = os.path.basename(entry['path'])
                logging.info(f"Adding entry to list: {entry}")
                if entry.get('type') == 'directory':
                    item = QListWidgetItem(QIcon.fromTheme('folder'), name)
                elif name.lower().endswith('.mid') or name.lower().endswith('.midi'):
                    item = QListWidgetItem(name)
                else:
                    continue
                self.list_widget.addItem(item)
            self.set_status(f"{len(entries)} items found.")
        except Exception as e:
            logging.error(f"Search failed: {e}")
            self.set_status(f"Search failed: {e}", error=True)

    def on_item_double_clicked(self, item):
        idx = self.list_widget.currentRow()
        if idx < 0 or idx >= len(self.entries):
            return
        entry = self.entries[idx]
        if entry['type'] == 'directory':
            self.dir_stack.append(self.current_path)
            self.current_path = entry['path']
            self.load_directory(self.current_path)
        elif entry['path'].lower().endswith('.mid'):
            self.download_and_send_mid(entry)

    def go_up(self):
        if self.current_path == "/":
            return
        if self.dir_stack:
            self.current_path = self.dir_stack.pop()
        else:
            self.current_path = os.path.dirname(self.current_path.rstrip('/')) or "/"
        self.load_directory(self.current_path)

    def update_buttons(self):
        idx = self.list_widget.currentRow()
        enable = False
        if idx >= 0 and idx < len(self.entries):
            entry = self.entries[idx]
            if entry['path'].lower().endswith('.mid'):
                enable = True
        self.send_button.setEnabled(enable)

    def send_selected_mid(self):
        idx = self.list_widget.currentRow()
        if idx < 0 or idx >= len(self.entries):
            return
        entry = self.entries[idx]
        if entry['path'].lower().endswith('.mid'):
            self.download_and_send_mid(entry)

    def download_and_send_mid(self, entry):
        # Use /music/ instead of /chip/ for .mid files
        url = f"https://gifx.co/music{entry['path']}"
        file_name = os.path.basename(entry['path'])
        self.set_status(f"Downloading {file_name} ...")
        self.worker = MidFileDownloadWorker(url, file_name)
        self.worker.finished.connect(self.on_mid_downloaded)
        self.worker.start()

    def on_mid_downloaded(self, local_path, file_name, error):
        if error:
            self.set_status(f"Failed to download {file_name}: {error}", error=True)
            return
        self.set_status(f"Downloaded {file_name} to {local_path}")
        try:
            midi = mido.MidiFile(local_path)
            dlg = TrackChannelDialog(midi, self)
            if not dlg.exec_():
                self.set_status("MIDI channel assignment canceled.")
                return
            assignments = dlg.get_assignments()
            new_midi = mido.MidiFile()
            new_midi.ticks_per_beat = midi.ticks_per_beat
            filter_bank = self.filter_bank_checkbox.isChecked()
            # Only assign channels to filtered tracks (those shown in the dialog)
            # Copy other tracks as-is
            filtered_set = set(dlg.filtered_track_indices)
            assign_map = dict(zip(dlg.filtered_track_indices, assignments))
            for i, track in enumerate(midi.tracks):
                new_track = mido.MidiTrack()
                if i in assign_map:
                    channel = assign_map[i] - 1
                    for msg in track:
                        if filter_bank:
                            # Filter out program changes and bank select (CC 0/32)
                            if msg.type == "program_change":
                                continue
                            if msg.type == "control_change" and hasattr(msg, 'control') and msg.control in (0, 32):
                                continue
                        # Copy all other messages, updating channel if appropriate
                        if hasattr(msg, 'channel'):
                            msg_out = msg.copy(channel=channel)
                        else:
                            # Meta messages and others: just append as-is
                            msg_out = msg
                        new_track.append(msg_out)
                else:
                    # Not a filtered track: copy as-is
                    for msg in track:
                        new_track.append(msg)
                new_midi.tracks.append(new_track)

            # Remove any silence from the beginning of the new MIDI file
            # by checking the first message of each track and then removing that time
            # on each track (same amount for all tracks)
            silence_time = min(track[0].time for track in new_midi.tracks if len(track) > 0)
            for track in new_midi.tracks:
                if len(track) > 0:
                    track[0].time -= silence_time
            # Move all messages forward by the silence time
            for track in new_midi.tracks:
                for msg in track:
                    if hasattr(msg, 'time'):
                        msg.time += silence_time
            # Remove any silence from the end of the new MIDI file
            # by checking the last message of each track and then removing that time
            # on each track (same amount for all tracks)
            silence_time = min(track[-1].time for track in new_midi.tracks if len(track) > 0)
            for track in new_midi.tracks:
                if len(track) > 0:
                    track[-1].time -= silence_time

            mw = self.main_window
            if mw is None or not hasattr(mw, 'midi_ops') or not hasattr(mw.midi_handler, 'outport') or not mw.midi_handler.outport:
                Dialogs.show_error(self, "Error", "No MIDI Out port selected in main window.")
                return
            midi_ops = mw.midi_ops
            # Stop any currently playing MIDI file, and wait for it to finish before starting new one
            def start_new_file():
                mw.show_status("Sending MIDI file with timing...")
                mw.file_ops.loaded_midi = new_midi
                QApplication.instance().midi_handler.send_midi_file(new_midi, on_finished=midi_ops.on_midi_send_finished, on_log=mw.show_status)
            # Use a flag to block repeat if needed
            if hasattr(midi_ops, '_repeat_blocked') and getattr(midi_ops, '_repeat_blocked', False):
                midi_ops._repeat_blocked = False
            # Always stop any current playback before starting new one
            QApplication.instance().midi_handler.stop_midi_file()
            # Start new file after a short delay to ensure stop is processed
            QTimer.singleShot(100, start_new_file)
        except Exception as e:
            Dialogs.show_error(self, "MIDI Error", f"Failed to parse/send MIDI: {e}")

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dlg = MidBrowser()
    dlg.show()
    sys.exit(app.exec())

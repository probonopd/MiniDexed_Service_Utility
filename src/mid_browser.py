print("=== mid_browser.py loaded ===")
import sys
import os
import json
import hashlib
import requests
import mido
import difflib
import logging
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QHBoxLayout, QPushButton, QLabel, QStatusBar, QListWidgetItem, QLineEdit,
    QDialogButtonBox, QComboBox, QSpinBox, QFormLayout, QCheckBox, QApplication
)
from PySide6.QtGui import QIcon
from dialogs import Dialogs
from mido import Message
from voice_browser import get_cache_dir, VOICE_LIST_CACHE_NAME, VoiceDownloadWorker

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
        self.send_button = QPushButton("Send", self)
        self.send_button.setEnabled(False)
        nav_layout.addWidget(self.send_button)
        layout.addLayout(nav_layout)
        self.status_bar = QStatusBar(self)
        layout.addWidget(self.status_bar)
        self.current_path = "/"
        self.dir_stack = []
        self.entries = []
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.itemSelectionChanged.connect(self.update_buttons)
        self.send_button.clicked.connect(self.send_selected_mid)
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
        import logging
        logging.debug(f"load_directory called with path={path}")
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
        import logging
        logging.basicConfig(level=logging.DEBUG)
        self.set_status(f"Searching for '{query}' ...")
        self.list_widget.clear()
        self.entries = []
        self.breadcrumb_label.setText(f"Search: {query}")
        try:
            url = f"https://gifx.co/chip/search?query={requests.utils.quote(query)}&limit=100"
            logging.debug(f"Search URL: {url}")
            resp = requests.get(url)
            resp.raise_for_status()
            entries = resp.json()
            logging.debug(f"Raw search response: {entries}")
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
            logging.debug(f"Filtered entries: {entries}")
            entries.sort(key=lambda e: (e.get('type') != 'directory', not (e['path'].lower().endswith('.mid') or e['path'].lower().endswith('.midi')), e['path'].lower()))
            self.entries = entries
            for entry in entries:
                name = os.path.basename(entry['path'])
                logging.debug(f"Adding entry to list: {entry}")
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
            class TrackChannelDialog(QDialog):
                _instance = None
                def __new__(cls, *args, **kwargs):
                    if cls._instance is not None and cls._instance.isVisible():
                        cls._instance.raise_()
                        cls._instance.activateWindow()
                        return cls._instance
                    instance = super().__new__(cls)
                    cls._instance = instance
                    return instance
                def closeEvent(self, event):
                    type(self)._instance = None
                    super().closeEvent(event)
                def __init__(self, midi, parent=None):
                    if hasattr(self, '_initialized') and self._initialized:
                        return
                    self._initialized = True
                    super().__init__(parent)
                    self.setWindowTitle("Assign Tracks to MIDI Channels")
                    self.setModal(False)
                    layout = QVBoxLayout(self)
                    form = QFormLayout()
                    self.channel_boxes = []
                    self.suggestion_labels = []
                    # Load voices from patch_list.json (cached by VoiceBrowser)
                    voices = []
                    try:
                        from voice_browser import get_cache_dir, VOICE_LIST_CACHE_NAME
                        cache_path = os.path.join(get_cache_dir(), VOICE_LIST_CACHE_NAME)
                        if os.path.exists(cache_path):
                            with open(cache_path, 'r', encoding='utf-8') as f:
                                voices = json.load(f)
                    except Exception as e:
                        voices = []
                    def suggest_voice(track_name):
                        if not track_name:
                            return None
                        tn = track_name.lower().strip()
                        # Exact match
                        for v in voices:
                            if v.get('name','').lower().strip() == tn:
                                return v['name']
                        # Fuzzy: best match by similarity
                        voice_names = [v.get('name','') for v in voices]
                        matches = difflib.get_close_matches(track_name, voice_names, n=1, cutoff=0.6)
                        if matches:
                            return matches[0]
                        # Fuzzy: contains
                        for v in voices:
                            if tn and tn in v.get('name','').lower():
                                return v['name']
                        return None
                    # Filter tracks: only include those with at least one note_on
                    filtered_tracks = []
                    filtered_track_indices = []
                    for i, track in enumerate(midi.tracks):
                        has_note_on = any(getattr(msg, 'type', None) == 'note_on' and getattr(msg, 'velocity', 0) > 0 for msg in track)
                        if has_note_on:
                            filtered_tracks.append((i, track))
                            filtered_track_indices.append(i)
                    for idx, (i, track) in enumerate(filtered_tracks):
                        label = f"Track {i}: {track.name if hasattr(track, 'name') and track.name else ''}".strip()
                        combo = QComboBox()
                        combo.addItems([str(ch+1) for ch in range(16)] + ["None"])
                        combo.setCurrentIndex(idx if idx < 16 else 15)
                        self.channel_boxes.append(combo)
                        # Suggestion label
                        suggestion = suggest_voice(getattr(track, 'name', ''))
                        suggestion_lbl = QLabel(f"Suggested: {suggestion}" if suggestion else "")
                        self.suggestion_labels.append(suggestion_lbl)
                        row_layout = QHBoxLayout()
                        row_layout.addWidget(combo)
                        row_layout.addWidget(suggestion_lbl)
                        form.addRow(label, row_layout)
                    layout.addLayout(form)
                    btn_layout = QHBoxLayout()
                    self.auto_btn = QPushButton("Send Voices")
                    self.auto_btn.clicked.connect(self.auto_assign)
                    btn_layout.addWidget(self.auto_btn)
                    self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    btn_layout.addWidget(self.buttons)
                    layout.addLayout(btn_layout)
                    self.buttons.accepted.connect(self.accept)
                    self.buttons.rejected.connect(self.reject)
                    self.setLayout(layout)
                    self.voices = voices
                    self.midi = midi
                    self.filtered_track_indices = filtered_track_indices
                    self.suggestions = [suggest_voice(getattr(midi.tracks[i], 'name', '')) for i in filtered_track_indices]
                    # After creating self.suggestions and self.channel_boxes, assign same channel to same voice
                    voice_to_channel = {}
                    used_channels = set()
                    for sugg in self.suggestions:
                        if not sugg:
                            continue
                        if sugg not in voice_to_channel:
                            for ch in range(16):
                                if ch not in used_channels:
                                    voice_to_channel[sugg] = ch
                                    used_channels.add(ch)
                                    break
                    for idx, sugg in enumerate(self.suggestions):
                        if sugg and sugg in voice_to_channel:
                            self.channel_boxes[idx].setCurrentIndex(voice_to_channel[sugg])
                def get_assignments(self):
                    return [box.currentIndex()+1 for box in self.channel_boxes]
                def auto_assign(self):
                    # Use global midi_handler from QApplication
                    app = QApplication.instance()
                    midi_handler = getattr(app, "midi_handler", None)
                    # Assign the same MIDI channel to all tracks with the same suggested voice
                    voice_to_channel = {}
                    used_channels = set()
                    for sugg in self.suggestions:
                        if not sugg:
                            continue
                        if sugg not in voice_to_channel:
                            for ch in range(16):
                                if ch not in used_channels:
                                    voice_to_channel[sugg] = ch
                                    used_channels.add(ch)
                                    break
                    for idx, sugg in enumerate(self.suggestions):
                        if sugg and sugg in voice_to_channel:
                            self.channel_boxes[idx].setCurrentIndex(voice_to_channel[sugg])
                    # Send channel assignment SysEx
                    for idx, (sugg, box) in enumerate(zip(self.suggestions, self.channel_boxes)):
                        if not sugg:
                            continue
                        channel = box.currentIndex() + 1
                        if channel <= 0 or channel > 16:
                            continue
                        sysex = [0xF0, 0x7D, 0x21, channel, 0x00, 0x02, 0x00, channel-1, 0xF7]
                        msg = mido.Message('sysex', data=sysex[1:-1])

                        logging.info(f"Setting TG{channel-1} to MIDI channel {channel}")
                        QApplication.instance().midi_handler.send_sysex(msg.bytes())
                    # Send voice SysEx for each channel/voice assignment
                    for idx, (sugg, box) in enumerate(zip(self.suggestions, self.channel_boxes)):
                        if not sugg:
                            continue
                        channel = box.currentIndex() + 1
                        if channel <= 0 or channel > 16:
                            continue
                        voice_obj = next((v for v in self.voices if v.get('name') == sugg and v.get('syx')), None)
                        if not voice_obj:
                            continue
                        syx_data = voice_obj['syx']
                        if isinstance(syx_data, str):
                            syx_data = [int(x, 16) for x in syx_data.split() if x.strip()]
                        elif isinstance(syx_data, bytes):
                            syx_data = list(syx_data)
                        if len(syx_data) > 3:
                            syx_data[2] = 0x10 | ((channel-1) & 0x0F)
                        if syx_data[0] != 0xF0:
                            syx_data = [0xF0] + syx_data
                        if syx_data[-1] != 0xF7:
                            syx_data = syx_data + [0xF7]
                        msg = mido.Message('sysex', data=syx_data[1:-1])
                        logging.info(f"Sending FF FF format SysEx to MIDI channel {channel}")
                        print(f"[DEBUG] About to send SysEx to channel {channel}, syx_data: {syx_data}")
                        app = QApplication.instance()
                        midi_handler = getattr(app, "midi_handler", None)
                        midi_handler.send_sysex(msg.bytes())

            dlg = TrackChannelDialog(midi, self)
            if not dlg.exec():
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

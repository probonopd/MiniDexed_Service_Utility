import sys
import os
import json
import hashlib
import requests
import mido
import difflib
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QHBoxLayout, QPushButton, QLabel, QStatusBar, QListWidgetItem, QLineEdit,
    QDialogButtonBox, QComboBox, QSpinBox, QFormLayout, QCheckBox
)
from PySide6.QtGui import QIcon
from dialogs import Dialogs

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
        self.in_search_mode = False
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.itemSelectionChanged.connect(self.update_buttons)
        self.send_button.clicked.connect(self.send_selected_mid)
        self.search_box.textChanged.connect(self.on_search_text_changed)
        self.load_directory(self.current_path)

        self.search_debounce_timer = QTimer(self)
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.timeout.connect(self._do_search)
        self._pending_search_text = ''

        self.filter_bank_checkbox = QCheckBox("Filter out bank/voice changes", self)
        self.filter_bank_checkbox.setChecked(True)
        layout.insertWidget(1, self.filter_bank_checkbox)  # Place below search box

    def set_status(self, msg, error=False):
        self.status_bar.showMessage(msg)
        if error:
            print(msg, file=sys.stderr)
        else:
            print(msg)

    def load_directory(self, path):
        if not self.in_search_mode:
            self.list_widget.clear()
            self.entries = []
            self.breadcrumb_label.setText("")
            self.set_status("")
            return
        self.set_status(f"Loading {path} ...")
        self.list_widget.clear()
        self.entries = []
        self.breadcrumb_label.setText(f"Path: {path}")
        try:
            url = MIDBROWSER_API_URL + requests.utils.quote(path)
            resp = requests.get(url)
            resp.raise_for_status()
            entries = resp.json()
            # Only show .mid or .midi files and directories
            entries = [e for e in entries if e['type'] == 'directory' or e['path'].lower().endswith('.mid') or e['path'].lower().endswith('.midi')]
            entries.sort(key=lambda e: (e['type'] != 'directory', not (e['path'].lower().endswith('.mid') or e['path'].lower().endswith('.midi')), e['path'].lower()))
            self.entries = entries
            for entry in entries:
                name = os.path.basename(entry['path'])
                if entry['type'] == 'directory':
                    item = QListWidgetItem(QIcon.fromTheme('folder'), name)
                elif name.lower().endswith('.mid') or name.lower().endswith('.midi'):
                    item = QListWidgetItem(QIcon.fromTheme('media-playback-start'), name)
                else:
                    continue  # Should not happen
                self.list_widget.addItem(item)
            self.set_status(f"{len(entries)} items.")
        except Exception as e:
            self.set_status(f"Failed to load directory: {e}", error=True)

    def on_search_text_changed(self, text):
        text = text.strip()
        self._pending_search_text = text
        if text:
            self.search_debounce_timer.start(400)  # 400ms debounce
        else:
            self.search_debounce_timer.stop()
            self.in_search_mode = False
            self.load_directory(self.current_path)

    def _do_search(self):
        text = self._pending_search_text
        if text:
            self.in_search_mode = True
            self.load_search_results(text)

    def load_search_results(self, query):
        self.set_status(f"Searching for '{query}' ...")
        self.list_widget.clear()
        self.entries = []
        self.breadcrumb_label.setText(f"Search: {query}")
        try:
            url = f"https://gifx.co/chip/search?query={requests.utils.quote(query)}&limit=100"
            resp = requests.get(url)
            resp.raise_for_status()
            entries = resp.json()
            # Handle new search result format
            if isinstance(entries, dict):
                if 'items' in entries:
                    items = entries['items']
                    entries = [
                        {'type': 'file', 'path': '/' + item['file']} for item in items
                    ]
                elif 'results' in entries:
                    entries = entries['results']
                else:
                    raise Exception(entries.get('error', 'Unexpected search result format'))
            if not isinstance(entries, list):
                raise Exception('Unexpected search result format')
            # Only show .mid or .midi files and directories
            entries = [e for e in entries if e.get('type') == 'directory' or e['path'].lower().endswith('.mid') or e['path'].lower().endswith('.midi')]
            entries.sort(key=lambda e: (e.get('type') != 'directory', not (e['path'].lower().endswith('.mid') or e['path'].lower().endswith('.midi')), e['path'].lower()))
            self.entries = entries
            for entry in entries:
                name = os.path.basename(entry['path'])
                if entry.get('type') == 'directory':
                    item = QListWidgetItem(QIcon.fromTheme('folder'), name)
                elif name.lower().endswith('.mid') or name.lower().endswith('.midi'):
                    item = QListWidgetItem(QIcon.fromTheme('media-playback-start'), name)
                else:
                    continue  # Should not happen
                self.list_widget.addItem(item)
            self.set_status(f"{len(entries)} items found.")
        except Exception as e:
            self.set_status(f"Search failed: {e}", error=True)

    def on_item_double_clicked(self, item):
        idx = self.list_widget.currentRow()
        if idx < 0 or idx >= len(self.entries):
            return
        entry = self.entries[idx]
        if entry['type'] == 'directory':
            if self.in_search_mode:
                # In search mode, jump to directory
                self.in_search_mode = False
                self.search_box.clear()
                self.dir_stack.append(self.current_path)
                self.current_path = entry['path']
                self.load_directory(self.current_path)
            else:
                self.dir_stack.append(self.current_path)
                self.current_path = entry['path']
                self.load_directory(self.current_path)
        elif entry['path'].lower().endswith('.mid'):
            self.download_and_send_mid(entry)

    def go_up(self):
        if self.in_search_mode:
            self.in_search_mode = False
            self.search_box.clear()
            self.load_directory(self.current_path)
            return
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
                def __init__(self, midi, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("Assign Tracks to MIDI Channels")
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
                    for i, track in enumerate(midi.tracks):
                        label = f"Track {i}: {track.name if hasattr(track, 'name') and track.name else ''}".strip()
                        combo = QComboBox()
                        combo.addItems([str(ch+1) for ch in range(16)])
                        combo.setCurrentIndex(i if i < 16 else 0)
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
                    self.auto_btn = QPushButton("Auto Assign")
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
                    self.suggestions = [suggest_voice(getattr(track, 'name', '')) for track in midi.tracks]
                def get_assignments(self):
                    return [box.currentIndex()+1 for box in self.channel_boxes]
                def auto_assign(self):
                    # Queue the respective voices to be sent to the selected MIDI channels
                    if self.parent() and hasattr(self.parent(), 'main_window'):
                        mw = self.parent().main_window
                        if mw and hasattr(mw, 'midi_handler'):
                            from voice_browser import get_cache_dir, VOICE_LIST_CACHE_NAME, VoiceDownloadWorker
                            cache_path = os.path.join(get_cache_dir(), VOICE_LIST_CACHE_NAME)
                            voices = []
                            if os.path.exists(cache_path):
                                with open(cache_path, 'r', encoding='utf-8') as f:
                                    voices = json.load(f)
                            send_queue = []
                            for i, (sugg, box) in enumerate(zip(self.suggestions, self.channel_boxes)):
                                if not sugg:
                                    continue
                                v = next((v for v in voices if v.get('name','').lower().strip() == sugg.lower().strip()), None)
                                if not v:
                                    continue
                                sig = v.get('signature')
                                if not sig:
                                    continue
                                url = f"https://patches.fm/patches/single-voice/dx7/{sig[:2]}/{sig}.syx"
                                channel = box.currentIndex() + 1
                                send_queue.append((url, sugg, channel))
                            self._voice_workers = []
                            def send_next():
                                if not send_queue:
                                    return
                                url, name, channel = send_queue.pop(0)
                                worker = VoiceDownloadWorker(url, name)
                                self._voice_workers.append(worker)
                                def after_download(syx_data, voice_name, error):
                                    if error:
                                        self._voice_workers.remove(worker)
                                        send_next()
                                        return
                                    midi_handler = mw.midi_handler
                                    def sanitize_sysex(data):
                                        if data and data[0] == 0xF0:
                                            data = data[1:]
                                        if data and data[-1] == 0xF7:
                                            data = data[:-1]
                                        return [b & 0x7F for b in data]
                                    sanitized = sanitize_sysex(syx_data)
                                    import mido
                                    msg = mido.Message('sysex', data=sanitized)
                                    if hasattr(midi_handler, 'midi_send_worker') and midi_handler.midi_send_worker:
                                        midi_handler.midi_send_worker.send(msg)
                                    else:
                                        midi_handler.outport.send(msg)
                                    self._voice_workers.remove(worker)
                                    send_next()
                                worker.finished.connect(after_download)
                                worker.start()
                            send_next()
            dlg = TrackChannelDialog(midi, self)
            if not dlg.exec():
                return
            assignments = dlg.get_assignments()
            new_midi = mido.MidiFile()
            new_midi.ticks_per_beat = midi.ticks_per_beat
            filter_bank = self.filter_bank_checkbox.isChecked()
            for i, track in enumerate(midi.tracks):
                new_track = mido.MidiTrack()
                channel = assignments[i] - 1
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
                new_midi.tracks.append(new_track)
            # Use main_window.midi_ops to send, so stop button and all-notes-off work
            mw = self.main_window
            if mw is None or not hasattr(mw, 'midi_ops') or not hasattr(mw.midi_handler, 'outport') or not mw.midi_handler.outport:
                Dialogs.show_error(self, "Error", "No MIDI Out port selected in main window.")
                return
            midi_ops = mw.midi_ops
            # Stop any currently playing MIDI file, and wait for it to finish before starting new one
            def start_new_worker():
                mw.show_status("Sending MIDI file with timing...")
                from workers import MidiSendWorker
                midi_ops.midi_send_worker = MidiSendWorker(mw.midi_handler.outport, new_midi)
                midi_ops.midi_send_worker.log.connect(mw.show_status)
                midi_ops.midi_send_worker.finished.connect(midi_ops.on_midi_send_finished)
                midi_ops.midi_send_worker.start()
            if midi_ops.midi_send_worker and midi_ops.midi_send_worker.isRunning():
                midi_ops._repeat_blocked = True
                # Disconnect any previous finished handler to avoid multiple triggers
                try:
                    midi_ops.midi_send_worker.finished.disconnect()
                except Exception:
                    pass
                def on_stopped_then_start():
                    midi_ops.midi_send_worker.finished.disconnect(on_stopped_then_start)
                    # Set as loaded_midi for repeat/stop logic
                    mw.file_ops.loaded_midi = new_midi
                    start_new_worker()
                midi_ops.midi_send_worker.finished.connect(on_stopped_then_start)
                midi_ops.midi_send_worker.stop()
                mw.show_status("Stopping previous MIDI file...")
                return
            # Set as loaded_midi for repeat/stop logic
            mw.file_ops.loaded_midi = new_midi
            start_new_worker()
        except Exception as e:
            Dialogs.show_error(self, "MIDI Error", f"Failed to parse/send MIDI: {e}")

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dlg = MidBrowser()
    dlg.show()
    sys.exit(app.exec())

import sys
import requests
import os
import hashlib
import json
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSettings
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QHBoxLayout, QComboBox, QPushButton, QLabel, QApplication, QListWidgetItem, QStatusBar, QMenuBar, QMenu
)
from PyQt6.QtGui import QAction

VOICE_LIST_URL = "https://patches.fm/patches/dx7/patch_list.json"
VOICE_LIST_CACHE_NAME = "patch_list.json"

def get_cache_dir():
    return os.path.join(os.getenv('LOCALAPPDATA') or os.path.expanduser('~/.local/share'), 'MiniDexed_Service_Utility', 'patches_cache')

class VoiceDownloadWorker(QThread):
    finished = pyqtSignal(list, str, object)  # syx_data, voice_name, error (None if ok)
    def __init__(self, url, voice_name):
        super().__init__()
        self.url = url
        self.voice_name = voice_name
    def run(self):
        try:
            cache_dir = get_cache_dir()
            os.makedirs(cache_dir, exist_ok=True)
            url_hash = hashlib.sha256(self.url.encode('utf-8')).hexdigest()
            cache_path = os.path.join(cache_dir, url_hash + '.syx')
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    syx_data = list(f.read())
                self.finished.emit(syx_data, self.voice_name, None)
                return
            import requests
            resp = requests.get(self.url)
            resp.raise_for_status()
            syx_data = resp.content
            with open(cache_path, 'wb') as f:
                f.write(syx_data)
            self.finished.emit(list(syx_data), self.voice_name, None)
        except Exception as e:
            self.finished.emit([], self.voice_name, e)

class VoiceJsonDownloadWorker(QThread):
    finished = pyqtSignal(dict, str, object)  # json_data, voice_name, error
    def __init__(self, url, voice_name):
        super().__init__()
        self.url = url
        self.voice_name = voice_name
    def run(self):
        try:
            cache_dir = get_cache_dir()
            os.makedirs(cache_dir, exist_ok=True)
            url_hash = hashlib.sha256(self.url.encode('utf-8')).hexdigest()
            cache_path = os.path.join(cache_dir, url_hash + '.json')
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                self.finished.emit(json_data, self.voice_name, None)
                return
            resp = requests.get(self.url)
            resp.raise_for_status()
            json_data = resp.json()
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f)
            self.finished.emit(json_data, self.voice_name, None)
        except Exception as e:
            self.finished.emit({}, self.voice_name, e)

class VoiceBrowser(QDialog):
    _instance = None

    @classmethod
    def get_instance(cls, parent=None):
        # If the instance doesn't exist or is not visible, create a new one
        if cls._instance is None or not cls._instance.isVisible():
            cls._instance = VoiceBrowser(parent)
            # When the dialog is closed, clear the instance
            cls._instance.finished.connect(lambda: setattr(cls, "_instance", None))
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self.setWindowTitle("DX7 Voice Browser")
        self.setModal(False)
        self.resize(200, 400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("Search voices...")
        layout.addWidget(self.search_box)
        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)
        self.bank_label = QLabel(self)
        self.bank_label.setText("")
        layout.addWidget(self.bank_label)
        controls_layout = QHBoxLayout()
        self.channel_combo = QComboBox(self)
        self.channel_combo.addItems([str(i) for i in range(1, 17)] + ["Omni"])
        controls_layout.addWidget(QLabel("MIDI Channel:"))
        controls_layout.addWidget(self.channel_combo)
        self.send_button = QPushButton("Send", self)
        controls_layout.addWidget(self.send_button)
        layout.addLayout(controls_layout)
        self.status_bar = QStatusBar(self)
        self.status_bar.setStyleSheet("QStatusBar { margin: 0; padding: 0; border: none; }")
        layout.addWidget(self.status_bar)
        self.voices = []
        self.filtered_voices = []
        self.search_box.textChanged.connect(self.filter_voices)
        self.send_button.clicked.connect(self.send_voice)
        self.list_widget.itemDoubleClicked.connect(lambda _: self.send_voice())
        self.list_widget.itemClicked.connect(self.on_voice_clicked)
        self.search_box.setMinimumWidth(0)
        self.list_widget.setMinimumWidth(0)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setWordWrap(True)
        self.load_voices()
        self.sending = False
        self.send_queue = []

    def set_status(self, msg, error=False):
        if not error:
            self.status_bar.showMessage(msg)
        parent = self.parent() if self.parent() else self
        mw = getattr(parent, 'main_window', parent)
        show_status = getattr(parent, 'show_status', None) or getattr(mw, 'show_status', None)
        if show_status:
            show_status(msg)
        print(msg, file=sys.stderr if error else sys.stdout)

    def load_voices(self):
        try:
            # Cache directory in AppData
            cache_dir = get_cache_dir()
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, VOICE_LIST_CACHE_NAME)
            # Try cache first
            voices = None
            if os.path.exists(cache_path):
                print(f"Opening cached patch_list.json: {cache_path}")
                with open(cache_path, 'r', encoding='utf-8') as f:
                    voices = json.load(f)
            else:
                print(f"Downloading patch_list.json: {VOICE_LIST_URL}")
                resp = requests.get(VOICE_LIST_URL)
                resp.raise_for_status()
                voices = resp.json()
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(voices, f)
            self.voices = voices
            self.set_status(f"Loaded {len(self.voices)} voices.")
            self.filter_voices()
        except Exception as e:
            self.set_status(f"Failed to load voices: {e}", error=True)

    def filter_voices(self):
        query = self.search_box.text().lower()
        self.list_widget.clear()
        self.filtered_voices = [v for v in self.voices if query in v["name"].lower() or query in v.get("author", "").lower()]
        for voice in self.filtered_voices:
            self.list_widget.addItem(QListWidgetItem(f"{voice['name']} - {voice.get('author', '')}"))

    def download_voice(self, idx):
        if self.sending:
            # Queue the request if one is running
            self.send_queue.append(idx)
            return
        self.sending = True
        self.send_button.setEnabled(False)
        voice = self.filtered_voices[idx]
        channel_text = self.channel_combo.currentText()
        url = f"https://patches.fm/patches/single-voice/dx7/{voice['signature'][:2]}/{voice['signature']}.syx"
        self.set_status("Downloading voice...")
        self.download_worker = VoiceDownloadWorker(url, voice["name"])
        try:
            self.download_worker.finished.disconnect()
        except Exception:
            pass
        self.download_worker.finished.connect(lambda syx_data, voice_name, error: self._on_voice_downloaded_wrapper(syx_data, voice, channel_text, error))
        self.download_worker.start()

    def _on_voice_downloaded_wrapper(self, syx_data, voice, channel_text, error):
        self.sending = False
        self.on_voice_downloaded(syx_data, voice, channel_text, error)
        # If there are queued requests, process the next one
        if self.send_queue:
            next_idx = self.send_queue.pop(0)
            self.download_voice(next_idx)

    def send_voice(self):
        idx = self.list_widget.currentRow()
        if idx < 0 or idx >= len(self.filtered_voices):
            self.set_status("No voice selected.", error=True)
            return
        self.download_voice(idx)

    def on_voice_downloaded(self, syx_data, voice, channel_text, error):
        self.send_button.setEnabled(True)
        if error:
            from dialogs import Dialogs
            Dialogs.show_error(self, "Voice Browser Error", f"Failed to download syx: {error}")
            self.set_status(f"Failed to download syx: {error}", error=True)
            return
        # Only log once here:
        self.set_status(f"Downloaded syx file length: {len(syx_data)} bytes")
        if syx_data and syx_data[0] == 0xF0:
            syx_data = syx_data[1:]
        if syx_data and syx_data[-1] == 0xF7:
            syx_data = syx_data[:-1]
        if len(syx_data) == 161 and syx_data[:4] == [0x43, 0x00, 0x09, 0x20]:
            syx_data = syx_data[6:161]
        if len(syx_data) != 155:
            self.set_status(f"Warning: Expected 155 bytes, got {len(syx_data)} bytes.", error=True)
        voice_sysex = [0xF0] + syx_data + [0xF7]
        def rewrite_channel(sysex, ch):
            if len(sysex) > 3:
                sysex[2] = (ch - 1) & 0x0F
        if channel_text != "Omni":
            try:
                channel = int(channel_text)
                rewrite_channel(voice_sysex, channel)
            except Exception as e:
                self.set_status(f"Channel rewrite error: {e}", error=True)
            send_sysex_list = [voice_sysex]
        else:
            send_sysex_list = []
            for ch in range(1, 17):
                sysex = voice_sysex.copy()
                rewrite_channel(sysex, ch)
                send_sysex_list.append(sysex)
        parent = self.parent() if self.parent() else self
        mw = getattr(parent, 'main_window', parent)
        try:
            if hasattr(mw, 'ui') and hasattr(mw.ui, 'out_text'):
                for sysex in send_sysex_list:
                    hex_str = ' '.join(f'{b:02X}' for b in sysex)
                    mw.ui.out_text.setPlainText(hex_str)
                    self.set_status(f"Sending '{voice['name']}'...")
                    if hasattr(mw, 'show_status'):
                        mw.show_status(f"Sending '{voice['name']}'...")
                    if hasattr(mw.midi_ops, 'send_sysex'):
                        mw.midi_ops.send_sysex()
                self.status_bar.clearMessage()
            else:
                if hasattr(mw, 'midi_handler') and hasattr(mw.midi_handler, 'outport') and mw.midi_handler.outport:
                    import mido
                    for sysex in send_sysex_list:
                        try:
                            data = sysex[1:-1] if sysex[0] == 0xF0 and sysex[-1] == 0xF7 else sysex
                            msg = mido.Message('sysex', data=data)
                            mw.midi_handler.outport.send(msg)
                            self.set_status(f"Sent '{voice['name']}' directly to MIDI Out.")
                        except Exception as e:
                            self.set_status(f"Failed to send MIDI: {e}", error=True)
                else:
                    raise AttributeError("Could not access main window Out area and no MIDI Out available.")
        except Exception as e:
            from dialogs import Dialogs
            Dialogs.show_error(self, "Voice Browser Error", f"Could not access main window Out area: {e}")
            self.set_status(f"Could not access main window Out area: {e}", error=True)
            if hasattr(mw, 'show_status'):
                mw.show_status(f"Could not access main window Out area: {e}")

    def on_voice_clicked(self, item):
        idx = self.list_widget.currentRow()
        if idx < 0 or idx >= len(self.filtered_voices):
            self.bank_label.setText("")
            return
        voice = self.filtered_voices[idx]
        sig = voice.get('signature')
        if not sig:
            self.bank_label.setText("")
            return
        json_url = f"https://patches.fm/patches/dx7/{sig[:2]}/{sig}.json"
        self.bank_label.setText("Loading bank info...")
        self.json_worker = VoiceJsonDownloadWorker(json_url, voice['name'])
        self.json_worker.finished.connect(self.on_json_downloaded)
        self.json_worker.start()

    def on_json_downloaded(self, json_data, voice_name, error):
        if error or not json_data:
            self.bank_label.setText("Source: (not available)")
            return
        bank = json_data.get('BANK', '(unknown)')
        author = json_data.get('AUTHOR', '(unknown)')
        # Remove .syx/.SXY suffix from bank name
        if isinstance(bank, str):
            bank = bank.removesuffix('.syx').removesuffix('.SXY').removesuffix('.SYX').removesuffix('.sxy')
        self.bank_label.setText(f"Source: Bank {bank} by {author}")

# For standalone testing
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = VoiceBrowser()
    # Add menubar if running standalone
    menubar = QMenuBar(dlg)
    dlg.layout().setMenuBar(menubar)
    # File menu
    file_menu = QMenu("File", menubar)
    menubar.addMenu(file_menu)
    exit_action = QAction("Exit", dlg)
    exit_action.triggered.connect(dlg.close)
    file_menu.addAction(exit_action)
    # MIDI Out menu (wired up like in main app)
    midi_out_menu = QMenu("MIDI Out", menubar)
    menubar.addMenu(midi_out_menu)
    def populate_out_menu():
        midi_out_menu.clear()
        import re
        from midi_handler import MIDIHandler
        handler = getattr(dlg, 'midi_handler', None)
        if handler is None:
            handler = MIDIHandler()
            dlg.midi_handler = handler
        # Remember last selected port using QSettings (like main app)
        settings = QSettings("MIDISend", "MIDISendApp")
        last_out = settings.value("last_out_port", "")
        ports = sorted(handler.list_output_ports(), key=str.casefold)
        current_out = getattr(handler, 'outport', None)
        current_out_name = current_out.name if current_out else last_out
        for port in ports:
            display_port = re.sub(r'\s*\d+$', '', str(port))
            action = QAction(display_port, dlg)
            action.setCheckable(True)
            if port == current_out_name:
                action.setChecked(True)
            def select_port(checked, p=port):
                handler.open_output(p)
                settings.setValue("last_out_port", p)
            action.triggered.connect(select_port)
            midi_out_menu.addAction(action)
    midi_out_menu.aboutToShow.connect(populate_out_menu)
    dlg.show()
    sys.exit(app.exec())
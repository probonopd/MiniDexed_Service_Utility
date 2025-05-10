import sys
import requests
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QHBoxLayout, QComboBox, QPushButton, QLabel, QApplication, QListWidgetItem, QStatusBar, QMenuBar, QMenu
from PyQt6.QtGui import QAction

VOICE_LIST_URL = "https://patches.fm/patches/dx7/patch_list.json"

class VoiceDownloadWorker(QThread):
    finished = pyqtSignal(list, str, object)  # syx_data, voice_name, error (None if ok)
    def __init__(self, url, voice_name):
        super().__init__()
        self.url = url
        self.voice_name = voice_name
    def run(self):
        import requests
        try:
            resp = requests.get(self.url)
            resp.raise_for_status()
            syx_data = list(resp.content)
            self.finished.emit(syx_data, self.voice_name, None)
        except Exception as e:
            self.finished.emit([], self.voice_name, e)

class VoiceBrowser(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
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

        # MIDI channel dropdown and Send button
        controls_layout = QHBoxLayout()
        self.channel_combo = QComboBox(self)
        self.channel_combo.addItems([str(i) for i in range(1, 17)])
        self.channel_combo.addItem("Omni")
        controls_layout.addWidget(QLabel("MIDI Channel:"))
        controls_layout.addWidget(self.channel_combo)
        self.send_button = QPushButton("Send", self)
        controls_layout.addWidget(self.send_button)
        layout.addLayout(controls_layout)

        # Remove QLabel status bar, use QStatusBar instead
        self.status_bar = QStatusBar(self)
        self.status_bar.setStyleSheet("QStatusBar { margin: 0; padding: 0; border: none; }")
        layout.addWidget(self.status_bar)

        self.voices = []
        self.filtered_voices = []
        self.search_box.textChanged.connect(self.filter_voices)
        self.send_button.clicked.connect(self.send_voice)
        self.list_widget.itemDoubleClicked.connect(lambda _: self.send_voice())

        self.search_box.setMinimumWidth(0)
        self.list_widget.setMinimumWidth(0)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setWordWrap(True)

        self.load_voices()

    def set_status(self, msg, error=False):
        if not error:
            self.status_bar.showMessage(msg)
        if hasattr(self.parent(), 'show_status'):
            self.parent().show_status(msg)
        elif hasattr(self.parent(), 'main_window') and hasattr(self.parent().main_window, 'show_status'):
            self.parent().main_window.show_status(msg)
        # Also print to stdout or stderr
        if error:
            print(msg, file=sys.stderr)
        else:
            print(msg)

    def load_voices(self):
        try:
            resp = requests.get(VOICE_LIST_URL)
            resp.raise_for_status()
            self.voices = resp.json()
            self.set_status(f"Loaded {len(self.voices)} voices.")
            self.filter_voices()
        except Exception as e:
            self.set_status(f"Failed to load voices: {e}", error=True)

    def filter_voices(self):
        query = self.search_box.text().lower()
        self.list_widget.clear()
        self.filtered_voices = [v for v in self.voices if query in v["name"].lower() or query in v.get("author", "").lower()]
        for voice in self.filtered_voices:
            item = QListWidgetItem(f"{voice['name']} - {voice.get('author', '')}")
            self.list_widget.addItem(item)

    def send_voice(self):
        selected = self.list_widget.currentRow()
        if selected < 0 or selected >= len(self.filtered_voices):
            self.set_status("No voice selected.", error=True)
            return
        voice = self.filtered_voices[selected]
        channel_text = self.channel_combo.currentText()
        sig = voice["signature"]
        url = f"https://patches.fm/patches/single-voice/dx7/{sig[:2]}/{sig}.syx"
        self.set_status("Downloading voice...")
        self.send_button.setEnabled(False)
        self.download_worker = VoiceDownloadWorker(url, voice["name"])
        self.download_worker.finished.connect(lambda syx_data, voice_name, error: self.on_voice_downloaded(syx_data, voice, channel_text, error))
        self.download_worker.start()

    def on_voice_downloaded(self, syx_data, voice, channel_text, error):
        self.send_button.setEnabled(True)
        if error:
            from dialogs import Dialogs
            Dialogs.show_error(self, "Voice Browser Error", f"Failed to download syx: {error}")
            self.set_status(f"Failed to download syx: {error}", error=True)
            return
        print(f"Downloaded syx file length: {len(syx_data)} bytes")
        # Remove leading F0 if present
        if syx_data and syx_data[0] == 0xF0:
            syx_data = syx_data[1:]
        # Remove trailing F7 if present
        if syx_data and syx_data[-1] == 0xF7:
            syx_data = syx_data[:-1]
        # Handle 161-byte files: skip header if present
        if len(syx_data) == 161 and syx_data[:4] == [0x43, 0x00, 0x09, 0x20]:
            syx_data = syx_data[6:161]
        if len(syx_data) != 155:
            print(f"Warning: Expected 155 bytes, got {len(syx_data)} bytes.")
        voice_sysex = [0xF0] + syx_data + [0xF7]
        # MIDI channel rewrite for DX7: the third byte (index 2 in voice_sysex) is the channel byte (0x00..0x0F)
        if channel_text != "Omni":
            try:
                channel = int(channel_text)
                if len(voice_sysex) > 3:
                    voice_sysex[2] = (channel - 1) & 0x0F
            except Exception as e:
                print(f"Channel rewrite error: {e}")
            send_sysex_list = [voice_sysex]
        else:
            send_sysex_list = []
            for ch in range(1, 17):
                sysex = voice_sysex.copy()
                if len(sysex) > 3:
                    sysex[2] = (ch - 1) & 0x0F
                send_sysex_list.append(sysex)
        parent = self.parent() if self.parent() else self
        main_window = getattr(parent, 'main_window', parent)
        try:
            if hasattr(main_window, 'ui') and hasattr(main_window.ui, 'out_text'):
                for sysex in send_sysex_list:
                    hex_str = ' '.join(f'{b:02X}' for b in sysex)
                    main_window.ui.out_text.setPlainText(hex_str)
                    self.set_status(f"Loaded '{voice['name']}' into Out area. Sending...")
                    if hasattr(main_window, 'show_status'):
                        main_window.show_status(f"Loaded '{voice['name']}' into Out area. Sending...")
                    if hasattr(main_window.midi_ops, 'send_sysex'):
                        main_window.midi_ops.send_sysex()
            else:
                # If Out area is not accessible, send MIDI directly
                if hasattr(main_window, 'midi_handler') and hasattr(main_window.midi_handler, 'outport') and main_window.midi_handler.outport:
                    import mido
                    for sysex in send_sysex_list:
                        try:
                            # Remove F0 and F7 for mido, as mido expects just the data
                            data = sysex[1:-1] if sysex[0] == 0xF0 and sysex[-1] == 0xF7 else sysex
                            msg = mido.Message('sysex', data=data)
                            main_window.midi_handler.outport.send(msg)
                            self.set_status(f"Sent '{voice['name']}' directly to MIDI Out.")
                        except Exception as e:
                            self.set_status(f"Failed to send MIDI: {e}", error=True)
                else:
                    raise AttributeError("Could not access main window Out area and no MIDI Out available.")
        except Exception as e:
            from dialogs import Dialogs
            Dialogs.show_error(self, "Voice Browser Error", f"Could not access main window Out area: {e}")
            self.set_status(f"Could not access main window Out area: {e}", error=True)
            if hasattr(main_window, 'show_status'):
                main_window.show_status(f"Could not access main window Out area: {e}")

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
        from PyQt6.QtCore import QSettings
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
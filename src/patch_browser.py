import sys
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel, QApplication, QHBoxLayout, QPushButton, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

PATCH_LIST_URL = "https://patches.fm/patches/dx7/patch_list.json"

class PatchDownloadWorker(QThread):
    finished = pyqtSignal(list, str, object)  # syx_data, patch_name, error (None if ok)
    def __init__(self, url, patch_name):
        super().__init__()
        self.url = url
        self.patch_name = patch_name
    def run(self):
        import requests
        try:
            resp = requests.get(self.url)
            resp.raise_for_status()
            syx_data = list(resp.content)
            self.finished.emit(syx_data, self.patch_name, None)
        except Exception as e:
            self.finished.emit([], self.patch_name, e)

class PatchBrowser(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DX7 Voice Browser")
        self.setModal(False)
        self.resize(500, 600)
        layout = QVBoxLayout(self)

        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("Search voices...")
        layout.addWidget(self.search_box)

        self.status_label = QLabel("Loading voices...", self)
        layout.addWidget(self.status_label)

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

        self.patches = []
        self.filtered_patches = []
        self.search_box.textChanged.connect(self.filter_patches)
        self.send_button.clicked.connect(self.send_patch)
        self.list_widget.itemDoubleClicked.connect(lambda _: self.send_patch())

        self.load_patches()

    def load_patches(self):
        try:
            resp = requests.get(PATCH_LIST_URL)
            resp.raise_for_status()
            self.patches = resp.json()
            self.status_label.setText(f"Loaded {len(self.patches)} patches.")
            self.filter_patches()
        except Exception as e:
            self.status_label.setText(f"Failed to load patches: {e}")

    def filter_patches(self):
        query = self.search_box.text().lower()
        self.list_widget.clear()
        self.filtered_patches = [p for p in self.patches if query in p["name"].lower() or query in p.get("author", "").lower()]
        for patch in self.filtered_patches:
            item = QListWidgetItem(f"{patch['name']} - {patch.get('author', '')}")
            self.list_widget.addItem(item)

    def send_patch(self):
        selected = self.list_widget.currentRow()
        if selected < 0 or selected >= len(self.filtered_patches):
            self.status_label.setText("No patch selected.")
            return
        patch = self.filtered_patches[selected]
        channel_text = self.channel_combo.currentText()
        sig = patch["signature"]
        url = f"https://patches.fm/patches/single-voice/dx7/{sig[:2]}/{sig}.syx"
        self.status_label.setText("Downloading patch...")
        self.send_button.setEnabled(False)
        self.download_worker = PatchDownloadWorker(url, patch["name"])
        self.download_worker.finished.connect(lambda syx_data, patch_name, error: self.on_patch_downloaded(syx_data, patch, channel_text, error))
        self.download_worker.start()

    def on_patch_downloaded(self, syx_data, patch, channel_text, error):
        self.send_button.setEnabled(True)
        if error:
            self.status_label.setText(f"Failed to download syx: {error}")
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
        # MIDI channel rewrite for DX7: channel is in the 5th byte (0x20 | (channel-1))
        if channel_text != "Omni":
            try:
                channel = int(channel_text)
                if len(voice_sysex) > 5 and (voice_sysex[4] & 0xF0) == 0x20:
                    voice_sysex[4] = 0x20 | ((channel - 1) & 0x0F)
            except Exception as e:
                print(f"Channel rewrite error: {e}")
            send_sysex_list = [voice_sysex]
        else:
            send_sysex_list = []
            for ch in range(1, 17):
                sysex = voice_sysex.copy()
                if len(sysex) > 5 and (sysex[4] & 0xF0) == 0x20:
                    sysex[4] = 0x20 | ((ch - 1) & 0x0F)
                send_sysex_list.append(sysex)
        parent = self.parent() if self.parent() else self
        main_window = getattr(parent, 'main_window', parent)
        if hasattr(main_window, 'ui') and hasattr(main_window.ui, 'out_text'):
            for sysex in send_sysex_list:
                hex_str = ' '.join(f'{b:02X}' for b in sysex)
                main_window.ui.out_text.setPlainText(hex_str)
                self.status_label.setText(f"Loaded '{patch['name']}' into Out area. Sending...")
                if hasattr(main_window.midi_ops, 'send_sysex'):
                    main_window.midi_ops.send_sysex()
        else:
            self.status_label.setText("Could not access main window Out area.")

# For standalone testing
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = PatchBrowser()
    dlg.show()  # Use show() instead of exec() for non-modal
    sys.exit(app.exec())

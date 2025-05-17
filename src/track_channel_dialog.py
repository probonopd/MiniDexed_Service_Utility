import logging
from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QLabel, QHBoxLayout, QDialogButtonBox

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
        # Only include tracks with at least one note_on
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
            row_layout = QHBoxLayout()
            row_layout.addWidget(combo)
            form.addRow(label, row_layout)
        layout.addLayout(form)
        btn_layout = QHBoxLayout()
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_layout.addWidget(self.buttons)
        layout.addLayout(btn_layout)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.setLayout(layout)
        self.midi = midi
        self.filtered_track_indices = filtered_track_indices

        # Group tracks by name and assign same channel to same name
        name_to_channel = {}
        used_channels = set()
        for idx, (i, track) in enumerate(filtered_tracks):
            name = (track.name if hasattr(track, 'name') and track.name else '').strip().upper()
            if name and name not in name_to_channel:
                # Find next available channel
                for ch in range(16):
                    if ch not in used_channels:
                        name_to_channel[name] = ch
                        used_channels.add(ch)
                        break
        for idx, (i, track) in enumerate(filtered_tracks):
            name = (track.name if hasattr(track, 'name') and track.name else '').strip().upper()
            if name and name in name_to_channel:
                self.channel_boxes[idx].setCurrentIndex(name_to_channel[name])
    def get_assignments(self):
        return [box.currentIndex()+1 for box in self.channel_boxes]

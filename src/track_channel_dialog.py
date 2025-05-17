import os
import json
import difflib
import logging
from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QLabel, QHBoxLayout, QPushButton, QDialogButtonBox, QApplication
from PySide6.QtCore import QTimer
import mido
from voice_browser import get_cache_dir, VOICE_LIST_CACHE_NAME, VoiceBrowser

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
            cache_path = os.path.join(get_cache_dir(), VOICE_LIST_CACHE_NAME)
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    voices = json.load(f)
            logging.debug(f"Loaded {len(voices)} voices from {cache_path}")
            if voices:
                logging.debug(f"Sample voice: {voices[0]}")
            else:
                logging.warning("Voice list is empty after loading.")
        except Exception as e:
            voices = []
            logging.error(f"Error loading voices: {e}")

        def suggest_voice(track_name):
            if not track_name:
                logging.debug(f"No track name provided for suggestion.")
                return None
            tn = track_name.lower().strip()
            # Always assign 'melody' to 'E.Piano 1'
            if tn == 'melody':
                logging.debug(f"Track name 'melody' matched. Forcing suggestion to 'E.Piano 1'.")
                return 'E.Piano 1'
            # Exact match
            for v in voices:
                if v.get('name','').lower().strip() == tn:
                    logging.debug(f"Exact match for track '{track_name}': {v.get('name','')}")
                    return v['name']
            # Fuzzy: best match by similarity
            voice_names = [v.get('name','') for v in voices]
            matches = difflib.get_close_matches(track_name, voice_names, n=1, cutoff=0.6)
            if matches:
                logging.debug(f"Fuzzy match for track '{track_name}': {matches[0]}")
                return matches[0]
            # Fuzzy: contains
            for v in voices:
                if tn and tn in v.get('name','').lower():
                    logging.debug(f"Contains match for track '{track_name}': {v.get('name','')}")
                    return v['name']
            logging.debug(f"No suggested voice for track '{track_name}'.")
            return None
        # Filter tracks: only include those with at least one note_on
        filtered_tracks = []
        filtered_track_indices = []
        for i, track in enumerate(midi.tracks):
            has_note_on = any(getattr(msg, 'type', None) == 'note_on' and getattr(msg, 'velocity', 0) > 0 for msg in track)
            if has_note_on:
                filtered_tracks.append((i, track))
                filtered_track_indices.append(i)
        self.suggested_voice_objs = [None for _ in filtered_tracks]
        for idx, (i, track) in enumerate(filtered_tracks):
            label = f"Track {i}: {track.name if hasattr(track, 'name') and track.name else ''}".strip()
            combo = QComboBox()
            combo.addItems([str(ch+1) for ch in range(16)] + ["None"])
            combo.setCurrentIndex(idx if idx < 16 else 15)
            self.channel_boxes.append(combo)
            # Suggestion label
            suggestion = suggest_voice(getattr(track, 'name', ''))
            # Find the actual voice object (if any)
            voice_obj = None
            if suggestion:
                for v in voices:
                    if v.get('name','') == suggestion:
                        voice_obj = v
                        break
            self.suggested_voice_objs[idx] = voice_obj
            suggestion_lbl = QLabel(f"Suggested: {suggestion}" if suggestion else "")
            self.suggestion_labels.append(suggestion_lbl)
            row_layout = QHBoxLayout()
            row_layout.addWidget(combo)
            row_layout.addWidget(suggestion_lbl)
            form.addRow(label, row_layout)
        layout.addLayout(form)
        btn_layout = QHBoxLayout()
        self.send_voices_btn = QPushButton("Send Voices")
        self.send_voices_btn.clicked.connect(self.send_voices)
        btn_layout.addWidget(self.send_voices_btn)
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
        self._active_workers = []  # Keep references to running QThreads
    def get_assignments(self):
        return [box.currentIndex()+1 for box in self.channel_boxes]
    def send_voices(self):
        logging.info("Sending voices to MIDI channels")
        midi_handler = getattr(QApplication.instance(), "midi_handler", None)
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
        logging.info(f"Voice to channel mapping: {voice_to_channel}")
        for idx, sugg in enumerate(self.suggestions):
            if sugg and sugg in voice_to_channel:
                self.channel_boxes[idx].setCurrentIndex(voice_to_channel[sugg])
        logging.info("Sending channel assignment SysEx")
        for idx, (sugg, box) in enumerate(zip(self.suggestions, self.channel_boxes)):
            if not sugg:
                continue
            channel = box.currentIndex() + 1
            if channel <= 0 or channel > 16:
                continue
            sysex = [0xF0, 0x7D, 0x21, channel-1, 0x00, 0x02, 0x00, channel-1, 0xF7]
            msg = mido.Message('sysex', data=sysex[1:-1])
            logging.info(f"Setting TG{channel-1} to MIDI channel {channel}")
            QApplication.instance().midi_handler.send_sysex(msg.bytes())
        # Send voice SysEx for each channel/voice assignment (async)
        def send_voice_sysex(idx, voice_obj, channel):
            from voice_browser import VoiceBrowser
            def on_syx_data(syx_data, voice_name, error):
                # Remove worker from active list after finishing
                if worker in self._active_workers:
                    self._active_workers.remove(worker)
                if error or not syx_data:
                    logging.warning(f"Track {idx}: Could not get syx data for '{voice_obj.get('name','')}', skipping. Error: {error}")
                    return
                if len(syx_data) > 3:
                    syx_data[2] = 0x10 | ((channel-1) & 0x0F)
                if syx_data[0] != 0xF0:
                    syx_data = [0xF0] + syx_data
                if syx_data[-1] != 0xF7:
                    syx_data = syx_data + [0xF7]
                data_bytes = syx_data[1:-1]
                if any(b < 0 or b > 127 for b in data_bytes):
                    logging.error(f"Track {idx}: Skipping SysEx for '{voice_obj.get('name','')}' to channel {channel}: bytes out of range 0..127: {data_bytes}")
                    return
                msg = mido.Message('sysex', data=data_bytes)
                logging.info(f"Track {idx}: Sending voice SysEx to MIDI channel {channel}: {syx_data}")
                app = QApplication.instance()
                midi_handler = getattr(app, "midi_handler", None)
                midi_handler.send_sysex(msg.bytes())
                logging.info(f"Track {idx}: Sent voice SysEx for '{voice_obj.get('name','')}' to channel {channel}")
            worker = VoiceBrowser.get_syx_data_for_voice_async(voice_obj, on_syx_data)
            if worker is not None:
                self._active_workers.append(worker)
        for idx, (voice_obj, box) in enumerate(zip(self.suggested_voice_objs, self.channel_boxes)):
            if not voice_obj:
                logging.info(f"Track {idx}: No suggested voice object, skipping.")
                continue
            channel = box.currentIndex() + 1
            if channel <= 0 or channel > 16:
                logging.info(f"Track {idx}: Invalid channel {channel}, skipping.")
                continue
            send_voice_sysex(idx, voice_obj, channel)

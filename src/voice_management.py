# voice_management.py
"""
Voice management logic for performance editor.
Includes voice selection dialog, voice editor opening, and voice dump handling.
"""
from performance_fields import PERFORMANCE_FIELDS
from PySide6.QtWidgets import QPushButton, QSpinBox

def select_voice_dialog(table, main_window, row, col):
    from voice_browser import VoiceBrowser
    dlg = VoiceBrowser.show_singleton(main_window=main_window)
    midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
    channel_widget = table.cellWidget(midi_channel_row, col)
    channel_index = None
    if channel_widget is not None:
        if channel_widget.metaObject().className() == "QComboBox":
            idx = channel_widget.currentIndex()
            if idx < 16:
                channel_index = idx
            else:
                channel_index = 16
        elif isinstance(channel_widget, QSpinBox):
            channel_value = channel_widget.value()
            if 1 <= channel_value <= 16:
                channel_index = channel_value - 1
            else:
                channel_index = 16
    if channel_index is not None and hasattr(dlg, "channel_combo"):
        dlg.channel_combo.setCurrentIndex(channel_index)
    def on_voice_selected():
        idx = dlg.list_widget.currentRow()
        if idx >= 0 and idx < len(dlg.filtered_voices):
            voice = dlg.filtered_voices[idx]
            name = voice['name']
            midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
            for c in range(8):
                channel_widget = table.cellWidget(midi_channel_row, c)
                channel_index = None
                if channel_widget is not None:
                    if channel_widget.metaObject().className() == "QComboBox":
                        idx_ch = channel_widget.currentIndex()
                        if idx_ch < 16:
                            channel_index = idx_ch
                        else:
                            channel_index = 16
                    elif isinstance(channel_widget, QSpinBox):
                        channel_value = channel_widget.value()
                        if 1 <= channel_value <= 16:
                            channel_index = channel_value - 1
                        else:
                            channel_index = 16
                vb_channel_idx = dlg.channel_combo.currentIndex()
                if channel_index == vb_channel_idx:
                    btn = table.cellWidget(PERFORMANCE_FIELDS.index("Voice"), c)
                    if isinstance(btn, QPushButton):
                        btn.setText(name)
    dlg.list_widget.itemDoubleClicked.connect(lambda _: on_voice_selected())
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()

def open_voice_editor(table, main_window, row, col, voice_dump_data):
    midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
    channel_widget = table.cellWidget(midi_channel_row, col)
    channel = 1
    if channel_widget is not None:
        if channel_widget.metaObject().className() == "QComboBox":
            idx = channel_widget.currentIndex()
            if idx < 16:
                channel = idx + 1
        elif isinstance(channel_widget, QSpinBox):
            channel = channel_widget.value()
    voice_bytes = None
    if voice_dump_data and col in voice_dump_data:
        voice_bytes = bytes(voice_dump_data[col])
    midi_outport = getattr(main_window, 'midi_handler', None)
    if midi_outport and hasattr(midi_outport, 'outport'):
        midi_outport = midi_outport.outport
    from voice_editor_panel import VoiceEditorPanel
    VoiceEditorPanel.show_singleton(parent=main_window, midi_outport=midi_outport, voice_bytes=voice_bytes)
    editor = VoiceEditorPanel.get_instance()
    if hasattr(editor, 'channel_combo'):
        editor.channel_combo.setCurrentIndex(channel - 1)

def on_voice_dump(table, main_window, data, voice_dump_data, pending_voice_dumps):
    from single_voice_dump_decoder import SingleVoiceDumpDecoder
    from PySide6.QtWidgets import QPushButton, QSpinBox
    if data and data[0] == 0xF0:
        data = data[1:]
    if data and data[-1] == 0xF7:
        data = data[:-1]
    if not data or len(data) < 155:
        return
    if data[0] != 0x43:
        return
    midi_channel = data[1] & 0x0F
    decoder = SingleVoiceDumpDecoder(data)
    if not decoder.is_valid():
        return
    voice_row = PERFORMANCE_FIELDS.index("Voice")
    midi_channel_row = PERFORMANCE_FIELDS.index("MIDIChannel")
    voice_name = decoder.get_param("VNAM")
    for tg in range(8):
        channel_widget = table.cellWidget(midi_channel_row, tg)
        tg_channel = None
        if channel_widget is not None:
            if channel_widget.metaObject().className() == "QComboBox":
                idx = channel_widget.currentIndex()
                if idx < 16:
                    tg_channel = idx
                else:
                    tg_channel = None
            elif isinstance(channel_widget, QSpinBox):
                channel_value = channel_widget.value()
                if 1 <= channel_value <= 16:
                    tg_channel = channel_value - 1
                else:
                    tg_channel = None
        if tg_channel is not None and tg_channel == midi_channel:
            cell_widget = table.cellWidget(voice_row, tg)
            btn = None
            if cell_widget is not None:
                for child in cell_widget.findChildren(QPushButton):
                    btn = child
                    break
            if btn is not None:
                btn.setText(str(voice_name))
            voice_dump_data[tg] = data
            pending_voice_dumps.discard(tg)

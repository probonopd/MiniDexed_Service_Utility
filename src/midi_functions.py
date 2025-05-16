# Utility functions for MIDI channel assignment and related operations

def set_tg_to_channels(table, performance_fields):
    """Set TG1-8 to MIDI channel 1-8 in the given table."""
    midi_channel_row = performance_fields.index("MIDIChannel")
    for col in range(8):
        widget = table.cellWidget(midi_channel_row, col)
        if widget is not None and widget.metaObject().className() == "QComboBox":
            widget.setCurrentIndex(col)
        elif hasattr(widget, 'setValue'):
            widget.setValue(col + 1)

def set_all_tg_to_ch1(table, performance_fields):
    """Set all TGs to MIDI channel 1 in the given table."""
    midi_channel_row = performance_fields.index("MIDIChannel")
    for col in range(8):
        widget = table.cellWidget(midi_channel_row, col)
        if widget is not None and widget.metaObject().className() == "QComboBox":
            widget.setCurrentIndex(0)
        elif hasattr(widget, 'setValue'):
            widget.setValue(1)

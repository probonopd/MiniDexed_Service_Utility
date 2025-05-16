# performance_fields.py
# Contains static data and mappings for performance editor

TG_FIELDS = [
    "Voice",  # New field for voice name/button
    "MIDIChannel", "BankNumber", "VoiceNumber", "Volume", "Pan", "Detune", "Cutoff", "Resonance", "NoteLimitLow", "NoteLimitHigh", "NoteShift", "ReverbSend", "PitchBendRange", "PitchBendStep", "PortamentoMode", "PortamentoGlissando", "PortamentoTime", "MonoMode", "ModulationWheelRange", "ModulationWheelTarget", "FootControlRange", "FootControlTarget", "BreathControlRange", "BreathControlTarget", "AftertouchRange", "AftertouchTarget"
]

GLOBAL_FIELDS = [
    "CompressorEnable", "ReverbEnable", "ReverbSize", "ReverbHighDamp", "ReverbLowDamp", "ReverbLowPass", "ReverbDiffusion", "ReverbLevel"
]

PERFORMANCE_FIELDS = TG_FIELDS + GLOBAL_FIELDS

PERFORMANCE_FIELD_RANGES = {
    "CompressorEnable": (0, 1),
    "ReverbEnable": (0, 1),
    "ReverbSize": (0, 99),
    "ReverbHighDamp": (0, 99),
    "ReverbLowDamp": (0, 99),
    "ReverbLowPass": (0, 99),
    "ReverbDiffusion": (0, 99),
    "ReverbLevel": (0, 99),
    "BankNumber": (0, 127),
    "VoiceNumber": (0, 31),
    "MIDIChannel": (0, 17),
    "Volume": (0, 127),
    "Pan": (0, 127),
    "Detune": (-99, 99),
    "Cutoff": (0, 127),
    "Resonance": (0, 127),
    "NoteLimitLow": (0, 127),
    "NoteLimitHigh": (0, 127),
    "NoteShift": (-24, 24),
    "ReverbSend": (0, 127),
    "PitchBendRange": (0, 12),
    "PitchBendStep": (0, 12),
    "PortamentoMode": (0, 1),
    "PortamentoGlissando": (0, 1),
    "PortamentoTime": (0, 99),
    "MonoMode": (0, 1),
    "ModulationWheelRange": (0, 127),
    "ModulationWheelTarget": (0, 127),
    "FootControlRange": (0, 127),
    "FootControlTarget": (0, 127),
    "BreathControlRange": (0, 127),
    "BreathControlTarget": (0, 127),
    "AftertouchRange": (0, 127),
    "AftertouchTarget": (0, 127)
}

TG_LABELS = [f"TG{i+1}" for i in range(8)]

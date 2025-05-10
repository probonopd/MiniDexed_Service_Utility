from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QCheckBox, QComboBox, QGroupBox, QDialogButtonBox, QScrollArea, QWidget, QTabWidget, QApplication, QTextEdit
from PyQt6.QtCore import Qt
from PyQt6 import QtGui, QtCore
import ftplib
import io
import re

# Define global GPIO pin range for all *Pin fields
pin_range_from = 0
pin_range_to = 27

# Field type and options hints derived from minidexed.ini documentation
FIELD_HINTS = {
    # Sound device
    'SoundDevice': {'type': 'enum', 'options': ['i2s', 'pwm', 'hdmi']},
    'SampleRate': {'type': 'int', 'min': 8000, 'max': 192000},
    'ChunkSize': {'type': 'int', 'min': 32, 'max': 2048},
    'DACI2CAddress': {'type': 'int', 'min': 0, 'max': 127},
    'ChannelsSwapped': {'type': 'bool'},
    'EngineType': {'type': 'enum', 'options': ['1', '2', '3'], 'labels': ['1 (Modern)', '2 (Mark I)', '3 (OPL)']},
    # MIDI
    'MIDIBaudRate': {'type': 'int', 'min': 1200, 'max': 1000000},
    'MIDIThru': {'type': 'str'},
    'IgnoreAllNotesOff': {'type': 'bool'},
    'MIDIAutoVoiceDumpOnPC': {'type': 'bool'},
    'HeaderlessSysExVoices': {'type': 'bool'},
    'MIDIRXProgramChange': {'type': 'bool'},
    'ExpandPCAcrossBanks': {'type': 'bool'},
    'PerformanceSelectChannel': {'type': 'int', 'min': 0, 'max': 32},
    # HD44780 LCD
    'LCDEnabled': {'type': 'bool'},
    'LCDPinEnable': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'LCDPinRegisterSelect': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'LCDPinReadWrite': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'LCDPinData4': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'LCDPinData5': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'LCDPinData6': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'LCDPinData7': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'LCDI2CAddress': {'type': 'hex'},
    # SSD1306 LCD
    'SSD1306LCDI2CAddress': {'type': 'hex'},
    'SSD1306LCDWidth': {'type': 'int', 'min': 32, 'max': 256},
    'SSD1306LCDHeight': {'type': 'int', 'min': 16, 'max': 128},
    'SSD1306LCDRotate': {'type': 'bool'},
    'SSD1306LCDMirror': {'type': 'bool'},
    # ST7789 LCD
    'SPIBus': {'type': 'int', 'min': 0, 'max': 1, 'allow_empty': True},
    'ST7789Enabled': {'type': 'bool'},
    'ST7789Data': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to, 'allow_empty': True},
    'ST7789Select': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to, 'allow_empty': True},
    'ST7789Reset': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to, 'allow_empty': True},
    'ST7789Backlight': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to, 'allow_empty': True},
    'ST7789Width': {'type': 'int', 'min': 0, 'max': 480},
    'ST7789Height': {'type': 'int', 'min': 0, 'max': 480},
    'ST7789Rotation': {'type': 'enum', 'options': ['0', '90', '180', '270']},
    'ST7789SmallFont': {'type': 'bool'},
    'LCDColumns': {'type': 'int', 'min': 1, 'max': 28},
    'LCDRows': {'type': 'int', 'min': 1, 'max': 8},
    # GPIO Button Navigation
    'ButtonPinPrev': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinNext': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinBack': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinSelect': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinHome': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinShortcut': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinPgmUp': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinPgmDown': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinBankUp': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinBankDown': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinTGUp': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'ButtonPinTGDown': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    # Timeouts
    'DoubleClickTimeout': {'type': 'int', 'min': 0, 'max': 5000},
    'LongPressTimeout': {'type': 'int', 'min': 0, 'max': 5000},
    # MIDI Button Navigation
    'MIDIButtonCh': {'type': 'int', 'min': 0, 'max': 32},
    'MIDIButtonNotes': {'type': 'bool'},
    'MIDIButtonPrev': {'type': 'int', 'min': 0, 'max': 127},
    'MIDIButtonNext': {'type': 'int', 'min': 0, 'max': 127},
    'MIDIButtonBack': {'type': 'int', 'min': 0, 'max': 127},
    'MIDIButtonSelect': {'type': 'int', 'min': 0, 'max': 127},
    'MIDIButtonHome': {'type': 'int', 'min': 0, 'max': 127},
    'MIDIButtonPgmUp': {'type': 'int', 'min': 0, 'max': 127},
    'MIDIButtonPgmDown': {'type': 'int', 'min': 0, 'max': 127},
    'MIDIButtonBankUp': {'type': 'int', 'min': 0, 'max': 127},
    'MIDIButtonBankDown': {'type': 'int', 'min': 0, 'max': 127},
    'MIDIButtonTGUp': {'type': 'int', 'min': 0, 'max': 127},
    'MIDIButtonTGDown': {'type': 'int', 'min': 0, 'max': 127},
    # Rotary Encoder
    'EncoderEnabled': {'type': 'bool'},
    'EncoderPinClock': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    'EncoderPinData': {'type': 'int', 'min': pin_range_from, 'max': pin_range_to},
    # Debug
    'MIDIDumpEnabled': {'type': 'bool'},
    'ProfileEnabled': {'type': 'bool'},
    # Network
    'NetworkEnabled': {'type': 'bool'},
    'NetworkDHCP': {'type': 'bool'},
    'NetworkType': {'type': 'enum', 'options': ['wlan', 'ethernet']},
    'NetworkHostname': {'type': 'str'},
    'NetworkIPAddress': {'type': 'str'},
    'NetworkSubnetMask': {'type': 'str'},
    'NetworkDefaultGateway': {'type': 'str'},
    'NetworkDNSServer': {'type': 'str'},
    'NetworkFTPEnabled': {'type': 'bool'},
    'NetworkSyslogEnabled': {'type': 'bool'},
    'NetworkSyslogServerIPAddress': {'type': 'str'},
    # Performance
    'PerformanceSelectToLoad': {'type': 'int', 'min': 0, 'max': 127},
    # Arturia
    'DAWControllerEnabled': {'type': 'bool'},
    # USB
    'USBGadget': {'type': 'bool'},
}

FIELD_TOOLTIPS = {
    # System Options
    'ToneGenerators': "Number of Tone Generators. On a Raspberry Pi 4 or above, can be 8 or 16 (default 8). On Pi V1/Zero, fixed at 1. Pi V2, V3, Zero 2: fixed at 8",
    'Polyphony': "Polyphony per Tone Generator. Default and max depend on Pi version. Pi V1: default/max 8. Pi V2/V3/Zero 2: default/max 16. Pi V4: default 24, max 32. Pi V5: default/max 32. Higher values may cause glitches",
    # Sound device
    'SoundDevice': "Sound device: pwm (headphone jack, default, worst quality), hdmi (HDMI output, better), i2s (i2s DAC, best). Choose to match your hardware",
    'SampleRate': "Sample rate for audio output. Best left at default",
    'ChunkSize': "Audio chunk size. Best left at default",
    'DACI2CAddress': "I2C address of your i2s DAC. 0 for autodetect. Can be decimal or hex (0x...)",
    'ChannelsSwapped': "Swap left/right stereo channels (due to hardware)",
    'EngineType': "Synth engine: 1=Modern (24-bit, default), 2=Mark I (DX7), 3=OPL Series",
    'QuadDAC8Chan': "Advanced (Pi 5 only): Use four I2S DACs for 8 mono outputs (one per TG). No effects/pan. See documentation for details",
    'MasterVolume': "Overall synth volume (0=muted, 128=loudest, default 64)",
    # MIDI
    'MIDIBaudRate': "MIDI bus speed. Normally 31250",
    'MIDIThru': "Forward MIDI messages to another device. See documentation for details",
    'MIDIRXProgramChange': "Enable receiving MIDI Program Change messages",
    'IgnoreAllNotesOff': "Ignore All Notes Off messages",
    'MIDIAutoVoiceDumpOnPC': "Send MIDI sysex dumps on program change",
    'HeaderlessSysExVoices': "Accept headerless SysEx voice bank files",
    'ExpandPCAcrossBanks': "Map Program Change 0..127 to 4 banks",
    'PerformanceSelectChannel': "0: PC/Bank select voices per TG. 1-16: PC/Bank on this channel select performances. >16: Any channel selects performances",
    'MIDISystemCCVol': "Enable separate MIDI CC control of TG volume. 0=not used. 1-7: see documentation for CC maps",
    'MIDISystemCCPan': "Enable separate MIDI CC control of TG pan. 0=not used. 1-7: see documentation for CC maps",
    'MIDISystemCCDetune': "Enable separate MIDI CC control of TG detune. 0=not used. 1-7: see documentation for CC maps",
    'MIDIGlobalExpression': "If nonzero, respond to MIDI CC 11 (Expression) on this channel as global. 0: per-channel only",
    'USBGadget': "1: Enable USB Gadget (device) mode. See documentation!",
    'USBGadgetPin': "When USBGadget=1, this pin LOW enables gadget mode, HIGH enables host mode",
    # LCD
    'LCDEnabled': "Enable HD44780 or SSD1306 display",
    # HD44780 LCD
    'LCDPinEnable': "GPIO pin for HD44780 Enable",
    'LCDPinRegisterSelect': "GPIO pin for HD44780 Register Select",
    'LCDPinReadWrite': "GPIO pin for HD44780 Read/Write",
    'LCDPinData4': "GPIO pin for HD44780 Data4",
    'LCDPinData5': "GPIO pin for HD44780 Data5",
    'LCDPinData6': "GPIO pin for HD44780 Data6",
    'LCDPinData7': "GPIO pin for HD44780 Data7",
    'LCDI2CAddress': "I2C address for HD44780. 0x00 for direct GPIO, 0x27 for i2c backpack",
    # SSD1306 OLED
    'SSD1306LCDI2CAddress': "I2C address for SSD1306 OLED (usually 0x3c)",
    'SSD1306LCDWidth': "Width of SSD1306 OLED (usually 128)",
    'SSD1306LCDHeight': "Height of SSD1306 OLED (32 or 64)",
    'SSD1306LCDRotate': "Rotate SSD1306 display 180°",
    'SSD1306LCDMirror': "Mirror SSD1306 display",
    'LCDColumns': "Number of columns for LCD (e.g. 16, 20)",
    'LCDRows': "Number of rows for LCD (e.g. 2, 4)",
    # ST7789 SPI
    'SPIBus': "SPI bus number (0 for default). Leave blank if not used",
    'ST7789Enabled': "Enable ST7789 display",
    'ST7789Data': "GPIO pin for ST7789 Data",
    'ST7789Select': "GPIO pin for ST7789 Select (CE0/CE1)",
    'ST7789Reset': "GPIO pin for ST7789 Reset",
    'ST7789Backlight': "GPIO pin for ST7789 Backlight",
    'ST7789Width': "Width of ST7789 display (e.g. 240)",
    'ST7789Height': "Height of ST7789 display (e.g. 240)",
    'ST7789Rotation': "Display rotation: 0, 90, 180, 270",
    'ST7789SmallFont': "Use small font on ST7789 display",
    # Buttons
    'ButtonPinPrev': "GPIO pin for Previous button (0 to disable)",
    'ButtonActionPrev': "Action for Previous button (click, doubleclick, longpress)",
    'ButtonPinNext': "GPIO pin for Next button (0 to disable)",
    'ButtonActionNext': "Action for Next button",
    'ButtonPinBack': "GPIO pin for Back button",
    'ButtonActionBack': "Action for Back button",
    'ButtonPinSelect': "GPIO pin for Select button",
    'ButtonActionSelect': "Action for Select button",
    'ButtonPinHome': "GPIO pin for Home button",
    'ButtonActionHome': "Action for Home button",
    'ButtonPinShortcut': "GPIO pin for Shortcut button",
    # Program/Bank/TG selection
    'ButtonPinPgmUp': "GPIO pin for Program Up button",
    'ButtonActionPgmUp': "Action for Program Up button",
    'ButtonPinPgmDown': "GPIO pin for Program Down button",
    'ButtonActionPgmDown': "Action for Program Down button",
    'ButtonPinBankUp': "GPIO pin for Bank Up button",
    'ButtonActionBankUp': "Action for Bank Up button",
    'ButtonPinBankDown': "GPIO pin for Bank Down button",
    'ButtonActionBankDown': "Action for Bank Down button",
    'ButtonPinTGUp': "GPIO pin for TG Up button",
    'ButtonActionTGUp': "Action for TG Up button",
    'ButtonPinTGDown': "GPIO pin for TG Down button",
    'ButtonActionTGDown': "Action for TG Down button",
    # Timeouts
    'DoubleClickTimeout': "Timeout for double click (ms)",
    'LongPressTimeout': "Timeout for long press (ms). Must be >= DoubleClickTimeout",
    # MIDI Button Navigation
    'MIDIButtonCh': "MIDI channel for button navigation. 0=OFF, 1-16=Ch, >16=Omni",
    'MIDIButtonNotes': "Use MIDI NoteOn/NoteOff as navigation buttons",
    'MIDIButtonPrev': "MIDI CC/Note for Previous button",
    'MIDIButtonNext': "MIDI CC/Note for Next button",
    'MIDIButtonBack': "MIDI CC/Note for Back button",
    'MIDIButtonSelect': "MIDI CC/Note for Select button",
    'MIDIButtonHome': "MIDI CC/Note for Home button",
    'MIDIButtonPgmUp': "MIDI CC/Note for Program Up button",
    'MIDIButtonPgmDown': "MIDI CC/Note for Program Down button",
    'MIDIButtonBankUp': "MIDI CC/Note for Bank Up button",
    'MIDIButtonBankDown': "MIDI CC/Note for Bank Down button",
    'MIDIButtonTGUp': "MIDI CC/Note for TG Up button",
    'MIDIButtonTGDown': "MIDI CC/Note for TG Down button",
    # Rotary Encoder
    'EncoderEnabled': "Enable rotary encoder",
    'EncoderPinClock': "GPIO pin for rotary encoder clock",
    'EncoderPinData': "GPIO pin for rotary encoder data",
    # Debug
    'MIDIDumpEnabled': "Show incoming MIDI on HDMI display",
    'ProfileEnabled': "Show CPU usage on HDMI display",
    # Network
    'NetworkEnabled': "Enable network connectivity",
    'NetworkDHCP': "Use DHCP for network configuration",
    'NetworkType': "wlan: WiFi, ethernet: Wired",
    'NetworkHostname': "Network hostname",
    'NetworkIPAddress': "Static IP address",
    'NetworkSubnetMask': "Static subnet mask",
    'NetworkDefaultGateway': "Static default gateway",
    'NetworkDNSServer': "Static DNS server",
    'NetworkFTPEnabled': "Enable FTP server",
    'NetworkSyslogEnabled': "Enable syslog server",
    'NetworkSyslogServerIPAddress': "Syslog server IP address",
    # Performance
    'PerformanceSelectToLoad': "Performance to load at startup",
    # Arturia
    'DAWControllerEnabled': "Enable Arturia DAW controller mode",
}

def categorize_section(section, section_keys=None):
    # If any key in the section contains 'Button', assign to Buttons
    if section_keys and any('button' in k.lower() for k in section_keys):
        return "Buttons"
    s = section.lower()
    if 'midi button' in s:
        return "Buttons"
    if any(k in s for k in ["sound", "system", "dac", "engine", "volume"]):
        return "Sound"
    if "midi" in s:
        return "MIDI"
    if any(k in s for k in ["lcd", "display", "oled", "hd44780", "ssd1306", "st7789"]):
        return "Display"
    if any(k in s for k in ["button", "timeout", "encoder", "navigation"]):
        return "Buttons"
    if "network" in s or "ftp" in s or "dhcp" in s:
        return "Network"
    if "debug" in s or "profile" in s:
        return "Debug"
    if any(k in s for k in ["performance", "arturia", "usb", "general"]):
        return "Other"
    return None

CATEGORY_ORDER = ['Sound', 'MIDI', 'Display', 'Buttons', 'Network', 'Debug', 'Other']

class IniEditorDialog(QDialog):
    def __init__(self, parent, ini_text, syslog_ip=None):
        super().__init__(parent)
        self.setWindowTitle("Edit minidexed.ini")
        self.setMinimumWidth(700)
        self.resize(self.minimumWidth(), 600)
        # Limit height to available screen size
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            max_height = screen_geometry.height() - 80  # leave some margin for taskbar
            self.setMaximumHeight(max_height)
        self.widgets = {}
        self.lines = []
        self.key_to_lineidx = {}
        self.section_order = []
        self.section_map = {}
        self.syslog_ip = syslog_ip
        self._parse_ini(ini_text)
        # Pre-fill NetworkSyslogServerIPAddress if empty and syslog_ip is provided (before widget creation)
        if self.syslog_ip:
            idx = self.key_to_lineidx.get('NetworkSyslogServerIPAddress')
            if idx is not None:
                linetype, data = self.lines[idx]
                key, value, comment, orig = data
                if not value:
                    self.lines[idx] = ('setting', (key, self.syslog_ip, comment, f'{key}={self.syslog_ip}{" " + comment if comment else ""}'))

        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        # Group sections by improved category logic
        category_sections = {cat: [] for cat in CATEGORY_ORDER}
        for section in self.section_order:
            # Gather all keys in this section
            section_keys = []
            for idx in self.section_map[section]:
                linetype, data = self.lines[idx]
                if linetype == 'setting':
                    key = data[0]
                    section_keys.append(key)
            cat = categorize_section(section, section_keys) or 'Other'
            category_sections[cat].append(section)
        for cat in CATEGORY_ORDER:
            if not category_sections[cat]:
                continue
            tab_content = QWidget()
            tab_layout = QVBoxLayout(tab_content)
            for section in category_sections[cat]:
                # Check if section has at least one setting (not just comments/blanks)
                has_setting = any(
                    self.lines[idx][0] == 'setting' for idx in self.section_map[section]
                )
                if not has_setting:
                    continue  # skip sections with only comments/blanks
                group = QGroupBox(section)
                group_layout = QVBoxLayout(group)
                visible = False
                for idx in self.section_map[section]:
                    linetype, data = self.lines[idx]
                    row = QHBoxLayout()
                    row.setAlignment(Qt.AlignmentFlag.AlignTop)
                    if linetype == 'setting':
                        key, value, comment, orig = data
                        hints = FIELD_HINTS.get(key)
                        is_checkbox = hints and hints.get('type') == 'bool'
                        desc = FIELD_TOOLTIPS.get(key, comment)
                        label = QLabel(key)
                        label.setFixedWidth(180)
                        if is_checkbox:
                            # Use description as checkbox text, styled as normal, but only prepend 'Enable' if not already a verb
                            cb_text = desc.rstrip('.') if desc else 'Enable option'
                            widget = self._make_widget(key, value)
                            widget.setText(cb_text)
                            self.widgets[key] = widget
                            # Remove setFixedWidth for widget, let it expand
                            row.addWidget(label, alignment=Qt.AlignmentFlag.AlignTop)
                            row.addWidget(widget, alignment=Qt.AlignmentFlag.AlignTop)
                            group_layout.addLayout(row)
                            visible = True
                        else:
                            desc_lbl = QLabel(desc)
                            desc_lbl.setWordWrap(True)
                            desc_lbl.setStyleSheet("color: #888; font-size: 8pt;")
                            widget = self._make_widget(key, value)
                            self.widgets[key] = widget
                            widget.setFixedWidth(200)
                            col_layout = QVBoxLayout()
                            col_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                            col_layout.addWidget(widget)
                            col_layout.addWidget(desc_lbl)
                            row.addWidget(label, alignment=Qt.AlignmentFlag.AlignTop)
                            row.addLayout(col_layout)
                            group_layout.addLayout(row)
                            visible = True
                    else:
                        if linetype == 'comment':
                            # Only show comment if it does not equal the group/section name (case-insensitive, strip # and whitespace)
                            comment_text = data.strip()
                            section_name = section.strip().lower()
                            # Remove leading '#' and whitespace for comparison and display
                            if comment_text.startswith('#'):
                                comment_text = comment_text[1:].lstrip()
                            if comment_text.lower() == section_name:
                                continue  # skip this comment
                            comment_lbl = QLabel(comment_text)
                            comment_lbl.setStyleSheet("color: gray; font-style: italic;")
                            row.addWidget(comment_lbl)
                            row.addWidget(QLabel(""))
                            group_layout.addLayout(row)
                            visible = True
                        elif linetype == 'blank':
                            row.addWidget(QLabel(""))
                            row.addWidget(QLabel(""))
                            group_layout.addLayout(row)
                group_layout.addStretch(1)
                if visible:
                    tab_layout.addWidget(group)
            tab_layout.addStretch(1)
            # Make only the tab content scrollable (default appearance)
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            # No padding
            scroll.setContentsMargins(0, 0, 0, 0)
            tab_content.setContentsMargins(0, 0, 0, 0)
            scroll.setWidget(tab_content)
            tabs.addTab(scroll, cat)
        # Add .ini file tab (read-only)
        ini_tab = QWidget()
        ini_layout = QVBoxLayout(ini_tab)
        ini_text = QTextEdit()
        ini_text.setReadOnly(True)
        ini_text.setPlainText(self.get_text())
        ini_layout.addWidget(ini_text)
        tabs.addTab(ini_tab, ".ini file")

        tabs.setContentsMargins(0, 0, 0, 0)
        tabs.setStyleSheet("QTabWidget::pane { border: 0px; }")
        layout.addWidget(tabs)
        # Add documentation link below the tabbed widget
        doc_link = QLabel('<a href="https://github.com/probonopd/MiniDexed/wiki/Files#minidexedini">minidexed.ini documentation</a>')
        doc_link.setOpenExternalLinks(True)

        layout.addWidget(doc_link)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _parse_ini(self, ini_text):
        section = "General"
        self.section_order = [section]
        self.section_map = {section: []}
        prev_blank = True  # Track if previous line was blank
        for line in ini_text.splitlines():
            orig = line
            line = line.rstrip("\r\n")
            if not line.strip():
                idx = len(self.lines)
                self.lines.append(('blank', ''))
                self.section_map[section].append(idx)
                prev_blank = True
                continue
            if prev_blank and line.strip().startswith('#'):
                # Section header if line is like '# Section' and previous line was blank
                m = re.match(r'#\s*([A-Za-z0-9 /\-]+)$', line.strip())
                if m:
                    section = m.group(1).strip()
                    if section not in self.section_order:
                        self.section_order.append(section)
                        self.section_map[section] = []
                idx = len(self.lines)
                self.lines.append(('comment', line))
                self.section_map[section].append(idx)
                prev_blank = False
                continue
            # Setting: key=value (may have inline comment)
            m = re.match(r'([^#=\s][^=]*)=([^#]*)(#.*)?$', line)
            if m:
                key = m.group(1).strip()
                value = m.group(2).strip()
                comment = m.group(3).strip() if m.group(3) else ''
                idx = len(self.lines)
                self.lines.append(('setting', (key, value, comment, orig)))
                self.key_to_lineidx[key] = idx
                self.section_map[section].append(idx)
                prev_blank = False
                continue
            # Fallback: treat as comment
            idx = len(self.lines)
            self.lines.append(('comment', line))
            self.section_map[section].append(idx)
            prev_blank = False

    def _make_widget(self, key, value):
        # Special handling for Action fields
        if 'action' in key.lower() and (
            key.lower().startswith('buttonaction') or key.lower().startswith('buttonaction') or 'button' in key.lower() or 'action' in key.lower()):
            cb = QComboBox()
            options = ['None', 'click', 'doubleclick', 'longpress']
            cb.addItems(options)
            if value in options:
                cb.setCurrentIndex(options.index(value))
            else:
                cb.setCurrentIndex(0)
            return cb
        hints = FIELD_HINTS.get(key)
        # Handle fields that allow empty values
        if hints and hints.get('allow_empty'):
            le = QLineEdit()
            le.setText(value)
            le.setPlaceholderText('(empty)')
            if hints.get('type') == 'int':
                le.setValidator(QtGui.QIntValidator())
            return le
        # Enum (ComboBox)
        if hints and hints.get('type') == 'enum':
            cb = QComboBox()
            options = hints.get('options', [])
            cb.addItems(options)
            # Use labels if present
            if 'labels' in hints:
                for i, label in enumerate(hints['labels']):
                    cb.setItemText(i, label)
            if value in options:
                cb.setCurrentIndex(options.index(value))
            return cb
        # Boolean (CheckBox)
        if hints and hints.get('type') == 'bool':
            cb = QCheckBox()
            cb.setChecked(value == '1')
            return cb
        # Integer (SpinBox)
        if hints and hints.get('type') == 'int':
            sb = QSpinBox()
            sb.setMinimum(hints.get('min', 0))
            sb.setMaximum(hints.get('max', 1000000))
            try:
                sb.setValue(int(value))
            except Exception:
                sb.setValue(sb.minimum())
            return sb
        # Hex (LineEdit with validator)
        if hints and hints.get('type') == 'hex':
            le = QLineEdit()
            le.setText(value)
            le.setPlaceholderText('0x00')
            # Accept hex or decimal
            le.setValidator(QtGui.QRegularExpressionValidator(QtCore.QRegularExpression(r'^(0x[0-9a-fA-F]+|\d*)$')))
            return le
        # Default: line edit
        le = QLineEdit()
        le.setText(value)
        return le

    def get_text(self):
        # Reconstruct ini file from widgets and original lines
        out = []
        for idx, (linetype, data) in enumerate(self.lines):
            if linetype == 'setting':
                key, value, comment, orig = data
                widget = self.widgets.get(key)
                if widget is None:
                    out.append(orig)
                    continue
                hints = FIELD_HINTS.get(key)
                if hints and hints.get('allow_empty'):
                    v = widget.text().strip()
                elif isinstance(widget, QCheckBox):
                    v = '1' if widget.isChecked() else '0'
                elif isinstance(widget, QSpinBox):
                    v = str(widget.value())
                elif isinstance(widget, QComboBox):
                    # If this is an Action dropdown, blank for 'None'
                    if widget.findText('None') != -1 and widget.currentText() == 'None':
                        v = ''
                    else:
                        v = widget.currentText().split(' ')[0]
                elif isinstance(widget, QLineEdit):
                    v = widget.text()
                else:
                    v = value
                line = f"{key}={v}"
                if comment:
                    line += f" {comment}"
                out.append(line)
            else:
                out.append(data)
        return '\n'.join(out)

def download_ini_file(device_ip):
    ftp = ftplib.FTP()
    ftp.connect(device_ip, 21, timeout=10)
    ftp.login("admin", "admin")
    ftp.set_pasv(True)
    ini_io = io.BytesIO()
    ftp.retrbinary('RETR /SD/minidexed.ini', ini_io.write)
    ftp.close() # CLose without sending BYE, do not use ftp.quit() because it would reboot the device
    return ini_io.getvalue().decode('utf-8', errors='replace')

def upload_ini_file(device_ip, ini_text):
    from dialogs import Dialogs
    import sys
    ftp = None
    try:
        ftp = ftplib.FTP()
        ftp.connect(device_ip, 21, timeout=10)
        ftp.login("admin", "admin")
        ftp.set_pasv(True)
        ini_bytes = ini_text.encode('utf-8')
        # Upload to .new first
        remote_new = '/SD/minidexed.ini.new'
        remote_final = '/SD/minidexed.ini'
        try:
            ftp.storbinary(f'STOR {remote_new}', io.BytesIO(ini_bytes))
        except Exception as e:
            Dialogs.show_error(None, "FTP Error", f"Failed to upload minidexed.ini.new: {e}")
            raise
        # Atomically replace old file with new one
        try:
            try:
                ftp.delete(remote_final)
            except Exception:
                pass
            ftp.rename(remote_new, remote_final)
        except Exception as e:
            Dialogs.show_error(None, "FTP Error", f"Failed to rename minidexed.ini.new to minidexed.ini: {e}")
            raise
        # Send BYE after upload/rename
        try:
            ftp.sendcmd("BYE")
        except Exception:
            pass
    except Exception as e:
        Dialogs.show_error(None, "FTP Error", f"FTP error: {e}")
        raise
    finally:
        if ftp is not None:
            try:
                ftp.quit()
            except Exception:
                pass

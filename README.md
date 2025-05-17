# MiniDexed Service Utility

## Overview

The MiniDexed Service Utility is a comprehensive tool for interacting with, testing, and updating [MiniDexed](https://github.com/probonopd/MiniDexed) and other MIDI devices. It supports sending/receiving MIDI and SysEx, device log monitoring, firmware updates, and advanced editing of device configuration and voices.

![image](https://github.com/user-attachments/assets/5cfe3a3e-b405-49a2-a72c-3052a35d60f9)

## Features

### MIDI Out Panel
- **Send MIDI/SysEx**: Enter or paste MIDI or SysEx data in hexadecimal and send to the selected MIDI Out port.
- **Send .mid**: Use the File menu to send a standard MIDI file, with progress and status updates.
- **Stop**: Interrupt a MIDI file transfer in progress.
- **Clear Out**: Clear the MIDI Out text area.

### MIDI In Panel
- **Receive MIDI/SysEx**: View incoming MIDI and SysEx messages from the selected MIDI In port, formatted for readability.
- **Clear In**: Clear the MIDI In text area.

### Syslog Panel
- **Syslog Server**: Built-in syslog server (port 8514) for device logs. Displays IP/port and a live, structured table of messages.

### Performance Editor
- **Edit Performances**: Edit and send full MiniDexed performance dumps, manage per-TG voices, and assign MIDI channels.

### Voice Editor
- **Edit Voices**: Graphical DX7 voice editor with envelopes, operator controls, and real-time parameter changes.

### minidexed.ini Editor
- **Edit Device Config**: Edit minidexed.ini with validation, upload/download, and categorized settings.

### Status Bar
- **Live Feedback**: Status and error messages shown in the status bar and printed to the console.

### MIDI Command Library
- **MIDI Commands Menu**: Library of common MIDI/SysEx commands, organized by device/function.
- **Parameter Dialogs**: Set command parameters with sliders/text boxes; only shown if multiple values are possible.
- **Device Number & Channel Handling**: Shown as 1–16 to user, sent as 0–15 to hardware.

### File Operations
- **Open/Save SysEx**: Load/save SysEx files (.syx) to/from MIDI Out area.
- **Save MIDI In**: Save received MIDI data as a standard MIDI file (.mid).

### Device Firmware Updater
- **Update MiniDexed**: Launch updater from File menu.
- **Device Discovery**: Devices auto-discovered via mDNS/zeroconf; menu enabled when devices found.
- **Release Selection**: Choose official, continuous, local, or PR builds.
- **Performances Option**: Optionally update Performances directory (overwrites all performances).

### MID Browser
- **Browse and Send MIDI Files**: Search, browse, and download MIDI files from an online repository. Double-click to send a MIDI file directly to your selected MIDI Out port. Optionally filter out bank/voice changes before sending. Provides a searchable list interface and status updates.

### Voice Browser
- **Browse and Send DX7 Voices**: Search and browse a large online library of DX7 voices (patches) by name or author. Select a voice to send it to your device on a chosen MIDI channel. Supports direct editing in either the classic Voice Editor or the graphical Voice Editor Panel. Downloads and caches voice SysEx data as needed, and displays source bank and author info.

## How to Use

1. **Start the Application**  
   Launch the program. The main window appears with MIDI Out, MIDI In, and Syslog panels.
2. **Select MIDI Ports**  
   Use the MIDI Out/In menus to select ports. Only available ports are shown; last used ports are remembered.
3. **Send MIDI/SysEx**  
   Enter/paste data in MIDI Out and click "Send" or use the File menu to send a .mid file.
4. **Receive MIDI/SysEx**  
   Incoming messages appear in MIDI In, formatted for readability.
5. **Monitor Syslog**  
   Syslog messages from your device are displayed in a structured table.
6. **Use MIDI Commands**  
   Access the MIDI Commands menu for device-specific commands. Set parameters as needed.
7. **Edit Performances/Voices/INI**  
   Use the menus to open the Performance Editor, Voice Editor, or INI Editor for advanced device editing.
8. **Update MiniDexed**  
   Use the File menu to open the updater, select device/release, and start the update.
9. **Browse and Send MIDI Files**  
   Use the MID Browser to search and browse for MIDI files. Double-click a file to send it to the selected MIDI Out port.
10. **Browse and Send DX7 Voices**  
    Use the Voice Browser to search and browse DX7 voices. Select a voice to send it to your device, or edit it in the Voice Editor.
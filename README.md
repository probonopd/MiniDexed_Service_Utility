# MiniDexed Service Utility

## Overview

The MiniDexed Service Utility is a graphical application for advanced interaction, testing, and updating of MiniDexed and other MIDI devices. It allows sending and receiving MIDI and SysEx messages, monitoring device logs, and updating device firmware.

## Features

### MIDI Out Panel
- **Send MIDI/SysEx**: Enter or paste MIDI or SysEx data in hexadecimal format and send it to your selected MIDI Out port.
- **Send .mid**: Use the File menu to send a standard MIDI file to your device, with real-time progress and status updates.
- **Stop**: Interrupt a MIDI file transfer in progress.
- **Clear Out**: Clear the MIDI Out text area.

### MIDI In Panel
- **Receive MIDI/SysEx**: View incoming MIDI and SysEx messages from your selected MIDI In port. Each message is displayed in hexadecimal, with a blank line after each for readability.
- **Clear In**: Clear the MIDI In text area.

### Syslog Panel

The tool includes a syslog server for logging messages from your MiniDexed device. The syslog server is enabled by default and listens on port 514.
You need to configure your MiniDexed device to send syslog messages to the IP address of the computer running this tool.

- **Syslog Server Info**: The panel displays the IP address and port on which the syslog server is listening.
- **Live Syslog Table**: View syslog messages from your MiniDexed device in a structured, non-editable table with columns for time, index, IP, service, and message.

### Status Bar
- **Live Feedback**: All status and error messages are shown in the status bar at the bottom of the window and also printed to the console for logging.

### MIDI Port Management
- **Automatic Discovery**: MIDI In and Out ports are listed in the menus, with trailing numbers removed for clarity.
- **Robust Selection**: If a port is unavailable, an error dialog is shown and the application continues running.
- **Last Used Ports**: The tool remembers your last selected MIDI In and Out ports.

### MIDI Command Library
- **MIDI Commands Menu**: Access a library of common MIDI and SysEx commands, organized by device and function.
- **Parameter Dialogs**: For commands with parameters, a dialog allows you to set values using sliders and text boxes. Parameters with only one possible value are not shown.
- **Device Number & Channel Handling**: Device numbers and channels are shown as 1–16 to the user, but sent as 0–15 to the hardware as required.

### File Operations
- **Open/Save SysEx**: Load and save SysEx files (.syx) to and from the MIDI Out area.
- **Save MIDI In**: Save received MIDI data as a standard MIDI file (.mid).

### Device Firmware Updater
- **Update MiniDexed**: Use the File menu to launch the updater.
- **Device Discovery**: Devices are automatically discovered on your network using mDNS/zeroconf. The update menu is only enabled when at least one device is found.
- **Release Selection**: Choose between the latest official release, continuous build, local build (from a selected folder), or a pull request build (by PR number or URL).
- **Performances Option**: Optionally update the Performances directory (overwriting all existing performances) via a checkbox.
- **Progress Dialog**: See real-time status and a progress bar during the update. Cancel or close the dialog at any time.

## How to Use

1. **Start the Application**  
   Launch the program. The main window will appear with MIDI Out, MIDI In, and Syslog panels.

2. **Select MIDI Ports**  
   Use the MIDI Out and MIDI In menus to select your desired ports. Only available ports are shown, and the last used ports are remembered.

3. **Send MIDI/SysEx**  
   - Enter or paste MIDI/SysEx data in the MIDI Out area and click "Send".
   - Use the File menu to send a .mid file to your device.

4. **Receive MIDI/SysEx**  
   Incoming messages appear in the MIDI In area, formatted for readability.

5. **Monitor Syslog**  
   Syslog messages from your device are displayed in a structured table. You can select and copy rows for analysis.

6. **Use MIDI Commands**  
   Access the MIDI Commands menu for a library of device-specific commands. Set parameters as needed in the dialogs.

7. **Update MiniDexed**  
   - Use the File menu to open the updater.
   - Wait for device discovery (the menu is enabled when a device is found).
   - Select the release type and device, and optionally enable Performances update.
   - Click "Start Update" and monitor progress in the dedicated dialog.

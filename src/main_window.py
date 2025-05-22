import os
from PySide6.QtWidgets import QMainWindow, QMessageBox, QFileDialog, QApplication, QComboBox
from PySide6.QtGui import QAction
from ui_main_window import UiMainWindow
from menus import setup_menus
from file_ops import FileOps
from midi_ops import MidiOps
from midi_handler import MIDIHandler
from workers import LogWorker, MIDIReceiveWorker, MidiSendWorker, SyslogWorker, FirewallCheckWorker
from dialogs import Dialogs
from PySide6.QtCore import QSettings
import re
from updater_dialog import UpdaterDialog, UpdaterProgressDialog
from updater_worker import UpdaterWorker, DeviceDiscoveryWorker
import sys
import subprocess
from windows_firewall_checker import WindowsFirewallChecker
import mido # Added import

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MiniDexed Service Utility")
        self.resize(800, 500)
        self.settings = QSettings("MIDISend", "MIDISendApp")
        
        # MIDIHandler is now a QObject and needs to be instantiated properly.
        # It should not be on QApplication.instance() if it's specific to MainWindow logic.
        # If it truly needs to be globally accessible, a different singleton pattern might be needed.
        # For now, let's assume it's owned by MainWindow.
        self.midi_handler = MIDIHandler() 
        # Connect MIDIHandler signals to MainWindow slots or other handlers
        # self.midi_handler.log_message.connect(self.show_status) # Or a more specific log handler
        # self.midi_handler.sysex_received.connect(self._maybe_forward_any)
        # self.midi_handler.note_on_received.connect(self._maybe_forward_any)
        # self.midi_handler.note_off_received.connect(self._maybe_forward_any)
        # self.midi_handler.control_change_received.connect(self._maybe_forward_any)
        # Instead, use the generic forward callback:
        self.midi_handler.set_forward_callback(self._maybe_forward_any)

        self.ui = UiMainWindow(self)
        self.file_ops = FileOps(self)
        self.midi_ops = MidiOps(self)
        self.device_list = []  # List of (name, ip) -- moved up before setup_menus
        setup_menus(self)
        self.update_device_actions()  # Ensure menu items are enabled if devices already found
        self.init_workers()
        self.restore_last_ports()
        self.statusBar()  # Ensure status bar is created
        self.update_action = None  # Will be set in menus.py
        self.edit_ini_action = None  # Will be set in menus.py
        self.device_discovery_worker = DeviceDiscoveryWorker()
        self.device_discovery_worker.device_found.connect(self.add_discovered_device)
        self.device_discovery_worker.device_removed.connect(self.remove_discovered_device)
        self.device_discovery_worker.device_updated.connect(self.update_discovered_device)
        self.device_discovery_worker.log.connect(self.show_status)
        self.device_discovery_worker.start()
        self.device_dialogs = []  # Track open device selection dialogs
        self.firewall_worker = FirewallCheckWorker()
        self.firewall_worker.result.connect(self.handle_firewall_check_result)
        self.firewall_worker.start()
        self.setup_midi_io_ui()
        # Ensure MIDI In-to-Out forwarding is set up immediately
        # self.start_receiving() # This is now implicitly handled by midi_handler.set_input_port

    def setup_midi_io_ui(self):
        # Setup MIDI input/output combo boxes
        # These are now part of UiMainWindow, assuming they are named self.ui.midi_in_combo etc.
        # If they are created here, ensure they are added to a layout.
        # Example if they are direct members of MainWindow:
        # self.midi_in_combo = QComboBox()
        # self.midi_out_combo = QComboBox()
        # self.ui.some_layout.addWidget(self.midi_in_combo) # Example add to layout
        # self.ui.some_layout.addWidget(self.midi_out_combo) # Example add to layout
        
        # Connect UI combo box signals if they are managed here
        # Assuming they are part of self.ui and named appropriately in ui_main_window.py
        if hasattr(self.ui, 'midi_in_combo') and hasattr(self.ui, 'midi_out_combo'):
            self.ui.midi_in_combo.currentIndexChanged.connect(self.on_midi_in_changed_ui)
            self.ui.midi_out_combo.currentIndexChanged.connect(self.on_midi_out_changed_ui)
        else:
            print("[UI WARNING] MIDI combo boxes not found on self.ui. Connections skipped.")

    def handle_firewall_check_result(self, has_rule, current_profile, rule_profiles, enabled_profiles, disabled_profiles, has_block):
        profile_display = current_profile.capitalize() if current_profile else "Unknown"
        needs_dialog = (not has_rule) or (current_profile in disabled_profiles) or has_block
        if not needs_dialog:
            print(f"Firewall rule exists for this application and current network profile: {profile_display}")
        else:
            # Log to the status bar that the Windows firewall is preventing the application from discovering devices on the network
            msg = f"Windows firewall is preventing the application from discovering devices on the network."
            self.statusBar().showMessage(msg)
            print(msg)

    def init_workers(self):
        self.receive_worker = None
        self.log_worker = LogWorker()
        def log_to_status_and_stdout(msg):
            self.statusBar().showMessage(msg)
            print(msg)
            # Update syslog label if this is the syslog server message
            if msg.startswith("Syslog server listening on "):
                import re
                m = re.match(r"Syslog server listening on ([^:]+):(\d+)", msg)
                if m:
                    ip, port = m.groups()
                    if hasattr(self.ui, 'update_syslog_label'):
                        self.ui.update_syslog_label(ip, port)
        self.log_worker.log.connect(log_to_status_and_stdout)
        self.log_worker.start()
        # Only start syslog server if port is available
        import socket
        SYSLOG_PORT = 8514
        syslog_port_available = True
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_sock.bind(("0.0.0.0", SYSLOG_PORT))
            test_sock.close()
        except OSError:
            syslog_port_available = False
        if syslog_port_available:
            self.syslog_worker = SyslogWorker()
            self.syslog_worker.syslog_message.connect(self.ui.append_syslog)
            self.syslog_worker.log.connect(log_to_status_and_stdout)
            self.syslog_worker.start()
        else:
            self.log_worker.add_message(f"Syslog port {SYSLOG_PORT} is not available. Syslog server will not start.")
            self.syslog_worker = None

    def restore_last_ports(self):
        last_in = self.settings.value("last_in_port", "")
        last_out = self.settings.value("last_out_port", "")
        
        self.ui.refresh_ports() # This populates combo boxes with names from MIDIHandler

        # Set the MIDI handler's ports first. This will start listeners.
        if last_out:
            self.show_status(f"[UI] Restoring last MIDI Out: '{last_out}'")
            self.midi_handler.open_output(last_out)
        else: # Ensure a default or no port state is explicitly set if nothing was saved
            self.midi_handler.open_output(None)

        if last_in:
            self.show_status(f"[UI] Restoring last MIDI In: '{last_in}'")
            try:
                self.midi_handler.open_input(last_in)
            except Exception as e:
                self.show_status(f"[ERROR] Could not open MIDI In '{last_in}': {e}")
                self.midi_handler.open_input(None)
        else: # Ensure a default or no port state is explicitly set
            self.midi_handler.open_input(None)

        # Now, update the UI to reflect the state of MIDIHandler
        # This should happen *after* MIDIHandler has tried to open the ports,
        # so current_input_port_name and current_output_port_name are accurate.
        current_ui_in_port = self.midi_handler.current_input_port_name
        current_ui_out_port = self.midi_handler.current_output_port_name

        if hasattr(self.ui, 'midi_in_combo'):
            if current_ui_in_port and current_ui_in_port in [self.ui.midi_in_combo.itemText(i) for i in range(self.ui.midi_in_combo.count())]:
                self.ui.midi_in_combo.setCurrentText(current_ui_in_port)
            elif not current_ui_in_port and self.ui.midi_in_combo.count() > 0:
                 # self.ui.midi_in_combo.setCurrentIndex(-1) # Or select a placeholder if one exists
                 pass # Or select a "None" or placeholder if available
            self.show_status(f"[UI] Restored MIDI In UI to: '{current_ui_in_port or "None"}'")

        if hasattr(self.ui, 'midi_out_combo'):
            if current_ui_out_port and current_ui_out_port in [self.ui.midi_out_combo.itemText(i) for i in range(self.ui.midi_out_combo.count())]:
                self.ui.midi_out_combo.setCurrentText(current_ui_out_port)
            elif not current_ui_out_port and self.ui.midi_out_combo.count() > 0:
                # self.ui.midi_out_combo.setCurrentIndex(-1)
                pass # Or select a "None" or placeholder
            self.show_status(f"[UI] Restored MIDI Out UI to: '{current_ui_out_port or "None"}'")

        # Forwarding should be enabled by default if ports are set
        # The `route_midi_in_to_out_enabled` attribute should be checked by forwarding methods
        self.route_midi_in_to_out_enabled = True # Enable by default
        if hasattr(self.ui, 'route_midi_action') and self.ui.route_midi_action:
            self.ui.route_midi_action.setChecked(True)
        self.show_status("[UI] MIDI In-to-Out forwarding enabled by default.")

    def closeEvent(self, event):
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logging.debug('closeEvent: Stopping MIDI sending')
        self.midi_ops.stop_sending()
        logging.debug('closeEvent: Stopping receive_worker')
        if self.receive_worker:
            self.receive_worker.stop()
            self.receive_worker.wait()
        logging.debug('closeEvent: Stopping log_worker')
        if hasattr(self, 'log_worker') and self.log_worker:
            self.log_worker.stop()
            self.log_worker.wait()
        logging.debug('closeEvent: Stopping syslog_worker')
        if hasattr(self, 'syslog_worker') and self.syslog_worker:
            self.syslog_worker.stop()
            self.syslog_worker.wait()
            self.syslog_worker = None
        logging.debug('closeEvent: Stopping device_discovery_worker')
        if hasattr(self, 'device_discovery_worker') and self.device_discovery_worker:
            self.device_discovery_worker.quit()
            self.device_discovery_worker.wait()
            self.device_discovery_worker = None
        logging.debug('closeEvent: Stopping firewall_worker')
        if hasattr(self, 'firewall_worker') and self.firewall_worker:
            self.firewall_worker.quit()
            self.firewall_worker.wait()
            self.firewall_worker = None
        logging.debug('closeEvent: Closing midi_handler')
        self.midi_handler.close()
        logging.debug('closeEvent: Accepting event')
        event.accept()
        QApplication.quit()

    def _maybe_forward_any(self, msg):
        # Log every incoming message
        print(f"[MIDI FORWARD DEBUG] _maybe_forward_any called with: {msg!r} (type: {type(msg)})")
        # [MIDI FORWARD DEBUG] _maybe_forward_any called with: Message('note_on', channel=0, note=74, velocity=35, time=0) (type: <class 'mido.messages.messages.Message'>)

        if not getattr(self, 'route_midi_in_to_out_enabled', False) or not self.midi_handler:
            print(f"[MIDI FORWARD DEBUG] Not forwarding: routing_disabled={not getattr(self, 'route_midi_in_to_out_enabled', False)} or no midi_handler")
            return

        can_send = self.midi_handler.udp_output_active or (self.midi_handler.outport and not getattr(self.midi_handler.outport, 'closed', True))
        if not can_send:
            print("[MIDI FORWARD DEBUG] No valid MIDI output configured in MIDIHandler.")
            return

        # Log where the message will be forwarded and print bytes
        if self.midi_handler.udp_output_active:
            midi_bytes = msg.bytes()
            hex_str = ' '.join(f'{b:02X}' for b in midi_bytes)
            print(f"[MIDI FORWARD DEBUG] Forwarding to UDP MIDI output: {hex_str}")
        elif self.midi_handler.outport:
            midi_bytes = msg.bytes()
            hex_str = ' '.join(f'{b:02X}' for b in midi_bytes)
            print(f"[MIDI FORWARD DEBUG] Forwarding to MIDI outport {self.midi_handler.current_output_port_name}: {hex_str}")
        else:
            print("[MIDI FORWARD DEBUG] No output port to forward to.")

        if isinstance(msg, list):
            self.midi_handler.send_sysex(msg)
        elif hasattr(msg, 'type') and hasattr(msg, 'bytes'):
            self.midi_handler.send_mido_message(msg)
        else:
            print(f"[MIDI FORWARD DEBUG] Unknown message type for forwarding: {type(msg)}")

    def show_status(self, msg):
        self.statusBar().showMessage(msg)
        print(msg)

    def log(self, msg):
        if msg.startswith("Syslog server listening on "):
            m = re.match(r"Syslog server listening on ([^:]+):(\d+)", msg)
            if m:
                ip, port = m.groups()
                if hasattr(self.ui, 'update_syslog_label'):
                    self.ui.update_syslog_label(ip, port)

    def add_discovered_device(self, name, ip):
        # Remove any existing device with this IP
        self.device_list = [(n, i) for n, i in self.device_list if i != ip]
        self.device_list.append((name, ip))
        self.show_status(f"Device discovered: {name} ({ip})")
        self.update_device_actions()
        self.update_device_dialogs()

    def remove_discovered_device(self, name, ip):
        self.device_list = [(n, i) for n, i in self.device_list if i != ip]
        self.show_status(f"Device removed: {name} ({ip})")
        self.update_device_actions()
        self.update_device_dialogs()

    def update_discovered_device(self, name, ip):
        # Just update the name for the IP if present
        updated = False
        new_list = []
        for n, i in self.device_list:
            if i == ip:
                new_list.append((name, ip))
                updated = True
            else:
                new_list.append((n, i))
        if not updated:
            new_list.append((name, ip))
        self.device_list = new_list
        self.show_status(f"Device updated: {name} ({ip})")
        self.update_device_actions()
        self.update_device_dialogs()

    def update_device_actions(self):
        # Enable/disable update and upload actions based on device_list
        has_device = bool(self.device_list)
        if self.update_action:
            self.update_action.setEnabled(has_device)
        if self.edit_ini_action:
            self.edit_ini_action.setEnabled(has_device)

    def update_device_dialogs(self):
        # Update all open device selection dialogs with the latest device list
        for dlg in self.device_dialogs:
            if hasattr(dlg, 'device_combo'):
                dlg.device_combo.clear()
                for name, ip in self.device_list:
                    dlg.device_combo.addItem(f"{name} ({ip})", ip)

    def show_updater_dialog(self):
        # Skip dialog if only one device
        if len(self.device_list) == 1:
            device_ip = self.device_list[0][1]
            dlg = UpdaterDialog(self, device_list=self.device_list)
            dlg.device_combo.setCurrentIndex(0)
            dlg.device_combo.setEnabled(False)
            if dlg.exec():
                update_performances = dlg.update_perf_checkbox.isChecked()
                release_type = dlg.release_combo.currentIndex()
                pr_number = dlg.pr_input.toPlainText().strip()
                device_ip = dlg.device_combo.currentData() or dlg.device_combo.currentText()
                src_path = None
                if release_type == 2:  # Local build
                    from PySide6.QtWidgets import QFileDialog
                    src_path = QFileDialog.getExistingDirectory(self, "Select your src/ folder")
                    if not src_path:
                        return  # User cancelled
                if release_type == 3:  # PR build
                    github_token = self.settings.value("github_token", "")
                    if not github_token:
                        Dialogs.show_error(self, "GitHub Token Required", "A GitHub Personal Access Token is required to download PR build artifacts. Please set it in Preferences.")
                        return
                github_token = self.settings.value("github_token", "")
                progress_dlg = UpdaterProgressDialog(self)
                worker = UpdaterWorker(release_type, pr_number, device_ip, update_performances, github_token=github_token, src_path=src_path)
                worker.status.connect(progress_dlg.set_status)
                worker.progress.connect(progress_dlg.set_progress)
                def on_finished(success, msg):
                    progress_dlg.set_status(msg)
                    if success:
                        progress_dlg.progress.setValue(100)
                        progress_dlg.cancel_btn.setText("Close")
                        progress_dlg.cancel_btn.clicked.disconnect()
                        progress_dlg.cancel_btn.clicked.connect(progress_dlg.accept)
                    else:
                        progress_dlg.reject()
                        Dialogs.show_error(self, "Update Error", msg)
                worker.finished.connect(on_finished)
                worker.finished.connect(worker.deleteLater)
                def cancel_update():
                    if worker.isRunning():
                        worker.terminate()
                    progress_dlg.reject()
                progress_dlg.cancel_btn.clicked.connect(cancel_update)
                worker.start()
                progress_dlg.exec()
            return

        dlg = UpdaterDialog(self, device_list=self.device_list)
        self.device_dialogs.append(dlg)
        dlg.device_combo.clear()
        for name, ip in self.device_list:
            dlg.device_combo.addItem(f"{name} ({ip})", ip)
        result = dlg.exec()
        self.device_dialogs.remove(dlg)
        if result:
            update_performances = dlg.update_perf_checkbox.isChecked()
            release_type = dlg.release_combo.currentIndex()
            pr_number = dlg.pr_input.toPlainText().strip()
            device_ip = dlg.device_combo.currentData() or dlg.device_combo.currentText()
            src_path = None
            if release_type == 2:  # Local build
                from PySide6.QtWidgets import QFileDialog
                src_path = QFileDialog.getExistingDirectory(self, "Select your src/ folder")
                if not src_path:
                    return  # User cancelled
            if release_type == 3:  # PR build
                github_token = self.settings.value("github_token", "")
                if not github_token:
                    Dialogs.show_error(self, "GitHub Token Required", "A GitHub Personal Access Token is required to download PR build artifacts. Please set it in Preferences.")
                    return
            github_token = self.settings.value("github_token", "")
            progress_dlg = UpdaterProgressDialog(self)
            worker = UpdaterWorker(release_type, pr_number, device_ip, update_performances, github_token=github_token, src_path=src_path)
            worker.status.connect(progress_dlg.set_status)
            worker.progress.connect(progress_dlg.set_progress)
            def on_finished(success, msg):
                progress_dlg.set_status(msg)
                if success:
                    progress_dlg.progress.setValue(100)
                    progress_dlg.cancel_btn.setText("Close")
                    progress_dlg.cancel_btn.clicked.disconnect()
                    progress_dlg.cancel_btn.clicked.connect(progress_dlg.accept)
                else:
                    progress_dlg.reject()
                    Dialogs.show_error(self, "Update Error", msg)
            worker.finished.connect(on_finished)
            worker.finished.connect(worker.deleteLater)
            def cancel_update():
                if worker.isRunning():
                    worker.terminate()
                progress_dlg.reject()
            progress_dlg.cancel_btn.clicked.connect(cancel_update)
            worker.start()
            progress_dlg.exec()

    def show_ini_editor_dialog(self):
        from dialogs import DeviceSelectDialog
        from ini_editor import IniEditorDialog
        import difflib
        from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel
        # Skip dialog if only one device
        if len(self.device_list) == 1:
            device_ip = self.device_list[0][1]
        else:
            dlg = DeviceSelectDialog(self, device_list=self.device_list)
            self.device_dialogs.append(dlg)
            dlg.device_combo.clear()
            for name, ip in self.device_list:
                dlg.device_combo.addItem(f"{name} ({ip})", ip)
            if not dlg.exec():
                self.device_dialogs.remove(dlg)
                return
            device_ip = dlg.get_selected_ip()
            self.device_dialogs.remove(dlg)
        try:
            from ini_editor import download_ini_file
            ini_text = download_ini_file(device_ip)
        except Exception as e:
            from dialogs import Dialogs
            Dialogs.show_error(self, "FTP Error", f"Failed to download minidexed.ini: {e}")
            return
        # Find syslog server IP if available
        syslog_ip = None
        if hasattr(self.ui, 'syslog_label'):
            import re
            m = re.search(r'Syslog \(([^:]+):', self.ui.syslog_label.text())
            if m:
                syslog_ip = m.group(1)
        editor = IniEditorDialog(self, ini_text, syslog_ip=syslog_ip)
        if editor.exec():
            new_text = editor.get_text()
            if new_text != ini_text:
                # Show diff and ask for confirmation, with color
                diff = list(difflib.unified_diff(
                    ini_text.splitlines(),
                    new_text.splitlines(),
                    fromfile='minidexed.ini (old)',
                    tofile='minidexed.ini (new)',
                    lineterm=''
                ))
                def colorize_diff(diff_lines):
                    html = []
                    for line in diff_lines:
                        if line.startswith('+') and not line.startswith('+++'):
                            html.append('<span style="color: #228B22;">{}</span>'.format(line.replace('<','&lt;').replace('>','&gt;')))
                        elif line.startswith('-') and not line.startswith('---'):
                            html.append('<span style="color: #B22222;">{}</span>'.format(line.replace('<','&lt;').replace('>','&gt;')))
                        elif line.startswith('@@'):
                            html.append('<span style="color: #888888;">{}</span>'.format(line.replace('<','&lt;').replace('>','&gt;')))
                        elif line.startswith('+++') or line.startswith('---'):
                            html.append('<span style="color: #888888; font-weight: bold;">{}</span>'.format(line.replace('<','&lt;').replace('>','&gt;')))
                        else:
                            html.append('<span style="color: #888888;">{}</span>'.format(line.replace('<','&lt;').replace('>','&gt;')))
                    return '<br>'.join(html)
                diff_html = colorize_diff(diff)
                class DiffDialog(QDialog):
                    def __init__(self, parent, diff_html):
                        super().__init__(parent)
                        self.setWindowTitle("Confirm Upload: minidexed.ini Diff")
                        self.setMinimumWidth(800)
                        layout = QVBoxLayout(self)
                        layout.addWidget(QLabel("Carefully review the changes below. Proceed with upload?"))
                        layout.addWidget(QLabel("This will overwrite the existing minidexed.ini on the device and reboot the device."))
                        layout.addWidget(QLabel("Invalid changes may cause the device to fail to boot."))
                        text = QTextEdit()
                        text.setReadOnly(True)
                        text.setHtml(diff_html)
                        layout.addWidget(text)
                        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
                        self.buttons.accepted.connect(self.accept)
                        self.buttons.rejected.connect(self.reject)
                        layout.addWidget(self.buttons)
                diff_dlg = DiffDialog(self, diff_html)
                if diff_dlg.exec():
                    try:
                        from ini_editor import upload_ini_file
                        upload_ini_file(device_ip, new_text)
                        from dialogs import Dialogs
                        Dialogs.show_message(self, "Success", "minidexed.ini uploaded successfully.\nThe device will reboot.")
                    except Exception as e:
                        from dialogs import Dialogs
                        Dialogs.show_error(self, "FTP Error", f"Failed to upload minidexed.ini: {e}")

    def menu_about(self):
        from dialogs import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()

    # Slot for UI MIDI In ComboBox change
    def on_midi_in_changed_ui(self, idx):
        if hasattr(self.ui, 'midi_in_combo'):
            port_name = self.ui.midi_in_combo.itemText(idx)
            if not port_name: return
            self.show_status(f"[UI] MIDI In ComboBox changed to: '{port_name}'")
            try:
                self.midi_handler.open_input(port_name)
            except Exception as e:
                self.show_status(f"[ERROR] Could not open MIDI In '{port_name}': {e}")
                self.midi_handler.open_input(None)
            self.settings.setValue("last_in_port", port_name)
        else:
            print("[UI ERROR] on_midi_in_changed_ui called but no midi_in_combo found.")

    # Slot for UI MIDI Out ComboBox change (renamed from on_midi_out_changed)
    def on_midi_out_changed_ui(self, idx):
        if hasattr(self.ui, 'midi_out_combo'):
            port_name = self.ui.midi_out_combo.itemText(idx)
            if not port_name: return
            self.show_status(f"[UI] MIDI Out ComboBox changed to: '{port_name}'")
            self.midi_handler.open_output(port_name)
            self.settings.setValue("last_out_port", port_name)
        else:
            print("[UI ERROR] on_midi_out_changed_ui called but no midi_out_combo found.")

    # This method is called by menu actions in menus.py
    def set_in_port_from_menu(self, port_name):
        self.show_status(f"[UI] MIDI In set from menu to: '{port_name}'")
        try:
            self.midi_handler.open_input(port_name)
        except Exception as e:
            self.show_status(f"[ERROR] Could not open MIDI In '{port_name}': {e}")
            self.midi_handler.open_input(None)
        self.settings.setValue("last_in_port", port_name)
        # Refresh combo box before setting value
        if hasattr(self.ui, 'refresh_ports'):
            self.ui.refresh_ports()
        # Debug print all combo box items
        if hasattr(self.ui, 'midi_in_combo'):
            items = [self.ui.midi_in_combo.itemText(i) for i in range(self.ui.midi_in_combo.count())]
            print(f"[DEBUG] MIDI In combo box items: {items}")
            # Normalize comparison: strip and lower
            norm_port = port_name.strip().lower()
            norm_items = [item.strip().lower() for item in items]
            if norm_port in norm_items:
                idx = norm_items.index(norm_port)
                self.ui.midi_in_combo.setCurrentIndex(idx)
            else:
                print(f"[UI WARNING] Selected MIDI In port '{port_name}' not found in combo box after menu selection.")
        else:
            print(f"[UI WARNING] midi_in_combo not found on UI.")

    # This method is called by menu actions in menus.py (newly added for consistency)
    def set_out_port_from_menu(self, port_name):
        self.show_status(f"[UI] MIDI Out set from menu to: '{port_name}'")
        self.midi_handler.open_output(port_name)
        self.settings.setValue("last_out_port", port_name)
        # Refresh combo box before setting value
        if hasattr(self.ui, 'refresh_ports'):
            self.ui.refresh_ports()
        # Debug print all combo box items
        if hasattr(self.ui, 'midi_out_combo'):
            items = [self.ui.midi_out_combo.itemText(i) for i in range(self.ui.midi_out_combo.count())]
            print(f"[DEBUG] MIDI Out combo box items: {items}")
            # Normalize comparison: strip and lower
            norm_port = port_name.strip().lower()
            norm_items = [item.strip().lower() for item in items]
            if norm_port in norm_items:
                idx = norm_items.index(norm_port)
                self.ui.midi_out_combo.setCurrentIndex(idx)
            else:
                print(f"[UI WARNING] Selected MIDI Out port '{port_name}' not found in combo box after menu selection.")
        else:
            print(f"[UI WARNING] midi_out_combo not found on UI.")

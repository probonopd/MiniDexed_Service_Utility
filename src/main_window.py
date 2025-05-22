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
        self.midi_handler = getattr(QApplication.instance(), "midi_handler", None)
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
        self.start_receiving()

    def setup_midi_io_ui(self):
        # Setup MIDI input/output combo boxes
        self.midi_in_combo = QComboBox()
        self.midi_out_combo = QComboBox()
        # ...existing code to populate with real MIDI ports...
        self.midi_in_combo.addItem('UDP MIDI (127.0.0.1:50007)')
        self.midi_out_combo.addItem('UDP MIDI (127.0.0.1:50007)')
        # ...existing code to add to layout...

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
        self.ui.refresh_ports()
        if last_out:
            if last_out == 'UDP MIDI (127.0.0.1:50007)':
                self.midi_handler.use_udp_midi(True, as_input=False)
            self.ui.set_out_port_from_menu(last_out)
        if last_in:
            if last_in == 'UDP MIDI (127.0.0.1:50007)':
                self.midi_handler.use_udp_midi(True, as_input=True)
            self.ui.set_in_port_from_menu(last_in)

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

    def start_receiving(self):
        if hasattr(self, 'receive_worker') and self.receive_worker and self.receive_worker.isRunning():
            self.receive_worker.stop()  # MIDIReceiveWorker.stop() includes a wait() call.
            # self.receive_worker = None # Optional: clear the reference after stopping

        self.receive_worker = MIDIReceiveWorker(self.midi_handler)
        self.receive_worker.log.connect(self.ui.append_log)
        # Forward ALL MIDI In to Out using _maybe_forward_any
        self.receive_worker.sysex_received.connect(self._maybe_forward_any)
        self.receive_worker.note_on_received.connect(self._maybe_forward_any)
        self.receive_worker.note_off_received.connect(self._maybe_forward_any)
        self.receive_worker.control_change_received.connect(self._maybe_forward_any)
        self.receive_worker.other_message_received.connect(self._maybe_forward_any)
        self.receive_worker.start()

    def _maybe_forward_sysex(self, data):
        print(f"[MIDI FORWARD DEBUG] _maybe_forward_sysex called, data len={len(data)}")
        if getattr(self, 'route_midi_in_to_out_enabled', False) and self.midi_handler:
            if getattr(self.midi_handler, 'udp_enabled', False):
                print(f"[MIDI FORWARD DEBUG] Forwarding SysEx to UDP MIDI")
                self.midi_handler.send_sysex(data)
            elif self.midi_handler.outport:
                print(f"[MIDI FORWARD DEBUG] Forwarding SysEx to outport: {self.midi_handler.outport}")
                self.midi_handler.send_sysex(data)
            else:
                print(f"[MIDI FORWARD DEBUG] No valid MIDI out for SysEx")
        else:
            print(f"[MIDI FORWARD DEBUG] Not forwarding SysEx: route_midi_in_to_out_enabled={getattr(self, 'route_midi_in_to_out_enabled', False)}, midi_handler={self.midi_handler}, outport={getattr(self.midi_handler, 'outport', None)}")

    def _maybe_forward_note_on(self, msg):
        print(f"[MIDI FORWARD DEBUG] _maybe_forward_note_on called: {msg}")
        if getattr(self, 'route_midi_in_to_out_enabled', False) and self.midi_handler:
            if getattr(self.midi_handler, 'udp_enabled', False):
                print(f"[MIDI FORWARD DEBUG] Forwarding Note On to UDP MIDI")
                self.midi_handler.send_note_on(msg.channel, msg.note, msg.velocity)
            elif self.midi_handler.outport:
                print(f"[MIDI FORWARD DEBUG] Forwarding Note On to outport: {self.midi_handler.outport}")
                self.midi_handler.outport.send(msg)
            else:
                print(f"[MIDI FORWARD DEBUG] No valid MIDI out for Note On")
        else:
            print(f"[MIDI FORWARD DEBUG] Not forwarding Note On: route_midi_in_to_out_enabled={getattr(self, 'route_midi_in_to_out_enabled', False)}, midi_handler={self.midi_handler}, outport={getattr(self.midi_handler, 'outport', None)}")

    def _maybe_forward_note_off(self, msg):
        print(f"[MIDI FORWARD DEBUG] _maybe_forward_note_off called: {msg}")
        if getattr(self, 'route_midi_in_to_out_enabled', False) and self.midi_handler:
            if getattr(self.midi_handler, 'udp_enabled', False):
                print(f"[MIDI FORWARD DEBUG] Forwarding Note Off to UDP MIDI")
                self.midi_handler.send_note_off(msg.channel, msg.note, msg.velocity)
            elif self.midi_handler.outport:
                print(f"[MIDI FORWARD DEBUG] Forwarding Note Off to outport: {self.midi_handler.outport}")
                self.midi_handler.outport.send(msg)
            else:
                print(f"[MIDI FORWARD DEBUG] No valid MIDI out for Note Off")
        else:
            print(f"[MIDI FORWARD DEBUG] Not forwarding Note Off: route_midi_in_to_out_enabled={getattr(self, 'route_midi_in_to_out_enabled', False)}, midi_handler={self.midi_handler}, outport={getattr(self.midi_handler, 'outport', None)}")

    def _maybe_forward_control_change(self, msg):
        print(f"[MIDI FORWARD DEBUG] _maybe_forward_control_change called: {msg}")
        if getattr(self, 'route_midi_in_to_out_enabled', False) and self.midi_handler:
            if getattr(self.midi_handler, 'udp_enabled', False):
                print(f"[MIDI FORWARD DEBUG] Forwarding Control Change to UDP MIDI")
                self.midi_handler.send_cc(msg.channel, msg.control, msg.value)
            elif self.midi_handler.outport:
                print(f"[MIDI FORWARD DEBUG] Forwarding Control Change to outport: {self.midi_handler.outport}")
                self.midi_handler.outport.send(msg)
            else:
                print(f"[MIDI FORWARD DEBUG] No valid MIDI out for Control Change")
        else:
            print(f"[MIDI FORWARD DEBUG] Not forwarding Control Change: route_midi_in_to_out_enabled={getattr(self, 'route_midi_in_to_out_enabled', False)}, midi_handler={self.midi_handler}, outport={getattr(self.midi_handler, 'outport', None)}")

    def _maybe_forward_other(self, msg):
        print(f"[MIDI FORWARD DEBUG] _maybe_forward_other called: {msg}")
        if getattr(self, 'route_midi_in_to_out_enabled', False) and self.midi_handler:
            if getattr(self.midi_handler, 'udp_enabled', False):
                print(f"[MIDI FORWARD DEBUG] Forwarding Other MIDI to UDP MIDI")
                # You may want to implement more message types here
            elif self.midi_handler.outport:
                print(f"[MIDI FORWARD DEBUG] Forwarding Other MIDI to outport: {self.midi_handler.outport}")
                self.midi_handler.outport.send(msg)
            else:
                print(f"[MIDI FORWARD DEBUG] No valid MIDI out for Other MIDI")
        else:
            print(f"[MIDI FORWARD DEBUG] Not forwarding Other MIDI: route_midi_in_to_out_enabled={getattr(self, 'route_midi_in_to_out_enabled', False)}, midi_handler={self.midi_handler}, outport={getattr(self.midi_handler, 'outport', None)}")

    def _maybe_forward_any(self, msg):
        print(f"[MIDI FORWARD DEBUG] _maybe_forward_any called: {msg}")
        if getattr(self, 'route_midi_in_to_out_enabled', False) and self.midi_handler:
            if getattr(self.midi_handler, 'udp_enabled', False) and self.midi_handler.udp_sock:
                print(f"[MIDI FORWARD DEBUG] Forwarding ANY MIDI to UDP MIDI")
                try:
                    bytes_to_send = None
                    if isinstance(msg, list):  # SysEx payload from sysex_received signal
                        # Wrap with F0 and F7 for UDP transmission as a complete SysEx message
                        bytes_to_send = bytes([0xF0] + msg + [0xF7])
                    elif hasattr(msg, 'bytes') and callable(msg.bytes):  # mido.Message object
                        # msg.bytes() returns a list of integers
                        bytes_to_send = bytes(msg.bytes())
                    else:
                        print(f"[MIDI FORWARD DEBUG] Unknown message type for UDP forwarding: {type(msg)}")
                        return

                    if bytes_to_send is not None:
                        self.midi_handler.udp_sock.sendto(bytes_to_send, (self.midi_handler.udp_host, self.midi_handler.udp_port))
                except Exception as e:
                    print(f"[MIDI FORWARD DEBUG] Error forwarding to UDP: {e}")
            elif self.midi_handler.outport:
                print(f"[MIDI FORWARD DEBUG] Forwarding ANY MIDI to outport: {self.midi_handler.outport}")
                try:
                    message_to_send = None
                    if isinstance(msg, list):  # SysEx payload
                        message_to_send = mido.Message('sysex', data=msg)
                    elif isinstance(msg, mido.Message):  # Already a mido.Message object
                        message_to_send = msg
                    else:
                        print(f"[MIDI FORWARD DEBUG] Unknown message type for outport forwarding: {type(msg)}")
                        return

                    if message_to_send:
                        self.midi_handler.outport.send(message_to_send)
                except Exception as e:
                    print(f"[MIDI FORWARD DEBUG] Error forwarding to outport: {e}")
            else:
                print(f"[MIDI FORWARD DEBUG] No valid MIDI out for ANY MIDI")
        else:
            print(f"[MIDI FORWARD DEBUG] Not forwarding ANY MIDI: route_midi_in_to_out_enabled={getattr(self, 'route_midi_in_to_out_enabled', False)}, midi_handler={self.midi_handler}, outport={getattr(self.midi_handler, 'outport', None)}")

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

    def on_midi_out_changed(self, idx):
        # Handle MIDI output change
        selected = self.midi_out_combo.currentText()
        if 'UDP MIDI' in selected:
            self.midi_handler.use_udp_midi(True)
        else:
            self.midi_handler.use_udp_midi(False)

    def set_in_port_from_menu(self, port):
        import re
        udp_label = 'UDP MIDI (127.0.0.1:50007)'
        if port == udp_label:
            QApplication.instance().midi_handler.use_udp_midi(True, as_input=True)
            if hasattr(self.main_window, 'show_status'):
                self.main_window.show_status(f"Selected MIDI In: {udp_label}")
            self.main_window.start_receiving()
            self.main_window.settings.setValue("last_in_port", port)
            return
        else:
            QApplication.instance().midi_handler.use_udp_midi(False)
        try:
            # Always open a new input port before starting the worker
            QApplication.instance().midi_handler.open_input(port)
            display_port = re.sub(r'\s*\d+$', '', str(port))
            if hasattr(self.main_window, 'show_status'):
                self.main_window.show_status(f"Selected MIDI In: {display_port}")
            self.main_window.start_receiving()
            self.main_window.settings.setValue("last_in_port", port)
        except Exception as e:
            from dialogs import Dialogs
            Dialogs.show_error(self.main_window, "MIDI In Error", f"Could not open MIDI In port '{port}': {e}")

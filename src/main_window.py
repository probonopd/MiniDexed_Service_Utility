import os
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QFileDialog
from PyQt6.QtGui import QAction
from ui_main_window import UiMainWindow
from menus import setup_menus
from file_ops import FileOps
from midi_ops import MidiOps
from midi_handler import MIDIHandler
from workers import LogWorker, MIDIReceiveWorker, MidiSendWorker, SyslogWorker
from dialogs import Dialogs
from PyQt6.QtCore import QSettings
import re
from updater_dialog import UpdaterDialog, UpdaterProgressDialog
from updater_worker import UpdaterWorker, DeviceDiscoveryWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MiniDexed Service Utility")
        self.resize(800, 500)
        self.settings = QSettings("MIDISend", "MIDISendApp")
        self.midi_handler = MIDIHandler()
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
            self.ui.set_out_port_from_menu(last_out)
        if last_in:
            self.ui.set_in_port_from_menu(last_in)

    def closeEvent(self, event):
        self.midi_ops.stop_sending()
        if self.receive_worker:
            self.receive_worker.stop()
        if hasattr(self, 'syslog_worker') and self.syslog_worker:
            self.syslog_worker.stop()
        self.midi_handler.close()
        self.log_worker.stop()
        event.accept()

    def start_receiving(self):
        if hasattr(self, 'receive_worker') and self.receive_worker:
            self.receive_worker.stop()
        self.receive_worker = MIDIReceiveWorker(self.midi_handler)
        self.receive_worker.sysex_received.connect(self.ui.display_sysex)
        self.receive_worker.log.connect(self.ui.append_log)
        self.receive_worker.start()

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
                    from PyQt6.QtWidgets import QFileDialog
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
                from PyQt6.QtWidgets import QFileDialog
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
        from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel
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

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
        setup_menus(self)
        self.init_workers()
        self.restore_last_ports()
        self.statusBar()  # Ensure status bar is created
        self.device_list = []  # List of (name, ip)
        self.update_action = None  # Will be set in menus.py
        self.device_discovery_worker = DeviceDiscoveryWorker()
        self.device_discovery_worker.device_found.connect(self.add_discovered_device)
        self.device_discovery_worker.finished.connect(self.device_discovery_finished)
        self.device_discovery_worker.start()

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
        self.syslog_worker = SyslogWorker()
        self.syslog_worker.syslog_message.connect(self.ui.append_syslog)
        self.syslog_worker.log.connect(log_to_status_and_stdout)
        self.syslog_worker.start()

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
        self.device_list.append((name, ip))
        if self.update_action:
            self.update_action.setEnabled(True)

    def device_discovery_finished(self):
        if not self.device_list and self.update_action:
            self.update_action.setEnabled(False)

    def show_updater_dialog(self):
        dlg = UpdaterDialog(self, device_list=self.device_list)
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

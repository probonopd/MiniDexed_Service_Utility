from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox
from PySide6.QtWidgets import QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QTextEdit
from PySide6.QtWidgets import QPushButton, QHBoxLayout
from PySide6.QtCore import Qt
import sys

class Dialogs:
    @staticmethod
    def get_file_open(parent, filter_str):
        return QFileDialog.getOpenFileName(parent, "Open File", "", filter_str)[0]

    @staticmethod
    def get_file_save(parent, filter_str):
        return QFileDialog.getSaveFileName(parent, "Save File", "", filter_str)[0]

    @staticmethod
    def get_text_input(parent, title, label):
        return QInputDialog.getText(parent, title, label)

    @staticmethod
    def show_message(parent, title, message):
        QMessageBox.information(parent, title, message)

    @staticmethod
    def show_error(parent, title, message):
        Dialogs.log_error_stderr(title, message)
        QMessageBox.critical(parent, title, message)

    @staticmethod
    def log_error_stderr(title, message):
        print(f"[ERROR] {title}: {message}", file=sys.stderr)

class PreferencesDialog(QDialog):
    def __init__(self, parent=None, github_token=""):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(600)  # 150% wider than default 400px
        layout = QVBoxLayout(self)
        label = QLabel("GitHub Token:")
        layout.addWidget(label)
        self.token_edit = QLineEdit()
        self.token_edit.setText(github_token)
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.token_edit)
        explanation = QTextEdit()
        explanation.setReadOnly(True)
        explanation.setHtml(
            "<b>What is a GitHub Token?</b><br>"
            "A GitHub Personal Access Token is used to authenticate with GitHub for downloading private or rate-limited files, such as PR build artifacts.<br><br>"
            "<b>Where to get it?</b><br>"
            "Go to <a href='https://github.com/settings/tokens'>https://github.com/settings/tokens</a> and create a token with 'public_repo' access. Copy and paste it here.<br><br>"
            "<b>When is it needed?</b><br>"
            "You only need this if you want to download PR build artifacts or if you encounter GitHub API rate limits during updates."
        )
        explanation.setMinimumHeight(120)
        layout.addWidget(explanation)
        # Add Clear application data button and explanation
        clear_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear application data")
        clear_layout.addWidget(clear_btn)
        clear_layout.addWidget(QLabel("Deletes all cached voices and settings. Use this if you want to reset the app or free up disk space."))
        layout.addLayout(clear_layout)
        def clear_app_data():
            import shutil
            import os
            from PySide6.QtWidgets import QMessageBox
            cache_dir = os.path.join(os.getenv('LOCALAPPDATA') or os.path.expanduser('~/.local/share'), 'MiniDexed_Service_Utility')
            try:
                if os.path.exists(cache_dir):
                    shutil.rmtree(cache_dir)
                QMessageBox.information(self, "Application Data Cleared", "All cached voices and settings have been deleted.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear application data: {e}")
        clear_btn.clicked.connect(clear_app_data)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
    def get_github_token(self):
        return self.token_edit.text()

class DeviceSelectDialog(QDialog):
    def __init__(self, parent=None, device_list=None):
        super().__init__(parent)
        self.setWindowTitle("Select Device")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        label = QLabel("Select a device to edit minidexed.ini:")
        layout.addWidget(label)
        from PySide6.QtWidgets import QComboBox
        self.device_combo = QComboBox(self)
        if device_list:
            for name, ip in device_list:
                self.device_combo.addItem(f"{name} ({ip})", ip)
        layout.addWidget(self.device_combo)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
    def get_selected_ip(self):
        return self.device_combo.currentData() or self.device_combo.currentText()

from PyQt6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QTextEdit
from PyQt6.QtCore import Qt
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
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
    def get_github_token(self):
        return self.token_edit.text()

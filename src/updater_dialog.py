from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout, QComboBox, QTextEdit, QCheckBox
from PySide6.QtCore import Qt

class UpdaterDialog(QDialog):
    def __init__(self, main_window, device_list=None):
        super().__init__(main_window)
        self.setWindowTitle("MiniDexed Updater")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        self.status = QLabel("Select release and device to update.")
        layout.addWidget(self.status)

        self.release_combo = QComboBox()
        self.release_combo.addItems([
            "Latest official release",
            "Continuous (experimental) build",
            "Local build (from src/)",
            "Pull request build (enter PR number below)"
        ])
        layout.addWidget(self.release_combo)

        self.pr_input = QTextEdit()
        self.pr_input.setPlaceholderText("Enter PR number or URL (for PR builds only)")
        self.pr_input.setMaximumHeight(30)
        layout.addWidget(self.pr_input)

        self.device_combo = QComboBox()
        if device_list:
            for name, ip in device_list:
                self.device_combo.addItem(f"{name} ({ip})", ip)
        layout.addWidget(self.device_combo)

        self.update_perf_checkbox = QCheckBox("Update Performances (OVERWRITES all existing performances)")
        self.update_perf_checkbox.setChecked(False)
        layout.addWidget(self.update_perf_checkbox)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Update")
        self.cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.cancel_btn.clicked.connect(self.reject)
        self.start_btn.clicked.connect(self.accept)

    def set_status(self, text):
        self.status.setText(text)

    def set_progress(self, value):
        pass  # No progress bar in this dialog

class UpdaterProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Updating MiniDexed...")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        self.status = QLabel("Starting update...")
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        self.cancel_btn.clicked.connect(self.reject)

    def set_status(self, text):
        self.status.setText(text)

    def set_progress(self, value):
        self.progress.setValue(value)

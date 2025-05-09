from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QSplitter, QTableView, QHeaderView
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction, QKeySequence
from PyQt6.QtCore import Qt
import re
from dialogs import Dialogs

class UiMainWindow:
    def __init__(self, main_window):
        self.main_window = main_window
        self.central = QWidget()
        main_window.setCentralWidget(self.central)
        main_layout = QVBoxLayout()
        splitter = QSplitter()

        # MIDI Out panel
        out_panel = QWidget()
        out_layout = QVBoxLayout()
        out_panel.setLayout(out_layout)
        out_layout.addWidget(QLabel("MIDI Out"))
        self.out_text = QTextEdit()
        out_layout.addWidget(self.out_text)
        out_btn_layout = QHBoxLayout()
        self.btn_send_out = QPushButton("Send")
        self.btn_clear_out = QPushButton("Clear")
        self.btn_stop_out = QPushButton("Stop")
        out_btn_layout.addWidget(self.btn_send_out)
        out_btn_layout.addWidget(self.btn_stop_out)
        out_btn_layout.addWidget(self.btn_clear_out)
        out_layout.addLayout(out_btn_layout)
        splitter.addWidget(out_panel)

        # MIDI In panel
        in_panel = QWidget()
        in_layout = QVBoxLayout()
        in_panel.setLayout(in_layout)
        in_layout.addWidget(QLabel("MIDI In"))
        self.in_text = QTextEdit()
        self.in_text.setReadOnly(True)
        in_layout.addWidget(self.in_text)
        self.btn_clear_in = QPushButton("Clear")
        in_btn_layout = QHBoxLayout()
        in_btn_layout.addWidget(self.btn_clear_in)
        in_layout.addLayout(in_btn_layout)
        splitter.addWidget(in_panel)

        main_layout.addWidget(splitter)
        self.syslog_label = QLabel("Syslog")
        main_layout.addWidget(self.syslog_label)
        self.syslog_view = QTableView()
        self.syslog_model = QStandardItemModel(0, 5)
        self.syslog_model.setHorizontalHeaderLabels(['Time', 'Index', 'IP', 'Service', 'Message'])
        self.syslog_view.setModel(self.syslog_model)
        self.syslog_view.setAlternatingRowColors(True)
        self.syslog_view.horizontalHeader().setStretchLastSection(True)
        self.syslog_view.verticalHeader().setDefaultSectionSize(6)  # 80% of previous 8px height
        self.syslog_view.setStyleSheet("""
            QTableView { border: none; gridline-color: transparent; alternate-background-color: #f6f6f6; background: white; }
            QTableView::item { border: none; padding-top: 0px; padding-bottom: 0px; padding-left: 0px; padding-right: 0px; margin: 0px; }
            QTableView::item:selected { color: black; background: #cce6ff; }
        """)
        self.syslog_view.horizontalHeader().setStyleSheet("QHeaderView::section { border: none; padding: 0px; margin: 0px; }")
        self.syslog_view.verticalHeader().setStyleSheet("QHeaderView::section { border: none; padding: 0px; margin: 0px; }")
        self.syslog_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.syslog_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.syslog_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.syslog_view.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        copy_action = QAction('Copy', self.syslog_view)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        select_all_action = QAction('Select All', self.syslog_view)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        def copy_selected():
            selection = self.syslog_view.selectionModel().selectedRows()
            if not selection:
                return
            lines = []
            for index in selection:
                row = index.row()
                values = [self.syslog_model.item(row, col).text() for col in range(self.syslog_model.columnCount())]
                lines.append('\t'.join(values))
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText('\n'.join(lines))
        def select_all():
            self.syslog_view.selectAll()
        copy_action.triggered.connect(copy_selected)
        select_all_action.triggered.connect(select_all)
        self.syslog_view.addAction(copy_action)
        self.syslog_view.addAction(select_all_action)
        # Native keyPressEvent for shortcuts
        orig_keyPressEvent = self.syslog_view.keyPressEvent
        def custom_keyPressEvent(event):
            if event.matches(QKeySequence.StandardKey.Copy):
                copy_selected()
            elif event.matches(QKeySequence.StandardKey.SelectAll):
                select_all()
            else:
                orig_keyPressEvent(event)
        self.syslog_view.keyPressEvent = custom_keyPressEvent
        main_layout.addWidget(self.syslog_view)
        self.central.setLayout(main_layout)

        self.syslog_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

    def append_log(self, msg):
        # Route all log messages to the main window's status bar and stdout
        if hasattr(self.main_window, 'show_status'):
            self.main_window.show_status(msg)

    def append_syslog(self, msg):
        line = msg.strip()
        # Try to match full line with message
        m = re.match(r'([0-9:.]+) ([<>][0-9]+) - ([0-9.]+) ([^ ]+) - - - (.*)', line)
        if m:
            time, idx, ip, service, message = m.groups()
        else:
            # Try to match line with empty message
            m2 = re.match(r'([0-9:.]+) ([<>][0-9]+) - ([0-9.]+) ([^ ]+) - - -$', line)
            if m2:
                time, idx, ip, service = m2.groups()
                message = ''
            else:
                time, idx, ip, service, message = '', '', '', '', line
        row = self.syslog_model.rowCount()
        items = []
        for val in [time, idx, ip, service, message]:
            item = QStandardItem(val)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            items.append(item)
        self.syslog_model.appendRow(items)
        if getattr(self.main_window, 'autoscroll_enabled', True):
            self.syslog_view.scrollToBottom()

    def display_sysex(self, data):
        hex_str = ' '.join(f'{b:02X}' for b in data)
        self.in_text.append(hex_str)
        self.in_text.append("")  # Add a blank line after each line
        if hasattr(self.main_window, 'show_status'):
            self.main_window.show_status(f"Received {len(data)} bytes successfully.")
        if getattr(self.main_window, 'autoscroll_enabled', True):
            self.in_text.verticalScrollBar().setValue(self.in_text.verticalScrollBar().maximum())

    def refresh_ports(self):
        # This should be called by menus.py when menus are opened
        pass

    def set_out_port_from_menu(self, port):
        import re
        try:
            self.main_window.midi_handler.open_output(port)
            # Remove trailing numbers from port name for display
            display_port = re.sub(r'\s*\d+$', '', str(port))
            if hasattr(self.main_window, 'show_status'):
                self.main_window.show_status(f"Selected MIDI Out: {display_port}")
            self.main_window.settings.setValue("last_out_port", port)
        except Exception as e:
            from dialogs import Dialogs
            Dialogs.show_error(self.main_window, "MIDI Out Error", f"Could not open MIDI Out port '{port}': {e}")

    def set_in_port_from_menu(self, port):
        import re
        try:
            self.main_window.midi_handler.open_input(port)
            # Remove trailing numbers from port name for display
            display_port = re.sub(r'\s*\d+$', '', str(port))
            if hasattr(self.main_window, 'show_status'):
                self.main_window.show_status(f"Selected MIDI In: {display_port}")
            self.main_window.start_receiving()
            self.main_window.settings.setValue("last_in_port", port)
        except Exception as e:
            from dialogs import Dialogs
            Dialogs.show_error(self.main_window, "MIDI In Error", f"Could not open MIDI In port '{port}': {e}")

    def update_syslog_label(self, ip, port):
        self.syslog_label.setText(f"Syslog ({ip}:{port})")

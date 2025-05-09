from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QSlider, QDialogButtonBox, QHBoxLayout, QLineEdit, QTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator
import os
import json
import re
from dialogs import PreferencesDialog

def setup_menus(main_window):
    menubar = main_window.menuBar()
    # Order: File, Edit, MIDI Out, MIDI In, Options, Help
    # File Menu
    file_menu = menubar.addMenu("File")
    open_action = QAction("Open .syx...", main_window)
    file_menu.addAction(open_action)
    save_action = QAction("Save Out as .syx...", main_window)
    file_menu.addAction(save_action)
    file_menu.addSeparator()
    send_mid_action = QAction("Send .mid...", main_window)
    file_menu.addAction(send_mid_action)
    save_midi_in_action = QAction("Save MIDI In as .mid...", main_window)
    file_menu.addAction(save_midi_in_action)
    file_menu.addSeparator()
    update_action = QAction("Update MiniDexed...", main_window)
    file_menu.addAction(update_action)
    exit_action = QAction("Exit", main_window)
    file_menu.addAction(exit_action)
    open_action.triggered.connect(main_window.file_ops.menu_open_syx)
    save_action.triggered.connect(main_window.file_ops.menu_save_syx)
    send_mid_action.triggered.connect(main_window.midi_ops.send_file)
    save_midi_in_action.triggered.connect(main_window.file_ops.menu_save_midi_in)
    update_action.triggered.connect(main_window.show_updater_dialog)
    exit_action.triggered.connect(main_window.close)

    # Edit Menu
    edit_menu = menubar.addMenu("Edit")
    undo_action = QAction("Undo", main_window)
    edit_menu.addAction(undo_action)
    redo_action = QAction("Redo", main_window)
    edit_menu.addAction(redo_action)
    edit_menu.addSeparator()
    cut_action = QAction("Cut", main_window)
    edit_menu.addAction(cut_action)
    copy_action = QAction("Copy", main_window)
    edit_menu.addAction(copy_action)
    paste_action = QAction("Paste", main_window)
    edit_menu.addAction(paste_action)
    edit_menu.addSeparator()
    select_all_action = QAction("Select All", main_window)
    edit_menu.addAction(select_all_action)
    def get_focused_textedit():
        widget = QApplication.focusWidget()
        from PyQt6.QtWidgets import QTextEdit
        if isinstance(widget, QTextEdit):
            return widget
        return None
    undo_action.triggered.connect(lambda: get_focused_textedit() and get_focused_textedit().undo())
    redo_action.triggered.connect(lambda: get_focused_textedit() and get_focused_textedit().redo())
    cut_action.triggered.connect(lambda: get_focused_textedit() and get_focused_textedit().cut())
    copy_action.triggered.connect(lambda: get_focused_textedit() and get_focused_textedit().copy())
    paste_action.triggered.connect(lambda: get_focused_textedit() and get_focused_textedit().paste())
    select_all_action.triggered.connect(lambda: get_focused_textedit() and get_focused_textedit().selectAll())

    # MIDI Out Menu
    midi_out_menu = menubar.addMenu("MIDI Out")
    def populate_out_menu():
        midi_out_menu.clear()
        import re
        ports = sorted(main_window.midi_handler.list_output_ports(), key=str.casefold)
        selected_out = main_window.settings.value("last_out_port", "")
        for port in ports:
            # Remove trailing numbers for display
            display_port = re.sub(r'\s*\d+$', '', str(port))
            action = QAction(display_port, main_window)
            action.setCheckable(True)
            if port == selected_out:
                action.setChecked(True)
            action.triggered.connect(lambda checked, p=port: main_window.ui.set_out_port_from_menu(p))
            midi_out_menu.addAction(action)
    midi_out_menu.aboutToShow.connect(populate_out_menu)

    # MIDI In Menu
    midi_in_menu = menubar.addMenu("MIDI In")
    def populate_in_menu():
        midi_in_menu.clear()
        import re
        ports = sorted(main_window.midi_handler.list_input_ports(), key=str.casefold)
        selected_in = main_window.settings.value("last_in_port", "")
        for port in ports:
            # Remove trailing numbers for display
            display_port = re.sub(r'\s*\d+$', '', str(port))
            action = QAction(display_port, main_window)
            action.setCheckable(True)
            if port == selected_in:
                action.setChecked(True)
            action.triggered.connect(lambda checked, p=port: main_window.ui.set_in_port_from_menu(p))
            midi_in_menu.addAction(action)
    midi_in_menu.aboutToShow.connect(populate_in_menu)

    # Options Menu
    options_menu = menubar.addMenu("Options")
    main_window.autoscroll_action = QAction("Autoscroll", main_window)
    main_window.autoscroll_action.setCheckable(True)
    main_window.autoscroll_action.setChecked(True)
    options_menu.addAction(main_window.autoscroll_action)
    main_window.autoscroll_action.toggled.connect(lambda enabled: setattr(main_window, 'autoscroll_enabled', enabled))
    # Preferences
    preferences_action = QAction("Preferences...", main_window)
    options_menu.addAction(preferences_action)
    def show_preferences():
        from dialogs import PreferencesDialog
        token = main_window.settings.value("github_token", "")
        dlg = PreferencesDialog(main_window, github_token=token)
        if dlg.exec():
            new_token = dlg.get_github_token()
            main_window.settings.setValue("github_token", new_token)
    preferences_action.triggered.connect(show_preferences)

    # MIDI Commands Menu
    midi_commands_menu = menubar.addMenu("MIDI Commands")
    midi_commands_dir = os.path.join(os.path.dirname(__file__), "midi_commands")

    def load_midi_commands():
        commands = []
        if os.path.isdir(midi_commands_dir):
            for fname in sorted(os.listdir(midi_commands_dir)):
                if fname.endswith(".json"):
                    with open(os.path.join(midi_commands_dir, fname), "r", encoding="utf-8") as f:
                        try:
                            cmd = json.load(f)
                            commands.append(cmd)
                        except Exception:
                            pass
        return commands

    def show_midi_command_dialog(cmd):
        # If there are no parameters or all parameters are fixed, skip dialog
        params = cmd.get("parameters", [])
        if not params or all(p["min"] == p["max"] for p in params):
            # No dialog needed, just send the command with default/fixed values
            values = [p["min"] for p in params]
            sysex_hex = main_window.midi_handler.get_command_hex(cmd, values)
            if sysex_hex:
                main_window.ui.out_text.setPlainText(sysex_hex)
            else:
                main_window.midi_handler.send_custom_midi_command(cmd, values)
            return

        class MidiParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle(cmd.get("name", "MIDI Command"))
                layout = QVBoxLayout(self)
                self.sliders = {}
                self.value_boxes = {}
                self.param_adjust = {}
                self.param_order = []
                for param in cmd.get("parameters", []):
                    # If only one allowable value, skip asking the user
                    if param["min"] == param["max"]:
                        continue
                    hlayout = QHBoxLayout()
                    # Special case: show Device Number as 1-16 if min=0, max=15
                    if param["name"] == "Device Number" and param["min"] == 0 and param["max"] == 15:
                        label = QLabel(f"{param['name']} (1-16):")
                        slider = QSlider()
                        slider.setOrientation(Qt.Orientation.Horizontal)
                        slider.setMinimum(1)
                        slider.setMaximum(16)
                        slider.setValue(param.get('default', 0) + 1)
                        self.param_adjust[param["name"]] = True
                        min_val, max_val, default_val = 1, 16, param.get('default', 0) + 1
                    # Special case: show MIDI Channel (!-16) for Channel param
                    elif param["name"] == "Channel" and param["min"] == 1 and param["max"] == 16:
                        label = QLabel("MIDI Channel (1-16):")
                        slider = QSlider()
                        slider.setOrientation(Qt.Orientation.Horizontal)
                        slider.setMinimum(1)
                        slider.setMaximum(16)
                        slider.setValue(param.get('default', 1))
                        self.param_adjust[param["name"]] = False
                        min_val, max_val, default_val = 1, 16, param.get('default', 1)
                    else:
                        label = QLabel(f"{param['name']} ({param['min']}-{param['max']}):")
                        slider = QSlider()
                        slider.setOrientation(Qt.Orientation.Horizontal)
                        slider.setMinimum(param['min'])
                        slider.setMaximum(param['max'])
                        slider.setValue(param.get('default', param['min']))
                        self.param_adjust[param["name"]] = False
                        min_val, max_val, default_val = param['min'], param['max'], param.get('default', param['min'])
                    value_box = QLineEdit(str(default_val))
                    value_box.setFixedWidth(40)
                    value_box.setValidator(QIntValidator(min_val, max_val, self))
                    # Sync slider and value_box
                    def make_slider_slot(slider, value_box):
                        return lambda val: value_box.setText(str(val))
                    slider.valueChanged.connect(make_slider_slot(slider, value_box))
                    def make_box_slot(slider, value_box, min_val, max_val):
                        def slot():
                            try:
                                val = int(value_box.text())
                                if val < min_val:
                                    val = min_val
                                elif val > max_val:
                                    val = max_val
                                value_box.setText(str(val))
                                slider.setValue(val)
                            except Exception:
                                # Reset to slider's value if invalid
                                value_box.setText(str(slider.value()))
                        return slot
                    value_box.editingFinished.connect(make_box_slot(slider, value_box, min_val, max_val))
                    hlayout.addWidget(label)
                    hlayout.addWidget(slider)
                    hlayout.addWidget(value_box)
                    layout.addLayout(hlayout)
                    self.sliders[param['name']] = slider
                    self.value_boxes[param['name']] = value_box
                    self.param_order.append(param['name'])
                self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
                self.buttons.accepted.connect(self.accept)
                self.buttons.rejected.connect(self.reject)
                layout.addWidget(self.buttons)
            def get_values(self):
                values = []
                for name in self.param_order:
                    slider = self.sliders[name]
                    val = slider.value()
                    if self.param_adjust.get(name, False):
                        val -= 1  # Convert 1-16 to 0-15 for Device Number
                    values.append(val)
                # For skipped params (min==max), insert the fixed value in the right order
                param_defs = cmd.get("parameters", [])
                result = []
                slider_idx = 0
                for param in param_defs:
                    if param["min"] == param["max"]:
                        result.append(param["min"])
                    else:
                        result.append(values[slider_idx])
                        slider_idx += 1
                return result
        dlg = MidiParamDialog(main_window)
        if dlg.exec():
            values = dlg.get_values()
            # Instead of sending, put the resulting SysEx or MIDI hex string in the MIDI Out text field
            sysex_hex = main_window.midi_handler.get_command_hex(cmd, values)
            if sysex_hex:
                main_window.ui.out_text.setPlainText(sysex_hex)
            # If not a SysEx, fallback to sending as before
            else:
                main_window.midi_handler.send_custom_midi_command(cmd, values)

    def load_midi_commands_recursive(base_dir):
        items = []
        for entry in sorted(os.listdir(base_dir)):
            full_path = os.path.join(base_dir, entry)
            if os.path.isdir(full_path):
                # Subdirectory: submenu
                items.append({
                    'type': 'submenu',
                    'name': entry,
                    'children': load_midi_commands_recursive(full_path)
                })
            elif entry.endswith('.json'):
                with open(full_path, 'r', encoding='utf-8') as f:
                    try:
                        cmd = json.load(f)
                        items.append({'type': 'command', 'cmd': cmd})
                    except Exception:
                        pass
        return items

    def add_midi_command_menu_items(menu, items):
        for item in items:
            if item['type'] == 'submenu':
                submenu = menu.addMenu(item['name'])
                add_midi_command_menu_items(submenu, item['children'])
            elif item['type'] == 'command':
                action = QAction(item['cmd'].get('name', 'Unnamed Command'), main_window)
                action.triggered.connect(lambda checked, c=item['cmd']: show_midi_command_dialog(c))
                menu.addAction(action)

    def populate_midi_commands_menu():
        midi_commands_menu.clear()
        items = load_midi_commands_recursive(midi_commands_dir)
        add_midi_command_menu_items(midi_commands_menu, items)
        midi_commands_menu.addSeparator()
        patch_browser_action = QAction("DX7 Voice Browser...", main_window)
        midi_commands_menu.addAction(patch_browser_action)
        def show_patch_browser():
            from patch_browser import PatchBrowser
            dlg = PatchBrowser(main_window)
            dlg.show()
        patch_browser_action.triggered.connect(show_patch_browser)
    midi_commands_menu.aboutToShow.connect(populate_midi_commands_menu)

    # Help Menu (move to last)
    help_menu = menubar.addMenu("Help")
    about_action = QAction("About", main_window)
    help_menu.addAction(about_action)
    about_action.triggered.connect(lambda: main_window.file_ops.menu_about())

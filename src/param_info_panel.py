from PySide6.QtWidgets import QTextEdit

class ParamInfoPanel(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumWidth(200)
        self.setStyleSheet("background: #23272e; color: #e0e0e0; font-size: 10pt; padding-left: 10px; padding-right: 10px;")

    def show_param_info(self, param_info, param_key):
        if not param_info:
            return
        info = param_info.get(param_key)
        if not info:
            return
        html = f"<b>{info.get('long', param_key)} ({info.get('short', param_key)})</b><br>"
        html += f"<b>Range:</b> {info.get('min', '')} – {info.get('max', '')}<br><br>"
        if 'values' in info:
            html += f"<b>Values:</b> {info['values']}<br><br>"
        html += f" {info.get('description', '')}<br><br>"
        html += f"{info.get('sound_impact', '')}<br><br>"
        self.setHtml(html)

from PySide6.QtWidgets import QTextEdit

class ParamInfoPanel(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMinimumWidth(240)
        self.setStyleSheet("background: #23272e; color: #e0e0e0; font-size: 10pt; padding-left: 10px; padding-right: 10px;")

    def show_param_info(self, param_info, param_key, hovered_op_idx=None, carrier_ops=None):
        import logging
        logging.basicConfig(level=logging.DEBUG)
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
        # Add Massey reference if available
        chapter = info.get('massey_chapter')
        chapter_name = info.get('massey_chapter_name')
        subchapter = info.get('massey_subchapter')
        if chapter and chapter_name:
            if subchapter and subchapter != chapter_name:
                html += f"<i>Reference: Massey, The Complete DX7, chapter {chapter}: {chapter_name}, {subchapter}.</i>"
            else:
                html += f"<i>Reference: Massey, The Complete DX7, chapter {chapter}: {chapter_name}.</i>"
        # Add special reference for modulators (non-carriers, i.e., brown-ish background)
        if hovered_op_idx is not None and carrier_ops is not None:
            # logging.debug(f"show_param_info: hovered_op_idx={hovered_op_idx}, carrier_ops={carrier_ops}, param_key={param_key}")
            # Only show for operator parameters (not global params)
            if param_key in [
                'R1','R2','R3','R4','L1','L2','L3','L4','BP','LD','RD','LC','RC','RS','TL','AMS','TS','PM','PC','PF','PD']:
                # Fix: hovered_op_idx and carrier_ops may be mismatched in direction, so try both
                # Check if hovered_op_idx or (self.op_count-1-hovered_op_idx) is in carrier_ops
                op_idx = hovered_op_idx
                alt_op_idx = None
                try:
                    from voice_editor_panel import VoiceEditorPanel
                    alt_op_idx = VoiceEditorPanel.op_count - 1 - hovered_op_idx
                except Exception:
                    pass
                if op_idx not in carrier_ops:
                    html += " <i>Since this is a modulator, also see, chapter 6: The modulator.</i>"
        self.setHtml(html)

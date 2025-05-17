from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath
from PySide6.QtCore import Qt, QRectF, Signal
import sys
import logging

logging.basicConfig(level=logging.DEBUG)

# Curve label mapping for display
curve_labels = {
    0: "+LIN",
    1: "-EXP",
    2: "+EXP",
    3: "-LIN"
}

class KeyboardScalingWidget(QWidget):
    paramsChanged = Signal(int, int, int, int, int)  # break_point, left_depth, right_depth, left_curve, right_curve
    labelHovered = Signal(str)  # Emits param_key when hovering over a label
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(80, 64)
        self.setMaximumSize(80, 64)
        self.break_point = 50  # 0-99
        self.left_depth = 50   # 0-99
        self.right_depth = 50  # 0-99
        self.left_curve = 1    # 0=LIN, 1=-EXP, 2=+EXP, 3=-LIN
        self.right_curve = 2   # 0=LIN, 1=-EXP, 2=+EXP, 3=-LIN
        self.bg_color = QColor('#332b28')
        self.line_color = QColor('#aaaaaa')
        self.curve_color = QColor('#aaaaaa')
        self.text_color = QColor('#e0e0e0')
        self.highlight = None  # 'break', 'left_depth', 'right_depth', 'left_curve', 'right_curve'
        self.highlight_color = QColor('#ffffff')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._hovered_label = None
        self.setMouseTracking(True)

    def set_params(self, break_point, left_depth, right_depth, left_curve, right_curve):
        changed = (
            self.break_point != break_point or
            self.left_depth != left_depth or
            self.right_depth != right_depth or
            self.left_curve != left_curve or
            self.right_curve != right_curve
        )
        self.break_point = break_point
        self.left_depth = left_depth
        self.right_depth = right_depth
        self.left_curve = left_curve
        self.right_curve = right_curve
        self.update()
        if changed:
            self.paramsChanged.emit(self.break_point, self.left_depth, self.right_depth, self.left_curve, self.right_curve)

    def set_highlight(self, part):
        self.highlight = part  # 'break', 'left_depth', 'right_depth', 'left_curve', 'right_curve'
        self.update()

    def clear_highlight(self):
        self.highlight = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        margin = 18
        # Draw grid
        painter.setPen(QPen(self.line_color, 1))
        painter.drawRect(margin, margin, w-2*margin, h-2*margin)
        painter.drawLine(w//2, margin, w//2, h-margin)  # Break point vertical
        # painter.drawLine(margin, h//2, w-margin, h//2)  # Center horizontal

        # Calculate break point x and y (always center y)
        bp_x = margin + (w-2*margin) * (self.break_point/99)
        bp_y = h//2
        # Draw left scaling curve (from left to break point)
        left_path = QPainterPath()
        left_path.moveTo(bp_x, bp_y)
        for i in range(int(bp_x), margin-1, -1):
            x = i
            rel = (bp_x - x) / (bp_x - margin) if (bp_x - margin) > 0 else 0
            y = self._dx7_curve(rel, self.left_depth, self.left_curve, h, margin, left=True)
            left_path.lineTo(x, y)
        curve_pen = QPen(self.curve_color, 2)
        if self.highlight in ('left_depth', 'left_curve'):
            curve_pen = QPen(self.highlight_color, 3)
        painter.setPen(curve_pen)
        painter.drawPath(left_path)
        # Draw right scaling curve (from break point to right)
        right_path = QPainterPath()
        right_path.moveTo(bp_x, bp_y)
        for i in range(int(bp_x), w-margin):
            x = i
            rel = (x - bp_x) / (w - margin - bp_x) if (w - margin - bp_x) > 0 else 0
            y = self._dx7_curve(rel, self.right_depth, self.right_curve, h, margin, left=False)
            right_path.lineTo(x, y)
        curve_pen = QPen(self.curve_color, 2)
        if self.highlight in ('right_depth', 'right_curve'):
            curve_pen = QPen(self.highlight_color, 3)
        painter.setPen(curve_pen)
        painter.drawPath(right_path)
        # Draw break point marker
        pen = QPen(QColor('white'), 2)
        if self.highlight == 'break':
            pen = QPen(self.highlight_color, 3)
        painter.setPen(pen)
        painter.drawLine(int(bp_x), margin, int(bp_x), h-margin)

        # Draw values equally spaced above and below the frame
        # Above: left_depth, break_point, right_depth
        x_left = margin
        x_center = margin + (w - 2 * margin) / 2
        x_right = w - margin
        painter.setPen(QPen(self.text_color))
        font = QFont()
        font.setPointSize(9)
        # Draw left_depth label
        left_label = str(self.left_depth)
        if len(left_label) >= 3:
            font.setPointSize(7)
        else:
            font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(QRectF(x_left-18, margin-18, 36, 16), Qt.AlignmentFlag.AlignCenter, left_label)
        # Draw break_point label
        font.setPointSize(9 if len(str(self.break_point)) < 3 else 7)
        painter.setFont(font)
        painter.drawText(QRectF(x_center-18, margin-18, 36, 16), Qt.AlignmentFlag.AlignCenter, str(self.break_point))
        # Draw right_depth label at the top right
        right_label = str(self.right_depth)
        font.setPointSize(9 if len(right_label) < 3 else 7)
        painter.setFont(font)
        painter.drawText(QRectF(x_right-18, margin-18, 36, 16), Qt.AlignmentFlag.AlignCenter, right_label)

        # Draw left_curve and right_curve labels only if not highlighted
        if self.highlight not in ('left_curve', 'right_curve'):
            # Always show curve labels below the rectangle
            label_left = curve_labels.get(self.left_curve, '')
            x_left_curve = x_left
            y_curve = margin + (self.height() - 2 * margin) + 2
            painter.drawText(QRectF(x_left_curve-20, y_curve, 40, 18), Qt.AlignmentFlag.AlignCenter, label_left)

            label_right = curve_labels.get(self.right_curve, '')
            x_right_curve = x_right
            painter.drawText(QRectF(x_right_curve-20, y_curve, 40, 18), Qt.AlignmentFlag.AlignCenter, label_right)

        # Draw highlighted curve labels above the rectangle
        if self.highlight == 'left_curve':
            label = curve_labels.get(self.left_curve, '')
            x = margin + (bp_x - margin) * 0.25
            y = margin + (self.height() - 2 * margin) + 2  # Move label below rectangle
            painter.drawText(QRectF(x-20, y, 40, 18), Qt.AlignmentFlag.AlignCenter, label)
        elif self.highlight == 'right_curve':
            label = curve_labels.get(self.right_curve, '')
            x = bp_x + (w - margin - bp_x) * 0.25
            y = margin + (self.height() - 2 * margin) + 2  # Move label below rectangle
            painter.drawText(QRectF(x-20, y, 40, 18), Qt.AlignmentFlag.AlignCenter, label)
        elif self.highlight == 'break':
            label = "BREAK"
            painter.drawText(QRectF(bp_x-20, 5, 40, 18), Qt.AlignmentFlag.AlignCenter, label)
        elif self.highlight == 'left_depth':
            # Horizontally center the label over the widget, accounting for text width
            label = 'L DEPTH'
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(label)
            x = (w / 2) - (text_width / 2)
            y = 5
            painter.drawText(QRectF(x, y, text_width, 18), Qt.AlignmentFlag.AlignCenter, label)
        elif self.highlight == 'right_depth':
            # Horizontally center the label over the widget, accounting for text width
            label = 'R DEPTH'
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(label)
            x = (w / 2) - (text_width / 2)
            y = 5
            painter.drawText(QRectF(x, y, text_width, 18), Qt.AlignmentFlag.AlignCenter, label)

    def wheelEvent(self, event):
        pos = event.position() if hasattr(event, 'position') else event.posF()
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        margin = 18
        # Above: left_depth, break_point, right_depth
        x_left = margin
        x_center = margin + (w - 2 * margin) / 2
        x_right = w - margin
        top_rects = [
            QRectF(x_left-18, margin-18, 36, 16),
            QRectF(x_center-18, margin-18, 36, 16),
            QRectF(x_right-18, margin-18, 36, 16)
        ]
        # Below: left_curve, right_curve (no break point)
        y_bottom = margin + (self.height() - 2 * margin) + 2
        bottom_rects = [
            QRectF(x_left-18, y_bottom, 36, 16),
            QRectF(x_right-18, y_bottom, 36, 16)
        ]
        delta = 1 if event.angleDelta().y() > 0 else -1
        # Check if mouse is over a top label (depths/break)
        if top_rects[0].contains(x, y):
            self.left_depth = max(0, min(99, self.left_depth + delta))
            changed = True
            self.update()
            if changed:
                self.paramsChanged.emit(self.break_point, self.left_depth, self.right_depth, self.left_curve, self.right_curve)
            return
        if top_rects[1].contains(x, y):
            self.break_point = max(0, min(99, self.break_point + delta))
            changed = True
            self.update()
            if changed:
                self.paramsChanged.emit(self.break_point, self.left_depth, self.right_depth, self.left_curve, self.right_curve)
            return
        if top_rects[2].contains(x, y):
            self.right_depth = max(0, min(99, self.right_depth + delta))
            changed = True
            self.update()
            if changed:
                self.paramsChanged.emit(self.break_point, self.left_depth, self.right_depth, self.left_curve, self.right_curve)
            return
        # Check if mouse is over a bottom label (curves)
        if bottom_rects[0].contains(x, y):
            self.left_curve = (self.left_curve + delta) % 4
            changed = True
            self.update()
            if changed:
                self.paramsChanged.emit(self.break_point, self.left_depth, self.right_depth, self.left_curve, self.right_curve)
            return
        if bottom_rects[1].contains(x, y):
            self.right_curve = (self.right_curve + delta) % 4
            changed = True
            self.update()
            if changed:
                self.paramsChanged.emit(self.break_point, self.left_depth, self.right_depth, self.left_curve, self.right_curve)
            return
        # Otherwise, pass event to base class
        super().wheelEvent(event)

    def mousePressEvent(self, event):
        w, h = self.width(), self.height()
        margin = 18
        x_left = margin
        x_center = margin + (w - 2 * margin) / 2
        x_right = w - margin
        y_top = margin-18
        y_bottom = margin + (self.height() - 2 * margin) + 2
        y_curve = y_bottom  # match paintEvent
        bp_x = margin + (w-2*margin) * (self.break_point/99)
        self._drag_part = None
        self._drag_label = None
        mx, my = event.position().x(), event.position().y()
        # Prioritize curve label hit test (wider area) before smaller rects
        if QRectF(x_left-20, y_curve, 40, 18).contains(mx, my):
            print('[DEBUG] Drag start: LC curve label')
            self._drag_label = 'LC'
        elif QRectF(x_right-20, y_curve, 40, 18).contains(mx, my):
            print('[DEBUG] Drag start: RC curve label')
            self._drag_label = 'RC'
        # Then check for top/bottom label rects
        elif QRectF(x_center-18, y_top, 36, 16).contains(mx, my):
            print('[DEBUG] Drag start: BP')
            self._drag_part = 'BP'
        elif QRectF(x_left-18, y_top, 36, 16).contains(mx, my):
            print('[DEBUG] Drag start: LD')
            self._drag_part = 'LD'
        elif QRectF(x_right-18, y_top, 36, 16).contains(mx, my):
            print('[DEBUG] Drag start: RD')
            self._drag_part = 'RD'
        elif QRectF(x_left-18, y_bottom, 36, 16).contains(mx, my):
            print('[DEBUG] Drag start: LC (small rect)')
            self._drag_label = 'LC'
        elif QRectF(x_right-18, y_bottom, 36, 16).contains(mx, my):
            print('[DEBUG] Drag start: RC (small rect)')
            self._drag_label = 'RC'
        self._last_mouse_pos = (mx, my)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        x, y = event.position().x(), event.position().y()
        w, h = self.width(), self.height()
        margin = 18
        # --- Drag logic for handles ---
        if hasattr(self, '_drag_part') and self._drag_part and event.buttons() & Qt.MouseButton.LeftButton:
            if self._drag_part == 'BP':
                bp = int(99 * (x - margin) / (w - 2*margin))
                bp = max(0, min(99, bp))
                self.break_point = bp
            elif self._drag_part == 'LD':
                ld = int(99 * (1 - (y - margin) / (h - 2*margin)))
                ld = max(0, min(99, ld))
                self.left_depth = ld
            elif self._drag_part == 'RD':
                rd = int(99 * (1 - (y - margin) / (h - 2*margin)))
                rd = max(0, min(99, rd))
                self.right_depth = rd
            self.update()
            return
        # --- Drag logic for labels ---
        if hasattr(self, '_drag_label') and self._drag_label and event.buttons() & Qt.MouseButton.LeftButton:
            x, y = event.position().x(), event.position().y()
            last_x, last_y = self._last_mouse_pos
            dx = x - last_x
            dy = y - last_y
            # Use the larger of dx or dy (in absolute value) for both LC and RC
            drag = dx if abs(dx) > abs(dy) else -dy
            if self._drag_label == 'LC':
                orig = self.left_curve
                delta = int(drag / 8)  # more sensitive drag
                if delta != 0:
                    new_val = (orig + delta) % 4
                    if new_val != self.left_curve:
                        print(f'[DEBUG] Drag LC: {orig} -> {new_val}')
                        self.left_curve = new_val
                        self.update()
                    # Reset last_mouse_pos so drag is incremental
                    self._last_mouse_pos = (x, y)
            elif self._drag_label == 'RC':
                orig = self.right_curve
                delta = int(drag / 8)
                if delta != 0:
                    new_val = (orig + delta) % 4
                    if new_val != self.right_curve:
                        print(f'[DEBUG] Drag RC: {orig} -> {new_val}')
                        self.right_curve = new_val
                        self.update()
                    self._last_mouse_pos = (x, y)
            return
        x, y = event.position().x(), event.position().y()
        w, h = self.width(), self.height()
        margin = 18
        x_left = margin
        x_center = margin + (w - 2 * margin) / 2
        x_right = w - margin
        y_bottom = margin + (self.height() - 2 * margin) + 2
        top_rects = [
            QRectF(x_left-18, margin-18, 36, 16),   # LD
            QRectF(x_center-18, margin-18, 36, 16), # BP
            QRectF(x_right-18, margin-18, 36, 16)   # RD
        ]
        bottom_rects = [
            QRectF(x_left-18, y_bottom, 36, 16),    # LC
            QRectF(x_right-18, y_bottom, 36, 16)    # RC
        ]
        hovered = None
        if top_rects[0].contains(x, y):
            hovered = 'LD'
        elif top_rects[1].contains(x, y):
            hovered = 'BP'
        elif top_rects[2].contains(x, y):
            hovered = 'RD'
        elif bottom_rects[0].contains(x, y):
            hovered = 'LC'
        elif bottom_rects[1].contains(x, y):
            hovered = 'RC'
        if hovered != self._hovered_label:
            self._hovered_label = hovered
            if hovered:
                self.labelHovered.emit(hovered)
            else:
                self.labelHovered.emit("")
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (hasattr(self, '_drag_part') and self._drag_part) or (hasattr(self, '_drag_label') and self._drag_label):
            self.paramsChanged.emit(self.break_point, self.left_depth, self.right_depth, self.left_curve, self.right_curve)
            self._drag_part = None
            self._drag_label = None
        self._last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._hovered_label = None
        self.labelHovered.emit("")
        super().leaveEvent(event)

    def _dx7_curve(self, rel, depth, curve, h, margin, left=True):
        # rel: 0..1, depth: 0..99, curve: 0=+LIN, 1=-EXP, 2=+EXP, 3=-LIN
        # Always 0 at rel=0 (break point), ±depth at rel=1 (edge)
        center = h // 2
        d = (depth / 99) * (h // 2 - margin - 2)
        k = 4.0  # Exponential steepness constant
        if curve == 0:  # +LIN (always down)
            y_off = -d * rel
        elif curve == 1:  # -EXP (always up)
            norm = (pow(2.71828, k) - 1)
            y_off = +d * (pow(2.71828, rel * k) - 1) / norm if norm != 0 else 0
        elif curve == 2:  # +EXP (always down)
            norm = (pow(2.71828, k) - 1)
            y_off = -d * (pow(2.71828, rel * k) - 1) / norm if norm != 0 else 0
        elif curve == 3:  # -LIN (always up)
            y_off = +d * rel
        else:
            y_off = 0
        return int(center + y_off)

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = KeyboardScalingWidget()
    # Symmetrical S-curve: break_point=50, max depth, left=+EXP, right=-EXP
    w.set_params(50, 99, 99, 1, 2)
    w.setWindowTitle("Keyboard Scaling Widget Test")
    w.resize(400, 200)
    w.show()
    sys.exit(app.exec())

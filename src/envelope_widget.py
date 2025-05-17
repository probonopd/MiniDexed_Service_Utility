from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QMouseEvent
from PySide6.QtCore import Qt, QRectF, Signal

class EnvelopeWidget(QWidget):
    envelopeChanged = Signal(list, list)  # Emits (rates, levels) when changed by user
    labelHovered = Signal(str)  # Emits param_key when hovering over a label
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rates = [50, 50, 50, 50]
        self.levels = [99, 70, 40, 0]
        self.setMinimumSize(100, 64)
        self.setMaximumSize(100, 64)
        self.bg_color = QColor('#332b28')
        self.fg_color = QColor('#ffb703')
        self.line_color = QColor('#aaaaaa')
        self.text_color = QColor('#e0e0e0')
        self.highlight_color = QColor('#ffffff')
        self._drag_idx = None  # Which point is being dragged
        self._drag_offset = (0, 0)
        self._last_mouse_pos = None
        self.highlight_type = None  # 'rate' or 'level'
        self.highlight_index = None
        self._hovered_label = None  # Track which label is hovered
        self.setMouseTracking(True)  # Enable mouse tracking for hover labels
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_envelope(self, rates, levels):
        if len(rates) == 4 and len(levels) == 4:
            self.rates = list(rates)
            self.levels = list(levels)
            self.update()

    def set_highlight(self, highlight_type, index):
        self.highlight_type = highlight_type  # 'rate' or 'level'
        self.highlight_index = index
        self.update()

    def clear_highlight(self):
        self.highlight_type = None
        self.highlight_index = None
        self.update()

    def _get_points(self):
        margin = 18
        w = self.width() - 2 * margin
        h = self.height() - 2 * margin
        def y(level):
            return margin + h * (1 - (level / 99.0))
        times = [1.0 / max(1, r) for r in self.rates]
        total_time = sum(times)
        x_points = [margin]
        for t in times[:3]:
            x_points.append(x_points[-1] + w * (t / total_time))
        key_off_x = x_points[-1]
        l4_end_x = key_off_x + w * (times[3] / total_time)
        x_points.append(key_off_x)  # KEY OFF (same as L3)
        x_points.append(l4_end_x)   # L4 (end)
        points = [
            (x_points[0], y(self.levels[3])),  # Start at L4 (left)
            (x_points[1], y(self.levels[0])),  # L1
            (x_points[2], y(self.levels[1])),  # L2
            (x_points[3], y(self.levels[2])),  # L3
            (x_points[4], y(self.levels[2])),  # KEY OFF (same level as L3)
            (x_points[5], y(self.levels[3]))   # L4 (right)
        ]
        return points, x_points, margin, w, h

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        points, x_points, margin, w, h = self._get_points()
        # Draw envelope lines
        pen = QPen(self.line_color, 2)
        painter.setPen(pen)
        for i in range(3):
            if self.highlight_type == 'rate' and self.highlight_index == i:
                painter.setPen(QPen(QColor('white'), 3))
            else:
                painter.setPen(QPen(self.line_color, 2))
            painter.drawLine(int(points[i][0]), int(points[i][1]), int(points[i+1][0]), int(points[i+1][1]))
        # Draw R4 line
        if self.highlight_type == 'rate' and self.highlight_index == 3:
            painter.setPen(QPen(QColor('white'), 3))
        else:
            painter.setPen(QPen(self.line_color, 2))
        painter.drawLine(int(points[4][0]), int(points[4][1]), int(points[5][0]), int(points[5][1]))
        # Draw dots at each point
        for idx, (x, y_) in enumerate(points):
            highlight = False
            if self.highlight_type == 'level':
                if self.highlight_index == 0 and idx == 1:
                    highlight = True
                elif self.highlight_index == 1 and idx == 2:
                    highlight = True
                elif self.highlight_index == 2 and (idx == 3 or idx == 4):  # L3 and KEY OFF
                    highlight = True
                elif self.highlight_index == 3 and idx == 5:
                    highlight = True
            if highlight:
                painter.setPen(QPen(QColor('white'), 2))
                painter.setBrush(QColor('white'))
                painter.drawEllipse(int(x)-4, int(y_)-4, 8, 8)
            else:
                painter.setPen(QPen(QColor('#777777'), 2))
                painter.setBrush(QColor('#777777'))
            # painter.drawEllipse(int(x)-4, int(y_)-4, 8, 8)
        painter.setPen(QPen(self.text_color))
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        # Draw level values (L1-L4) equally spaced above the frame
        num_levels = 4
        for i in range(num_levels):
            x = margin + i * (w / (num_levels - 1))
            painter.drawText(QRectF(x-14, margin-18, 28, 16), Qt.AlignmentFlag.AlignCenter, str(self.levels[i]))
        # Draw rate values (R1-R4) equally spaced below the frame
        num_rates = 4
        for i in range(num_rates):
            x = margin + i * (w / (num_rates - 1))
            painter.drawText(QRectF(x-14, margin+h+2, 28, 16), Qt.AlignmentFlag.AlignCenter, str(self.rates[i]))

        painter.setPen(QPen(self.text_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(margin, margin, w, h)

    def mousePressEvent(self, event: QMouseEvent):
        points, x_points, margin, w, h = self._get_points()
        mx, my = event.position().x(), event.position().y()
        # Only allow dragging L1, L2, L3, L4 (end) (indices 1,2,3,5)
        for idx in [1,2,3,5]:
            px, py = points[idx]
            if (mx - px)**2 + (my - py)**2 < 64:  # within 8px
                self._drag_idx = idx
                self._last_mouse_pos = (mx, my)
                break
        else:
            self._drag_idx = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        points, x_points, margin, w, h = self._get_points()
        x, y = event.position().x(), event.position().y()
        num_levels = 4
        num_rates = 4
        # Calculate label rects for levels (top) and rates (bottom)
        level_rects = []
        for i in range(num_levels):
            lx = margin + i * (w / (num_levels - 1))
            level_rects.append(QRectF(lx-14, margin-18, 28, 16))
        rate_rects = []
        for i in range(num_rates):
            rx = margin + i * (w / (num_rates - 1))
            rate_rects.append(QRectF(rx-14, margin+h+2, 28, 16))
        hovered = None
        for i, rect in enumerate(level_rects):
            if rect.contains(x, y):
                hovered = f'L{i+1}'
                break
        if not hovered:
            for i, rect in enumerate(rate_rects):
                if rect.contains(x, y):
                    hovered = f'R{i+1}'
                    break
        if hovered != self._hovered_label:
            self._hovered_label = hovered
            if hovered:
                self.labelHovered.emit(hovered)
            else:
                self.labelHovered.emit("")
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_label = None
        self.labelHovered.emit("")
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_idx = None
        self._last_mouse_pos = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        # Detect if mouse is over a level or rate label and adjust the value
        pos = event.position() if hasattr(event, 'position') else event.posF()
        x, y = pos.x(), pos.y()
        points, x_points, margin, w, h = self._get_points()
        num_levels = 4
        num_rates = 4
        # Calculate label rects for levels (top) and rates (bottom)
        level_rects = []
        for i in range(num_levels):
            lx = margin + i * (w / (num_levels - 1))
            level_rects.append(QRectF(lx-14, margin-18, 28, 16))
        rate_rects = []
        for i in range(num_rates):
            rx = margin + i * (w / (num_rates - 1))
            rate_rects.append(QRectF(rx-14, margin+h+2, 28, 16))
        # Check if mouse is over a level label
        for i, rect in enumerate(level_rects):
            if rect.contains(x, y):
                delta = 1 if event.angleDelta().y() > 0 else -1
                self.levels[i] = max(0, min(99, self.levels[i] + delta))
                self.update()
                self.envelopeChanged.emit(self.rates, self.levels)
                return
        # Check if mouse is over a rate label
        for i, rect in enumerate(rate_rects):
            if rect.contains(x, y):
                delta = 1 if event.angleDelta().y() > 0 else -1
                self.rates[i] = max(1, min(99, self.rates[i] + delta))
                self.update()
                self.envelopeChanged.emit(self.rates, self.levels)
                return
        # Otherwise, pass event to base class
        super().wheelEvent(event)

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    def on_env_changed(rates, levels):
        print("Rates:", rates, "Levels:", levels)
    app = QApplication(sys.argv)
    w = EnvelopeWidget()
    w.set_envelope([80, 40, 60, 30], [99, 60, 30, 0])
    w.envelopeChanged.connect(on_env_changed)
    w.setWindowTitle("EnvelopeWidget Test")
    w.resize(320, 100)
    w.show()
    sys.exit(app.exec())

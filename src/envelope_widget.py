from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QMouseEvent
from PySide6.QtCore import Qt, QRectF, Signal

class EnvelopeWidget(QWidget):
    envelopeChanged = Signal(list, list)  # Emits (rates, levels) when changed by user
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rates = [50, 50, 50, 50]
        self.levels = [99, 70, 40, 0]
        self.setMinimumHeight(60)
        self.setMinimumWidth(180)
        self.setMaximumHeight(120)
        self.setMaximumWidth(400)
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
        self.setMouseTracking(True)  # Enable mouse tracking for hover labels

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
        painter.fillRect(self.rect(), self.bg_color)
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
        # Draw labels only if highlighted
        painter.setPen(QPen(self.text_color))
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        # Show L1/L2/L3/L4 or R1/R2/R3/R4 labels depending on highlight type
        label_offset = 20  # Space between point/line and label
        if self.highlight_type == 'level':
            if self.highlight_index == 0:
                painter.drawText(QRectF(points[1][0]-10, points[1][1]-label_offset, 20, 16), Qt.AlignmentFlag.AlignCenter, "L1")
            if self.highlight_index == 1:
                painter.drawText(QRectF(points[2][0]-10, points[2][1]-label_offset, 20, 16), Qt.AlignmentFlag.AlignCenter, "L2")
            if self.highlight_index == 2:
                painter.drawText(QRectF(points[3][0]-10, points[3][1]-label_offset, 20, 16), Qt.AlignmentFlag.AlignCenter, "L3")
            if self.highlight_index == 3:
                painter.drawText(QRectF(points[5][0]-10, points[5][1]-label_offset, 20, 16), Qt.AlignmentFlag.AlignCenter, "L4")
        elif self.highlight_type == 'rate':
            # Draw R1-R4 in the middle of the corresponding line segments
            if self.highlight_index == 0:
                mx = (points[0][0] + points[1][0]) / 2
                my = (points[0][1] + points[1][1]) / 2
                painter.drawText(QRectF(mx-10, my-label_offset, 20, 16), Qt.AlignmentFlag.AlignCenter, "R1")
            if self.highlight_index == 1:
                mx = (points[1][0] + points[2][0]) / 2
                my = (points[1][1] + points[2][1]) / 2
                painter.drawText(QRectF(mx-10, my-label_offset, 20, 16), Qt.AlignmentFlag.AlignCenter, "R2")
            if self.highlight_index == 2:
                mx = (points[2][0] + points[3][0]) / 2
                my = (points[2][1] + points[3][1]) / 2
                painter.drawText(QRectF(mx-10, my-label_offset, 20, 16), Qt.AlignmentFlag.AlignCenter, "R3")
            if self.highlight_index == 3:
                mx = (points[4][0] + points[5][0]) / 2
                my = (points[4][1] + points[5][1]) / 2
                painter.drawText(QRectF(mx-10, my-label_offset, 20, 16), Qt.AlignmentFlag.AlignCenter, "R4")

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
        if self._drag_idx is None:
            return super().mouseMoveEvent(event)
        points, x_points, margin, w, h = self._get_points()
        mx, my = event.position().x(), event.position().y()
        idx = self._drag_idx
        # Vertical drag: update level
        if idx in [1,2,3,5]:
            y_clamped = min(max(my, margin), margin + h)
            level = int(99 * (1 - (y_clamped - margin) / h))
            level = max(0, min(99, level))
            if idx == 1:
                self.levels[0] = level
            elif idx == 2:
                self.levels[1] = level
            elif idx == 3:
                self.levels[2] = level
            elif idx == 5:
                self.levels[3] = level
            self.update()
            self.envelopeChanged.emit(self.rates, self.levels)
        # Horizontal drag: update rate (for L1, L2, L3 only)
        if idx in [1,2,3]:
            # Allow horizontal drag up to the next point (not past it)
            min_x = x_points[idx-1] + 1
            max_x = x_points[idx+1] - 1
            # But also, don't allow to cross the previous point
            if idx > 1:
                min_x = max(min_x, x_points[idx-2] + 2)
            if idx < 3:
                max_x = min(max_x, x_points[idx+2] - 2)
            x_clamped = min(max(mx, min_x), max_x)
            prev_x = x_points[idx-1]
            next_x = x_points[idx+1]
            times = [1.0 / max(1, r) for r in self.rates]
            seg_time = (x_clamped - prev_x) / w * sum(times)
            seg_time = max(0.001, seg_time)
            self.rates[idx-1] = int(1.0 / seg_time)
            self.rates[idx-1] = max(1, min(99, self.rates[idx-1]))
            self.update()
            self.envelopeChanged.emit(self.rates, self.levels)
        self._last_mouse_pos = (mx, my)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_idx = None
        self._last_mouse_pos = None
        super().mouseReleaseEvent(event)

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

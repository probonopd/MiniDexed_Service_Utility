from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QPainterPath
from PyQt6.QtCore import Qt
import sys

class KeyboardScalingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 160)
        self.break_point = 50  # 0-99
        self.left_depth = 50   # 0-99
        self.right_depth = 50  # 0-99
        self.left_curve = 1    # 0=LIN, 1=-EXP, 2=+EXP, 3=-LIN
        self.right_curve = 2   # 0=LIN, 1=-EXP, 2=+EXP, 3=-LIN
        self.bg_color = QColor('#23272e')
        self.line_color = QColor('#aaaaaa')
        self.curve_color = QColor('#aaaaaa')
        self.text_color = QColor('#e0e0e0')
        self.highlight = None  # 'break', 'left_depth', 'right_depth', 'left_curve', 'right_curve'
        self.highlight_color = QColor('#ffffff')

    def set_params(self, break_point, left_depth, right_depth, left_curve, right_curve):
        self.break_point = break_point
        self.left_depth = left_depth
        self.right_depth = right_depth
        self.left_curve = left_curve
        self.right_curve = right_curve
        self.update()

    def set_highlight(self, part):
        self.highlight = part  # 'break', 'left_depth', 'right_depth', 'left_curve', 'right_curve'
        self.update()

    def clear_highlight(self):
        self.highlight = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), self.bg_color)
        w, h = self.width(), self.height()
        margin = 24
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
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = KeyboardScalingWidget()
    # Symmetrical S-curve: break_point=50, max depth, left=+EXP, right=-EXP
    w.set_params(50, 99, 99, 1, 2)
    w.setWindowTitle("Keyboard Scaling Widget Test")
    w.resize(400, 200)
    w.show()
    sys.exit(app.exec())

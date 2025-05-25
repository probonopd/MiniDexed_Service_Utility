from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtSvgWidgets import QSvgWidget
import os
import glob

class AlgorithmGalleryDialog(QDialog):
    def __init__(self, parent, alg_combo, images_path):
        super().__init__(parent)
        self.setWindowTitle("Select Algorithm")
        self.alg_combo = alg_combo
        self.setMinimumSize(900, 600)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setContentsMargins(0, 0, 0, 0)
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(0)
        grid.setContentsMargins(0, 0, 0, 0)
        svg_files = sorted(glob.glob(os.path.join(images_path, "algorithm-*.svg")))
        self.svg_widgets = []
        fixed_height = 240
        max_cols = 16  # 16 per row

        # Calculate required width and height to fit all items without scrolling
        total_width = 0
        svg_widths = []
        for idx, svg_path in enumerate(svg_files[:max_cols]):
            svg_widget = QSvgWidget(svg_path)
            renderer = svg_widget.renderer()
            if renderer is not None:
                size = renderer.defaultSize()
                if size.height() > 0:
                    aspect = size.width() / size.height()
                    width = int(fixed_height * aspect)
                else:
                    width = fixed_height
            else:
                width = fixed_height
            svg_widths.append(width)
            total_width += width
        spacing = 8  # Spacing between columns
        total_width += (max_cols - 1) * spacing
        total_height = fixed_height * 2 + spacing  # Two rows of fixed height + spacing

        # Set the window size to fit all items
        self.setFixedSize(total_width + 40, total_height + 40)

        for idx, svg_path in enumerate(svg_files):
            svg_widget = QSvgWidget(svg_path)
            renderer = svg_widget.renderer()
            if renderer is not None:
                size = renderer.defaultSize()
                if size.height() > 0:
                    aspect = size.width() / size.height()
                    width = int(fixed_height * aspect)
                else:
                    width = fixed_height
            else:
                width = fixed_height
            svg_widget.setFixedSize(width, fixed_height)
            svg_widget.setCursor(Qt.PointingHandCursor)
            svg_widget.mousePressEvent = self._make_select_handler(idx)
            label = QLabel(str(idx+1))
            label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            vbox = QVBoxLayout()
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.setSpacing(0)
            vbox.addWidget(svg_widget, alignment=Qt.AlignHCenter)
            vbox.addWidget(label, alignment=Qt.AlignHCenter)
            w = QWidget()
            w.setLayout(vbox)
            w.setContentsMargins(0, 0, 0, 0)
            row = idx // max_cols      # 0 for first 16, 1 for next 16
            col = idx % max_cols       # 0-15 for each row
            grid.addWidget(w, row, col)
            self.svg_widgets.append(svg_widget)
        # Assert: only 2 rows, and at most 16 items per row
        num_rows = (len(svg_files) + max_cols - 1) // max_cols
        num_cols = min(len(svg_files), max_cols)
        assert num_cols <= max_cols, "More than 16 items per row"
        assert num_rows <= 2, "More than 2 rows of items"
        container.setLayout(grid)
        container.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _make_select_handler(self, idx):
        def handler(event):
            if self.alg_combo:
                self.alg_combo.setCurrentIndex(idx)
            self.accept()
        return handler

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QComboBox

    app = QApplication(sys.argv)
    images_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "images"))
    combo = QComboBox()
    dlg = AlgorithmGalleryDialog(None, combo, images_path)
    if dlg.exec():
        print("Selected index:", combo.currentIndex())
    else:
        print("Dialog cancelled")

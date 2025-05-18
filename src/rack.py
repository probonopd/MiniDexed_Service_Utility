import logging
logging.basicConfig(level=logging.DEBUG, force=True)

from PySide6.QtWidgets import QWidget, QHBoxLayout, QApplication, QVBoxLayout, QLCDNumber, QLabel
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QMouseEvent, QPalette, QColor
from voice_editor_panel import VoiceEditorPanel

class RackSection(QWidget):
    SECTION_MARGIN = 0
    MIN_WIDTH = 32
    MAX_HEIGHT = 600
    def __init__(self, title, index, parent=None):
        super().__init__(parent)
        self.title = title
        self.index = index
        self._width = self.MIN_WIDTH
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setMaximumHeight(self.MAX_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.panel = None
        self.lcd = None
        self.rack_label = None  # For the first section expanded
        self._init_lcd()
        self.is_collapsed = True  # Track collapsed state

    def _init_lcd(self):
        # Create a container widget for the LCD and other content
        self.lcd_container = QWidget(self)
        self.lcd_container.setObjectName("lcd_container")
        self.lcd_container.setStyleSheet("#lcd_container { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #000, stop:1 #222); border-radius: 2px; }")
        layout = QVBoxLayout(self.lcd_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.lcd_container.setContentsMargins(0, 0, 0, 0)
        self.lcd = QLCDNumber(2, self.lcd_container)
        self.lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Filled)
        palette = self.lcd.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor('#cc0000'))
        palette.setColor(QPalette.ColorRole.Light, QColor('#cc0000'))
        palette.setColor(QPalette.ColorRole.Shadow, QColor('black'))
        self.lcd.setPalette(palette)
        self.lcd.setAutoFillBackground(True)
        self.lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        self.lcd.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #42372e, stop:1 #332b28); border-radius: 2px;")
        self.lcd.display(0)
        self.lcd.setFixedWidth(68)
        self.lcd.setFixedHeight(36)
        layout.addWidget(self.lcd, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.lcd_container.hide()

    def setSectionWidth(self, w):
        self._width = w
        self.setFixedWidth(w)
        self._resize_panel()
        self.update()
        if self.panel and self.panel.parent() is self:
            self.panel.setGeometry(0, 0, w, self.height())
        if self.lcd and self.lcd.parent() is self:
            self.lcd.setGeometry(0, 0, w, self.height())

    def getSectionWidth(self):
        return self._width

    sectionWidth = Property(int, fget=getSectionWidth, fset=setSectionWidth)

    def showEvent(self, event):
        # Ensure the correct widget is shown on first display
        if hasattr(self, 'is_collapsed') and self.is_collapsed:
            self.set_collapsed(True)
        else:
            self.set_collapsed(False)
        super().showEvent(event)

    def set_collapsed(self, collapsed: bool):
        self.is_collapsed = collapsed
        import logging
        from voice_editor_panel import VoiceEditorPanel
        # Remove LCD container if present
        if self.lcd_container and self.lcd_container.parent() is self:
            self.lcd_container.hide()
            self.lcd_container.setParent(None)
        # Remove and delete any existing panel
        if hasattr(self, 'panel') and self.panel:
            self.panel.hide()
            self.panel.setParent(None)
            self.panel.deleteLater()
            self.panel = None
        # Remove rack_label if present
        if hasattr(self, 'rack_label') and self.rack_label:
            self.rack_label.hide()
            self.rack_label.setParent(None)
            self.rack_label.deleteLater()
            self.rack_label = None
        if collapsed:
            if self.index == 0:
                # No LCD for first section, just keep it empty
                pass
            else:
                self.lcd_container.setParent(self)
                self.lcd_container.show()
                self.lcd_container.raise_()
                self.lcd_container.setGeometry(0, 0, self.width(), self.height())
        else:
            if self.index == 0:
                # Show centered label 'Rack' for first section
                self.rack_label = QLabel(self)
                self.rack_label.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #000, stop:1 #222); border-radius: 2px;")
                self.rack_label = QLabel('Rack', self)
                self.rack_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                font = self.rack_label.font()
                font.setPointSize(16)
                font.setBold(True)
                self.rack_label.setFont(font)
                self.rack_label.setGeometry(0, 0, self.width(), self.height())
                self.rack_label.show()
                self.rack_label.raise_()
            else:
                self.lcd_container.hide()
                self.panel = VoiceEditorPanel(parent=self)
                self.panel.setGeometry(0, 0, self.width(), self.height())
                self.panel.show()
                self.panel.raise_()
                self.panel.update()
                self.update()
        self._resize_panel()

    def resizeEvent(self, event):
        self._resize_panel()
        if self.lcd and self.lcd.parent() is self:
            self.lcd.setGeometry(0, 0, self.width(), self.height())
        if self.panel and self.panel.parent() is self:
            self.panel.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def _resize_panel(self):
        w, h = self.width(), self.height()
        if self.panel and self.panel.parent() is self:
            self.panel.setGeometry(0, 0, w, h)
        if self.lcd_container and self.lcd_container.parent() is self:
            self.lcd_container.setGeometry(0, 0, w, h)
        if hasattr(self, 'rack_label') and self.rack_label and self.rack_label.parent() is self:
            self.rack_label.setGeometry(0, 0, w, h)

class AnimatedHorizontalRack(QWidget):
    MAX_WIDTH = 1800
    MIN_WIDTH = 1200
    SECTION_HEIGHT = 600
    COLLAPSED_WIDTH = 64
    SECTION_MARGIN = 3
    def __init__(self, section_titles=None, parent=None):
        super().__init__(parent)
        self.section_count = 9
        self.section_titles = section_titles or [f"Section {i+1}" for i in range(self.section_count)]
        self.expanded_index = 0
        self.sections = []
        self.animations = []
        self.setMaximumWidth(self.MAX_WIDTH)
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setMinimumHeight(self.SECTION_HEIGHT)
        self.setMaximumHeight(self.SECTION_HEIGHT)
        self.panel_instance = VoiceEditorPanel()  # Do not pass parent here
        self._init_ui()

    def _init_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)  # 1 px space between sections
        self.setContentsMargins(0, 0, 0, 0)
        for i, title in enumerate(self.section_titles):
            section = RackSection(title, i, self)
            section.setContentsMargins(0, 0, 0, 0)
            section.mousePressEvent = self._make_mouse_press(i)
            self.sections.append(section)
            self.layout.addWidget(section)
        self._update_sections(animate=False)

    def _make_mouse_press(self, idx):
        def handler(event: QMouseEvent):
            if self.expanded_index != idx:
                self.expand_section(idx)
        return handler

    def expand_section(self, idx):
        self.expanded_index = idx
        self._update_sections(animate=True)

    def _update_sections(self, animate=True):
        collapsed_w = self.COLLAPSED_WIDTH
        spacing = self.layout.spacing()
        total_width = min(self.width(), self.MAX_WIDTH)
        total_spacing = (self.section_count - 1) * spacing
        available_width = total_width - total_spacing
        expanded_w = max(available_width - collapsed_w * (self.section_count - 1), collapsed_w)
        for i, section in enumerate(self.sections):
            target_w = expanded_w if i == self.expanded_index else collapsed_w
            if animate:
                anim = QPropertyAnimation(section, b'sectionWidth')
                anim.setDuration(250)
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                anim.setStartValue(section.width())
                anim.setEndValue(target_w)
                anim.start()
                self.animations.append(anim)
                # Clean up finished animations
                anim.finished.connect(lambda a=anim: self.animations.remove(a))
            else:
                section.setSectionWidth(target_w)
            # Only pass collapsed/expanded state
            section.set_collapsed(i != self.expanded_index)

    def resizeEvent(self, event):
        self.setMaximumWidth(self.MAX_WIDTH)
        self.setMinimumHeight(self.SECTION_HEIGHT)
        self.setMaximumHeight(self.SECTION_HEIGHT)
        self._update_sections(animate=False)
        super().resizeEvent(event)

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    w = AnimatedHorizontalRack()
    w.setWindowTitle("Rack")
    w.resize(1200, 600)
    w.show()
    sys.exit(app.exec())

#!/bin/env python3
# -*- coding: utf-8 -*-
# nuitka-project: --enable-plugin=pyside6
# nuitka-project: --include-package=zeroconf
# nuitka-project: --include-package=rtmidi
# nuitka-project: --include-package=mido.backends.rtmidi
# nuitka-project: --include-data-dir=src/midi_commands=midi_commands
# nuitka-project: --include-data-dir=src/data=data
# nuitka-project: --include-data-dir=src/images=images
# nuitka-project: --prefer-source-code

import sys
from PySide6.QtWidgets import QApplication
from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

# nuitka-project: --include-module=zeroconf._handlers.answers
# nuitka-project: --include-module=zeroconf._utils.ipaddress
# nuitka-project: --include-package=zeroconf
# nuitka-project: --include-package=zeroconf._protocol
# nuitka-project: --include-package=zeroconf._services
# nuitka-project: --include-package=zeroconf._dns
# nuitka-project: --include-package=zeroconf._listener
# nuitka-project: --include-package=zeroconf._record_update
# nuitka-project: --include-package=zeroconf._updates
# nuitka-project: --include-package=zeroconf._history
# nuitka-project: --include-package=zeroconf._utils

import sys
from PySide6.QtWidgets import QApplication
from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

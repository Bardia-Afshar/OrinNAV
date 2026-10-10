#!/usr/bin/env python3
import os
import sys


os.environ["AT_SPI_BUS_ADDRESS"] = "unix:path=/nonexistent"
os.environ["NO_AT_BRIDGE"] = "1"
os.environ.setdefault("QT_LOGGING_RULES", "qt.accessibility.atspi*=false")

from PySide6.QtWidgets import QApplication

from gui import theme
from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    theme.apply(app)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

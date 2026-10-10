from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from gui.gps_tab import GPSTab
from gui.imu_tab import IMUTab
from gui.rtk_tab import RTKTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OrinNav Test GUI")

        self.imu_tab = IMUTab()
        self.gps_tab = GPSTab()
        self.rtk_tab = RTKTab(self.gps_tab.worker)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.tabBar().setDrawBase(False)
        tabs.addTab(self.imu_tab, "IMU")
        tabs.addTab(self.gps_tab, "GPS")
        tabs.addTab(self.rtk_tab, "RTK")

        central = QWidget()
        central.setObjectName("page")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_header())
        layout.addWidget(tabs, stretch=1)
        self.setCentralWidget(central)

    @staticmethod
    def _build_header():
        header = QWidget()
        header.setObjectName("header")
        header.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(0)
        title = QLabel("OrinNav")
        title.setObjectName("appTitle")
        subtitle = QLabel("Test Bench")
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    def closeEvent(self, event):
        # RTK feeds the GPS worker, stop it before the port closes
        self.rtk_tab.shutdown()
        self.imu_tab.shutdown()
        self.gps_tab.shutdown()
        super().closeEvent(event)

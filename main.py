import os
import sys
from pathlib import Path

# Keep PySide6 DLL resolution isolated to this project's virtual environment.
pyside6_dir = Path(sys.prefix) / "Lib" / "site-packages" / "PySide6"
if os.name == "nt" and pyside6_dir.exists():
    os.add_dll_directory(str(pyside6_dir))

from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow

app = QApplication(sys.argv)
app.setApplicationName("Central Camera Monitor")
app.setStyle("Fusion")
window = MainWindow()
window.show()
sys.exit(app.exec())

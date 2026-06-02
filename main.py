"""
Boletines QR - Generador Automático de Boletines Escolares
Punto de entrada principal de la aplicación.
"""

import sys
import os

# Asegurar que el directorio raíz esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont

from ui.main_window import MainWindow


def main():
    """Función principal de la aplicación."""
    # Evitar el ícono genérico de Python en la barra de tareas de Windows
    if os.name == 'nt':
        import ctypes
        try:
            myappid = "edutools.boletinesqr.v1"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Boletines QR")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("EduTools")

    # Configurar ícono de la aplicación
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logo.jpg")
    if os.path.exists(logo_path):
        app.setWindowIcon(QIcon(logo_path))

    # Fuente global
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Habilitar soporte HiDPI
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Estilo global moderno
    app.setStyleSheet("""
        /* === TEMA HAPPY KIDS === */
        /* Colores: Teal #00A99D, Naranja #F7941D, Azul #0072BC, Verde #39B54A */
        QMainWindow { background-color: #f0fafa; }
        QWidget { background-color: #f0fafa; color: #1a1a2e; font-family: 'Segoe UI', Arial, sans-serif; }

        QPushButton {
            background-color: #00A99D;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 8px 18px;
            font-weight: bold;
            font-size: 10pt;
        }
        QPushButton:hover { background-color: #008f84; }
        QPushButton:pressed { background-color: #007a70; }
        QPushButton:disabled { background-color: #b2dfdc; color: #80cbc4; }

        QPushButton#btnSecondary {
            background-color: #ffffff;
            color: #00A99D;
            border: 2px solid #00A99D;
        }
        QPushButton#btnSecondary:hover { background-color: #e0f7f6; }

        QPushButton#btnDanger {
            background-color: #F7941D;
            color: white;
        }
        QPushButton#btnDanger:hover { background-color: #e07d10; }

        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #ffffff;
            border: 2px solid #b2dfdc;
            border-radius: 6px;
            padding: 6px 10px;
            color: #1a1a2e;
        }
        QLineEdit:focus, QTextEdit:focus { border: 2px solid #00A99D; }

        QTableWidget {
            background-color: #ffffff;
            border: 2px solid #b2dfdc;
            border-radius: 8px;
            gridline-color: #e0f7f6;
            selection-background-color: #00A99D;
            selection-color: white;
        }
        QTableWidget::item { padding: 6px; border: none; color: #1a1a2e; }
        QHeaderView::section {
            background-color: #00A99D;
            color: white;
            padding: 8px;
            border: none;
            font-weight: bold;
        }

        QProgressBar {
            background-color: #e0f7f6;
            border: none;
            border-radius: 6px;
            height: 14px;
            text-align: center;
            color: white;
            font-weight: bold;
        }
        QProgressBar::chunk {
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #00A99D, stop:1 #F7941D);
            border-radius: 6px;
        }

        QLabel { color: #1a1a2e; }
        QLabel#labelTitle { font-size: 16pt; font-weight: bold; color: #00A99D; }
        QLabel#labelSubtitle { font-size: 10pt; color: #555; }

        QGroupBox {
            border: 2px solid #b2dfdc;
            border-radius: 10px;
            margin-top: 12px;
            padding: 10px;
            font-weight: bold;
            color: #00A99D;
            background-color: #ffffff;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; background-color: #ffffff; }

        QComboBox {
            background-color: #ffffff;
            border: 2px solid #b2dfdc;
            border-radius: 6px;
            padding: 6px 10px;
            color: #1a1a2e;
        }
        QComboBox:focus { border: 2px solid #00A99D; }
        QComboBox QAbstractItemView {
            background-color: #ffffff;
            border: 2px solid #b2dfdc;
            selection-background-color: #00A99D;
            color: #1a1a2e;
        }

        QScrollBar:vertical { background-color: #e0f7f6; width: 10px; border-radius: 5px; }
        QScrollBar::handle:vertical { background-color: #80cbc4; border-radius: 5px; min-height: 20px; }
        QScrollBar::handle:vertical:hover { background-color: #00A99D; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

        QStatusBar { background-color: #00A99D; color: white; border-top: 2px solid #008f84; }

        QCheckBox { color: #1a1a2e; spacing: 8px; }
        QCheckBox::indicator { width: 16px; height: 16px; border: 2px solid #b2dfdc; border-radius: 4px; background-color: white; }
        QCheckBox::indicator:checked { background-color: #00A99D; border-color: #00A99D; }

        QSpinBox {
            background-color: #ffffff;
            border: 2px solid #b2dfdc;
            border-radius: 6px;
            padding: 4px 8px;
            color: #1a1a2e;
        }

        QListWidget { background-color: #ffffff; border: 2px solid #b2dfdc; border-radius: 8px; }
        QListWidget::item { color: #1a1a2e; padding: 4px; }
        QListWidget::item:selected { background-color: #00A99D; color: white; }

        QTabWidget::pane { border: 2px solid #b2dfdc; border-radius: 8px; background-color: #ffffff; }
        QTabBar::tab { background-color: #e0f7f6; color: #00A99D; padding: 8px 20px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; font-weight: bold; }
        QTabBar::tab:selected { background-color: #00A99D; color: white; }

        QToolTip { background-color: #1a1a2e; color: white; border: 1px solid #00A99D; border-radius: 4px; padding: 4px; }

        QDialog { background-color: #f0fafa; }
        QFrame { background-color: transparent; }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
Galería de verificación final.
"""

import webbrowser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QGridLayout, QLabel, QPushButton, QFrame, QSizePolicy,
    QDialog, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QColor, QFont, QPainter

THUMB_SIZE = 160


class ThumbnailLoader(QThread):
    thumbnail_ready = Signal(int, QPixmap)

    def __init__(self, png_paths, parent=None):
        super().__init__(parent)
        self.png_paths = png_paths

    def run(self):
        for i, path in enumerate(self.png_paths):
            if os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    thumb = pix.scaled(THUMB_SIZE, THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.thumbnail_ready.emit(i, thumb)


class StudentCard(QFrame):
    clicked = Signal(str)

    def __init__(self, student_name, png_path, drive_url, success, parent=None):
        super().__init__(parent)
        self.drive_url = drive_url
        self.success = success

        self.setFixedWidth(THUMB_SIZE + 24)
        self.setFrameShape(QFrame.StyledPanel)

        if success:
            self.setStyleSheet("""
                QFrame { background-color: #313244; border: 2px solid #45475a; border-radius: 10px; }
                QFrame:hover { border: 2px solid #89b4fa; background-color: #363650; }
            """)
        else:
            self.setStyleSheet("""
                QFrame { background-color: #2a1f3a; border: 2px solid #cba6f7; border-radius: 10px; }
                QFrame:hover { border: 2px solid #f38ba8; }
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self.thumb_label.setStyleSheet("background-color: #1e1e2e; border-radius: 6px;")
        self._set_placeholder()
        layout.addWidget(self.thumb_label)

        # Nombre con fondo para legibilidad
        name_lbl = QLabel(student_name)
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setWordWrap(True)
        name_lbl.setFixedHeight(44)
        name_lbl.setStyleSheet("""
            QLabel {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-size: 8pt;
                font-weight: bold;
                border-radius: 4px;
                padding: 2px 4px;
            }
        """)
        layout.addWidget(name_lbl)

        status_lbl = QLabel("✅ Completo" if success else "❌ Con error")
        status_lbl.setAlignment(Qt.AlignCenter)
        status_lbl.setStyleSheet(
            "color: #a6e3a1; font-size: 7pt;" if success else "color: #f38ba8; font-size: 7pt;"
        )
        layout.addWidget(status_lbl)

        self.setCursor(Qt.PointingHandCursor)

    def _set_placeholder(self):
        pix = QPixmap(THUMB_SIZE, THUMB_SIZE)
        pix.fill(QColor("#1e1e2e"))
        painter = QPainter(pix)
        painter.setPen(QColor("#45475a"))
        painter.drawText(pix.rect(), Qt.AlignCenter, "📄")
        painter.end()
        self.thumb_label.setPixmap(pix)

    def set_thumbnail(self, pixmap):
        self.thumb_label.setPixmap(pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.drive_url:
            self.clicked.emit(self.drive_url)


class GalleryDialog(QDialog):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.results = results
        self._cards = []
        self.setWindowTitle("Galería de Verificación — Boletines Generados")
        self.setMinimumSize(950, 620)
        self._setup_ui()
        self._load_gallery()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("🖼️ Galería de Verificación")
        title.setObjectName("labelTitle")
        header.addWidget(title)
        header.addStretch()

        total = len(self.results)
        ok = sum(1 for r in self.results if r.success)
        stats = QLabel(f"✅ {ok} exitosos   ❌ {total - ok} con errores   📊 {total} total")
        stats.setStyleSheet("color: #444444; font-size: 10pt; font-weight: bold;")
        header.addWidget(stats)
        layout.addLayout(header)

        info = QLabel("Haz clic en un boletín para abrir el PDF en el navegador.")
        info.setObjectName("labelSubtitle")
        layout.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(12)
        self.grid_layout.setContentsMargins(12, 12, 12, 12)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll.setWidget(self.grid_widget)
        layout.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        btn_folder = QPushButton("📁 Abrir Carpeta de Salida")
        btn_folder.setObjectName("btnSecondary")
        btn_folder.clicked.connect(self._open_folder)
        btn_close = QPushButton("✅ Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_folder)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _load_gallery(self):
        if not self.results:
            return

        cols = 5
        png_paths = []

        for idx, result in enumerate(self.results):
            row = idx // cols
            col = idx % cols
            card = StudentCard(
                student_name=result.student_name,
                png_path=result.png_path,
                drive_url=result.drive_url,
                success=result.success,
            )
            card.clicked.connect(self._open_url)
            self.grid_layout.addWidget(card, row, col)
            self._cards.append(card)
            png_paths.append(result.png_path)

        self._loader = ThumbnailLoader(png_paths)
        self._loader.thumbnail_ready.connect(self._set_thumbnail)
        self._loader.start()

    def _set_thumbnail(self, idx, pixmap):
        if idx < len(self._cards):
            self._cards[idx].set_thumbnail(pixmap)

    def _open_url(self, url):
        if url:
            webbrowser.open(url)

    def _open_folder(self):
        for result in self.results:
            if result.png_path:
                folder = os.path.dirname(result.png_path)
                if os.path.exists(folder):
                    os.startfile(folder)
                    return

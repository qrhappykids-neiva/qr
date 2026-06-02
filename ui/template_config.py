import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
Diálogo de configuración de plantilla.
Permite cargar la imagen de plantilla y definir visualmente
las áreas del nombre y del QR mediante drag & drop.
"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QGroupBox, QFormLayout, QSpinBox, QComboBox,
    QColorDialog, QScrollArea, QWidget, QCheckBox, QSlider,
    QSizePolicy, QFrame, QToolBar, QApplication, QMessageBox, QLineEdit,
)
from PySide6.QtCore import Qt, QRect, QPoint, QSize, Signal, QRectF
from PySide6.QtGui import (
    QPixmap, QPainter, QPen, QColor, QBrush, QFont,
    QFontDatabase, QCursor, QImage,
)

from core.config import AppConfig, BoxConfig, TextConfig, save_config


class DraggableBox:
    """Representa una caja que puede ser arrastrada sobre la imagen."""
    
    def __init__(self, name: str, x: int, y: int, w: int, h: int, color: QColor):
        self.name = name
        self.rect = QRect(x, y, w, h)
        self.color = color
        self.dragging = False
        self.resizing = False
        self.drag_offset = QPoint()
        self.resize_handle_size = 10

    def handle_rect(self) -> QRect:
        """Rectángulo del manejador de redimensionado (esquina inferior derecha)."""
        r = self.rect
        hs = self.resize_handle_size
        return QRect(r.right() - hs, r.bottom() - hs, hs * 2, hs * 2)

    def contains(self, p: QPoint) -> bool:
        return self.rect.contains(p)

    def on_handle(self, p: QPoint) -> bool:
        return self.handle_rect().contains(p)


class TemplateCanvas(QLabel):
    """
    Widget canvas donde se muestra la plantilla y se pueden
    arrastrar las cajas de nombre y QR.
    """
    
    boxes_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setCursor(QCursor(Qt.ArrowCursor))
        
        self._pixmap_original: QPixmap = None
        self._scale = 1.0
        self._active_box: DraggableBox = None
        
        # Cajas
        self.name_box = DraggableBox("NOMBRE", 100, 100, 400, 70,
                                     QColor(89, 180, 250, 160))
        self.qr_box = DraggableBox("QR", 100, 200, 200, 200,
                                   QColor(166, 227, 161, 160))
        self._boxes = [self.name_box, self.qr_box]
        
        self.setMouseTracking(True)

    def load_image(self, path: str) -> bool:
        """Carga la imagen de plantilla."""
        pix = QPixmap(path)
        if pix.isNull():
            return False
        self._pixmap_original = pix
        self._update_display()
        return True

    def _update_display(self):
        """Actualiza el widget con la imagen escalada."""
        if not self._pixmap_original:
            return
        available = self.size()
        scaled = self._pixmap_original.scaled(
            available, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._scale = scaled.width() / self._pixmap_original.width()
        self._render_with_boxes(scaled)

    def _render_with_boxes(self, base: QPixmap):
        """Dibuja la imagen base con las cajas superpuestas."""
        result = QPixmap(base.size())
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.drawPixmap(0, 0, base)
        
        for box in self._boxes:
            # Escalar rect al tamaño de visualización
            sr = QRect(
                int(box.rect.x() * self._scale),
                int(box.rect.y() * self._scale),
                int(box.rect.width() * self._scale),
                int(box.rect.height() * self._scale),
            )
            
            # Fondo semitransparente
            fill_color = QColor(box.color)
            fill_color.setAlpha(80)
            painter.fillRect(sr, fill_color)
            
            # Borde
            pen = QPen(box.color, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(sr)
            
            # Etiqueta
            label_color = QColor(box.color)
            label_color.setAlpha(255)
            painter.setPen(QPen(label_color))
            font = QFont("Segoe UI", 10, QFont.Bold)
            painter.setFont(font)
            painter.drawText(sr.adjusted(4, 4, 0, 0), Qt.AlignTop | Qt.AlignLeft, box.name)
            
            # Handle de redimensionado
            hr_display = QRect(
                int(box.handle_rect().x() * self._scale),
                int(box.handle_rect().y() * self._scale),
                int(box.handle_rect().width() * self._scale),
                int(box.handle_rect().height() * self._scale),
            )
            painter.fillRect(hr_display, box.color)
        
        painter.end()
        self.setPixmap(result)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap_original:
            self._update_display()

    def _display_to_original(self, point: QPoint) -> QPoint:
        """Convierte coordenadas del display a coordenadas originales de la imagen."""
        return QPoint(
            int(point.x() / self._scale),
            int(point.y() / self._scale),
        )

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self._pixmap_original:
            return
        orig = self._display_to_original(event.position().toPoint())
        
        for box in reversed(self._boxes):
            if box.on_handle(orig):
                box.resizing = True
                self._active_box = box
                return
            if box.contains(orig):
                box.dragging = True
                box.drag_offset = orig - box.rect.topLeft()
                self._active_box = box
                return

    def mouseMoveEvent(self, event):
        if not self._pixmap_original:
            return
        orig = self._display_to_original(event.position().toPoint())
        
        if self._active_box:
            box = self._active_box
            if box.dragging:
                new_tl = orig - box.drag_offset
                box.rect.moveTo(new_tl)
                self.setCursor(QCursor(Qt.ClosedHandCursor))
            elif box.resizing:
                new_w = max(50, orig.x() - box.rect.x())
                new_h = max(50, orig.y() - box.rect.y())
                box.rect.setWidth(new_w)
                box.rect.setHeight(new_h)
            self._update_display()
            self.boxes_changed.emit()
        else:
            # Cambiar cursor según posición
            for box in self._boxes:
                if box.on_handle(orig):
                    self.setCursor(QCursor(Qt.SizeFDiagCursor))
                    return
                if box.contains(orig):
                    self.setCursor(QCursor(Qt.OpenHandCursor))
                    return
            self.setCursor(QCursor(Qt.ArrowCursor))

    def mouseReleaseEvent(self, event):
        if self._active_box:
            self._active_box.dragging = False
            self._active_box.resizing = False
            self._active_box = None
        self.setCursor(QCursor(Qt.ArrowCursor))

    def get_box_config(self, box: DraggableBox) -> BoxConfig:
        return BoxConfig(
            x=box.rect.x(),
            y=box.rect.y(),
            width=box.rect.width(),
            height=box.rect.height(),
        )


class TemplateConfigDialog(QDialog):
    """
    Diálogo principal de configuración de plantilla.
    """
    
    config_saved = Signal(object)  # AppConfig

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Configurar Plantilla Visual")
        self.setMinimumSize(1000, 700)
        self._setup_ui()
        self._load_existing_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Título
        title = QLabel("🎨 Configuración de Plantilla")
        title.setObjectName("labelTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(
            "Carga tu plantilla y arrastra las cajas para definir dónde irá el nombre y el QR"
        )
        subtitle.setObjectName("labelSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # Área principal: canvas + controles
        main = QHBoxLayout()
        layout.addLayout(main, stretch=1)

        # ── Canvas ──
        canvas_frame = QFrame()
        canvas_frame.setFrameShape(QFrame.StyledPanel)
        canvas_layout = QVBoxLayout(canvas_frame)
        
        self.canvas = TemplateCanvas()
        canvas_layout.addWidget(self.canvas)
        main.addWidget(canvas_frame, stretch=3)

        # ── Panel derecho (con Scroll Area para evitar que las cajas se aplasten) ──
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        right_scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                background: #e0f7f6;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #00A99D;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #008f84;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        right_widget = QWidget()
        right_widget.setStyleSheet("background-color: transparent;")
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(2, 2, 22, 2)
        right.setSpacing(10)

        # Cargar imagen
        grp_img = QGroupBox("📁 Imagen de Plantilla")
        grp_img_l = QVBoxLayout(grp_img)
        
        self.lbl_template_path = QLabel("Sin imagen cargada")
        self.lbl_template_path.setWordWrap(True)
        self.lbl_template_path.setStyleSheet("color: #444444; font-size: 9pt;")
        grp_img_l.addWidget(self.lbl_template_path)
        
        btn_load = QPushButton("📂 Cargar Plantilla (PNG/JPG)")
        btn_load.clicked.connect(self._load_template)
        grp_img_l.addWidget(btn_load)
        
        right.addWidget(grp_img)

        # Posiciones (solo lectura)
        grp_pos = QGroupBox("📍 Posiciones (arrastra en el canvas)")
        grp_pos_l = QFormLayout(grp_pos)
        
        self.lbl_name_pos = QLabel("")
        self.lbl_qr_pos = QLabel("")
        grp_pos_l.addRow("Nombre:", self.lbl_name_pos)
        grp_pos_l.addRow("QR:", self.lbl_qr_pos)
        
        self.canvas.boxes_changed.connect(self._update_position_labels)
        right.addWidget(grp_pos)

        # Configuración de texto
        grp_text = QGroupBox("✏️ Estilo del Nombre")
        grp_text_l = QFormLayout(grp_text)
        
        self.cmb_font = QComboBox()
        fonts = QFontDatabase.families()
        self.cmb_font.addItems([f for f in fonts if f])
        self.cmb_font.setCurrentText("Arial")
        grp_text_l.addRow("Fuente:", self.cmb_font)
        
        self.spn_font_size = QSpinBox()
        self.spn_font_size.setRange(8, 200)
        self.spn_font_size.setValue(36)
        grp_text_l.addRow("Tamaño:", self.spn_font_size)
        
        self.chk_bold = QCheckBox("Negrita")
        self.chk_bold.setChecked(True)
        grp_text_l.addRow("", self.chk_bold)
        
        color_row = QHBoxLayout()
        self.btn_color = QPushButton("  Negro")
        self.btn_color.setStyleSheet("background-color: #000000; color: white;")
        self._text_color = "#000000"
        self.btn_color.clicked.connect(self._pick_color)
        color_row.addWidget(self.btn_color)
        grp_text_l.addRow("Color:", color_row)
        
        self.cmb_align = QComboBox()
        self.cmb_align.addItems(["Centro", "Izquierda", "Derecha"])
        grp_text_l.addRow("Alineación:", self.cmb_align)
        
        right.addWidget(grp_text)

        # Configuración de Drive
        grp_drive = QGroupBox("☁️ Google Drive")
        grp_drive_l = QVBoxLayout(grp_drive)
        
        self.lbl_creds = QLabel("Sin credenciales")
        self.lbl_creds.setWordWrap(True)
        self.lbl_creds.setStyleSheet("color: #444444; font-size: 9pt;")
        grp_drive_l.addWidget(self.lbl_creds)
        
        btn_creds = QPushButton("📄 Cargar Credenciales JSON")
        btn_creds.setStyleSheet("color: black;")
        btn_creds.clicked.connect(self._load_credentials)
        grp_drive_l.addWidget(btn_creds)
        
        drive_note = QLabel("ℹ️ Sin credenciales, se generarán URLs de prueba")
        drive_note.setStyleSheet("color: #d08770; font-size: 8pt; font-weight: bold;")
        drive_note.setWordWrap(True)
        grp_drive_l.addWidget(drive_note)

        # Campo ID de carpeta Drive
        folder_form = QFormLayout()
        folder_lbl = QLabel("ID de carpeta Drive:")
        folder_lbl.setStyleSheet("color: #444444; font-size: 9pt;")
        self.txt_folder_id = QLineEdit()
        self.txt_folder_id.setPlaceholderText("Pega aquí el ID de la carpeta de Drive...")
        self.txt_folder_id.setToolTip(
            "Abre la carpeta en drive.google.com y copia el ID de la URL:\n"
            "https://drive.google.com/drive/folders/👉ESTE_ID👈"
        )
        folder_form.addRow(folder_lbl, self.txt_folder_id)
        grp_drive_l.addLayout(folder_form)

        folder_help = QLabel("📋 Copia el ID del final de la URL de tu carpeta de Drive")
        folder_help.setStyleSheet("color: #666666; font-size: 8pt;")
        folder_help.setWordWrap(True)
        grp_drive_l.addWidget(folder_help)

        right.addWidget(grp_drive)
        right.addStretch()
        
        right_scroll.setWidget(right_widget)
        right_scroll.setFixedWidth(340)
        main.addWidget(right_scroll)

        # Botones finales
        btn_row = QHBoxLayout()
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("btnSecondary")
        btn_cancel.clicked.connect(self.reject)
        
        btn_save = QPushButton("✅ Guardar y Continuar")
        btn_save.clicked.connect(self._save_config)
        
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

        self._update_position_labels()

    def _load_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Plantilla",
            os.path.expanduser("~"),
            "Imágenes (*.png *.jpg *.jpeg *.bmp *.tiff)"
        )
        if path:
            if self.canvas.load_image(path):
                self.config.template_path = path
                self.lbl_template_path.setText(self._get_short_name(path))
            else:
                QMessageBox.warning(self, "Error", "No se pudo cargar la imagen.")

    def _load_credentials(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Credenciales de Google",
            os.path.expanduser("~"),
            "Archivos JSON (*.json)"
        )
        if path:
            self.config.google_drive_credentials = path
            self.lbl_creds.setText(self._get_short_name(path))

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._text_color), self, "Seleccionar color del texto")
        if color.isValid():
            self._text_color = color.name()
            self.btn_color.setStyleSheet(
                f"background-color: {self._text_color}; "
                f"color: {'black' if color.lightness() > 128 else 'white'};"
            )
            self.btn_color.setText(f"  {self._text_color.upper()}")

    def _update_position_labels(self):
        nb = self.canvas.name_box.rect
        qb = self.canvas.qr_box.rect
        self.lbl_name_pos.setText(f"X:{nb.x()} Y:{nb.y()} W:{nb.width()} H:{nb.height()}")
        self.lbl_qr_pos.setText(f"X:{qb.x()} Y:{qb.y()} W:{qb.width()} H:{qb.height()}")

    def _get_short_name(self, path: str, max_len: int = 30) -> str:
        if not path:
            return "Sin archivo"
        name = os.path.basename(path)
        if len(name) > max_len:
            return name[:15] + "..." + name[-10:]
        return name

    def _load_existing_config(self):
        """Carga configuración existente en el formulario."""
        if self.config.template_path and os.path.exists(self.config.template_path):
            self.canvas.load_image(self.config.template_path)
            self.lbl_template_path.setText(self._get_short_name(self.config.template_path))
        
        # Restaurar posiciones
        nb = self.config.name_box
        self.canvas.name_box.rect = QRect(nb.x, nb.y, nb.width, nb.height)
        
        qb = self.config.qr_box
        self.canvas.qr_box.rect = QRect(qb.x, qb.y, qb.width, qb.height)
        
        # Texto
        tc = self.config.text_config
        idx = self.cmb_font.findText(tc.font_family)
        if idx >= 0:
            self.cmb_font.setCurrentIndex(idx)
        self.spn_font_size.setValue(tc.font_size)
        self.chk_bold.setChecked(tc.font_bold)
        self._text_color = tc.color
        self.btn_color.setStyleSheet(f"background-color: {tc.color};")
        
        align_map = {"center": 0, "left": 1, "right": 2}
        self.cmb_align.setCurrentIndex(align_map.get(tc.align, 0))
        
        if self.config.google_drive_credentials:
            self.lbl_creds.setText(self._get_short_name(self.config.google_drive_credentials))
        if self.config.google_drive_folder_id:
            self.txt_folder_id.setText(self.config.google_drive_folder_id)
        
        self._update_position_labels()

    def _save_config(self):
        if not self.config.template_path:
            QMessageBox.warning(self, "Falta plantilla", "Por favor carga una imagen de plantilla.")
            return
        
        # Leer posiciones del canvas
        self.config.name_box = self.canvas.get_box_config(self.canvas.name_box)
        self.config.qr_box = self.canvas.get_box_config(self.canvas.qr_box)
        
        # Texto
        align_map = {0: "center", 1: "left", 2: "right"}
        self.config.text_config = TextConfig(
            font_family=self.cmb_font.currentText(),
            font_size=self.spn_font_size.value(),
            font_bold=self.chk_bold.isChecked(),
            color=self._text_color,
            align=align_map.get(self.cmb_align.currentIndex(), "center"),
        )
        
        self.config.google_drive_folder_id = self.txt_folder_id.text().strip()
        if save_config(self.config):
            self.config_saved.emit(self.config)
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "No se pudo guardar la configuración.")

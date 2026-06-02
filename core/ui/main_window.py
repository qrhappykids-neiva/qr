import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
Ventana principal de la aplicación Boletines QR.
Coordina todos los módulos y presenta la interfaz principal.
"""

import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QProgressBar, QTextEdit, QGroupBox,
    QSplitter, QFrame, QMessageBox, QStatusBar, QTabWidget,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCursor, QIcon, QPixmap

from core.config import load_config, save_config, config_exists, AppConfig
from core.file_scanner import scan_pptx_files, get_folder_summary
from core.name_extractor import batch_extract_names
from core.processor import ProcessingWorker
from ui.template_config import TemplateConfigDialog
from ui.names_editor import NamesEditorDialog
from ui.gallery import GalleryDialog

logger = logging.getLogger(__name__)


class LogHandler(logging.Handler):
    """Handler de logging que redirige al widget de texto."""
    
    def __init__(self, text_widget: QTextEdit):
        super().__init__()
        self.widget = text_widget
    
    def emit(self, record):
        msg = self.format(record)
        self.widget.append(msg)
        self.widget.moveCursor(QTextCursor.End)


class MainWindow(QMainWindow):
    """Ventana principal de Boletines QR."""

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.current_folder = self.config.last_folder
        self.students = []  # lista de dicts post-edición
        self._worker = None
        self._results = []
        
        self.setWindowTitle("📋 Boletines QR — Generador Automático")
        self.setMinimumSize(1100, 750)
        
        # Cargar ícono de la ventana
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(project_root, "Logo.jpg")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
        
        self._setup_ui()
        self._setup_logging()
        self._check_initial_config()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 12)
        main_layout.setSpacing(12)

        # ── HEADER ──
        header = QHBoxLayout()
        
        logo_lbl = QLabel()
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(project_root, "Logo.jpg")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Soporte para pantallas de alta resolución (HiDPI) para evitar que se vea borroso
            ratio = self.devicePixelRatioF()  # Obtiene el factor de escala decimal exacto de la pantalla
            target_height = 55
            scaled_pixmap = pixmap.scaledToHeight(int(target_height * ratio), Qt.SmoothTransformation)
            scaled_pixmap.setDevicePixelRatio(ratio)
            logo_lbl.setPixmap(scaled_pixmap)
        else:
            logo_lbl.setText("📋")
            logo_lbl.setFont(QFont("Segoe UI Emoji", 28))
        header.addWidget(logo_lbl)
        
        title_col = QVBoxLayout()
        title = QLabel("Boletines QR")
        title.setObjectName("labelTitle")
        subtitle = QLabel("Generador Automático de Boletines Escolares con Código QR")
        subtitle.setObjectName("labelSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch()
        
        # Indicador de plantilla
        self.lbl_template_status = QLabel()
        self._update_template_status()
        header.addWidget(self.lbl_template_status)
        
        btn_config = QPushButton("⚙️ Configurar Plantilla")
        btn_config.setObjectName("btnSecondary")
        btn_config.clicked.connect(self._open_template_config)
        header.addWidget(btn_config)
        
        main_layout.addLayout(header)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #45475a;")
        sep.setFixedHeight(1)
        main_layout.addWidget(sep)

        # ── CONTENIDO PRINCIPAL ──
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter, stretch=1)

        # Panel superior: controles
        top_panel = QWidget()
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        # Selección de carpeta
        folder_grp = QGroupBox("📁 Selección de Carpeta")
        folder_layout = QHBoxLayout(folder_grp)
        
        self.lbl_folder = QLabel("Ninguna carpeta seleccionada")
        self.lbl_folder.setStyleSheet("color: #555555;")
        self.lbl_folder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        folder_layout.addWidget(self.lbl_folder, stretch=1)
        
        btn_select = QPushButton("📂 Seleccionar Carpeta")
        btn_select.clicked.connect(self._select_folder)
        folder_layout.addWidget(btn_select)
        
        top_layout.addWidget(folder_grp)

        # Resumen de archivos encontrados
        self.summary_grp = QGroupBox("📊 Resumen de Archivos Encontrados")
        summary_layout = QHBoxLayout(self.summary_grp)
        
        self.lbl_pptx_count = QLabel("—")
        self.lbl_pptx_count.setStyleSheet("font-size: 24pt; font-weight: bold; color: #0072BC;")
        self.lbl_pptx_count.setAlignment(Qt.AlignCenter)
        
        summary_right = QVBoxLayout()
        self.lbl_summary_text = QLabel("Selecciona una carpeta para comenzar")
        self.lbl_summary_text.setStyleSheet("color: #555555;")
        self.lbl_summary_text.setWordWrap(True)
        summary_right.addWidget(self.lbl_summary_text)
        
        self.btn_edit_names = QPushButton("✏️ Ver y Editar Nombres")
        self.btn_edit_names.setObjectName("btnSecondary")
        self.btn_edit_names.setEnabled(False)
        self.btn_edit_names.clicked.connect(self._edit_names)
        summary_right.addWidget(self.btn_edit_names)
        
        summary_layout.addWidget(self.lbl_pptx_count)
        summary_layout.addLayout(summary_right, stretch=1)
        top_layout.addWidget(self.summary_grp)

        # Progreso
        progress_grp = QGroupBox("⚙️ Progreso de Procesamiento")
        progress_layout = QVBoxLayout(progress_grp)
        
        self.lbl_stage = QLabel("En espera...")
        self.lbl_stage.setStyleSheet("color: #0072BC; font-weight: bold;")
        progress_layout.addWidget(self.lbl_stage)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%  —  %v de %m operaciones")
        progress_layout.addWidget(self.progress_bar)
        
        self.lbl_progress_detail = QLabel("")
        self.lbl_progress_detail.setStyleSheet("color: #555555; font-size: 9pt;")
        progress_layout.addWidget(self.lbl_progress_detail)
        
        top_layout.addWidget(progress_grp)
        splitter.addWidget(top_panel)

        # Panel inferior: log
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        
        log_header = QHBoxLayout()
        log_lbl = QLabel("📝 Registro de Procesamiento")
        log_lbl.setStyleSheet("font-weight: bold; color: #0072BC;")
        log_header.addWidget(log_lbl)
        log_header.addStretch()
        
        btn_clear_log = QPushButton("Limpiar")
        btn_clear_log.setObjectName("btnSecondary")
        btn_clear_log.setMaximumWidth(80)
        btn_clear_log.clicked.connect(lambda: self.log_text.clear())
        log_header.addWidget(btn_clear_log)
        log_layout.addLayout(log_header)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 6px;
            }
        """)
        log_layout.addWidget(self.log_text)
        splitter.addWidget(log_widget)
        
        splitter.setSizes([420, 250])

        # ── BOTONES DE ACCIÓN ──
        action_row = QHBoxLayout()
        
        self.btn_process = QPushButton("🚀 Iniciar Procesamiento")
        self.btn_process.setEnabled(False)
        self.btn_process.setMinimumHeight(42)
        self.btn_process.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.btn_process.clicked.connect(self._start_processing)
        
        self.btn_cancel = QPushButton("⏹ Cancelar")
        self.btn_cancel.setObjectName("btnDanger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setMinimumHeight(42)
        self.btn_cancel.clicked.connect(self._cancel_processing)
        
        self.btn_gallery = QPushButton("🖼️ Ver Galería")
        self.btn_gallery.setObjectName("btnSecondary")
        self.btn_gallery.setEnabled(False)
        self.btn_gallery.setMinimumHeight(42)
        self.btn_gallery.clicked.connect(self._show_gallery)
        
        action_row.addWidget(self.btn_gallery)
        action_row.addStretch()
        action_row.addWidget(self.btn_cancel)
        action_row.addWidget(self.btn_process)
        main_layout.addLayout(action_row)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo — Configura la plantilla y selecciona una carpeta para comenzar.")

    def _setup_logging(self):
        """Configura el sistema de logging para mostrar en el widget de texto."""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        handler = LogHandler(self.log_text)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        root_logger.addHandler(handler)

    def _check_initial_config(self):
        """Al inicio, verifica si hay plantilla configurada."""
        if not config_exists():
            QTimer.singleShot(500, self._prompt_initial_config)
        else:
            self._log("✅ Configuración cargada correctamente.")
            if self.current_folder and os.path.exists(self.current_folder):
                self._load_folder(self.current_folder)

    def _prompt_initial_config(self):
        """Solicita configurar la plantilla si no hay una."""
        reply = QMessageBox.question(
            self,
            "Bienvenido a Boletines QR",
            "No se encontró una plantilla configurada.\n\n"
            "¿Deseas configurar la plantilla ahora?\n"
            "(También puedes hacerlo después desde ⚙️ Configurar Plantilla)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._open_template_config()

    def _open_template_config(self):
        """Abre el diálogo de configuración de plantilla."""
        dlg = TemplateConfigDialog(self.config, self)
        dlg.config_saved.connect(self._on_config_saved)
        dlg.exec()

    def _on_config_saved(self, config: AppConfig):
        self.config = config
        self._update_template_status()
        self._log("✅ Plantilla configurada y guardada.")
        self.status_bar.showMessage("Plantilla configurada. Ahora selecciona una carpeta.")

    def _update_template_status(self):
        if self.config.template_path and os.path.exists(self.config.template_path):
            name = os.path.basename(self.config.template_path)
            self.lbl_template_status.setText(f"🟢 Plantilla: {name}")
            self.lbl_template_status.setStyleSheet("color: #2e7d32; font-size: 9pt; font-weight: bold;")
        else:
            self.lbl_template_status.setText("🔴 Sin plantilla")
            self.lbl_template_status.setStyleSheet("color: #c62828; font-size: 9pt; font-weight: bold;")

    def _select_folder(self):
        """Abre diálogo para seleccionar carpeta."""
        start = self.current_folder or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, "Seleccionar Carpeta con Presentaciones PowerPoint", start
        )
        if folder:
            self._load_folder(folder)

    def _load_folder(self, folder: str):
        """Carga y analiza la carpeta seleccionada."""
        self.current_folder = folder
        self.config.last_folder = folder
        save_config(self.config)
        
        self.lbl_folder.setText(folder)
        self._log(f"\n📁 Carpeta seleccionada: {folder}")
        
        summary = get_folder_summary(folder)
        total = summary["total_files"]
        
        if total == 0:
            self.lbl_pptx_count.setText("0")
            self.lbl_summary_text.setText(
                "No se encontraron archivos .pptx en esta carpeta."
            )
            self.btn_edit_names.setEnabled(False)
            self.btn_process.setEnabled(False)
            self._log("⚠️ No se encontraron archivos .pptx")
            return
        
        self.lbl_pptx_count.setText(str(total))
        self.lbl_summary_text.setText(
            f"Se encontraron {total} archivos PowerPoint en "
            f"{summary['total_folders']} carpeta(s).\n"
            "Usa 'Ver y Editar Nombres' para revisar los nombres detectados."
        )
        
        # Extraer nombres automáticamente
        self.students = batch_extract_names(summary["files"])
        self._log(f"✅ {total} archivos detectados. Nombres extraídos automáticamente.")
        
        self.btn_edit_names.setEnabled(True)
        self.btn_process.setEnabled(True)
        self.status_bar.showMessage(
            f"{total} archivos listos. Edita los nombres y luego presiona 'Iniciar Procesamiento'."
        )

    def _edit_names(self):
        """Abre el editor de nombres."""
        if not self.students:
            return
        dlg = NamesEditorDialog(self.students, self)
        dlg.names_confirmed.connect(self._on_names_confirmed)
        dlg.exec()

    def _on_names_confirmed(self, confirmed_students: list):
        """Callback cuando se confirman los nombres."""
        self.students = confirmed_students
        self._log(f"✅ {len(confirmed_students)} nombres confirmados por el usuario.")
        self.status_bar.showMessage(
            f"Nombres confirmados. Presiona 'Iniciar Procesamiento' para continuar."
        )

    def _start_processing(self):
        """Inicia el procesamiento en hilo separado."""
        if not self.students:
            QMessageBox.warning(self, "Sin estudiantes", "Primero selecciona una carpeta.")
            return
        
        if not self.config.template_path:
            reply = QMessageBox.question(
                self, "Sin plantilla",
                "No hay plantilla configurada. ¿Continuar sin generar imágenes PNG?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                self._open_template_config()
                return
        
        # Confirmar
        reply = QMessageBox.question(
            self, "Iniciar Procesamiento",
            f"¿Procesar {len(self.students)} estudiante(s)?\n\n"
            "El proceso puede tardar varios minutos dependiendo de la cantidad.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        self._log(f"\n{'='*50}")
        self._log(f"🚀 INICIANDO PROCESAMIENTO — {len(self.students)} estudiantes")
        self._log(f"{'='*50}")

        # Configurar UI
        self.btn_process.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_edit_names.setEnabled(False)
        self.btn_gallery.setEnabled(False)
        self.progress_bar.setMaximum(len(self.students) * 4)
        self.progress_bar.setValue(0)

        # Crear y arrancar worker
        self._worker = ProcessingWorker(self.students, self.config, self)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.stage_changed.connect(self._on_stage_changed)
        self._worker.student_done.connect(self._on_student_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.log_message.connect(self._log)
        self._worker.start()

    def _cancel_processing(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.btn_cancel.setEnabled(False)
            self.lbl_stage.setText("Cancelando...")

    def _on_progress(self, current: int, total: int, message: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.lbl_progress_detail.setText(message)

    def _on_stage_changed(self, stage: str):
        self.lbl_stage.setText(stage)
        self.status_bar.showMessage(stage)

    def _on_student_done(self, result):
        pass  # Log ya se hace en el worker

    def _on_all_done(self, results: list):
        self._results = results
        ok = sum(1 for r in results if r.success)
        fail = len(results) - ok
        
        self.btn_process.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_edit_names.setEnabled(True)
        self.btn_gallery.setEnabled(True)
        self.lbl_stage.setText(f"✅ Completado — {ok} exitosos, {fail} con errores")
        
        self.status_bar.showMessage(
            f"Procesamiento completo: {ok}/{len(results)} exitosos. "
            "Usa 'Ver Galería' para verificar."
        )

        if ok > 0:
            QMessageBox.information(
                self,
                "Procesamiento Completo",
                f"✅ Se procesaron {ok} de {len(results)} estudiantes correctamente.\n"
                + (f"⚠️ {fail} tuvieron errores (revisar el log).\n" if fail else "")
                + "\nPresiona 'Ver Galería' para verificar los resultados.",
            )

    def _show_gallery(self):
        if not self._results:
            QMessageBox.information(self, "Galería", "Aún no hay resultados para mostrar.")
            return
        dlg = GalleryDialog(self._results, self)
        dlg.exec()

    def _log(self, message: str):
        """Agrega un mensaje al log de la interfaz."""
        self.log_text.append(message)
        self.log_text.moveCursor(QTextCursor.End)

    def closeEvent(self, event):
        """Al cerrar, guardar config y cancelar worker si está activo."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        save_config(self.config)
        event.accept()

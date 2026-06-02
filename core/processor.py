import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
Módulo de procesamiento en hilo separado.
Ejecuta todo el pipeline sin bloquear la interfaz gráfica.
"""

import os
import logging
import traceback
from typing import Callable, Optional

from PySide6.QtCore import QThread, Signal

from core.pdf_converter import convert_with_fallback
from core.drive_uploader import create_uploader
from core.qr_generator import generate_qr
from core.image_composer import compose_bulletin
from core.file_scanner import get_output_paths, create_output_dirs
from core.name_extractor import sanitize_filename
from core.config import AppConfig

logger = logging.getLogger(__name__)


class ProcessingResult:
    """Resultado del procesamiento de un estudiante."""
    
    def __init__(self, student_name: str, pptx_path: str):
        self.student_name = student_name
        self.pptx_path = pptx_path
        self.pdf_path: str = ""
        self.qr_path: str = ""
        self.png_path: str = ""
        self.drive_url: str = ""
        self.pdf_ok = False
        self.upload_ok = False
        self.qr_ok = False
        self.png_ok = False
        self.error: str = ""
    
    @property
    def success(self) -> bool:
        return self.pdf_ok and self.upload_ok and self.qr_ok and self.png_ok
    
    def to_dict(self) -> dict:
        return {
            "student_name": self.student_name,
            "pptx_path": self.pptx_path,
            "pdf_path": self.pdf_path,
            "qr_path": self.qr_path,
            "png_path": self.png_path,
            "drive_url": self.drive_url,
            "pdf_ok": self.pdf_ok,
            "upload_ok": self.upload_ok,
            "qr_ok": self.qr_ok,
            "png_ok": self.png_ok,
            "error": self.error,
        }


class ProcessingWorker(QThread):
    """
    Hilo de trabajo que ejecuta el pipeline completo de procesamiento.
    Emite señales para actualizar la UI sin bloquear el hilo principal.
    """
    
    # Señales
    progress_updated = Signal(int, int, str)  # actual, total, mensaje
    student_done = Signal(object)             # ProcessingResult
    stage_changed = Signal(str)               # nombre de la etapa actual
    all_done = Signal(list)                   # lista de ProcessingResult
    error_occurred = Signal(str)              # mensaje de error crítico
    log_message = Signal(str)                 # mensaje de log

    def __init__(
        self,
        students: list[dict],  # [{"path": ..., "name": ...}]
        config: AppConfig,
        parent=None
    ):
        super().__init__(parent)
        self.students = students
        self.config = config
        self._cancelled = False
        self.results: list[ProcessingResult] = []

    def cancel(self):
        """Solicita cancelación del procesamiento."""
        self._cancelled = True
        logger.info("Cancelación solicitada por el usuario.")

    def run(self):
        """Método principal del hilo."""
        total = len(self.students)
        self.results = []

        self.log_message.emit(f"Iniciando procesamiento de {total} estudiantes...")

        # Inicializar uploader de Drive
        self.stage_changed.emit("Conectando a Google Drive...")
        uploader = create_uploader(
            self.config.google_drive_credentials,
            self.config.google_drive_folder_id,
            mock=not bool(self.config.google_drive_credentials)
        )

        for idx, student in enumerate(self.students):
            if self._cancelled:
                self.log_message.emit("⚠️ Procesamiento cancelado por el usuario.")
                break

            name = student["name"]
            pptx_path = student["path"]
            safe_name = sanitize_filename(name)

            result = ProcessingResult(name, pptx_path)
            self.log_message.emit(f"\n▶ [{idx+1}/{total}] {name}")

            try:
                # Crear directorios
                dirs = create_output_dirs(pptx_path)
                paths = {
                    "pdf": os.path.join(dirs["PDF"], f"{safe_name}.pdf"),
                    "qr": os.path.join(dirs["QR"], f"{safe_name}.png"),
                    "png": os.path.join(dirs["PNG"], f"{safe_name}.png"),
                }
                result.pdf_path = paths["pdf"]
                result.qr_path = paths["qr"]
                result.png_path = paths["png"]

                # ── ETAPA 1: Convertir PPTX → PDF ──
                self.stage_changed.emit(f"Convirtiendo PPT ({idx+1}/{total})...")
                self.progress_updated.emit(idx * 4 + 1, total * 4, f"Convirtiendo: {name}")
                self.log_message.emit(f"  📄 Convirtiendo PPTX a PDF...")
                
                ok, method = convert_with_fallback(pptx_path, paths["pdf"])
                result.pdf_ok = ok
                
                if ok:
                    self.log_message.emit(f"  ✅ PDF generado ({method})")
                else:
                    self.log_message.emit(f"  ❌ Error al convertir PPTX")
                    result.error = "Fallo en conversión PPTX→PDF"

                # ── ETAPA 2: Subir a Google Drive ──
                self.stage_changed.emit(f"Subiendo a Drive ({idx+1}/{total})...")
                self.progress_updated.emit(idx * 4 + 2, total * 4, f"Subiendo: {name}")
                self.log_message.emit(f"  ☁️ Subiendo a Google Drive...")
                
                if result.pdf_ok:
                    url = uploader.upload_pdf(paths["pdf"], f"{safe_name}.pdf")
                    if url:
                        result.drive_url = url
                        result.upload_ok = True
                        self.log_message.emit(f"  ✅ Subido: {url[:60]}...")
                    else:
                        self.log_message.emit(f"  ❌ Error al subir a Drive")
                        result.error = "Fallo en subida a Drive"
                else:
                    self.log_message.emit(f"  ⏭️ Subida omitida (PDF inválido)")

                # ── ETAPA 3: Generar QR ──
                self.stage_changed.emit(f"Generando QR ({idx+1}/{total})...")
                self.progress_updated.emit(idx * 4 + 3, total * 4, f"Generando QR: {name}")
                self.log_message.emit(f"  📲 Generando código QR...")
                
                qr_url = result.drive_url or f"https://placeholder.url/{safe_name}"
                ok_qr = generate_qr(
                    url=qr_url,
                    output_path=paths["qr"],
                    size=800,
                    error_correction=self.config.qr_error_correction,
                )
                result.qr_ok = ok_qr
                
                if ok_qr:
                    self.log_message.emit(f"  ✅ QR generado")
                else:
                    self.log_message.emit(f"  ❌ Error generando QR")
                    result.error = result.error or "Fallo en generación QR"

                # ── ETAPA 4: Generar PNG final ──
                self.stage_changed.emit(f"Generando PNG ({idx+1}/{total})...")
                self.progress_updated.emit(idx * 4 + 4, total * 4, f"Generando imagen: {name}")
                self.log_message.emit(f"  🖼️ Componiendo imagen final...")
                
                if self.config.template_path and os.path.exists(self.config.template_path):
                    ok_png = compose_bulletin(
                        template_path=self.config.template_path,
                        output_path=paths["png"],
                        student_name=name,
                        qr_path=paths["qr"],
                        name_box={
                            "x": self.config.name_box.x,
                            "y": self.config.name_box.y,
                            "width": self.config.name_box.width,
                            "height": self.config.name_box.height,
                        },
                        qr_box={
                            "x": self.config.qr_box.x,
                            "y": self.config.qr_box.y,
                            "width": self.config.qr_box.width,
                            "height": self.config.qr_box.height,
                        },
                        text_config={
                            "font_family": self.config.text_config.font_family,
                            "font_size": self.config.text_config.font_size,
                            "font_bold": self.config.text_config.font_bold,
                            "color": self.config.text_config.color,
                            "align": self.config.text_config.align,
                        },
                        dpi=self.config.output_dpi,
                    )
                    result.png_ok = ok_png
                    if ok_png:
                        self.log_message.emit(f"  ✅ PNG generado en alta calidad")
                    else:
                        self.log_message.emit(f"  ❌ Error generando PNG")
                else:
                    self.log_message.emit(f"  ⚠️ Sin plantilla configurada. PNG omitido.")
                    result.png_ok = False

            except Exception as e:
                result.error = str(e)
                self.log_message.emit(f"  💥 Error inesperado: {e}")
                logger.error(f"Error procesando {name}: {traceback.format_exc()}")

            self.results.append(result)
            self.student_done.emit(result)

        # Resumen final
        ok_count = sum(1 for r in self.results if r.success)
        fail_count = len(self.results) - ok_count
        self.log_message.emit(
            f"\n{'='*50}\n"
            f"✅ Completados: {ok_count}\n"
            f"❌ Con errores: {fail_count}\n"
            f"{'='*50}"
        )
        
        self.progress_updated.emit(total * 4, total * 4, "¡Procesamiento completo!")
        self.stage_changed.emit("Completado")
        self.all_done.emit(self.results)

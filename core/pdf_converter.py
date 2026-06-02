"""
Módulo de conversión PPTX → PDF.
Usa Microsoft PowerPoint vía COM (win32com) para Windows.
"""

import os
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_pptx_to_pdf(pptx_path: str, pdf_path: str) -> bool:
    try:
        import win32com.client
        import pythoncom
    except ImportError:
        raise RuntimeError("Requiere pywin32: pip install pywin32")

    pptx_path = str(Path(pptx_path).resolve())
    pdf_path = str(Path(pdf_path).resolve())
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    powerpoint = None
    presentation = None

    try:
        pythoncom.CoInitialize()

        # Crear instancia visible para evitar el error de PowerPoint 2016
        powerpoint = win32com.client.Dispatch("PowerPoint.Application")
        # NO poner Visible = False en PowerPoint 2016, causa error
        # En su lugar abrimos minimizada
        powerpoint.WindowState = 2  # ppWindowMinimized

        presentation = powerpoint.Presentations.Open(
            pptx_path,
            WithWindow=False,
            ReadOnly=True
        )

        # Guardar como PDF (formato 32 = ppSaveAsPDF)
        presentation.SaveAs(pdf_path, 32)

        logger.info(f"Convertido: {os.path.basename(pptx_path)} → {os.path.basename(pdf_path)}")
        return True

    except Exception as e:
        logger.error(f"Error convirtiendo {pptx_path}: {e}")
        return False

    finally:
        if presentation:
            try:
                presentation.Close()
            except Exception:
                pass
        if powerpoint:
            try:
                powerpoint.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        time.sleep(0.5)


def convert_pptx_to_pdf_libreoffice(pptx_path: str, pdf_path: str) -> bool:
    import subprocess
    pptx_path = str(Path(pptx_path).resolve())
    output_dir = str(Path(pdf_path).parent.resolve())
    try:
        result = subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf",
             "--outdir", output_dir, pptx_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return False
        generated = os.path.join(
            output_dir,
            os.path.splitext(os.path.basename(pptx_path))[0] + ".pdf"
        )
        if generated != pdf_path and os.path.exists(generated):
            os.rename(generated, pdf_path)
        return os.path.exists(pdf_path)
    except Exception as e:
        logger.error(f"Error con LibreOffice: {e}")
        return False


def convert_with_fallback(pptx_path: str, pdf_path: str) -> tuple:
    try:
        success = convert_pptx_to_pdf(pptx_path, pdf_path)
        if success:
            return True, "PowerPoint"
    except RuntimeError:
        pass
    except Exception as e:
        logger.warning(f"PowerPoint falló: {e}")

    success = convert_pptx_to_pdf_libreoffice(pptx_path, pdf_path)
    return success, "LibreOffice"

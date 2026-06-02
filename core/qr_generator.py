"""
Módulo de generación de códigos QR en alta resolución.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Niveles de corrección de error para QR
ERROR_CORRECTION_MAP = {
    "L": None,  # se resuelve en runtime
    "M": None,
    "Q": None,
    "H": None,
}


def generate_qr(
    url: str,
    output_path: str,
    size: int = 800,
    error_correction: str = "H",
    border: int = 2,
    fill_color: str = "black",
    back_color: str = "white",
) -> bool:
    """
    Genera un código QR de alta resolución.
    
    Args:
        url: URL a codificar en el QR.
        output_path: Ruta donde guardar el PNG.
        size: Tamaño en píxeles del QR generado (cuadrado).
        error_correction: Nivel de corrección 'L', 'M', 'Q', 'H'.
        border: Borde en módulos alrededor del QR.
        fill_color: Color del QR.
        back_color: Color de fondo.
        
    Returns:
        True si fue exitoso.
    """
    try:
        import qrcode
        from qrcode.constants import (
            ERROR_CORRECT_L, ERROR_CORRECT_M,
            ERROR_CORRECT_Q, ERROR_CORRECT_H
        )
        from PIL import Image
    except ImportError:
        logger.error("Instala: pip install qrcode[pil] Pillow")
        raise RuntimeError("Dependencias faltantes: qrcode, Pillow")

    ec_map = {
        "L": ERROR_CORRECT_L,
        "M": ERROR_CORRECT_M,
        "Q": ERROR_CORRECT_Q,
        "H": ERROR_CORRECT_H,
    }
    ec = ec_map.get(error_correction.upper(), ERROR_CORRECT_H)

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        qr = qrcode.QRCode(
            version=None,          # auto-detectar versión
            error_correction=ec,
            box_size=10,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)

        # Crear imagen
        img = qr.make_image(fill_color=fill_color, back_color=back_color)
        
        # Redimensionar a tamaño deseado con alta calidad
        img = img.convert("RGBA")
        img = img.resize((size, size), Image.LANCZOS)
        
        # Guardar como PNG sin compresión pérdida
        img.save(output_path, "PNG", optimize=False, compress_level=1)
        
        logger.info(f"QR generado: {os.path.basename(output_path)} ({size}x{size}px)")
        return True

    except Exception as e:
        logger.error(f"Error generando QR para {url}: {e}")
        return False


def generate_qr_with_logo(
    url: str,
    output_path: str,
    logo_path: str,
    size: int = 800,
    logo_size_ratio: float = 0.2,
) -> bool:
    """
    Genera QR con logo en el centro (ideal para branding institucional).
    El logo ocupa logo_size_ratio del tamaño total del QR.
    Usa error_correction=H para mayor tolerancia al logo tapando parte del QR.
    """
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_H
        from PIL import Image
    except ImportError:
        raise RuntimeError("Instala: pip install qrcode[pil] Pillow")

    try:
        # Generar QR base
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        img = img.resize((size, size), Image.LANCZOS)

        # Insertar logo si existe
        if logo_path and os.path.exists(logo_path):
            logo = Image.open(logo_path).convert("RGBA")
            logo_size = int(size * logo_size_ratio)
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
            
            pos = ((size - logo_size) // 2, (size - logo_size) // 2)
            img.paste(logo, pos, mask=logo)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, "PNG")
        return True

    except Exception as e:
        logger.error(f"Error generando QR con logo: {e}")
        return False

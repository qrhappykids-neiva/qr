"""
Módulo de composición de imagen final.
Inserta el nombre del estudiante y el código QR sobre la plantilla visual.
"""

import os
import logging
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def compose_bulletin(
    template_path: str,
    output_path: str,
    student_name: str,
    qr_path: str,
    name_box: dict,
    qr_box: dict,
    text_config: dict,
    dpi: int = 300,
) -> bool:
    """
    Compone la imagen final del boletín insertando nombre y QR en la plantilla.
    
    Args:
        template_path: Ruta a la imagen de plantilla (PNG/JPG).
        output_path: Ruta de salida para el PNG final.
        student_name: Nombre completo del estudiante.
        qr_path: Ruta al PNG del código QR.
        name_box: Dict con x, y, width, height para el área del nombre.
        qr_box: Dict con x, y, width, height para el área del QR.
        text_config: Dict con font_family, font_size, font_bold, color, align.
        dpi: Resolución de salida (default 300 DPI).
        
    Returns:
        True si fue exitoso.
    """
    try:
        # Abrir plantilla
        template = Image.open(template_path).convert("RGBA")
        draw = ImageDraw.Draw(template)

        # === Insertar QR ===
        _insert_qr(template, qr_path, qr_box)

        # === Insertar nombre ===
        _insert_name(draw, template, student_name, name_box, text_config)

        # Guardar como PNG con metadata DPI
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final = template.convert("RGB")
        final.save(output_path, "PNG", dpi=(dpi, dpi))
        
        logger.info(f"Boletín generado: {os.path.basename(output_path)}")
        return True

    except Exception as e:
        logger.error(f"Error componiendo boletín para {student_name}: {e}")
        return False


def _insert_qr(template: Image.Image, qr_path: str, qr_box: dict):
    """Inserta el QR en la posición especificada."""
    if not qr_path or not os.path.exists(qr_path):
        logger.warning(f"QR no encontrado: {qr_path}")
        return

    qr_img = Image.open(qr_path).convert("RGBA")
    
    # Redimensionar al área definida
    target_size = (qr_box["width"], qr_box["height"])
    qr_img = qr_img.resize(target_size, Image.LANCZOS)
    
    # Pegar con transparencia
    template.paste(qr_img, (qr_box["x"], qr_box["y"]), mask=qr_img)


def _insert_name(
    draw: ImageDraw.ImageDraw,
    template: Image.Image,
    name: str,
    name_box: dict,
    text_config: dict,
):
    """Inserta el nombre del estudiante ajustando el tamaño si es necesario."""
    font_size = text_config.get("font_size", 36)
    font_family = text_config.get("font_family", "Arial")
    color = text_config.get("color", "#000000")
    align = text_config.get("align", "center")
    bold = text_config.get("font_bold", True)

    max_width = name_box["width"]
    max_height = name_box["height"]

    # Cargar fuente, reducir tamaño automáticamente si el nombre no entra
    font = _load_font(font_family, font_size, bold)
    
    # Auto-ajustar tamaño si es necesario
    font, font_size = _auto_fit_text(draw, name, font_family, bold, font_size, max_width, max_height)

    # Calcular posición según alineación
    x, y = _calculate_text_position(draw, name, font, name_box, align)
    
    # Dibujar sombra sutil para mejor legibilidad (opcional)
    shadow_color = _get_shadow_color(color)
    if shadow_color:
        draw.text((x + 2, y + 2), name, font=font, fill=shadow_color)

    draw.text((x, y), name, font=font, fill=color)


def _load_font(family: str, size: int, bold: bool) -> ImageFont.FreeTypeFont:
    """Carga una fuente TrueType, con fallback inteligente a fuentes Unicode del sistema."""
    # Carpetas de fuentes (sistema y de usuario local)
    font_dirs = [r"C:\Windows\Fonts"]
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        font_dirs.append(os.path.join(local_appdata, r"Microsoft\Windows\Fonts"))

    # Intentar búsqueda inteligente: buscar cualquier archivo de fuente que contenga el nombre de la familia
    family_clean = family.replace(" ", "").lower()
    
    # 1. Buscar coincidencias que respeten la variante Bold deseada
    for font_dir in font_dirs:
        if not os.path.exists(font_dir):
            continue
        try:
            for filename in os.listdir(font_dir):
                if not (filename.lower().endswith(".ttf") or filename.lower().endswith(".otf")):
                    continue
                name_without_ext = os.path.splitext(filename)[0].lower()
                if family_clean in name_without_ext:
                    is_bold_file = any(x in name_without_ext for x in ["bd", "bold", "b"])
                    # Coincidencia con el estilo solicitado (bold)
                    if bold == is_bold_file:
                        path = os.path.join(font_dir, filename)
                        try:
                            return ImageFont.truetype(path, size)
                        except Exception:
                            pass
        except Exception:
            pass

    # 2. Segunda pasada: cualquier coincidencia con el nombre si no se encontró con el estilo exacto
    for font_dir in font_dirs:
        if not os.path.exists(font_dir):
            continue
        try:
            for filename in os.listdir(font_dir):
                if not (filename.lower().endswith(".ttf") or filename.lower().endswith(".otf")):
                    continue
                name_without_ext = os.path.splitext(filename)[0].lower()
                if family_clean in name_without_ext:
                    path = os.path.join(font_dir, filename)
                    try:
                        return ImageFont.truetype(path, size)
                    except Exception:
                        pass
        except Exception:
            pass

    # Fallback robusto a Arial, Calibri o fuentes comunes que sí soportan caracteres con acentos
    for fname in ["arial.ttf", "calibri.ttf", "times.ttf", "verdana.ttf"]:
        for font_dir in font_dirs:
            path = os.path.join(font_dir, fname)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass

    # Último recurso absoluto: fuente por defecto de Pillow
    logger.warning(f"Fuente '{family}' no encontrada. Usando fuente por defecto de Pillow.")
    return ImageFont.load_default()


def _auto_fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    family: str,
    bold: bool,
    initial_size: int,
    max_width: int,
    max_height: int,
    min_size: int = 10,
) -> Tuple[ImageFont.FreeTypeFont, int]:
    """
    Reduce el tamaño de fuente automáticamente hasta que el texto entre en el área.
    """
    size = initial_size
    
    while size >= min_size:
        font = _load_font(family, size, bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        if text_w <= max_width and text_h <= max_height:
            return font, size
        
        size -= 2
    
    font = _load_font(family, min_size, bold)
    return font, min_size


def _calculate_text_position(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    box: dict,
    align: str,
) -> Tuple[int, int]:
    """Calcula la posición X, Y para el texto según la alineación."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # Centrar verticalmente siempre
    y = box["y"] + (box["height"] - text_h) // 2
    
    if align == "center":
        x = box["x"] + (box["width"] - text_w) // 2
    elif align == "right":
        x = box["x"] + box["width"] - text_w
    else:  # left
        x = box["x"]
    
    return x, y


def _get_shadow_color(color: str) -> Optional[str]:
    """Retorna un color de sombra basado en el color principal."""
    try:
        # Sombra oscura para texto claro, sombra clara para texto oscuro
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        if brightness > 128:
            return "#404040"  # sombra oscura para texto claro
        else:
            return None  # sin sombra para texto oscuro
    except Exception:
        return None


def preview_template(
    template_path: str,
    name_box: dict,
    qr_box: dict,
    max_preview_size: int = 800,
) -> Optional[Image.Image]:
    """
    Genera una vista previa de la plantilla con las cajas marcadas visualmente.
    Útil para el configurador de plantilla.
    """
    try:
        img = Image.open(template_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        
        # Dibujar caja del nombre (azul)
        _draw_box(draw, name_box, color=(89, 180, 250, 180), label="NOMBRE")
        
        # Dibujar caja del QR (verde)
        _draw_box(draw, qr_box, color=(166, 227, 161, 180), label="QR")
        
        # Redimensionar para previsualización
        img.thumbnail((max_preview_size, max_preview_size), Image.LANCZOS)
        return img

    except Exception as e:
        logger.error(f"Error generando preview: {e}")
        return None


def _draw_box(draw: ImageDraw.ImageDraw, box: dict, color: tuple, label: str):
    """Dibuja una caja semitransparente con etiqueta."""
    x, y, w, h = box["x"], box["y"], box["width"], box["height"]
    
    # Fondo semitransparente
    overlay = Image.new("RGBA", draw.im.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([x, y, x + w, y + h], fill=(*color[:3], 60))
    od.rectangle([x, y, x + w, y + h], outline=(*color[:3], 220), width=3)
    
    # Texto de la etiqueta
    od.text((x + 5, y + 5), label, fill=(255, 255, 255, 230))
    
    draw.bitmap((0, 0), overlay.convert("L"))

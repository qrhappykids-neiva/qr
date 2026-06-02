"""
Módulo de extracción inteligente de nombres desde nombres de archivo PPTX.
"""

import re
import os

REMOVE_PATTERNS = [
    r"\d{1,2}\s*[°º]\s*",     # 5°, 11°, 5 °, etc
    r"\bC\s*[°º]\s*",         # C°
    r"\bINFORMES?\b",
    r"\bBOLET[IÍ]N\b",
    r"\bBOLETINES\b",
    r"\bP[1-4]\b",             # P1, P2, P3, P4
    r"\bPERIODO\b",
    r"\bPER[IÍ]ODO\b",
    r"\b20\d{2}\b",            # años 2000-2099
    r"\bGRADO\b",
    r"\bCURSO\b",
    r"\bSECCI[OÓ]N\b",
    r"\bNOTAS\b",
    r"\bCALIFICACIONES\b",
    r"[-_]+",
]

INVALID_WIN_CHARS = r'[<>:"/\\|?*\x00-\x1f]'


def extract_name_from_filename(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = name.upper()
    for pattern in REMOVE_PATTERNS:
        name = re.sub(pattern, " ", name, flags=re.IGNORECASE | re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip()
    
    # Limpieza adicional de caracteres sobrantes al inicio/final (como el punto que queda de "INFORME.")
    name = re.sub(r"^[.,\-_ ]+", "", name)  # Limpiar inicio
    name = re.sub(r"[.,\-_ ]+$", "", name)  # Limpiar final
    
    if not name:
        name = os.path.splitext(filename)[0].upper().strip()
    return name


def sanitize_filename(name: str) -> str:
    sanitized = re.sub(INVALID_WIN_CHARS, "", name)
    sanitized = sanitized.strip(". ")
    if len(sanitized) > 200:
        sanitized = sanitized[:200].strip()
    return sanitized if sanitized else "ESTUDIANTE"


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.upper().strip())


def batch_extract_names(pptx_files: list) -> list:
    results = []
    for path in pptx_files:
        filename = os.path.basename(path)
        extracted = extract_name_from_filename(filename)
        results.append({
            "path": path,
            "original_filename": filename,
            "name": extracted,
        })
    return results

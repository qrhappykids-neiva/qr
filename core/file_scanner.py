"""
Módulo de escaneo de archivos.
Busca archivos PPTX en subcarpetas y crea la estructura de directorios de salida.
"""

import os
from pathlib import Path


SUBDIRS = ["PDF", "QR", "PNG"]


def scan_pptx_files(root_folder: str) -> list[str]:
    """
    Busca recursivamente todos los archivos .pptx en root_folder.
    Excluye archivos que ya estén en subcarpetas PDF/QR/PNG.
    """
    pptx_files = []
    root = Path(root_folder)
    
    for pptx_path in root.rglob("*.pptx"):
        # Excluir archivos temporales de PowerPoint (empiezan con ~$)
        if pptx_path.name.startswith("~$"):
            continue
        # Excluir si está en una subcarpeta de salida
        parts = pptx_path.relative_to(root).parts
        if any(part in SUBDIRS for part in parts):
            continue
        pptx_files.append(str(pptx_path))
    
    return sorted(pptx_files)


def create_output_dirs(pptx_path: str) -> dict[str, str]:
    """
    Crea las subcarpetas PDF, QR y PNG en el mismo directorio del PPTX.
    Retorna un dict con las rutas de cada subcarpeta.
    """
    parent = os.path.dirname(pptx_path)
    dirs = {}
    for subdir in SUBDIRS:
        path = os.path.join(parent, subdir)
        os.makedirs(path, exist_ok=True)
        dirs[subdir] = path
    return dirs


def get_output_paths(pptx_path: str, student_name: str) -> dict[str, str]:
    """
    Calcula las rutas de salida para PDF, QR y PNG de un estudiante.
    """
    dirs = create_output_dirs(pptx_path)
    safe_name = student_name  # ya sanitizado
    return {
        "pdf": os.path.join(dirs["PDF"], f"{safe_name}.pdf"),
        "qr": os.path.join(dirs["QR"], f"{safe_name}.png"),
        "png": os.path.join(dirs["PNG"], f"{safe_name}.png"),
    }


def get_folder_summary(root_folder: str) -> dict:
    """
    Retorna un resumen del contenido de la carpeta seleccionada.
    """
    pptx_files = scan_pptx_files(root_folder)
    
    # Agrupar por subcarpeta padre
    folders = {}
    for f in pptx_files:
        parent = os.path.dirname(f)
        folders.setdefault(parent, []).append(f)
    
    return {
        "total_files": len(pptx_files),
        "total_folders": len(folders),
        "files": pptx_files,
        "by_folder": folders,
    }

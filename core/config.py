"""
Módulo de gestión de configuración.
Lee y escribe la configuración de la aplicación en un archivo JSON local.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".boletines_qr", "config.json")


@dataclass
class TextConfig:
    """Configuración del texto del nombre."""
    font_family: str = "Arial"
    font_size: int = 36
    font_bold: bool = True
    color: str = "#000000"
    align: str = "center"  # left, center, right


@dataclass
class BoxConfig:
    """Posición y tamaño de una caja en la plantilla."""
    x: int = 0
    y: int = 0
    width: int = 400
    height: int = 80


@dataclass
class AppConfig:
    """Configuración principal de la aplicación."""
    template_path: str = ""
    name_box: BoxConfig = field(default_factory=BoxConfig)
    qr_box: BoxConfig = field(default_factory=lambda: BoxConfig(x=50, y=50, width=200, height=200))
    text_config: TextConfig = field(default_factory=TextConfig)
    google_drive_credentials: str = ""
    google_drive_folder_id: str = ""
    output_dpi: int = 300
    qr_error_correction: str = "H"  # L, M, Q, H
    last_folder: str = ""


def load_config() -> AppConfig:
    """Carga la configuración desde el archivo JSON."""
    if not os.path.exists(CONFIG_FILE):
        return AppConfig()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        config = AppConfig()
        if "template_path" in data:
            config.template_path = data["template_path"]
        if "name_box" in data:
            config.name_box = BoxConfig(**data["name_box"])
        if "qr_box" in data:
            config.qr_box = BoxConfig(**data["qr_box"])
        if "text_config" in data:
            config.text_config = TextConfig(**data["text_config"])
        if "google_drive_credentials" in data:
            config.google_drive_credentials = data["google_drive_credentials"]
        if "google_drive_folder_id" in data:
            config.google_drive_folder_id = data["google_drive_folder_id"]
        if "output_dpi" in data:
            config.output_dpi = data["output_dpi"]
        if "qr_error_correction" in data:
            config.qr_error_correction = data["qr_error_correction"]
        if "last_folder" in data:
            config.last_folder = data["last_folder"]
        return config
    except Exception as e:
        print(f"Error cargando configuración: {e}")
        return AppConfig()


def save_config(config: AppConfig) -> bool:
    """Guarda la configuración en el archivo JSON."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        data = {
            "template_path": config.template_path,
            "name_box": asdict(config.name_box),
            "qr_box": asdict(config.qr_box),
            "text_config": asdict(config.text_config),
            "google_drive_credentials": config.google_drive_credentials,
            "google_drive_folder_id": config.google_drive_folder_id,
            "output_dpi": config.output_dpi,
            "qr_error_correction": config.qr_error_correction,
            "last_folder": config.last_folder,
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error guardando configuración: {e}")
        return False


def config_exists() -> bool:
    """Verifica si existe una configuración guardada con plantilla válida."""
    if not os.path.exists(CONFIG_FILE):
        return False
    config = load_config()
    return bool(config.template_path and os.path.exists(config.template_path))

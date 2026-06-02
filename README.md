---
title: Boletines QR
emoji: 📋
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: 1.30.0
app_file: app.py
pinned: false
---

# 📋 Boletines QR — Generador Automático de Boletines Escolares

Aplicación de escritorio para Windows que automatiza la generación de boletines escolares con códigos QR. Convierte presentaciones PowerPoint a PDF, los sube a Google Drive, genera códigos QR y compone imágenes finales de alta calidad.

---

## 🚀 Características

- ✅ Conversión automática PPTX → PDF (via Microsoft PowerPoint COM)
- ✅ Subida a Google Drive con enlace público compartible
- ✅ Generación de códigos QR en alta resolución (800×800px)
- ✅ Detección inteligente del nombre del estudiante desde el nombre del archivo
- ✅ Editor masivo de nombres con soporte copia/pega desde Excel
- ✅ Inserción del nombre y QR en plantilla visual personalizable
- ✅ Arrastrar y posicionar áreas de nombre y QR visualmente
- ✅ Galería de verificación al finalizar
- ✅ Procesamiento en hilo separado (no congela la UI)
- ✅ Soporte completo para caracteres acentuados
- ✅ Genera subcarpetas PDF/, QR/ y PNG/ automáticamente
- ✅ Exportable como .exe con PyInstaller

---

## 📦 Instalación

### Requisitos previos
- Windows 10/11
- Python 3.11+
- Microsoft PowerPoint instalado (para conversión PPTX→PDF)

### Instalar dependencias

```bash
pip install -r requirements.txt
```

### Ejecutar en desarrollo

```bash
python main.py
```

---

## 🏗️ Estructura del Proyecto

```
boletines_qr/
│
├── main.py                      # Punto de entrada
├── requirements.txt             # Dependencias
├── BoletinesQR.spec             # Configuración de PyInstaller
│
├── core/                        # Lógica de negocio
│   ├── config.py                # Gestión de configuración JSON
│   ├── file_scanner.py          # Búsqueda de archivos PPTX
│   ├── name_extractor.py        # Extracción inteligente de nombres
│   ├── pdf_converter.py         # Conversión PPTX→PDF (win32com)
│   ├── drive_uploader.py        # Subida a Google Drive API
│   ├── qr_generator.py          # Generación de códigos QR
│   ├── image_composer.py        # Composición de imagen final
│   └── processor.py             # Worker thread del pipeline
│
└── ui/                          # Interfaz gráfica (PySide6)
    ├── main_window.py           # Ventana principal
    ├── template_config.py       # Configurador de plantilla (drag & drop)
    ├── names_editor.py          # Editor masivo de nombres
    └── gallery.py               # Galería de verificación final
```

---

## ⚙️ Configuración de Google Drive

Para subida real a Google Drive (opcional):

1. Ir a [Google Cloud Console](https://console.cloud.google.com)
2. Crear proyecto → Habilitar Google Drive API
3. Crear cuenta de servicio (Service Account)
4. Descargar el JSON de credenciales
5. En la app: ⚙️ Configurar Plantilla → Cargar Credenciales JSON

> **Sin credenciales:** La app funciona en modo simulado (genera URLs de prueba para testing).

---

## 🔍 Reglas de Extracción de Nombres

El algoritmo elimina automáticamente:

| Patrón | Ejemplo |
|--------|---------|
| Prefijos de grado | `C°`, `5°`, `11°` |
| Palabra INFORME | `INFORME` |
| Períodos | `P1`, `P2`, `P3`, `P4` |
| Años | `2024`, `2025` |

**Ejemplo:**
```
Entrada:  "C° INFORME P1-2024 JULIETA HERNANDEZ ROA.pptx"
Salida:   "JULIETA HERNANDEZ ROA"

Entrada:  "5° Informe p4 2025 Pepito perez.pptx"
Salida:   "PEPITO PEREZ"
```

---

## 📁 Estructura de Salida

```
CarpetaOriginal/
    INFORME P1-2024 JULIETA HERNANDEZ ROA.pptx
    PDF/
        JULIETA HERNANDEZ ROA.pdf
    QR/
        JULIETA HERNANDEZ ROA.png
    PNG/
        JULIETA HERNANDEZ ROA.png
```

---

## 📦 Compilar como .exe

```bash
# Instalar PyInstaller
pip install pyinstaller

# Compilar (desde la raíz del proyecto)
pyinstaller BoletinesQR.spec

# El ejecutable queda en: dist/BoletinesQR.exe
```

> ⚠️ Compila en Windows para que win32com y PowerPoint funcionen correctamente.

---

## 🔧 Notas Técnicas

- La conversión PPTX→PDF usa Microsoft PowerPoint via COM (`win32com`). Requiere Office instalado.
- Si PowerPoint no está disponible, hay fallback automático a LibreOffice.
- El procesamiento usa `QThread` de PySide6 para no bloquear la interfaz.
- La configuración se guarda en `~/.boletines_qr/config.json`.
- Soporta 50–200 archivos sin problemas de rendimiento.

---

## 💡 Mejoras Recomendadas (Roadmap)

- [ ] Soporte para plantillas múltiples (por grado/curso)
- [ ] Modo batch programado (procesar a hora específica)
- [ ] Exportar reporte Excel con URLs de todos los QR
- [ ] Envío de notificaciones por WhatsApp/email a padres
- [ ] Vista previa del boletín antes de procesar
- [ ] Soporte para QR con logo institucional
- [ ] Integración con OneDrive como alternativa a Google Drive

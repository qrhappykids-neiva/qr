import os
import sys
import tempfile
import shutil
import zipfile
import traceback
import streamlit as st
from PIL import Image

# Asegurar que el directorio raíz esté en el path de Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.qr_generator import generate_qr
from core.image_composer import compose_bulletin
from core.pdf_converter import convert_with_fallback
from core.name_extractor import sanitize_filename, batch_extract_names
from core.drive_uploader import create_uploader

# Configuración de página de Streamlit
st.set_page_config(
    page_title="Boletines QR — Generador Web",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo personalizado para un diseño premium e infantil "Happy Kids"
st.markdown("""
    <style>
    .main-title {
        color: #00A99D;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: #F7941D;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    .stButton>button {
        background-color: #00A99D !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: bold !important;
        padding: 0.5rem 2rem !important;
    }
    .stButton>button:hover {
        background-color: #008f84 !important;
    }
    .preview-container {
        border: 2px dashed #b2dfdc;
        padding: 10px;
        border-radius: 10px;
        background-color: #ffffff;
    }
    </style>
""", unsafe_allow_html=True)


def setup_custom_fonts():
    """Copia las fuentes de la carpeta local 'fonts/' al sistema en Linux para que LibreOffice las reconozca."""
    if os.name != 'nt':
        local_fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
        if os.path.exists(local_fonts_dir):
            system_fonts_dir = os.path.expanduser("~/.fonts")
            os.makedirs(system_fonts_dir, exist_ok=True)
            copied = False
            for file in os.listdir(local_fonts_dir):
                if file.lower().endswith(('.ttf', '.otf')):
                    src = os.path.join(local_fonts_dir, file)
                    dst = os.path.join(system_fonts_dir, file)
                    if not os.path.exists(dst):
                        shutil.copy(src, dst)
                        copied = True
            if copied:
                try:
                    import subprocess
                    subprocess.run(["fc-cache", "-f", "-v"], check=True, capture_output=True)
                except Exception:
                    pass


# Ejecutar instalación de fuentes personalizadas si aplica
setup_custom_fonts()


# Inicializar variables de estado
if "template_image" not in st.session_state:
    st.session_state.template_image = None
if "template_path" not in st.session_state:
    st.session_state.template_path = ""
if "google_credentials_path" not in st.session_state:
    st.session_state.google_credentials_path = ""


# --- HEADER Y LOGO ---
col_logo, col_title = st.columns([1, 6])
with col_logo:
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logo.jpg")
    if os.path.exists(logo_path):
        st.image(logo_path, width=100)
    else:
        st.markdown("<h1 style='font-size: 4rem; margin:0;'>📋</h1>", unsafe_allow_html=True)

with col_title:
    st.markdown("<div class='main-title'>Boletines QR</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Generador Automático de Boletines Escolares en la Nube</div>", unsafe_allow_html=True)


# --- LATERAL: CONFIGURACIÓN ---
st.sidebar.markdown("### ⚙️ Configuración General")

# 1. Cargar Plantilla
uploaded_template = st.sidebar.file_uploader(
    "1. Subir Imagen Plantilla (JPG/PNG)",
    type=["jpg", "png", "jpeg"],
    key="template_uploader"
)

if uploaded_template:
    # Guardar en archivo temporal para poder ser leída por Pillow y Core
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tfile.write(uploaded_template.read())
    tfile.close()
    st.session_state.template_path = tfile.name
    st.session_state.template_image = Image.open(tfile.name)

# 2. Configurar Coordenadas y Textos
st.sidebar.markdown("#### 📍 Posicionamiento de Elementos")

# Caja de Nombre
with st.sidebar.expander("👤 Caja del Nombre del Estudiante", expanded=False):
    name_x = st.number_input("X (Posición horizontal)", value=100, step=10)
    name_y = st.number_input("Y (Posición vertical)", value=1000, step=10)
    name_w = st.number_input("Ancho de la caja", value=800, step=10)
    name_h = st.number_input("Alto de la caja", value=120, step=10)

    st.markdown("**Estilo de Texto**")
    font_family = st.selectbox("Tipografía", ["Arial", "Courier New", "Liberation Sans", "Georgia", "Comic Sans MS", "Times New Roman"])
    font_size = st.slider("Tamaño de letra", min_value=12, max_value=72, value=36)
    font_bold = st.checkbox("Texto en Negrita (Bold)", value=True)
    font_color = st.color_picker("Color de letra", value="#000000")
    font_align = st.selectbox("Alineación", ["center", "left", "right"])

# Caja de QR
with st.sidebar.expander("📲 Caja del Código QR", expanded=False):
    qr_x = st.number_input("X (Posición QR)", value=100, step=10)
    qr_y = st.number_input("Y (Posición QR)", value=100, step=10)
    qr_w = st.number_input("Ancho QR", value=250, step=10)
    qr_h = st.number_input("Alto QR", value=250, step=10)
    qr_ecc = st.selectbox("Corrección de errores QR", ["H (Máxima)", "Q (Alta)", "M (Media)", "L (Baja)"])

# 3. Google Drive (Opcional)
with st.sidebar.expander("☁️ Conectar a Google Drive (Opcional)", expanded=False):
    st.markdown("<small>Si no subes credenciales, el programa generará los archivos en un ZIP descargable.</small>", unsafe_allow_html=True)
    uploaded_creds = st.file_uploader("Subir Archivo JSON de Credenciales", type=["json"])
    drive_folder_id = st.text_input("Folder ID de Google Drive", value="")
    
    if uploaded_creds:
        cfile = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        cfile.write(uploaded_creds.read())
        cfile.close()
        st.session_state.google_credentials_path = cfile.name


# --- PANEL PRINCIPAL: PESTAÑAS ---
tab_preview, tab_process = st.tabs(["👁️ Previsualización y Diseño", "🚀 Procesamiento en Lote"])

# PESTAÑA 1: PREVISUALIZACIÓN Y DISEÑO
with tab_preview:
    st.markdown("### Previsualización Interactiva de la Plantilla")
    
    if st.session_state.template_image:
        st.markdown("Ajusta los valores en el panel lateral. Verás una muestra en tiempo real de cómo quedará el nombre y el código QR.")
        
        # Generar QR de prueba
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_qr:
            generate_qr("https://github.com", tmp_qr.name, size=800, error_correction=qr_ecc[0])
            
            # Componer previsualización en alta definición
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_preview:
                compose_bulletin(
                    template_path=st.session_state.template_path,
                    output_path=tmp_preview.name,
                    student_name="DULCE MARÍA MONTOYA SIERRA",
                    qr_path=tmp_qr.name,
                    name_box={"x": name_x, "y": name_y, "width": name_w, "height": name_h},
                    qr_box={"x": qr_x, "y": qr_y, "width": qr_w, "height": qr_h},
                    text_config={
                        "font_family": font_family,
                        "font_size": font_size,
                        "font_bold": font_bold,
                        "color": font_color,
                        "align": font_align
                    },
                    dpi=300
                )
                
                # Cargar y mostrar la imagen compuesta
                preview_img = Image.open(tmp_preview.name)
                st.image(preview_img, caption="Previsualización del boletín con datos de muestra", use_column_width=True)
                
            os.unlink(tmp_qr.name)
            os.unlink(tmp_preview.name)
            
    else:
        st.info("💡 Sube una imagen de plantilla (JPG/PNG) en el panel lateral para poder ajustar el diseño visualmente.")


# PESTAÑA 2: PROCESAMIENTO EN LOTE
with tab_process:
    st.markdown("### Procesar Presentaciones PowerPoint (.pptx)")
    
    uploaded_files = st.file_uploader(
        "Sube tus archivos PowerPoint (.pptx) o un archivo .zip que los contenga",
        type=["pptx", "zip"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        st.markdown(f"**Archivos cargados:** {len(uploaded_files)}")
        
        # Crear entorno temporal para el procesamiento
        temp_dir = tempfile.mkdtemp()
        pptx_files = []
        
        for u_file in uploaded_files:
            if u_file.name.endswith(".zip"):
                zip_path = os.path.join(temp_dir, u_file.name)
                with open(zip_path, "wb") as f:
                    f.write(u_file.read())
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                os.unlink(zip_path)
            else:
                dest = os.path.join(temp_dir, u_file.name)
                with open(dest, "wb") as f:
                    f.write(u_file.read())
        
        # Escanear archivos extraídos o subidos
        for root, _, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith(".pptx") and not file.startswith("~$"):
                    pptx_files.append(os.path.join(root, file))
                    
        if len(pptx_files) == 0:
            st.error("No se encontraron archivos PowerPoint (.pptx) en la selección.")
        else:
            st.success(f"¡Se detectaron {len(pptx_files)} archivos de boletines PowerPoint listos para procesar!")
            
            # Extraer nombres automáticamente para revisar
            students = []
            extracted_students = batch_extract_names(pptx_files)
            
            with st.expander("✏️ Revisar y Editar Nombres Detectados antes de Iniciar", expanded=True):
                st.markdown("<small>Puedes modificar los nombres si la extracción automática no los detectó correctamente.</small>", unsafe_allow_html=True)
                for idx, student in enumerate(extracted_students):
                    col_file, col_name = st.columns([1, 1])
                    with col_file:
                        st.text(os.path.basename(student["path"]))
                    with col_name:
                        edited_name = st.text_input(
                            f"Nombre del Estudiante {idx}",
                            value=student["name"],
                            key=f"name_{idx}",
                            label_visibility="collapsed"
                        )
                        students.append({"path": student["path"], "name": edited_name})
                        
            # Botón de Procesar
            if st.button("🚀 Iniciar Procesamiento Completo"):
                if not st.session_state.template_path:
                    st.error("Debes cargar una imagen plantilla en el panel lateral antes de procesar.")
                else:
                    # Preparar directorios de salida
                    out_dir = tempfile.mkdtemp()
                    out_pdf = os.path.join(out_dir, "PDF")
                    out_qr = os.path.join(out_dir, "QR")
                    out_png = os.path.join(out_dir, "PNG")
                    os.makedirs(out_pdf, exist_ok=True)
                    os.makedirs(out_qr, exist_ok=True)
                    os.makedirs(out_png, exist_ok=True)
                    
                    progress_bar = st.progress(0)
                    progress_text = st.empty()
                    log_area = st.empty()
                    log_messages = []
                    
                    def add_log(msg: str):
                        log_messages.append(msg)
                        log_area.code("\n".join(log_messages))
                    
                    add_log(f"Iniciando procesamiento de {len(students)} boletines...")
                    
                    # Conectar a Drive si aplica
                    uploader = create_uploader(
                        st.session_state.google_credentials_path,
                        drive_folder_id,
                        mock=not bool(st.session_state.google_credentials_path)
                    )
                    if st.session_state.google_credentials_path:
                        add_log("☁️ Conectado exitosamente a Google Drive.")
                    else:
                        add_log("ℹ️ No se cargaron credenciales de Drive. Los archivos se descargarán directamente en un archivo ZIP.")
                    
                    total = len(students)
                    success_count = 0
                    results = []
                    
                    for idx, student in enumerate(students):
                        name = student["name"]
                        pp_path = student["path"]
                        safe_name = sanitize_filename(name)
                        
                        add_log(f"\n▶ [{idx+1}/{total}] {name}")
                        progress_text.text(f"Procesando {idx+1} de {total}: {name}")
                        
                        pdf_path = os.path.join(out_pdf, f"{safe_name}.pdf")
                        qr_path = os.path.join(out_qr, f"{safe_name}.png")
                        png_path = os.path.join(out_png, f"{safe_name}.png")
                        
                        try:
                            # 1. PPTX -> PDF
                            progress_bar.progress((idx * 4 + 1) / (total * 4))
                            add_log("  📄 Convirtiendo presentación a PDF...")
                            ok, method = convert_with_fallback(pp_path, pdf_path)
                            
                            if ok:
                                add_log(f"  ✅ PDF generado usando {method}")
                            else:
                                add_log("  ❌ Error de conversión a PDF")
                                continue
                                
                            # 2. Drive
                            progress_bar.progress((idx * 4 + 2) / (total * 4))
                            drive_url = ""
                            if st.session_state.google_credentials_path:
                                add_log("  ☁️ Subiendo PDF a Google Drive...")
                                drive_url = uploader.upload_pdf(pdf_path, f"{safe_name}.pdf")
                                if drive_url:
                                    add_log(f"  ✅ Subido a Drive: {drive_url[:50]}...")
                                else:
                                    add_log("  ❌ Error subiendo a Google Drive")
                            
                            # 3. QR
                            progress_bar.progress((idx * 4 + 3) / (total * 4))
                            add_log("  📲 Generando código QR...")
                            qr_link = drive_url or f"https://example.com/qr/{safe_name}"
                            ok_qr = generate_qr(qr_link, qr_path, size=800, error_correction=qr_ecc[0])
                            if ok_qr:
                                add_log("  ✅ Código QR generado")
                            else:
                                add_log("  ❌ Error generando QR")
                                continue
                                
                            # 4. Componer PNG
                            progress_bar.progress((idx * 4 + 4) / (total * 4))
                            add_log("  🖼️ Componiendo imagen final sobre la plantilla...")
                            ok_png = compose_bulletin(
                                template_path=st.session_state.template_path,
                                output_path=png_path,
                                student_name=name,
                                qr_path=qr_path,
                                name_box={"x": name_x, "y": name_y, "width": name_w, "height": name_h},
                                qr_box={"x": qr_x, "y": qr_y, "width": qr_w, "height": qr_h},
                                text_config={
                                    "font_family": font_family,
                                    "font_size": font_size,
                                    "font_bold": font_bold,
                                    "color": font_color,
                                    "align": font_align
                                },
                                dpi=300
                            )
                            if ok_png:
                                add_log("  ✅ Boletín final PNG generado en alta resolución")
                                success_count += 1
                                results.append({"name": name, "png": png_path})
                            else:
                                add_log("  ❌ Error al componer imagen final")
                                
                        except Exception as e:
                            add_log(f"  💥 Error inesperado: {e}")
                            traceback.print_exc()
                            
                    progress_bar.progress(1.0)
                    progress_text.text("¡Procesamiento completo!")
                    
                    st.balloons()
                    st.success(f"¡Procesamiento completado con éxito! {success_count} de {total} boletines generados.")
                    
                    # Generar ZIP consolidado para descarga
                    zip_download_path = os.path.join(temp_dir, "boletines_procesados.zip")
                    with zipfile.ZipFile(zip_download_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        # Guardar PNGs
                        for root_dir, _, files in os.walk(out_png):
                            for file in files:
                                zipf.write(os.path.join(root_dir, file), os.path.join("Imagenes", file))
                        # Guardar PDFs
                        for root_dir, _, files in os.walk(out_pdf):
                            for file in files:
                                zipf.write(os.path.join(root_dir, file), os.path.join("PDFs", file))
                                
                    with open(zip_download_path, "rb") as f:
                        st.download_button(
                            label="📥 Descargar todos los boletines (.ZIP)",
                            data=f,
                            file_name="boletines_procesados.zip",
                            mime="application/zip"
                        )
                        
                    # Mostrar galería en la web
                    st.markdown("### 🖼️ Galería de Resultados")
                    cols = st.columns(3)
                    for i, res in enumerate(results):
                        with cols[i % 3]:
                            img_preview = Image.open(res["png"])
                            st.image(img_preview, caption=res["name"], use_column_width=True)
                            
        # Limpieza de temporales al finalizar
        shutil.rmtree(temp_dir, ignore_errors=True)

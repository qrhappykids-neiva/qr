import os
import sys
import tempfile
import shutil
import zipfile
import traceback
import io
import base64
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

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
# Rutas persistentes de configuración en el servidor
SAVED_CREDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_drive_credentials.json")
SAVED_FOLDER_ID_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_drive_folder_id.txt")

# Inicializar variables de estado
if "template_image" not in st.session_state:
    st.session_state.template_image = None
if "template_path" not in st.session_state:
    st.session_state.template_path = ""

# Cargar automáticamente credenciales de Google Drive si ya existen guardadas
if "google_credentials_path" not in st.session_state:
    if os.path.exists(SAVED_CREDS_PATH):
        st.session_state.google_credentials_path = SAVED_CREDS_PATH
    else:
        st.session_state.google_credentials_path = ""

# Cargar automáticamente el Folder ID de Google Drive si ya existe guardado
if "drive_folder_id_val" not in st.session_state:
    if os.path.exists(SAVED_FOLDER_ID_PATH):
        try:
            with open(SAVED_FOLDER_ID_PATH, "r", encoding="utf-8") as f:
                st.session_state.drive_folder_id_val = f.read().strip()
        except Exception:
            st.session_state.drive_folder_id_val = ""
    else:
        st.session_state.drive_folder_id_val = ""

# Inicializar coordenadas en session_state con valores por defecto tipo escritorio
if "name_x" not in st.session_state: st.session_state.name_x = 100
if "name_y" not in st.session_state: st.session_state.name_y = 100
if "name_w" not in st.session_state: st.session_state.name_w = 400
if "name_h" not in st.session_state: st.session_state.name_h = 70

if "qr_x" not in st.session_state: st.session_state.qr_x = 100
if "qr_y" not in st.session_state: st.session_state.qr_y = 200
if "qr_w" not in st.session_state: st.session_state.qr_w = 200
if "qr_h" not in st.session_state: st.session_state.qr_h = 200

# Variables de persistencia para descarga y galería en la web
if "processed_zip_data" not in st.session_state:
    st.session_state.processed_zip_data = None
if "results_gallery" not in st.session_state:
    st.session_state.results_gallery = []


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
    st.markdown("**📍 Posición y Dimensiones:**")
    st.markdown(f"* **Posición X:** `{st.session_state.name_x} px` \n* **Posición Y:** `{st.session_state.name_y} px` \n* **Ancho:** `{st.session_state.name_w} px` \n* **Alto:** `{st.session_state.name_h} px` (Ajustables con el mouse)")
    
    name_x = st.session_state.name_x
    name_y = st.session_state.name_y
    name_w = st.session_state.name_w
    name_h = st.session_state.name_h

    st.markdown("**Estilo de Texto**")
    font_family = st.selectbox("Tipografía", ["Arial", "Courier New", "Liberation Sans", "Georgia", "Comic Sans MS", "Times New Roman"])
    font_size = st.slider("Tamaño de letra", min_value=12, max_value=72, value=36)
    font_bold = st.checkbox("Texto en Negrita (Bold)", value=True)
    font_color = st.color_picker("Color de letra", value="#000000")
    font_align = st.selectbox("Alineación", ["center", "left", "right"])

# Caja de QR
with st.sidebar.expander("📲 Caja del Código QR", expanded=False):
    st.markdown("**📍 Posición y Dimensiones:**")
    st.markdown(f"* **Posición X:** `{st.session_state.qr_x} px` \n* **Posición Y:** `{st.session_state.qr_y} px` \n* **Ancho:** `{st.session_state.qr_w} px` \n* **Alto:** `{st.session_state.qr_h} px` (Ajustables con el mouse)")
    
    qr_x = st.session_state.qr_x
    qr_y = st.session_state.qr_y
    qr_w = st.session_state.qr_w
    qr_h = st.session_state.qr_h
    qr_ecc = st.selectbox("Corrección de errores QR", ["H (Máxima)", "Q (Alta)", "M (Media)", "L (Baja)"])

# 3. Google Drive (Opcional)
st.sidebar.markdown("---")
st.sidebar.markdown("### ☁️ Google Drive (Opcional)")
st.sidebar.markdown("<small>Los datos se guardarán en el servidor para que solo los configures una vez.</small>", unsafe_allow_html=True)

# Mostrar estado de credenciales guardadas
if os.path.exists(SAVED_CREDS_PATH) or (st.session_state.google_credentials_path == SAVED_CREDS_PATH):
    st.sidebar.success("🟢 Credenciales guardadas en el servidor")
else:
    st.sidebar.info("🟡 Sin credenciales guardadas")
    
uploaded_creds = st.sidebar.file_uploader("Subir Archivo JSON de Credenciales (Reemplazar)", type=["json"])

if uploaded_creds:
    try:
        # Guardar el archivo JSON de manera permanente en el servidor
        with open(SAVED_CREDS_PATH, "wb") as f:
            f.write(uploaded_creds.read())
        st.session_state.google_credentials_path = SAVED_CREDS_PATH
        st.sidebar.success("¡Credenciales guardadas con éxito!")
    except Exception as e:
        st.sidebar.error(f"Error al guardar credenciales: {e}")
        
drive_folder_id = st.sidebar.text_input("Folder ID de Google Drive", value=st.session_state.drive_folder_id_val)

# Guardar permanentemente el Folder ID si ha cambiado
if drive_folder_id != st.session_state.drive_folder_id_val:
    st.session_state.drive_folder_id_val = drive_folder_id
    try:
        with open(SAVED_FOLDER_ID_PATH, "w", encoding="utf-8") as f:
            f.write(drive_folder_id)
    except Exception:
        pass

# Mostrar confirmación visual del ID guardado
if st.session_state.drive_folder_id_val:
    st.sidebar.success(f"📁 ID de Carpeta guardado:\n`{st.session_state.drive_folder_id_val}`")


# --- PANEL PRINCIPAL: PESTAÑAS ---
tab_preview, tab_process = st.tabs(["👁️ Previsualización y Diseño", "🚀 Procesamiento en Lote"])

# PESTAÑA 1: PREVISUALIZACIÓN Y DISEÑO
with tab_preview:
    st.markdown("### 🎨 Diseñador de Plantilla (Arrastra y Redimensiona con tu Mouse)")
    
    if st.session_state.template_image:
        st.markdown("<small>✨ Haz clic sobre la caja **NOMBRE** (azul/celeste) o la caja **QR** (naranja) para **arrastrarlas y moverlas** por la pantalla o **estirarlas desde las esquinas** para cambiar su tamaño.</small>", unsafe_allow_html=True)
        
        img = st.session_state.template_image
        orig_w, orig_h = img.size
        
        # Canvas de ancho completo (ej. 800px) para un diseño amplio y cómodo
        canvas_width = 800
        canvas_height = int(orig_h * (canvas_width / orig_w))
        scale = orig_w / canvas_width
        
        # Construir dibujo inicial de Fabric.js con las cajas NOMBRE y QR estáticas (evita snap-back al actualizar de forma interactiva)
        initial_drawing = {
            "version": "4.4.0",
            "objects": [
                {
                    "type": "rect",
                    "left": float(100 / scale),
                    "top": float(100 / scale),
                    "width": float(400 / scale),
                    "height": float(70 / scale),
                    "fill": "rgba(0, 169, 157, 0.35)",  # Teal semitransparente
                    "stroke": "#00A99D",
                    "strokeWidth": 2,
                    "angle": 0,
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "selectable": True,
                    "label": "NOMBRE"
                },
                {
                    "type": "rect",
                    "left": float(100 / scale),
                    "top": float(200 / scale),
                    "width": float(200 / scale),
                    "height": float(200 / scale),
                    "fill": "rgba(247, 148, 29, 0.35)",  # Naranja semitransparente
                    "stroke": "#F7941D",
                    "strokeWidth": 2,
                    "angle": 0,
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "selectable": True,
                    "label": "QR"
                }
            ]
        }
        
        # Mostrar el diseñador de lienzo
        canvas_result = st_canvas(
            fill_color="rgba(0, 0, 0, 0)",
            stroke_width=2,
            background_image=img,
            initial_drawing=initial_drawing,
            update_streamlit=True,
            width=canvas_width,
            height=canvas_height,
            drawing_mode="transform",
            display_toolbar=False,
            key="canvas_designer",
        )
        
        # Capturar movimientos de las cajas
        if canvas_result.json_data is not None:
            objects = canvas_result.json_data.get("objects", [])
            
            # Buscamos y leemos la nueva posición de ambas cajas
            if len(objects) >= 2:
                obj_name = objects[0]
                obj_qr = objects[1]
                
                # Función helper para extraer coordenadas del canvas con escala
                def get_scaled_coords(obj):
                    left = obj.get("left", 0)
                    top = obj.get("top", 0)
                    # En Fabric.js, redimensionar cambia scaleX y scaleY
                    w = obj.get("width", 50) * obj.get("scaleX", 1.0)
                    h = obj.get("height", 50) * obj.get("scaleY", 1.0)
                    return int(left * scale), int(top * scale), int(w * scale), int(h * scale)
                
                nx, ny, nw, nh = get_scaled_coords(obj_name)
                qx, qy, qw, qh = get_scaled_coords(obj_qr)
                
                # Guardar las nuevas coordenadas en st.session_state (se actualizarán en la barra lateral sin necesidad de st.experimental_rerun)
                st.session_state.name_x = nx
                st.session_state.name_y = ny
                st.session_state.name_w = nw
                st.session_state.name_h = nh
                
                st.session_state.qr_x = qx
                st.session_state.qr_y = qy
                st.session_state.qr_w = qw
                st.session_state.qr_h = qh
            
    else:
        st.info("💡 Sube una imagen de plantilla (JPG/PNG) en el panel lateral para poder posicionar y arrastrar las cajas de Nombre y QR con tu mouse.")


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
        # Limpiar resultados anteriores cuando se suben nuevos archivos
        st.session_state.processed_zip_data = None
        st.session_state.results_gallery = []
        
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
                                results.append({"name": name, "png": png_path, "qr_link": qr_link})
                            else:
                                add_log("  ❌ Error al componer imagen final")
                                
                        except Exception as e:
                            add_log(f"  💥 Error inesperado: {e}")
                            traceback.print_exc()
                            
                    progress_bar.progress(1.0)
                    progress_text.text("¡Procesamiento completo!")
                    
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
                                
                    # Leer el archivo ZIP en memoria para que no desaparezca
                    with open(zip_download_path, "rb") as f:
                        st.session_state.processed_zip_data = f.read()
                        
                    # Cargar las imágenes finales en memoria en st.session_state
                    st.session_state.results_gallery = []
                    for res in results:
                        try:
                            img_data = Image.open(res["png"])
                            img_data.load()  # Forzar carga en memoria
                            st.session_state.results_gallery.append({
                                "name": res["name"],
                                "img": img_data,
                                "qr_link": res.get("qr_link", "")
                            })
                        except Exception:
                            pass
                            
        # Limpieza de temporales al finalizar
        shutil.rmtree(temp_dir, ignore_errors=True)
 
     # Mostrar de forma permanente los resultados si ya han sido procesados
    if st.session_state.processed_zip_data is not None:
        st.markdown("---")
        st.markdown("### 📥 Descarga de Boletines Procesados")
        st.download_button(
            label="📥 Descargar todos los boletines (.ZIP)",
            data=st.session_state.processed_zip_data,
            file_name="boletines_procesados.zip",
            mime="application/zip"
        )
        
        # Mostrar galería de forma permanente con enlaces clicables a los PDFs
        if st.session_state.results_gallery:
            st.markdown("### 🖼️ Galería de Resultados")
            st.markdown("<small>💡 Haz clic sobre cualquier boletín para **abrir y verificar el PDF del código QR correspondiente** en una nueva pestaña.</small>", unsafe_allow_html=True)
            cols = st.columns(3)
            for i, res in enumerate(st.session_state.results_gallery):
                with cols[i % 3]:
                    try:
                        buffered = io.BytesIO()
                        res["img"].save(buffered, format="PNG")
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                        img_data_uri = f"data:image/png;base64,{img_str}"
                        
                        href_link = res.get("qr_link", "#")
                        clickable_html = f"""
                        <div style="text-align: center; margin-bottom: 20px;">
                            <a href="{href_link}" target="_blank" title="Haz clic para abrir el PDF del código QR">
                                <img src="{img_data_uri}" style="width:100%; border-radius: 10px; border: 2px solid #b2dfdc; box-shadow: 0 4px 8px rgba(0,0,0,0.1); transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'" />
                            </a>
                            <p style="font-weight: bold; color: #00A99D; margin-top: 8px; margin-bottom: 0;">{res['name']}</p>
                            <a href="{href_link}" target="_blank" style="font-size: 0.85rem; color: #F7941D; text-decoration: none; font-weight: bold;">🔗 Probar Enlace QR</a>
                        </div>
                        """
                        st.markdown(clickable_html, unsafe_allow_html=True)
                    except Exception as e:
                        st.image(res["img"], caption=res["name"], use_column_width=True)

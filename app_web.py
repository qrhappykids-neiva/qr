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

def download_fonts_on_startup():
    """Descarga las fuentes de Poppins si no están presentes localmente."""
    fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    os.makedirs(fonts_dir, exist_ok=True)
    poppins_bold = os.path.join(fonts_dir, "Poppins-Bold.ttf")
    poppins_regular = os.path.join(fonts_dir, "Poppins-Regular.ttf")
    
    import urllib.request
    if not os.path.exists(poppins_bold):
        try:
            urllib.request.urlretrieve('https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf', poppins_bold)
        except Exception:
            pass
    if not os.path.exists(poppins_regular):
        try:
            urllib.request.urlretrieve('https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf', poppins_regular)
        except Exception:
            pass

download_fonts_on_startup()

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
# Rutas persistentes de configuración en el servidor
SAVED_CREDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_drive_credentials.json")
SAVED_FOLDER_ID_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_drive_folder_id.txt")
SAVED_TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_drive_saved_template.png")
SAVED_COORDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_drive_saved_coords.json")

# Cargar automáticamente plantilla guardada
if "template_image" not in st.session_state:
    if os.path.exists(SAVED_TEMPLATE_PATH):
        try:
            st.session_state.template_path = SAVED_TEMPLATE_PATH
            st.session_state.template_image = Image.open(SAVED_TEMPLATE_PATH)
            st.session_state.template_image.load()
            st.session_state.has_saved_template = True
        except Exception:
            st.session_state.template_image = None
            st.session_state.template_path = ""
            st.session_state.has_saved_template = False
    else:
        st.session_state.template_image = None
        st.session_state.template_path = ""
        st.session_state.has_saved_template = False

# Cargar automáticamente credenciales de Google Drive si ya existen guardadas o están en st.secrets
if "google_credentials_path" not in st.session_state:
    try:
        if "GOOGLE_DRIVE_CREDENTIALS" in st.secrets:
            import json
            creds_data = st.secrets["GOOGLE_DRIVE_CREDENTIALS"]
            if isinstance(creds_data, str):
                creds_dict = json.loads(creds_data)
            else:
                creds_dict = dict(creds_data)
            with open(SAVED_CREDS_PATH, "w", encoding="utf-8") as f:
                json.dump(creds_dict, f, indent=4)
            st.session_state.google_credentials_path = SAVED_CREDS_PATH
    except Exception:
        pass

if "google_credentials_path" not in st.session_state:
    if os.path.exists(SAVED_CREDS_PATH):
        st.session_state.google_credentials_path = SAVED_CREDS_PATH
    else:
        # Buscar en la carpeta local un archivo que empiece con client_secret y termine en .json
        try:
            local_secrets = [f for f in os.listdir(os.path.dirname(os.path.abspath(__file__))) 
                              if f.startswith("client_secret") and f.endswith(".json")]
            if local_secrets:
                shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), local_secrets[0]), SAVED_CREDS_PATH)
                st.session_state.google_credentials_path = SAVED_CREDS_PATH
            else:
                st.session_state.google_credentials_path = ""
        except Exception:
            st.session_state.google_credentials_path = ""

# Cargar automáticamente el Folder ID de Google Drive si ya existe guardado (con fallback por defecto o st.secrets)
if "drive_folder_id_val" not in st.session_state:
    loaded_folder_id = False
    try:
        if "GOOGLE_DRIVE_FOLDER_ID" in st.secrets:
            st.session_state.drive_folder_id_val = st.secrets["GOOGLE_DRIVE_FOLDER_ID"]
            loaded_folder_id = True
    except Exception:
        pass

    if not loaded_folder_id:
        if os.path.exists(SAVED_FOLDER_ID_PATH):
            try:
                with open(SAVED_FOLDER_ID_PATH, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                    st.session_state.drive_folder_id_val = val if val else "1ljat0NmC6_kPYN7HlQt1P5Ljaeyc9R8m"
            except Exception:
                st.session_state.drive_folder_id_val = "1ljat0NmC6_kPYN7HlQt1P5Ljaeyc9R8m"
        else:
            st.session_state.drive_folder_id_val = "1ljat0NmC6_kPYN7HlQt1P5Ljaeyc9R8m"

# Inicializar coordenadas en session_state con valores del archivo guardado o valores por defecto
loaded_coords = {}
if os.path.exists(SAVED_COORDS_PATH):
    try:
        import json
        with open(SAVED_COORDS_PATH, "r", encoding="utf-8") as f:
            loaded_coords = json.load(f)
    except Exception:
        pass

if "name_x" not in st.session_state: st.session_state.name_x = loaded_coords.get("name_x", 100)
if "name_y" not in st.session_state: st.session_state.name_y = loaded_coords.get("name_y", 100)
if "name_w" not in st.session_state: st.session_state.name_w = loaded_coords.get("name_w", 400)
if "name_h" not in st.session_state: st.session_state.name_h = loaded_coords.get("name_h", 70)

if "qr_x" not in st.session_state: st.session_state.qr_x = loaded_coords.get("qr_x", 100)
if "qr_y" not in st.session_state: st.session_state.qr_y = loaded_coords.get("qr_y", 200)
if "qr_w" not in st.session_state: st.session_state.qr_w = loaded_coords.get("qr_w", 200)
if "qr_h" not in st.session_state: st.session_state.qr_h = loaded_coords.get("qr_h", 200)

# Variables de persistencia para descarga y galería en la web
if "processed_zip_data" not in st.session_state:
    st.session_state.processed_zip_data = None
if "results_gallery" not in st.session_state:
    st.session_state.results_gallery = []
if "current_step" not in st.session_state:
    st.session_state.current_step = 1


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


# --- LATERAL: PERSONALIZACIÓN DE ESTILOS ---
st.sidebar.markdown("### 🎨 Personalizar Diseño")

# Estilo de Letra (Nombre)
with st.sidebar.expander("👤 Estilo del Nombre", expanded=True):
    font_family = st.selectbox("Tipografía", ["Poppins", "Arial", "Courier New", "Liberation Sans", "Georgia", "Comic Sans MS", "Times New Roman", "Brittany Signature"])
    font_size = st.slider("Tamaño de letra", min_value=10, max_value=250, value=80)
    font_bold = st.checkbox("Texto en Negrita (Bold)", value=True)
    font_color = st.color_picker("Color de letra", value="#000000")
    font_align = st.selectbox("Alineación", ["center", "left", "right"])

# Ajustes de QR
with st.sidebar.expander("📲 Configuración de QR", expanded=False):
    qr_ecc = st.selectbox("Corrección de errores QR", ["H (Máxima)", "Q (Alta)", "M (Media)", "L (Baja)"])
    
# Mostrar coordenadas informativas del Nombre
name_x = st.session_state.name_x
name_y = st.session_state.name_y
name_w = st.session_state.name_w
name_h = st.session_state.name_h

# Mostrar coordenadas informativas del QR
qr_x = st.session_state.qr_x
qr_y = st.session_state.qr_y
qr_w = st.session_state.qr_w
qr_h = st.session_state.qr_h

# --- WIZARD PROGRESS BAR (INDICADOR DE PASOS) ---
step = st.session_state.current_step

st.markdown("""
<style>
.step-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: #f0fdfa;
    padding: 20px;
    border-radius: 15px;
    border: 2px solid #99f6e4;
    margin-bottom: 2rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}
.step-bubble {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    text-align: center;
}
.step-number {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 1.2rem;
    margin-bottom: 5px;
    transition: all 0.3s;
}
.step-active {
    background-color: #00A99D;
    color: white;
    box-shadow: 0 0 10px rgba(0, 169, 157, 0.5);
    transform: scale(1.15);
}
.step-pending {
    background-color: #e2e8f0;
    color: #64748b;
}
.step-completed {
    background-color: #34d399;
    color: white;
}
.step-label {
    font-size: 0.9rem;
    font-weight: 600;
}
.step-label-active {
    color: #00A99D;
    font-weight: 800;
}
.step-label-pending {
    color: #64748b;
}
.step-arrow {
    font-size: 1.5rem;
    color: #99f6e4;
    user-select: none;
    margin: 0 10px;
}
</style>
""", unsafe_allow_html=True)

# Generar clases de estilo basadas en el paso actual
def get_step_class(s):
    if step == s: return "step-number step-active", "step-label step-label-active"
    elif step > s: return "step-number step-completed", "step-label"
    else: return "step-number step-pending", "step-label step-label-pending"

c1_num, c1_lbl = get_step_class(1)
c2_num, c2_lbl = get_step_class(2)
c3_num, c3_lbl = get_step_class(3)

st.markdown(f"""
<div class="step-container">
    <div class="step-bubble">
        <div class="{c1_num}">1</div>
        <div class="{c1_lbl}">1. Subir Plantilla</div>
    </div>
    <div class="step-arrow">➔</div>
    <div class="step-bubble">
        <div class="{c2_num}">2</div>
        <div class="{c2_lbl}">2. Diseñar Caja/QR</div>
    </div>
    <div class="step-arrow">➔</div>
    <div class="step-bubble">
        <div class="{c3_num}">3</div>
        <div class="{c3_lbl}">3. Generar Boletines</div>
    </div>
</div>
""", unsafe_allow_html=True)


# --- LÓGICA DE CADA PASO ---

# --- PASO 1: SUBIR PLANTILLA ---
if step == 1:
    st.markdown("### 1️⃣ Paso 1: Configurar la Plantilla de Fondo")
    st.markdown("Sube la imagen que servirá de fondo para tus boletines, o selecciona la plantilla guardada anteriormente.")
    
    if os.path.exists(SAVED_TEMPLATE_PATH):
        opcion_plantilla = st.radio(
            "Selecciona una opción para tu plantilla:",
            ["Usar la plantilla guardada anteriormente", "Subir una nueva plantilla"],
            key="template_option_radio"
        )
    else:
        opcion_plantilla = "Subir una nueva plantilla"
        
    if opcion_plantilla == "Usar la plantilla guardada anteriormente":
        st.session_state.template_path = SAVED_TEMPLATE_PATH
        try:
            st.session_state.template_image = Image.open(SAVED_TEMPLATE_PATH)
            st.session_state.template_image.load()
        except Exception:
            st.error("Error al cargar la plantilla guardada. Por favor sube una nueva.")
            opcion_plantilla = "Subir una nueva plantilla"
            
    if opcion_plantilla == "Subir una nueva plantilla":
        uploaded_template_main = st.file_uploader(
            "Haz clic o arrastra aquí tu imagen de plantilla",
            type=["jpg", "png", "jpeg"],
            key="main_template_uploader"
        )
        
        if uploaded_template_main:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tfile.write(uploaded_template_main.read())
            tfile.close()
            st.session_state.template_path = tfile.name
            st.session_state.template_image = Image.open(tfile.name)
            
            # Guardar copia permanente en el servidor
            try:
                shutil.copy(tfile.name, SAVED_TEMPLATE_PATH)
                st.session_state.has_saved_template = True
            except Exception:
                pass
        
    if st.session_state.template_image:
        st.success("🟢 ¡Plantilla lista para usar!")
        st.image(st.session_state.template_image, caption="Tu plantilla de fondo", use_column_width=True)
        
        st.markdown("---")
        if opcion_plantilla == "Usar la plantilla guardada anteriormente":
            col_skip1, col_skip2 = st.columns(2)
            with col_skip1:
                if st.button("🚀 Ir Directo a Generar Boletines (Paso 3)", use_container_width=True, type="primary"):
                    st.session_state.current_step = 3
                    st.rerun()
            with col_skip2:
                if st.button("✏️ Ajustar Diseño y Posición (Paso 2)", use_container_width=True):
                    st.session_state.current_step = 2
                    st.session_state.reset_canvas = True
                    st.rerun()
        else:
            if st.button("➡️ Siguiente Paso: Ubicar Elementos con el Mouse", use_container_width=True):
                st.session_state.current_step = 2
                st.session_state.reset_canvas = True
                st.rerun()
    else:
        st.info("💡 Por favor, configura una plantilla para poder continuar al siguiente paso.")


# --- PASO 2: DISEÑAR POSICIONES ---
elif step == 2:
    st.markdown("### 2️⃣ Paso 2: Ajustar Cajas de Nombre y QR con el Mouse")
    
    if not st.session_state.template_image:
        st.warning("⚠️ No se ha detectado ninguna plantilla de fondo. Por favor vuelve al paso anterior.")
        if st.button("⬅️ Volver a Paso 1: Subir Plantilla", use_container_width=True):
            st.session_state.current_step = 1
            st.rerun()
    else:
        st.markdown("✨ Haz clic sobre la caja **NOMBRE** (azul/celeste) o la caja **QR** (naranja) para **arrastrarlas y moverlas** por la pantalla, o **estíralas desde las esquinas** para cambiar su tamaño.")
        
        img = st.session_state.template_image
        orig_w, orig_h = img.size
        
        canvas_width = 800
        canvas_height = int(orig_h * (canvas_width / orig_w))
        scale = orig_w / canvas_width
        # Inicializar el dibujo inicial una sola vez para evitar bucles de actualización en st_canvas
        if "canvas_initial_drawing" not in st.session_state or st.session_state.get("reset_canvas", False):
            st.session_state.canvas_initial_drawing = {
                "version": "4.4.0",
                "objects": [
                    {
                        "type": "rect",
                        "left": float(st.session_state.name_x / scale),
                        "top": float(st.session_state.name_y / scale),
                        "width": float(st.session_state.name_w / scale),
                        "height": float(st.session_state.name_h / scale),
                        "fill": "rgba(0, 169, 157, 0.35)",
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
                        "left": float(st.session_state.qr_x / scale),
                        "top": float(st.session_state.qr_y / scale),
                        "width": float(st.session_state.qr_w / scale),
                        "height": float(st.session_state.qr_h / scale),
                        "fill": "rgba(247, 148, 29, 0.35)",
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
            st.session_state.reset_canvas = False
        
        canvas_result = st_canvas(
            fill_color="rgba(0, 0, 0, 0)",
            stroke_width=2,
            background_image=img,
            initial_drawing=st.session_state.canvas_initial_drawing,
            update_streamlit=True,
            width=canvas_width,
            height=canvas_height,
            drawing_mode="transform",
            display_toolbar=False,
            key="canvas_designer",
        )
        
        if canvas_result.json_data is not None:
            objects = canvas_result.json_data.get("objects", [])
            if len(objects) >= 2:
                obj_name = objects[0]
                obj_qr = objects[1]
                
                def get_scaled_coords(obj):
                    left = obj.get("left", 0)
                    top = obj.get("top", 0)
                    w = obj.get("width", 50) * obj.get("scaleX", 1.0)
                    h = obj.get("height", 50) * obj.get("scaleY", 1.0)
                    return int(left * scale), int(top * scale), int(w * scale), int(h * scale)
                
                nx, ny, nw, nh = get_scaled_coords(obj_name)
                qx, qy, qw, qh = get_scaled_coords(obj_qr)
                
                # Solo actualizar si cambiaron de forma relevante para evitar loops infinitos
                if (nx != st.session_state.name_x or ny != st.session_state.name_y or
                    nw != st.session_state.name_w or nh != st.session_state.name_h or
                    qx != st.session_state.qr_x or qy != st.session_state.qr_y or
                    qw != st.session_state.qr_w or qh != st.session_state.qr_h):
                    
                    st.session_state.name_x = nx
                    st.session_state.name_y = ny
                    st.session_state.name_w = nw
                    st.session_state.name_h = nh
                    
                    st.session_state.qr_x = qx
                    st.session_state.qr_y = qy
                    st.session_state.qr_w = qw
                    st.session_state.qr_h = qh
    
                    # Guardar coordenadas en archivo permanente
                    try:
                        import json
                        with open(SAVED_COORDS_PATH, "w", encoding="utf-8") as f:
                            json.dump({
                                "name_x": nx, "name_y": ny, "name_w": nw, "name_h": nh,
                                "qr_x": qx, "qr_y": qy, "qr_w": qw, "qr_h": qh
                            }, f)
                    except Exception:
                        pass

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Paso Anterior (Plantilla)", use_container_width=True):
                st.session_state.current_step = 1
                st.rerun()
        with col2:
            if st.button("➡️ Siguiente Paso: Subir PowerPoint y Generar", use_container_width=True):
                st.session_state.current_step = 3
                st.rerun()


# --- PASO 3: SUBIR BOLETINES Y GENERAR ---
elif step == 3:
    if st.session_state.processed_zip_data is not None:
        st.markdown("### 🎉 ¡Procesamiento Completado con Éxito!")
        st.markdown("Los boletines han sido generados y los códigos QR fueron insertados y vinculados correctamente.")
        
        st.markdown("---")
        st.markdown("### 📥 Descarga de Boletines Procesados")
        
        col_down, col_reset = st.columns([1, 1])
        with col_down:
            st.download_button(
                label="📥 Descargar todos los boletines (.ZIP)",
                data=st.session_state.processed_zip_data,
                file_name="boletines_procesados.zip",
                mime="application/zip",
                use_container_width=True
            )
        with col_reset:
            if st.button("🔄 REINICIAR PROCESO / NUEVO GRADO", type="primary", use_container_width=True):
                # Limpiar todo el estado de generación y volver al Paso 1
                st.session_state.processed_zip_data = None
                st.session_state.results_gallery = []
                st.session_state.current_step = 1
                st.rerun()
        
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
    else:
        st.markdown("### 4️⃣ Paso 4: Subir Boletines PowerPoint y Generar Resultados")
        st.markdown("Sube las presentaciones de PowerPoint (.pptx) de tus alumnos o un archivo ZIP que contenga todas. ¡El sistema las convertirá en PDF y colocará los QR de forma totalmente automática!")
        
        uploaded_files = st.file_uploader(
            "Sube tus archivos PowerPoint (.pptx) o un archivo .zip que los contenga",
            type=["pptx", "zip"],
            accept_multiple_files=True,
            key="main_pptx_uploader"
        )
        
        if uploaded_files:
            st.markdown(f"**Archivos cargados:** {len(uploaded_files)}")
            
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
            
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith(".pptx") and not file.startswith("~$"):
                        pptx_files.append(os.path.join(root, file))
                        
            if len(pptx_files) == 0:
                st.error("No se encontraron archivos PowerPoint (.pptx) en la selección.")
            else:
                st.success(f"¡Se detectaron {len(pptx_files)} archivos de boletines PowerPoint listos para procesar!")
                
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
                            
                # Botón de Procesar gigante y visible
                if st.button("🚀 INICIAR PROCESAMIENTO COMPLETO", use_container_width=True):
                    if not st.session_state.template_path:
                        st.error("Falta la imagen de la plantilla. Por favor vuelve al Paso 1.")
                    else:
                        st.session_state.processed_zip_data = None
                        st.session_state.results_gallery = []
                        
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
                        
                        uploader = create_uploader(
                            st.session_state.google_credentials_path,
                            st.session_state.drive_folder_id_val,
                            mock=not bool(st.session_state.google_credentials_path)
                        )
                        if getattr(uploader, "is_mock", True):
                            if st.session_state.google_credentials_path:
                                add_log("❌ Error de autenticación con Google Drive. Usando modo simulado (los enlaces QR serán ficticios).")
                            else:
                                add_log("ℹ️ No se cargaron credenciales de Drive. Los archivos se descargarán directamente en un archivo ZIP (enlaces QR simulados).")
                        else:
                            add_log("☁️ Conectado exitosamente a Google Drive y listo para subir PDFs.")
                        
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
                                        err_msg = getattr(uploader, "last_error", "Error desconocido")
                                        add_log(f"  ❌ Error subiendo a Google Drive: {err_msg}")
                                
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
                            for root_dir, _, files in os.walk(out_png):
                                for file in files:
                                    zipf.write(os.path.join(root_dir, file), os.path.join("Imagenes", file))
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
                                img_data.load()
                                st.session_state.results_gallery.append({
                                    "name": res["name"],
                                    "img": img_data,
                                    "qr_link": res.get("qr_link", "")
                                })
                            except Exception:
                                pass
                                
                        # Limpieza de temporales al finalizar
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        st.rerun()
            
            # Limpieza de temporales al finalizar si no se inició el procesamiento
            shutil.rmtree(temp_dir, ignore_errors=True)

            # Sección opcional de Google Drive colapsada al final
            st.markdown("---")
            with st.expander("☁️ Configuración de Google Drive (Opcional / Auto)", expanded=False):
                st.markdown("Si deseas que los boletines PDF se suban automáticamente a tu Google Drive para que los códigos QR funcionen en internet, revisa tu conexión aquí:")
                
                # Mostrar estado de credenciales guardadas
                if os.path.exists(SAVED_CREDS_PATH) or (st.session_state.google_credentials_path == SAVED_CREDS_PATH):
                    st.success("🟢 Conectado exitosamente: Las credenciales ya están guardadas de forma segura.")
                else:
                    st.info("🟡 Sin conexión: Los archivos se descargarán de forma local en un ZIP pero no se subirán a Drive.")
                    
                uploaded_creds_main = st.file_uploader(
                    "Subir archivo JSON de credenciales de Google Drive (Reemplazar/Configurar)",
                    type=["json"],
                    key="main_drive_creds_uploader"
                )
                
                if uploaded_creds_main:
                    try:
                        with open(SAVED_CREDS_PATH, "wb") as f:
                            f.write(uploaded_creds_main.read())
                        st.session_state.google_credentials_path = SAVED_CREDS_PATH
                        st.success("¡Credenciales de Google Drive guardadas con éxito!")
                    except Exception as e:
                        st.error(f"Error al guardar credenciales: {e}")
                        
                drive_folder_id = st.text_input(
                    "Folder ID de Google Drive (Carpeta de destino)",
                    value=st.session_state.drive_folder_id_val
                )
                
                if drive_folder_id != st.session_state.drive_folder_id_val:
                    st.session_state.drive_folder_id_val = drive_folder_id
                    try:
                        with open(SAVED_FOLDER_ID_PATH, "w", encoding="utf-8") as f:
                            f.write(drive_folder_id)
                    except Exception:
                        pass
                        
                if st.session_state.drive_folder_id_val:
                    st.info(f"📁 Carpeta vinculada ID: `{st.session_state.drive_folder_id_val}`")

        st.markdown("---")
        if st.button("⬅️ Paso Anterior (Diseñar)", use_container_width=True):
            st.session_state.current_step = 2
            st.rerun()

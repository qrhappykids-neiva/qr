FROM python:3.10-slim

# Instalar dependencias del sistema necesarias (LibreOffice, fuentes y utilidades)
RUN apt-get update && apt-get install -y \
    libreoffice \
    fontconfig \
    fonts-liberation \
    fonts-dejavu \
    poppler-utils \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Definir directorio de trabajo
WORKDIR /app

# Copiar requerimientos e instalar dependencias de Python
COPY requirements_web.txt .
RUN pip install --no-cache-dir -r requirements_web.txt

# Copiar el código del proyecto
COPY . .

# Exponer el puerto por defecto de Hugging Face Spaces (7860)
EXPOSE 7860

# Comando para ejecutar Streamlit en el puerto correcto de la nube
CMD ["streamlit", "run", "app_web.py", "--server.port=7860", "--server.address=0.0.0.0"]

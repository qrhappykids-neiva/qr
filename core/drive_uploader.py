import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
Módulo de subida a Google Drive usando OAuth2 (cuenta personal).
No requiere cuenta de servicio ni Google Workspace.
"""

import os
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)

# Archivo donde se guarda el token OAuth2 (se crea automáticamente)
TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".boletines_qr", "token.json")
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveUploader:
    """Sube archivos a Google Drive usando OAuth2 o Cuenta de Servicio."""

    def __init__(self, credentials_path: str, folder_id: str = ""):
        self.credentials_path = credentials_path
        self.folder_id = folder_id
        self._service = None
        self._authenticated = False
        self.is_mock = False
        self.last_error = ""

    def authenticate(self) -> bool:
        # 1. Intentar autenticación por Cuenta de Servicio si es ese tipo de JSON
        is_service_account = False
        try:
            with open(self.credentials_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("type") == "service_account":
                    is_service_account = True
        except Exception:
            pass

        if is_service_account:
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                
                creds = service_account.Credentials.from_service_account_file(
                    self.credentials_path, scopes=SCOPES
                )
                self._service = build("drive", "v3", credentials=creds)
                self._authenticated = True
                logger.info("✅ Autenticado con Cuenta de Servicio de Google Drive")
                return True
            except Exception as e:
                logger.error(f"Error conectando con Cuenta de Servicio: {e}")
                return False

        # 2. Flujo de OAuth2 Personal si no es cuenta de servicio
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            logger.error("Instala: pip install google-auth google-auth-oauthlib google-api-python-client")
            return False

        creds = None

        # Cargar token guardado si existe
        if os.path.exists(TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            except Exception:
                pass

        # Si no hay token válido, iniciar flujo OAuth2
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    from google.auth.transport.requests import Request
                    creds.refresh(Request())
                except Exception:
                    creds = None

            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, SCOPES
                    )
                    # Abre el navegador para que el usuario autorice
                    creds = flow.run_local_server(port=0, open_browser=True)
                except Exception as e:
                    logger.error(f"Error en autenticación OAuth2: {e}")
                    return False

            # Guardar token para la próxima vez
            os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

        try:
            self._service = build("drive", "v3", credentials=creds)
            self._authenticated = True
            logger.info("✅ Autenticado con Google Drive (cuenta personal)")
            return True
        except Exception as e:
            logger.error(f"Error conectando a Drive: {e}")
            return False

    def ensure_folder(self, folder_name: str = "Boletines QR") -> bool:
        """Usa la carpeta configurada o crea una nueva."""
        if self.folder_id:
            return True
        new_id = self._create_folder(folder_name)
        if new_id:
            self.folder_id = new_id
            return True
        return False

    def _create_folder(self, name: str, parent_id: str = "") -> Optional[str]:
        try:
            metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            if parent_id:
                metadata["parents"] = [parent_id]
            elif self.folder_id:
                metadata["parents"] = [self.folder_id]

            folder = self._service.files().create(body=metadata, fields="id").execute()
            fid = folder.get("id")
            logger.info(f"Carpeta creada en Drive: {name} (ID: {fid})")
            return fid
        except Exception as e:
            logger.error(f"Error creando carpeta: {e}")
            return None

    def upload_pdf(self, pdf_path: str, filename: str = "") -> Optional[str]:
        if not self._authenticated:
            return None
        if not os.path.exists(pdf_path):
            return None

        try:
            from googleapiclient.http import MediaFileUpload

            if not filename:
                filename = os.path.basename(pdf_path)

            metadata = {"name": filename, "mimeType": "application/pdf"}
            if self.folder_id:
                metadata["parents"] = [self.folder_id]

            media = MediaFileUpload(pdf_path, mimetype="application/pdf", resumable=True)
            file = self._service.files().create(
                body=metadata, media_body=media, fields="id,webViewLink"
            ).execute()

            file_id = file.get("id")

            # Hacer público
            self._service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"}
            ).execute()

            share_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
            logger.info(f"✅ Subido: {filename}")
            return share_link

        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Error subiendo {pdf_path}: {e}")
            return None


class MockDriveUploader:
    """Uploader simulado para pruebas sin Drive."""

    def __init__(self):
        self.is_mock = True

    def authenticate(self) -> bool:
        return True

    def ensure_folder(self, folder_name: str = "") -> bool:
        return True

    def upload_pdf(self, pdf_path: str, filename: str = "") -> Optional[str]:
        import hashlib
        name = filename or os.path.basename(pdf_path)
        fake_id = hashlib.md5(name.encode()).hexdigest()[:20]
        url = f"https://drive.google.com/file/d/{fake_id}/view?usp=sharing"
        logger.info(f"[SIMULADO] {name}: {url}")
        return url


def create_uploader(credentials_path: str, folder_id: str = "", mock: bool = False):
    if mock or not credentials_path or not os.path.exists(credentials_path):
        logger.warning("Usando uploader simulado.")
        return MockDriveUploader()

    uploader = GoogleDriveUploader(credentials_path, folder_id)
    if not uploader.authenticate():
        logger.warning("Falla autenticación. Usando simulado.")
        return MockDriveUploader()

    uploader.ensure_folder("Boletines QR")
    return uploader

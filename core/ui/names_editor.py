import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
Widget de edición masiva de nombres detectados.
Permite ver y editar todos los nombres antes de procesar.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QDialog, QMessageBox, QHeaderView,
    QAbstractItemView, QLineEdit, QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut


class NamesEditorDialog(QDialog):
    """
    Diálogo de edición masiva de nombres de estudiantes.
    Muestra una tabla editable con todos los nombres detectados.
    """
    
    names_confirmed = Signal(list)  # lista de dicts {"path": ..., "name": ...}

    def __init__(self, students: list[dict], parent=None):
        """
        Args:
            students: Lista de dicts [{"path": ..., "original_filename": ..., "name": ...}]
        """
        super().__init__(parent)
        self.students = [s.copy() for s in students]
        self.setWindowTitle("Edición de Nombres Detectados")
        self.setMinimumSize(900, 600)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Encabezado
        header = QHBoxLayout()
        title = QLabel("✏️ Verificación y Edición de Nombres")
        title.setObjectName("labelTitle")
        header.addWidget(title)
        header.addStretch()
        
        count_lbl = QLabel(f"{len(self.students)} estudiantes detectados")
        count_lbl.setStyleSheet("color: #555555; font-weight: bold;")
        header.addWidget(count_lbl)
        layout.addLayout(header)

        info = QLabel(
            "Revisa y edita los nombres antes de procesar. "
            "Haz doble clic en una celda para editarla. "
            "Puedes copiar y pegar desde Excel (Ctrl+V)."
        )
        info.setObjectName("labelSubtitle")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Barra de herramientas
        toolbar = QHBoxLayout()
        
        self.lbl_search = QLineEdit()
        self.lbl_search.setPlaceholderText("🔍 Buscar estudiante...")
        self.lbl_search.textChanged.connect(self._filter_table)
        toolbar.addWidget(self.lbl_search, stretch=2)
        
        btn_upper = QPushButton("A→ MAYÚSCULAS")
        btn_upper.setObjectName("btnSecondary")
        btn_upper.setToolTip("Convertir todos los nombres a mayúsculas")
        btn_upper.clicked.connect(self._to_uppercase)
        toolbar.addWidget(btn_upper)
        
        btn_reset = QPushButton("↺ Restaurar Original")
        btn_reset.setObjectName("btnSecondary")
        btn_reset.clicked.connect(self._reset_names)
        toolbar.addWidget(btn_reset)
        
        layout.addLayout(toolbar)

        # Tabla
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["#", "Archivo Original", "Nombre del Estudiante"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(38)  # Renglones más altos y modernos
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { alternate-background-color: #f2fbfb; }
            QTableWidget QLineEdit {
                padding: 3px 6px;
                border: 2px solid #00A99D;
                border-radius: 4px;
                background-color: #ffffff;
            }
        """)
        layout.addWidget(self.table, stretch=1)

        # Estadísticas
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #555555; font-size: 9pt;")
        layout.addWidget(self.lbl_status)

        # Botones
        btn_row = QHBoxLayout()
        
        btn_cancel = QPushButton("❌ Cancelar")
        btn_cancel.setObjectName("btnDanger")
        btn_cancel.clicked.connect(self.reject)
        
        btn_confirm = QPushButton("✅ Confirmar y Procesar")
        btn_confirm.clicked.connect(self._confirm)
        
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(QLabel("Edita los nombres incorrectos antes de continuar"))
        btn_row.addWidget(btn_confirm)
        layout.addLayout(btn_row)

        # Atajo Ctrl+V para pegar desde Excel
        paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self.table)
        paste_shortcut.activated.connect(self._paste_from_clipboard)

    def _load_data(self):
        """Carga los datos en la tabla."""
        self.table.setRowCount(len(self.students))
        for row, student in enumerate(self.students):
            # Número
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            num_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, num_item)
            
            # Archivo original (solo lectura)
            orig_item = QTableWidgetItem(student.get("original_filename", ""))
            orig_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            orig_item.setForeground(QColor("#555555"))
            self.table.setItem(row, 1, orig_item)
            
            # Nombre editable
            name_item = QTableWidgetItem(student.get("name", ""))
            name_item.setToolTip("Haz doble clic para editar")
            self.table.setItem(row, 2, name_item)
        
        self._update_status()

    def _filter_table(self, text: str):
        """Filtra las filas según el texto de búsqueda."""
        for row in range(self.table.rowCount()):
            match = False
            for col in range(1, 3):
                item = self.table.item(row, col)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match and bool(text))

    def _to_uppercase(self):
        """Convierte todos los nombres editables a mayúsculas."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 2)
            if item:
                item.setText(item.text().upper().strip())

    def _reset_names(self):
        """Restaura los nombres al estado original detectado."""
        reply = QMessageBox.question(
            self, "Restaurar",
            "¿Restaurar todos los nombres al valor detectado automáticamente?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for row, student in enumerate(self.students):
                item = self.table.item(row, 2)
                if item:
                    item.setText(student.get("name", ""))

    def _paste_from_clipboard(self):
        """Pega nombres desde el portapapeles (soporte para copiar desde Excel)."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return
        
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        start_row = self.table.currentRow()
        if start_row < 0:
            start_row = 0
        
        for i, line in enumerate(lines):
            row = start_row + i
            if row >= self.table.rowCount():
                break
            # Si la línea tiene tabuladores (Excel), tomar solo la columna del nombre
            parts = line.split("\t")
            name = parts[-1].strip() if parts else line
            item = self.table.item(row, 2)
            if item:
                item.setText(name.upper())

    def _update_status(self):
        empty = sum(
            1 for row in range(self.table.rowCount())
            if not (self.table.item(row, 2) and self.table.item(row, 2).text().strip())
        )
        total = self.table.rowCount()
        if empty:
            self.lbl_status.setText(
                f"⚠️ {empty} nombre(s) vacío(s) de {total}. "
                "Los estudiantes sin nombre serán omitidos."
            )
            self.lbl_status.setStyleSheet("color: #d08770; font-size: 9pt; font-weight: bold;")
        else:
            self.lbl_status.setText(f"✅ {total} nombres listos para procesar")
            self.lbl_status.setStyleSheet("color: #2e7d32; font-size: 9pt; font-weight: bold;")

    def _confirm(self):
        """Confirma los nombres y emite la señal."""
        # Leer nombres actualizados de la tabla
        confirmed = []
        for row, student in enumerate(self.students):
            item = self.table.item(row, 2)
            name = item.text().strip().upper() if item else ""
            if not name:
                continue  # omitir vacíos
            confirmed.append({
                "path": student["path"],
                "original_filename": student.get("original_filename", ""),
                "name": name,
            })
        
        if not confirmed:
            QMessageBox.warning(self, "Sin nombres", "No hay nombres válidos para procesar.")
            return
        
        self.names_confirmed.emit(confirmed)
        self.accept()

    def get_confirmed_students(self) -> list[dict]:
        """Retorna la lista de estudiantes con nombres confirmados."""
        result = []
        for row, student in enumerate(self.students):
            item = self.table.item(row, 2)
            name = item.text().strip().upper() if item else ""
            if name:
                result.append({**student, "name": name})
        return result

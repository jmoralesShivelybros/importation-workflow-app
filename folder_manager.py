import os
from datetime import datetime, timedelta
import shutil
from pathlib import Path

class FolderManager:
    def __init__(self, logistica_root):
        """
        Inicializa el gestor de carpetas con una ruta raíz configurable.
        :param logistica_root: La ruta base donde se creará la estructura 'Logistica'.
        """
        self.logistica_root = logistica_root
        self.current_year = str(datetime.now().year)
        
        # Rutas específicas para importación y exportación
        self.importacion_base_path = os.path.join(self.logistica_root, "importacion", self.current_year)
        self.exportacion_base_path = os.path.join(self.logistica_root, "exportacion")
        self.almacen_base_path = os.path.join(self.logistica_root, "almacen")
        
        # Subcarpetas estándar para cada área
        self.importacion_subfolders = ['Facturas', 'OMs', 'Cartas', 'master']
        self.exportacion_subfolders = ['Archivos importantes', 'Certificados'] # El año se crea dinámicamente

        # Al inicializar, nos aseguramos de que la estructura base exista
        self.setup_folders()

    def setup_folders(self):
        """Crea la estructura de carpetas base para importación y exportación si no existen."""
        print(f"Configurando carpetas en: {self.logistica_root}")
        os.makedirs(self.importacion_base_path, exist_ok=True)
        os.makedirs(self.exportacion_base_path, exist_ok=True)
        os.makedirs(self.almacen_base_path, exist_ok=True)

        for subfolder in self.exportacion_subfolders:
            path = os.path.join(self.exportacion_base_path, subfolder)
            os.makedirs(path, exist_ok=True)
        
        # Asegura que la carpeta del año actual exista dentro de exportación
        os.makedirs(os.path.join(self.exportacion_base_path, self.current_year), exist_ok=True)

        # --- Copia los archivos de recursos (importantes y certificados) ---
        self._copy_resources('archivos_importantes', 'Archivos importantes')
        self._copy_resources('exportacion/certificados', 'Certificados')

    def _copy_resources(self, source_subpath, dest_subfolder_name):
        """
        Copia archivos desde una carpeta de recursos del proyecto a una carpeta de destino en Logistica.
        :param source_subpath: Ruta relativa dentro de 'test_files' (ej: 'exportacion/certificados').
        :param dest_subfolder_name: Nombre de la carpeta de destino dentro de 'exportacion'.
        """
        # La ruta de origen es relativa a la ubicación del script, dentro de 'test_files'
        source_path = Path(__file__).parent / 'test_files' / source_subpath
        # La ruta de destino está en la carpeta de exportación del usuario
        dest_path = os.path.join(self.exportacion_base_path, dest_subfolder_name)

        if source_path.exists():
            for item in os.listdir(source_path):
                src_file = os.path.join(source_path, item)
                dest_file = os.path.join(dest_path, item)
                # Copiar solo si el archivo no existe en el destino para no sobrescribir
                if not os.path.exists(dest_file):
                    shutil.copy2(src_file, dest_file)
                    print(f"Copiado recurso a '{dest_subfolder_name}': {item}")

    def get_next_weeks(self, count=3):
        """Obtiene las próximas semanas a partir de la actual"""
        current_week = datetime.now().isocalendar()[1]
        return [current_week + i for i in range(count)]

    def check_and_create_folders(self):
        """Verifica y crea las carpetas de las próximas semanas si no existen"""
        created_folders = []
        next_weeks = self.get_next_weeks()

        for week_num in next_weeks:
            folder_name = f"semana {week_num}"
            folder_path = os.path.join(self.importacion_base_path, folder_name)
            
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                created_folders.append(folder_name)
                
                # Crear subcarpetas estándar
                for subcarpeta in self.importacion_subfolders:
                    os.makedirs(os.path.join(folder_path, subcarpeta), exist_ok=True)

        return created_folders

    def create_week_folder(self, week_num):
        """Crea una carpeta para la semana especificada tanto en importación como en exportación."""
        folder_name = f"semana {week_num}"
        created_any = False

        # --- Carpeta de Importación ---
        import_folder_path = os.path.join(self.importacion_base_path, folder_name)
        if not os.path.exists(import_folder_path):
            os.makedirs(import_folder_path)
            # Crear subcarpetas estándar
            for subcarpeta in self.importacion_subfolders:
                os.makedirs(os.path.join(import_folder_path, subcarpeta), exist_ok=True)
            created_any = True

        # --- Carpeta de Exportación ---
        export_year_path = os.path.join(self.exportacion_base_path, self.current_year)
        export_folder_path = os.path.join(export_year_path, folder_name)
        if not os.path.exists(export_folder_path):
            os.makedirs(export_folder_path) # No tiene subcarpetas
            created_any = True
        
        return created_any

    def get_existing_weeks(self):
        """Obtiene la lista de carpetas de semanas existentes"""
        weeks = []
        if os.path.exists(self.importacion_base_path):
            for item in os.listdir(self.importacion_base_path):
                if item.startswith("semana "):
                    weeks.append(item)
        return sorted(weeks)

    def get_omc_folder_path(self, week_num):
        year = datetime.now().year
        week_folder = f"semana {week_num}"
        return os.path.join(self.importacion_base_path, str(year), week_folder, "OMC")

    def get_cartas_folder_path(self, week_num):
        """Devuelve la ruta a la carpeta 'Cartas' para una semana específica."""
        week_folder = f"semana {week_num}"
        return os.path.join(self.importacion_base_path, week_folder, "Cartas")

    def get_master_folder_path(self, week_num):
        """Devuelve la ruta a la carpeta 'master' para una semana específica."""
        week_folder = f"semana {week_num}"
        return os.path.join(self.importacion_base_path, week_folder, "master")

    def get_certificados_folder_path(self):
        """Devuelve la ruta a la carpeta 'Certificados' de exportación."""
        return os.path.join(self.exportacion_base_path, "Certificados")

    def get_warehouse_db_path(self):
        """Devuelve la ruta al archivo CSV principal de inventario."""
        return os.path.join(self.almacen_base_path, "inventario_almacen.csv")

    def get_warehouse_log_path(self):
        """Devuelve la ruta al archivo CSV de historial/logs."""
        return os.path.join(self.almacen_base_path, "historial_movimientos.csv")
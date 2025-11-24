import tkinter as tk
import ttkbootstrap as ttk
from tkinter.ttk import LabelFrame
from ttkbootstrap.constants import *
from ttkbootstrap import Style
from tkinter import messagebox
import json
from tkinter import filedialog
import time
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__))) # Añade la raíz del proyecto al sys.path
from firma_cartas import letter_generator # Importar desde el subpaquete firma_cartas

from folder_manager import FolderManager
from importation_window import ImportationWindow
from norm_letter_window import NormLetterWindow
from exportation_window import ExportationWindow


def get_base_path():
    """ Obtiene la ruta base para encontrar los recursos, tanto en desarrollo como en el ejecutable."""
    if getattr(sys, 'frozen', False):
        # Si la aplicación está "congelada" (es un .exe), la base es el directorio temporal _MEIPASS
        return sys._MEIPASS
    else:
        # Si se está ejecutando como un script normal, la base es el directorio del script
        return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(get_base_path(), "config.json")

def load_or_request_config(window):
    """Carga la configuración o solicita al usuario que elija una ruta base."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        if "logistica_root" in config and os.path.exists(config["logistica_root"]):
            return config["logistica_root"]
        else:
            raise FileNotFoundError  # Forzar la selección si la ruta guardada no es válida
    except (FileNotFoundError, json.JSONDecodeError):
        # Si no hay config.json o está corrupto, iniciamos el asistente de configuración.
        # Ocultamos la ventana principal para que el asistente sea el foco.
        window.withdraw()
        
        messagebox.showinfo(
            "Asistente de Configuración Inicial",
            "Bienvenido. Parece que es la primera vez que ejecutas el programa o se ha perdido la configuración.\n\nVamos a configurar la carpeta 'Logistica' donde se guardarán todos tus archivos."
        )
        
        use_existing = messagebox.askyesno(
            "Carpeta 'Logistica'",
            "¿Ya tienes una carpeta 'Logistica' que deseas usar?"
        )

        logistica_root = ""
        if use_existing:
            messagebox.showinfo("Seleccionar Carpeta", "A continuación, selecciona tu carpeta 'Logistica' existente.")
            chosen_path = filedialog.askdirectory(title="Selecciona tu carpeta 'Logistica'")
            if chosen_path:
                logistica_root = chosen_path
            else:
                messagebox.showwarning("Selección Inválida", "No seleccionaste una carpeta. La aplicación se cerrará.")
                window.destroy() # Usamos destroy() para cerrar la app de forma segura
                return None
        else:
            messagebox.showinfo(
                "Crear Nueva Carpeta",
                "A continuación, selecciona la ubicación donde deseas crear la nueva carpeta 'Logistica' (por ejemplo, en 'Mis Documentos')."
            )
            parent_path = filedialog.askdirectory(title="Selecciona la carpeta para guardar los datos de Logística")
            if parent_path:
                logistica_root = os.path.join(parent_path, "Logistica")
            else:
                messagebox.showwarning("Selección Inválida", "No seleccionaste una ubicación. La aplicación se cerrará.")
                window.destroy()
                return None

        config = {"logistica_root": logistica_root}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)

        # Si todo salió bien, volvemos a mostrar la ventana principal
        window.deiconify()
        return logistica_root

class ImportationApp(ttk.Window):
    def __init__(self):
        super().__init__(themename='flatly')
        self.title("Sistema de Logistica")
        self.geometry("1000x800")
        self._center_window() # Centramos la ventana principal al iniciar
        
        # --- Carga de configuración mejorada ---
        self.logistica_root_path = load_or_request_config(self)
        if not self.logistica_root_path:
            return # Si la configuración falla, no continuamos con la inicialización

        # --- Verificación de recursos críticos ---
        if not self._check_critical_resources():
            return # Si faltan recursos, la aplicación ya se habrá cerrado

        self.folder_manager = FolderManager(self.logistica_root_path)
        
        current_week = datetime.now().isocalendar()[1]
        self.selected_week = tk.StringVar(value=str(current_week))
        self.child_window = None  # Para controlar ventanas hijas

        # --- Creación de la Interfaz Gráfica ---
        self.create_gui()
        self._update_status_bar() # Actualiza la barra de estado con la ruta inicial

    def create_gui(self):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        week_frame = LabelFrame(
            main_frame,
            text="Selección de Semana",
            padding="10",
            bootstyle="secondary"
        )
        week_frame.pack(fill=tk.X, pady=10)

        ttk.Label(
            week_frame,
            text="Número de semana:",
            bootstyle="secondary inverse"
        ).pack(side=tk.LEFT, padx=10)

        self.week_spinbox = ttk.Spinbox(
            week_frame,
            from_=1,
            to=53,
            width=10,
            textvariable=self.selected_week,
            bootstyle="secondary"
        )
        self.week_spinbox.pack(side=tk.LEFT, padx=10)

        self.create_week_btn = ttk.Button(
            week_frame,
            text="Crear carpeta de semana",
            command=self.create_week_folder,
            bootstyle="secondary",
            padding=(20, 10)
        )
        self.create_week_btn.pack(side=tk.LEFT, padx=10)

        actions_frame = LabelFrame(
            main_frame,
            text="Acciones",
            padding="15",
            bootstyle="secondary"
        )
        actions_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        actions = [
            ("Generar Importación(Beta)", self.extract_pdf_data, "primary"),
            ("Generar Exportación", self.open_exportation_window, "info"),
            ("Generar Carta de Norma", self.generate_norm_letter, "success"),
        ]

        for text, command, style in actions:
            btn = ttk.Button(
                actions_frame,
                text=text,
                command=command,
                bootstyle=style,
                padding=(20, 15)
            )
            btn.pack(fill=tk.X, pady=8, padx=10)

        log_frame = LabelFrame(
            main_frame,
            text="Log de actividades",
            padding="15",
            bootstyle="secondary"
        )
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        log_scroll = ttk.Scrollbar(log_frame, bootstyle="round-secondary")
        self.log_text = tk.Text(
            log_frame,
            height=12,
            relief="flat",
            bg='#2b3e50',
            fg='#ffffff',
            insertbackground='#ffffff',
            font=("Consolas", 12),
            padx=10,
            pady=10
        )
        log_scroll.config(command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Barra de Estado (para mostrar la ruta de Logistica) ---
        status_frame = ttk.Frame(self, padding=(5, 2), bootstyle="secondary")
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=1, pady=1)

        self.status_label = ttk.Label(status_frame, text="Cargando...", bootstyle="secondary inverse")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # --- Barra de Menú (para Configuración) ---
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)

        file_menu.add_command(label="Cambiar Carpeta de Logistica...", command=self._open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.destroy)

    def _update_status_bar(self):
        self.status_label.config(text=f"Carpeta de trabajo: {self.logistica_root_path}")

    def show_loading(self, message="Procesando..."):
        self.loading = ttk.Toplevel(self)
        self.loading.title("Procesando")
        self.loading.geometry("400x150")
        self.loading.transient(self)
        self.loading.grab_set()

        ttk.Label(
            self.loading,
            text=message,
            bootstyle="secondary inverse"
        ).pack(pady=20)

        progress = ttk.Progressbar(
            self.loading,
            mode='indeterminate',
            bootstyle="secondary",
            length=300
        )
        progress.pack(fill=tk.X, padx=30)
        progress.start()
        self.loading.update()

    def hide_loading(self):
        if hasattr(self, 'loading'):
            self.loading.destroy()

    def show_toast(self, message, style="success"):
        toast = ttk.Toplevel()
        toast.title("")
        toast.geometry("300x50+{}+{}".format(
            self.winfo_x() + self.winfo_width() - 350,
            self.winfo_y() + self.winfo_height() - 100
        ))
        toast.overrideredirect(True)

        ttk.Label(
            toast,
            text=message,
            bootstyle=style
        ).pack(expand=True)

        self.after(2000, toast.destroy)

    def log_message(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.update()

    def create_week_folder(self):
        week_num = self.selected_week.get()
        if not week_num:
            ttk.dialogs.Messagebox.show_warning(
                "Por favor selecciona un número de semana",
                "Advertencia"
            )
            return

        try:
            self.show_loading("Creando carpetas...")

            week_num = int(week_num)
            if week_num < 1 or week_num > 53:
                raise ValueError("Número de semana inválido")

            created_folder = self.folder_manager.create_week_folder(week_num)

            self.hide_loading()

            if created_folder:
                self.show_toast(f"Carpeta semana {week_num} creada exitosamente")
                self.log_message(f"Carpeta creada: semana {week_num}")
                for subcarpeta in self.folder_manager.importacion_subfolders:
                    self.log_message(f"  - {subcarpeta}")
            else:
                self.show_toast(
                    f"La carpeta de semana {week_num} ya existe",
                    "warning"
                )
                self.log_message(f"La carpeta de la semana {week_num} ya existe")

            existing_weeks = self.folder_manager.get_existing_weeks()
            self.log_message("\nCarpetas existentes:")
            for week in existing_weeks:
                self.log_message(f"- {week}")

        except ValueError as e:
            self.hide_loading()
            ttk.dialogs.Messagebox.show_error(str(e), "Error")

    def extract_pdf_data(self):
        if not self.selected_week.get():
            messagebox.showwarning("Advertencia", "Por favor selecciona un número de semana")
            return
        self.open_child_window(ImportationWindow)

    def open_exportation_window(self):
        if not self.selected_week.get():
            messagebox.showwarning("Advertencia", "Por favor selecciona un número de semana")
            return
        self.open_child_window(ExportationWindow) # La lógica es la misma, pero el nombre es más claro

    def generate_norm_letter(self):
        if not self.selected_week.get():
            messagebox.showwarning("Advertencia", "Por favor selecciona un número de semana")
            return
        self.open_child_window(NormLetterWindow)

    def open_child_window(self, WindowClass):
        # Oculta la ventana principal y abre la secundaria
        self.withdraw()
        self.child_window = WindowClass(self)
        self._center_window(self.child_window) # Centramos la ventana hija
        self.child_window.protocol("WM_DELETE_WINDOW", self.on_child_close)

    def on_child_close(self):
        if self.child_window:
            self.child_window.destroy()
            self.child_window = None
        self.deiconify()

    def _center_window(self, window=None):
        """Centra una ventana en la pantalla."""
        if window is None:
            window = self

        window.update_idletasks()  # Actualiza la geometría de la ventana

        # Obtener dimensiones de la pantalla y de la ventana
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        window_width = window.winfo_width()
        window_height = window.winfo_height()

        # Calcular la posición x, y
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)

        window.geometry(f'{window_width}x{window_height}+{x}+{y}')

    def _check_critical_resources(self):
        """
        Verifica la existencia de la carpeta de plantillas y el archivo del logo.
        Si alguno falta, muestra un error y cierra la aplicación.
        """
        template_dir = letter_generator.get_template_path()
        logo_path = os.path.join(get_base_path(), 'firma_cartas', 'logo', 'logo_shively.png')

        if not os.path.exists(template_dir):
            messagebox.showerror(
                "Error de Recursos",
                f"No se encontró la carpeta de plantillas de cartas:\n{template_dir}\n\nAsegúrate de que la estructura de archivos sea correcta."
            )
            self.destroy()
            return False
        
        if not os.path.exists(logo_path):
            messagebox.showerror(
                "Error de Recursos",
                f"No se encontró el archivo del logo:\n{logo_path}\n\nAsegúrate de que el archivo 'logo_shively.png' esté en la carpeta 'firma_cartas/logo'."
            )
            self.destroy()
            return False
        return True

    def _open_settings(self):
        """Abre un diálogo para cambiar la carpeta 'Logistica' y actualiza la configuración."""
        new_path = filedialog.askdirectory(
            title="Selecciona la nueva carpeta 'Logistica'",
            initialdir=os.path.dirname(self.logistica_root_path) # Abre el diálogo en la ubicación padre de la carpeta actual
        )

        if new_path and new_path != self.logistica_root_path:
            # Actualizar el archivo de configuración
            config = {"logistica_root": new_path}
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)

            # Actualizar la aplicación en tiempo de ejecución
            self.logistica_root_path = new_path
            self.folder_manager = FolderManager(self.logistica_root_path)
            self._update_status_bar()

            messagebox.showinfo(
                "Configuración Actualizada",
                f"La carpeta de trabajo ha sido cambiada a:\n{new_path}\n\nLos cambios se han aplicado."
            )
            self.log_message(f"CONFIG: Carpeta de trabajo cambiada a {new_path}")

if __name__ == "__main__":
    app = ImportationApp()
    app.mainloop()
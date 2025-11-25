import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
from tkinter.ttk import LabelFrame # Importar LabelFrame directamente de tkinter.ttk
import os
from master.master_data import MasterDataManager # Importamos la nueva clase de lógica

class MasterWindow(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        
        # Configuración básica de la ventana
        self.title("Actualizar Archivo Master")
        self.geometry("1200x800")

        # --- CONFIGURACIÓN DE CONEXIÓN A SHAREPOINT ---
        # ¡¡¡IMPORTANTE!!! Completa estos datos.
        site_url = "https://shivelybrothersinc.sharepoint.com/sites/Logistica" # URL de tu sitio de SharePoint
        file_relative_url = "/Shared Documents/master.xlsx" # Ruta relativa del archivo dentro del sitio
        
        # --- Manejo de Credenciales (¡Mejorar en el futuro!) ---
        # Por ahora, para la prueba, las ponemos aquí.
        # En una versión final, esto debería leerse de un lugar seguro o solicitarse al usuario.
        username = "tu_correo@shivelybros.com" # <-- CAMBIA ESTO
        password = "tu_contraseña" # <-- CAMBIA ESTO
        
        # --- Instancia del gestor de datos ---
        # La ventana ahora delega toda la lógica de datos a esta clase.
        try:
            self.data_manager = MasterDataManager(site_url, file_relative_url, username, password)
        except Exception as e:
            messagebox.showerror("Error de Configuración", f"No se pudo inicializar el gestor de datos: {e}")
            self.destroy()
            return
        
        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- NUEVO: Frame para ingresar datos manualmente ---
        input_frame = LabelFrame(main_frame, text="Prueba de Escritura en Celda de SharePoint", padding="15")
        input_frame.pack(fill=tk.X, pady=20)

        # Variables para los campos de entrada
        self.sheet_name_var = tk.StringVar(value="Hoja1") # Valor por defecto
        self.cell_address_var = tk.StringVar(value="A1") # Valor por defecto
        self.text_to_write_var = tk.StringVar(value="Prueba de conexión exitosa") # Valor por defecto

        # Creación de los campos de entrada
        ttk.Label(input_frame, text="Nombre de la Pestaña:").grid(row=0, column=0, padx=5, pady=10, sticky="w")
        sheet_entry = ttk.Entry(input_frame, textvariable=self.sheet_name_var, width=30)
        sheet_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        ttk.Label(input_frame, text="Celda (ej. B5):").grid(row=1, column=0, padx=5, pady=10, sticky="w")
        cell_entry = ttk.Entry(input_frame, textvariable=self.cell_address_var, width=30)
        cell_entry.grid(row=1, column=1, padx=5, pady=10, sticky="ew")

        ttk.Label(input_frame, text="Texto a Escribir:").grid(row=2, column=0, padx=5, pady=10, sticky="w")
        text_entry = ttk.Entry(input_frame, textvariable=self.text_to_write_var, width=50)
        text_entry.grid(row=2, column=1, padx=5, pady=10, sticky="ew")

        input_frame.grid_columnconfigure(1, weight=1)

        # Botón para ejecutar la prueba
        test_btn = ttk.Button(main_frame, text="Escribir en Excel", command=self.run_write_test, bootstyle="success", padding=(20,10))
        test_btn.pack(pady=20)

    def run_write_test(self):
        # Obtener los datos de la interfaz
        sheet = self.sheet_name_var.get()
        cell = self.cell_address_var.get()
        text = self.text_to_write_var.get()
        
        if not all([sheet, cell, text]):
            messagebox.showwarning("Datos Incompletos", "Por favor, completa todos los campos.")
            return

        try:
            self.parent.show_loading("Conectando y escribiendo en SharePoint...")
            self.data_manager.write_single_cell(sheet, cell, text)
            self.parent.hide_loading()
            messagebox.showinfo("Éxito", f"Se ha escrito '{text}' en la celda {cell} de la hoja '{sheet}'.\n\n¡La conexión funciona!")
        except Exception as e:
            self.parent.hide_loading()
            messagebox.showerror("Error al Escribir", f"No se pudo escribir en el archivo de SharePoint. Error:\n\n{e}\n\nVerifica tus credenciales, la URL del sitio y la ruta del archivo.")

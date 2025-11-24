import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter.ttk import LabelFrame
from tkinter import messagebox

# Importamos las funciones de lógica
from firma_cartas.letter_generator import generate_letter_content, get_available_templates, generate_letter_pdf
import os

class NormLetterWindow(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Generador de Cartas de Norma")
        self.geometry("800x500") # Hacemos la ventana más compacta

        # Cargamos dinámicamente las plantillas disponibles desde la carpeta
        self.letter_templates = get_available_templates()
        self.selected_template = tk.StringVar()
        self.invoice_numbers = tk.StringVar()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Sección de Selección y Entradas ---
        input_frame = LabelFrame(main_frame, text="Datos de la Carta", padding="15", bootstyle="primary")
        input_frame.pack(fill=tk.X, pady=10)

        # Menú desplegable para seleccionar la plantilla
        ttk.Label(input_frame, text="Selecciona la plantilla de la carta:").pack(anchor='w', pady=(0, 5))
        template_combo = ttk.Combobox(
            input_frame,
            textvariable=self.selected_template,
            values=self.letter_templates,
            state="readonly",
            bootstyle="primary"
        )
        template_combo.pack(fill=tk.X, pady=(0, 15))
        template_combo.set("Selecciona una opción...")

        # Campo para ingresar números de factura
        ttk.Label(input_frame, text="Ingresa los números de factura (separados por coma):").pack(anchor='w', pady=(0, 5))
        invoice_entry = ttk.Entry(input_frame, textvariable=self.invoice_numbers, bootstyle="primary")
        invoice_entry.pack(fill=tk.X, pady=(0, 20))

        # Botón único para generar y guardar el PDF
        generate_btn = ttk.Button(
            input_frame,
            text="Generar y Guardar PDF",
            command=self.save_as_pdf,
            bootstyle="success"
        )
        generate_btn.pack(fill=tk.X, ipady=10)

    def save_as_pdf(self):
        # 1. Validar que los datos necesarios estén seleccionados
        template = self.selected_template.get()
        invoices = self.invoice_numbers.get()
        if not template or template == "Selecciona una opción..." or not invoices:
            messagebox.showwarning("Datos Faltantes", "Por favor, selecciona una plantilla e ingresa los números de factura.")
            return

        try:
            # 1. Obtener la semana seleccionada de la ventana principal
            week_num = self.parent.selected_week.get()
            if not week_num:
                messagebox.showwarning("Semana no seleccionada", "No se ha seleccionado una semana en la ventana principal.")
                return

            # 2. Obtener la ruta de la carpeta 'Cartas' usando el FolderManager
            output_folder = self.parent.folder_manager.get_cartas_folder_path(week_num)
            os.makedirs(output_folder, exist_ok=True) # Asegurarse de que la carpeta exista

            # 3. Crear el nombre del archivo y la ruta completa
            filename = f"{template}_{self.invoice_numbers.get().replace(',', '_').replace(' ', '')}.pdf"
            file_path = os.path.join(output_folder, filename)

            # 4. Generar y guardar el PDF
            generate_letter_pdf(template, self.invoice_numbers.get(), file_path)
            messagebox.showinfo("Éxito", f"El archivo PDF ha sido guardado exitosamente en:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el PDF. Error: {e}")
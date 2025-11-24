import tkinter as tk
from tkinter import filedialog
import pdfplumber
import ttkbootstrap as ttk
from tkinter.ttk import LabelFrame # Añadir esta línea
import re
from tabulate import tabulate
from utils import get_text_widget_colors # Importar la función de colores desde utils

class PDFExtractorWindow(ttk.Toplevel): # Cambiado a ttk.Toplevel
    def __init__(self, parent, current_theme_name="flatly"): # Añadido argumento de tema
        super().__init__(parent)
        self.parent = parent
        self.current_theme_name = current_theme_name # Guardar el nombre del tema
        
        # Configuración básica de la ventana
        self.title("Extractor de Datos OM")
        self.geometry("1200x800")  # Ventana más grande para mostrar más información
        
        # Hacer la ventana modal
        self.transient(parent)
        self.grab_set()
        
        # Crear widgets
        self.create_widgets()
        self._apply_text_widget_colors(self.current_theme_name) # Aplicar colores al iniciar

    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Botón para volver
        back_btn = ttk.Button(main_frame, text="← Volver", command=self.go_back, bootstyle="secondary")
        back_btn.pack(anchor=tk.W, pady=5)
        
        # Frame para selección de archivos
        file_frame = LabelFrame(main_frame, text="Selección de Archivos", padding="10", bootstyle="primary") # Cambiar ttk.LabelFrame a LabelFrame
        file_frame.pack(fill=tk.X, pady=5)
        
        select_btn = ttk.Button(file_frame, text="Seleccionar PDF(s)", command=self.select_files, bootstyle="primary")
        select_btn.pack(side=tk.LEFT, padx=5)
        
        # Frame para resultados
        results_frame = LabelFrame(main_frame, text="Resultados", padding="10", bootstyle="info") # Cambiar ttk.LabelFrame a LabelFrame
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.tree = ttk.Treeview(results_frame, columns=("docfile", "fecha_remision", "po_guia"), show="headings")
        self.tree.heading("docfile", text="DocFile")
        self.tree.heading("fecha_remision", text="Fecha de Remisión")
        self.tree.heading("po_guia", text="PO/Guía")

        self.tree.column("docfile", width=200)
        self.tree.column("fecha_remision", width=150)
        self.tree.column("po_guia", width=300)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Frame para log de extracción
        log_frame = LabelFrame(main_frame, text="Log de extracción", padding="10", bootstyle="secondary") # Cambiar ttk.LabelFrame a LabelFrame
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text( # Eliminados colores hardcodeados
            log_frame,
            height=10,
            relief="flat",
            font=("Consolas", 12)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def go_back(self):
        self.destroy()

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Seleccionar PDFs",
            filetypes=[("PDF files", "*.pdf")]
        )
        if files:
            self.process_pdfs(files)

    def process_pdfs(self, files):
        # Limpiar datos existentes
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.log_text.delete("1.0", tk.END)
        
        # Agregar encabezado al log
        header = "DocFile\tFecha de Remisión\tPO/Guía\n"
        self.log_text.insert(tk.END, header)
        
        extracted_data = []  # Para almacenar los datos extraídos
        
        for file in files:
            try:
                with pdfplumber.open(file) as pdf:
                    text = pdf.pages[0].extract_text()
                    
                    # Registrar el texto extraído para depuración
                    self.log_text.insert(tk.END, f"\nTexto extraído de {file}:\n{text}\n")
                    
                    data = self.extract_data_from_text(file, text)
                    
                    # Insertar en Treeview
                    self.tree.insert("", tk.END, values=(
                        data['docfile'],
                        data['fecha_remision'],
                        data['po_guia']
                    ))
                    
                    # Agregar al log con formato tabulado
                    log_entry = f"{data['docfile']}\t{data['fecha_remision']}\t{data['po_guia']}\n"
                    self.log_text.insert(tk.END, log_entry)
                    
                    # Agregar datos a la lista para la consola
                    extracted_data.append([
                        data['docfile'],
                        data['fecha_remision'],
                        data['po_guia']
                    ])
                    
            except Exception as e:
                error_msg = f"Error procesando {file}: {str(e)}\n"
                self.log_text.insert(tk.END, error_msg)
        
        # Mostrar datos en consola como tabla
        print(tabulate(extracted_data, headers=["DocFile", "Fecha de Remisión", "PO/Guía"], tablefmt="grid"))
        
        self.log_text.see(tk.END)

    def extract_data_from_text(self, file, text):
        """Extrae datos del texto del PDF"""
        patterns = {
            'fecha_remision': r'\d{2}/\d{2}/\d{4}',  # Fecha en formato DD/MM/YYYY
            'linea': r'(UPS|FEDEX|DHL|ESTAFETA)',    # Nombre de la paquetería
            'talon': r'[A-Z0-9]{10,18}'             # Número de guía (puede contener letras y números)
        }
        
        data = {
            'docfile': file.split("/")[-1],  # Nombre del archivo
            'fecha_remision': '',
            'po_guia': ''
        }
        
        # Extraer fecha de remisión
        fecha_match = re.search(patterns['fecha_remision'], text)
        if fecha_match:
            data['fecha_remision'] = fecha_match.group()
        
        # Extraer línea y talón
        text_upper = text.upper()
        linea_match = re.search(patterns['linea'], text_upper)
        if linea_match:
            linea = linea_match.group()
            talon_match = re.search(patterns['talon'], text_upper)
            if talon_match:
                talon = talon_match.group()
                data['po_guia'] = f"{linea} {talon}"
        
        return data

    def _apply_text_widget_colors(self, theme_name):
        colors = get_text_widget_colors(theme_name)
        self.log_text.config(**colors)
        return data
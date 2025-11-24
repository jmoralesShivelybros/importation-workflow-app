# importation_window.py

import tkinter as tk
from tkinter import filedialog
import threading #librería para hilos
import ttkbootstrap as ttk
from tkinter.ttk import LabelFrame
import pytesseract
from pdf2image import convert_from_path
import re
import sys
import os
import cv2
import numpy as np
from io import BytesIO # Para manejar imágenes en memoria
# --- IA DE GOOGLE ---
import google.generativeai as genai
import pandas as pd # Importamos pandas para exportar a Excel
from tkinter import messagebox # Para mostrar mensajes de advertencia/éxito
import json
# -------------------------------------------

def get_base_path():
    """ Obtiene la ruta base para encontrar los recursos, tanto en desarrollo como en el ejecutable."""
    if getattr(sys, 'frozen', False):
        # Si la aplicación está "congelada" (es un .exe), la ruta base es el directorio del ejecutable
        return os.path.dirname(sys.executable)
    else:
        # Si está en modo de desarrollo, la ruta base es el directorio del script actual
        return os.path.dirname(os.path.abspath(__file__))

class ImportationWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.base_path = get_base_path()
        vendor_path = os.path.join(self.base_path, 'vendor')

        tesseract_path = os.path.join(vendor_path, 'Tesseract-OCR', 'tesseract.exe')
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

        # --- CONFIGURACIÓN DE LA API DE GEMINI ---
        try:
            # Carga la API key desde la variable de entorno (forma segura)
            api_key = os.environ.get("GOOGLE_API_KEY")
            genai.configure(api_key=api_key)
        except Exception as e:
            print(f"Error al configurar la API de Google: {e}. Asegúrate de haber configurado la variable de entorno GOOGLE_API_KEY.")

        # --- Búsqueda automática de la carpeta Poppler ---
        self.poppler_path = None
        if os.path.exists(vendor_path):
            for item in os.listdir(vendor_path):
                if item.lower().startswith('poppler'):
                    # Construye la ruta a la carpeta 'bin' de Poppler
                    # Algunas versiones la tienen en 'Library/bin', otras directamente en 'bin'
                    potential_path1 = os.path.join(vendor_path, item, 'bin')
                    potential_path2 = os.path.join(vendor_path, item, 'Library', 'bin')
                    if os.path.exists(potential_path1):
                        self.poppler_path = potential_path1
                        break
                    elif os.path.exists(potential_path2):
                        self.poppler_path = potential_path2
                        break

        # --- Configuración básica de la ventana ---
        self.title("Ventana de Importación")
        self.geometry("1200x800")

        # --- Llamada para crear los elementos de la interfaz ---
        self.create_widgets()
        
        # --- Habilitar la edición de celdas con doble clic ---
        self.tree.bind("<Double-1>", self._on_double_click)

    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame para selección de archivos
        file_frame = LabelFrame(main_frame, text="Selección de Archivos", padding="10", bootstyle="primary")
        file_frame.pack(fill=tk.X, padx=10, pady=10)

        # --- Botones de acción en el frame superior ---
        select_btn = ttk.Button(file_frame, text="1. Seleccionar PDFs", command=self.select_files, bootstyle="primary")
        select_btn.pack(side=tk.LEFT, padx=5, pady=5)

        export_btn = ttk.Button(file_frame, text="2. Exportar a Excel", command=self.export_to_excel, bootstyle="success")
        export_btn.pack(side=tk.LEFT, padx=5, pady=5)

        remove_selected_btn = ttk.Button(file_frame, text="Eliminar Fila", command=self.remove_selected_row, bootstyle="warning")
        remove_selected_btn.pack(side=tk.LEFT, padx=20, pady=5)

        clear_all_btn = ttk.Button(file_frame, text="Limpiar Tabla", command=self.clear_all_rows, bootstyle="danger")
        clear_all_btn.pack(side=tk.LEFT, padx=5, pady=5)

        # Frame para resultados en una tabla
        results_frame = LabelFrame(main_frame, text="Resultados", padding="10", bootstyle="info")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Definición de las columnas para la tabla ---
        columns = [
            ("status", "STATUS", 50),
            ("docfile", "DocFile Nm", 150),
            ("fecha_reporte", "FECHA REPORTE", 110),
            ("om", "OM", 80),
            ("po_guia", "PO/GUIA", 150),
            ("cantidad", "CANTIDAD", 80),
            ("descripcion", "DESCRIPCION", 300),
            ("proveedor", "PROVEEDOR", 150),
            ("programa", "PROGRAMA", 100),
            ("costo", "COSTO", 80),
            ("factura", "FACTURA", 100),
            ("pk", "PK", 50)
        ]
        column_ids = [c[0] for c in columns]

        # --- Creación de la tabla (Treeview) y sus scrollbars ---
        tree_frame = ttk.Frame(results_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # --- Creación de un estilo personalizado para la tabla con bordes ---
        style = ttk.Style()
        style.configure("Custom.Treeview", highlightthickness=0, bd=0, font=('Segoe UI', 10))
        style.configure("Custom.Treeview.Heading", font=('Segoe UI', 10, 'bold'))
        style.layout("Custom.Treeview", [('Treeview.treearea', {'sticky': 'nswe'})]) # Elimina bordes extraños

        self.tree = ttk.Treeview(tree_frame, columns=column_ids, show="headings", style="Custom.Treeview")

        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        # --- Configuración de las cabeceras y el ancho de las columnas ---
        for col_id, col_text, col_width in columns:
            self.tree.heading(col_id, text=col_text)
            self.tree.column(col_id, width=col_width, anchor='w')

        # --- Posicionamiento de la tabla y los scrollbars en el frame ---
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # --- Estilo para filas alternadas (efecto cuadriculado) ---
        self.tree.tag_configure('oddrow', background='#f0f0f0') # Gris claro
        self.tree.tag_configure('evenrow', background='white')

        # Frame para log de extracción
        log_frame = LabelFrame(main_frame, text="Log de extracción", padding="10", bootstyle="secondary")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.log_text = tk.Text(log_frame, height=3, relief="flat", bg="#2b3e50", fg="#ffffff", insertbackground="#ffffff", font=("Consolas", 12))
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Seleccionar PDFs",
            filetypes=[("PDF files", "*.pdf")]
        )
        if files:
            # Iniciamos el procesamiento en un hilo separado para no congelar la GUI
            processing_thread = threading.Thread(target=self._process_pdfs_thread, args=(files,))
            processing_thread.start()

    def _log_message(self, message):
        """Función segura para actualizar el log desde cualquier hilo."""
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END) # Auto-scroll al final

    def _insert_tree_data(self, i, data):
        """Función segura para insertar datos en la tabla desde cualquier hilo."""
        tag = 'evenrow' if i % 2 == 0 else 'oddrow'
        self.tree.insert("", tk.END, values=(
            data["status"], data["docfile"], data["fecha_reporte"],
            data["om"], data["po_guia"], data["cantidad"],
            data["descripcion"], data["proveedor"], data["programa"],
            data["costo"], data["factura"], data["pk"]
        ), tags=(tag,))

    def _process_pdfs_thread(self, files):
        """Esta función se ejecuta en un hilo secundario para procesar los PDFs."""
        # Ya no limpiamos la tabla para mantener el historial.
        # Solo limpiamos el log para la nueva sesión de procesamiento.

        # Agregar encabezado al log
        self.after(0, self._log_message, "--- INICIO DEL PROCESAMIENTO ---\n")

        for i, file in enumerate(files):
            try:
                filename = os.path.basename(file)
                self.after(0, self._log_message, f"\n[ {i+1}/{len(files)} ] Escaneando: {filename}...\n")
                
                # Llamamos a nuestra nueva función de backend
                data, ocr_text = self._extract_data_from_pdf(file)
                
                if "error" in data:
                    self.after(0, self._log_message, f"  -> ERROR: {data['error']}\n")
                else:
                    # Usamos self.after para asegurarnos de que la actualización de la GUI
                    # se ejecute en el hilo principal de forma segura.
                    self.after(0, self._log_message, f"  -> Datos extraídos para OM: {data.get('om', 'N/A')}\n")
                    self.after(0, self._insert_tree_data, i, data)

            except Exception as e:
                error_msg = f"Error procesando {file}: {str(e)}\n"
                self.after(0, self._log_message, error_msg)
        
        self.after(0, self._log_message, "\n--- PROCESAMIENTO FINALIZADO ---\n")

    def _extract_data_from_pdf(self, pdf_path):
        """
        Extrae datos de la primera página de un PDF (que contiene una imagen) usando OCR.
        """
        text = ""
        try:
            if not self.poppler_path:
                # Si no se encontró Poppler, devuelve un error claro.
                return {"error": "No se encontró la carpeta de Poppler en el directorio 'vendor'."}, ""

            # 1. Convierte la primera página del PDF a una imagen con mayor resolución (DPI)
            images = convert_from_path(
                pdf_path,
                poppler_path=self.poppler_path,
                dpi=300  # Aumentamos la resolución para mejorar la calidad
            )
            if not images:
                return {"error": "No se pudo convertir el PDF a imagen."}, ""

            # --- INICIO: PRE-PROCESAMIENTO DE IMAGEN CON OPENCV ---
            # Mantenemos el pre-procesamiento con OpenCV y Tesseract para fines de LOGGING
            # y para tener un fallback o referencia del texto "crudo" del OCR.
            # Sin embargo, la extracción principal de datos la hará Gemini Vision directamente de la imagen original.
            
            first_pil_image = images[0] # Usamos la primera imagen para el OCR de logging

            # Convertir la imagen PIL a un formato que OpenCV pueda usar para el OCR de logging
            open_cv_image_for_ocr = np.array(first_pil_image) 
            open_cv_image_for_ocr = cv2.cvtColor(open_cv_image_for_ocr, cv2.COLOR_RGB2BGR) # Convertir a BGR

            # Aplicar pre-procesamiento para el OCR de logging (umbral adaptativo)
            gray_image_for_ocr = cv2.cvtColor(open_cv_image_for_ocr, cv2.COLOR_BGR2GRAY)
            thresh_image_for_ocr = cv2.adaptiveThreshold(gray_image_for_ocr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)

            # --- FIN: PRE-PROCESAMIENTO DE IMAGEN PARA OCR DE LOGGING ---

            # 2. Extrae el texto de la imagen pre-procesada usando OCR
            #    Este texto se usará SOLO para el log, no como entrada para Gemini Vision.
            #    Añadimos configuración a Tesseract para mejorar la precisión en formularios.
            #    --psm 3: Totalmente automático, bueno para diseños variados.
            #    --psm 11: Trata la imagen como un único bloque de texto disperso.
            custom_config = r'--oem 3 --psm 3 -l spa'
            text = pytesseract.image_to_string(thresh_image_for_ocr, config=custom_config)

            if not text:
                return {"error": "OCR no pudo extraer texto de la imagen del PDF."}, ""

        except Exception as e:
            return {"error": f"Error en OCR o conversión de PDF: {e}"}, ""

        # Diccionario para almacenar los datos extraídos
        data = {
            "status": "PTE",
            "docfile": os.path.splitext(os.path.basename(pdf_path))[0],
            "fecha_reporte": "",
            "om": "",
            "po_guia": "",
            "cantidad": "",
            "descripcion": "", "proveedor": "", "programa": "",
            "costo": "", "factura": "", "pk": "1 CAJA"
        }

        # --- INICIO: EXTRACCIÓN CON IA GENERATIVA (GEMINI) ---
        # Ahora usaremos Gemini Vision para analizar la imagen directamente
        try:
            model = genai.GenerativeModel('gemini-pro-latest') # Usamos el modelo estándar más compatible

            # --- Preparamos TODAS las imágenes para enviarlas a Gemini ---
            image_parts = []
            for img in images:
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format='JPEG')
                image_parts.append({
                    'mime_type': 'image/jpeg',
                    'data': img_byte_arr.getvalue()
                })
            
            # --- El prompt que has diseñado ---
            prompt = f"""
            Actúa como un experto en extracción de datos de logística.
            Analiza las imágenes de este reporte de entrada de almacén. La primera imagen es el reporte principal, las siguientes pueden ser facturas o documentos de soporte.
            Usa tu razonamiento para interpretar el contenido visual correctamente, incluso si el texto tiene errores.

            Extrae los siguientes campos y devuélvelos estrictamente en formato JSON. Si no encuentras un valor, déjalo como un string vacío ("").
            - "om": El número de la Orden de Material. Suele estar después de "REFERENCIA: OM-".
            - "fecha_reporte": La fecha del reporte. Suele estar después de "FECHA:".
            - "po_guia": El número de guía o PO. A menudo está cerca de "LINEA:" o "TALON:". Busca códigos largos alfanuméricos, como los de UPS (empiezan con 1Z) o FedEx.
            - "cantidad": La cantidad del producto. Búscala en la segunda página, generalmente dentro de la tabla de artículos bajo encabezados como "Qty", "Quantity" o "Cantidad". El valor puede ser numérico o incluir texto (ej: "50 pz", "1 paquete").
            - "descripcion": La descripción del artículo. Busca el campo "DESCRIPCION:" en la segunda página.
            - "proveedor": El nombre del proveedor. Búscalo en la segunda página, a menudo es el emisor de la factura.
            - "factura": El número de factura. En la segunda página, busca un texto como "Invoice:", "Invoice #", o "Factura:". Si el proveedor es "Shively", es muy probable que esté ahí.
            - "costo": El costo total. En la segunda página, busca el valor asociado a "Total", "Total Amount" o "Grand Total". Debe ser un valor numérico.
            """

            # --- Creamos el contenido para la API: el prompt y la lista de imágenes ---
            content = [prompt] + image_parts
            response = model.generate_content(content) # Pasamos el prompt y TODAS las imágenes
            
            # Limpiar la respuesta para obtener solo el JSON
            json_text = response.text.strip()
            if json_text.startswith("```json"):
                json_text = json_text[7:]
            if json_text.endswith("```"):
                json_text = json_text[:-3]
            
            extracted_ia_data = json.loads(json_text)

            # Actualizar nuestro diccionario 'data' con los valores de la IA
            data.update(extracted_ia_data)

            return data, text

        except Exception as e:
            return {"error": f"Error al procesar con IA (Gemini Vision): {e}"}, text
        # --- FIN: EXTRACCIÓN CON IA GENERATIVA ---

    def _clean_ocr_text(self, text):
        """Reemplaza caracteres que el OCR suele confundir con números."""
        replacements = {
            '|': '', '°': '', '—': '', '_': '',
            'L': '1', 'O': '0', 'S': '5', 'B': '8', 'G': '6', 'Z': '2', 'I': '1', 'A': '4',
            'l': '1', 'o': '0', 's': '5', 'b': '8', 'g': '6', 'z': '2', 'i': '1'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _on_double_click(self, event):
        """Manejador de eventos para editar una celda con doble clic."""
        # Identificar la celda en la que se hizo clic
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)

        # Obtener las coordenadas y el tamaño de la celda
        x, y, width, height = self.tree.bbox(item, column)

        # Crear un widget Entry temporal sobre la celda
        entry = ttk.Entry(self.tree, style="info.TEntry")
        entry.place(x=x, y=y, width=width, height=height)

        # Obtener el valor actual y ponerlo en el Entry
        current_value = self.tree.set(item, column)
        entry.insert(0, current_value)
        entry.focus_force()

        def save_edit(event):
            """Guarda el nuevo valor y destruye el Entry."""
            new_value = entry.get()
            self.tree.set(item, column, new_value)
            
            # Actualizar el log para registrar el cambio manual
            column_name = self.tree.heading(column, "text")
            om_value = self.tree.set(item, "om")
            log_msg = f"  -> EDICIÓN MANUAL: OM '{om_value}', campo '{column_name}' cambiado a '{new_value}'.\n"
            self._log_message(log_msg)

            entry.destroy()

        # Vincular eventos para guardar o cancelar la edición
        entry.bind("<Return>", save_edit) # Guardar con Enter
        entry.bind("<KP_Enter>", save_edit) # Guardar con Enter del teclado numérico
        entry.bind("<FocusOut>", lambda e: entry.destroy()) # Cancelar si se hace clic fuera
        entry.bind("<Escape>", lambda e: entry.destroy()) # Cancelar con la tecla Escape

    def export_to_excel(self):
        """Exporta los datos de la tabla a un archivo de Excel."""
        if not self.tree.get_children():
            messagebox.showwarning("Tabla Vacía", "No hay datos en la tabla para exportar.")
            return

        try:
            # Obtener los encabezados de la tabla
            columns = [self.tree.heading(col, "text") for col in self.tree["columns"]]
            
            # Obtener los datos de cada fila
            data = []
            for item in self.tree.get_children():
                data.append(self.tree.item(item, "values"))
            
            # Crear un DataFrame de pandas
            df = pd.DataFrame(data, columns=columns)

            # Pedir al usuario la ubicación para guardar el archivo
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Archivos de Excel", "*.xlsx"), ("Todos los archivos", "*.*")],
                title="Guardar como archivo de Excel",
                initialfile="Reporte_Importacion.xlsx"
            )

            if file_path:
                df.to_excel(file_path, index=False)
                messagebox.showinfo("Éxito", f"La tabla ha sido exportada exitosamente a:\n{file_path}")
                self._log_message(f"INFO: Tabla exportada a {file_path}\n")

        except Exception as e:
            messagebox.showerror("Error de Exportación", f"Ocurrió un error al exportar a Excel: {e}")
            self._log_message(f"ERROR: Falló la exportación a Excel: {e}\n")

    def remove_selected_row(self):
        """Elimina la fila (o filas) seleccionada de la tabla."""
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Sin Selección", "Por favor, selecciona al menos una fila para eliminar.")
            return

        if messagebox.askyesno("Confirmar Eliminación", f"¿Estás seguro de que deseas eliminar {len(selected_items)} fila(s) seleccionada(s)?"):
            for item in selected_items:
                om_value = self.tree.set(item, "om")
                self.tree.delete(item)
                self._log_message(f"INFO: Fila con OM '{om_value}' eliminada manualmente.\n")

    def clear_all_rows(self):
        """Elimina todas las filas de la tabla."""
        if not self.tree.get_children():
            messagebox.showinfo("Tabla Vacía", "La tabla ya está vacía.")
            return
        
        if messagebox.askyesno("Confirmar Limpieza", "¿Estás seguro de que deseas limpiar toda la tabla? Esta acción no se puede deshacer."):
            for item in self.tree.get_children():
                self.tree.delete(item)
            self._log_message("INFO: Toda la tabla ha sido limpiada.\n")

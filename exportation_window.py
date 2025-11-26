import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox, filedialog
from tkinter.ttk import LabelFrame # Añadir esta línea
import pdfplumber
from datetime import datetime
import os
import re
import sys
import pandas as pd
from tabulate import tabulate
import textwrap
from pypdf import PdfWriter
from packing_slip_generator import generate_packing_slip


DIRECCION_ORIGEN = (
    "SHIVELY BROS DE MEXICO\n"
    "FRESNOS 184 RES ARBOLEDAS\n"
    "SALTILLO COAHUILA\n"
    "CP 25200 MX"
)

def get_base_path():
    """ Obtiene la ruta base para encontrar los recursos, tanto en desarrollo como en el ejecutable."""
    if getattr(sys, 'frozen', False):
        # Si la aplicación está "congelada" (es un .exe), la base es el directorio temporal _MEIPASS
        return sys._MEIPASS
    else:
        # Si está en modo de desarrollo, la ruta base es el directorio del script actual
        return os.path.dirname(os.path.abspath(__file__))

class ExportationWindow(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Generar Exportación")
        self.geometry("1200x900")  # Pantalla más larga y ancha
        self.parent = parent

        # --- Llamada para crear los elementos de la interfaz ---
        self.create_widgets()
        self.parent._center_window(self) # Centrar la ventana después de crear los widgets

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text="Sube los archivos requeridos para la exportación:",
            bootstyle="secondary inverse",
            font=("Segoe UI", 14, "bold")
        ).pack(pady=(0, 20))

        self.files = [None, None, None]
        self.file_labels = []
        self.extracted_data_cache = [None, None, None] # Caché para los datos extraídos
        self.certificate_files = self.get_certificate_files()
        self.selected_cert = tk.StringVar()

        file_names = [
            "Carta de General Motors (PDF)",
            "Factura Comercial (PDF)",
            "Custom Order (PDF) (opcional)"
        ]

        files_frame = ttk.Frame(main_frame)
        files_frame.pack(fill=tk.X, pady=10)

        for idx, name in enumerate(file_names):
            frame = ttk.Frame(files_frame)
            frame.pack(fill="x", pady=10, padx=20)
            label = ttk.Label(frame, text=name + ": ", width=35, anchor="w")
            label.pack(side="left")
            self.file_labels.append(label)
            btn = ttk.Button(frame, text="Seleccionar archivo", command=lambda i=idx: self.select_file(i))
            btn.pack(side="left", padx=10)

        # --- Sección para Certificados de Origen ---
        ttk.Separator(files_frame, orient='horizontal').pack(fill='x', pady=15, padx=20)

        cert_label = ttk.Label(files_frame, text="Seleccionar Certificado de Origen (opcional):", font=("Segoe UI", 11, "bold"))
        cert_label.pack(padx=20, anchor='w')

        cert_frame = ttk.Frame(files_frame)
        cert_frame.pack(fill='x', pady=5, padx=20)
        ttk.Label(cert_frame, text="Certificado:", width=15).pack(side="left")
        cert_combo = ttk.Combobox(
            cert_frame,
            textvariable=self.selected_cert,
            values=[""] + self.certificate_files, # Añadir opción vacía
            state="readonly"
        )
        cert_combo.pack(side="left", fill="x", expand=True)

        # --- Frame para botones de acción ---
        action_buttons_frame = ttk.Frame(files_frame)
        action_buttons_frame.pack(fill=tk.X, pady=(20, 10), padx=20)

        # Botón para generar PDF final
        generate_pdf_btn = ttk.Button(
            action_buttons_frame,
            text="✓ Generar PDF Final",
            bootstyle="success",
            command=self.generate_final_pdf,
            padding=(20, 15)
        )
        generate_pdf_btn.pack(side="left", expand=True, fill=tk.X, padx=(0, 5))

        # Botón para exportar a Excel
        export_excel_btn = ttk.Button(
            action_buttons_frame,
            text="Exportar Tabla a Excel",
            bootstyle="info",
            command=self.export_to_excel,
            padding=(20, 15)
        )
        export_excel_btn.pack(side="left", expand=True, fill=tk.X, padx=(5, 0))
        # Información de la exportación (cambiar ttk.LabelFrame a LabelFrame)
        self.info_frame = LabelFrame(
            main_frame,
            text="Información de la exportación",
            padding="15",
            bootstyle="info"
        )
        self.info_frame.pack(fill=tk.BOTH, expand=True, pady=20)

        self.info_text = tk.Text(
            self.info_frame,
            height=30,
            relief="flat",
            bg='#eaf6fb',
            fg='#222222',
            font=("Consolas", 13),
            padx=10,
            pady=10,
            state="disabled",
            wrap="word"
        )
        self.info_text.pack(fill=tk.BOTH, expand=True)

        # Log de eventos
        log_frame = LabelFrame( # Cambiar ttk.LabelFrame a LabelFrame
            main_frame,
            text="Log de eventos",
            padding="15",
            bootstyle="secondary"
        )
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        log_scroll = ttk.Scrollbar(log_frame, bootstyle="round-secondary")
        self.log_text = tk.Text(
            log_frame,
            height=8,
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


    def select_file(self, idx):
        file_path = tk.filedialog.askopenfilename(
            filetypes=[("PDF files", "*.pdf")]
        )
        if file_path:
            self.files[idx] = file_path
            self.file_labels[idx].config(
                text=f"✔ {self.file_labels[idx].cget('text').split(':')[0]}: {os.path.basename(file_path)}",
                bootstyle="success"
            )
            self.log_message(f"Archivo seleccionado: {os.path.basename(file_path)}")
            self.log_message("Extrayendo datos del PDF...")
            self.extracted_data_cache[idx] = self.extract_and_process_info(file_path)
            self.log_message("Extracción completada.")
            self.update_export_info()

    def update_export_info(self):
        self.info_text.config(state="normal")
        self.info_text.delete(1.0, tk.END)
        # Configura el tag para negritas si no existe
        if not "bold" in self.info_text.tag_names():
            self.info_text.tag_configure("bold", font=("Consolas", 13, "bold"))
        
        for datos in self.extracted_data_cache:
            if datos:
                # Usamos los datos del caché para mostrar el resumen
                resumen = self.format_export_summary(datos)
                for texto, tag in resumen:
                    if tag:
                        self.info_text.insert(tk.END, texto, tag)
                    else:
                        self.info_text.insert(tk.END, texto)
                self.info_text.insert(tk.END, "\n\n")
        self.info_text.config(state="disabled")

    def get_certificate_files(self):
        """Obtiene la lista de archivos PDF de la carpeta de certificados."""
        try:
            # Usamos el FolderManager para obtener la ruta correcta y centralizada
            cert_folder = self.parent.folder_manager.get_certificados_folder_path()
            if not os.path.exists(cert_folder):
                self.log_message(f"ADVERTENCIA: La carpeta de certificados no se encontró en {cert_folder}")
                return []
            return sorted([f for f in os.listdir(cert_folder) if f.lower().endswith('.pdf') and not f.startswith('~$')])
        except Exception as e:
            self.log_message(f"ADVERTENCIA: Error al leer la carpeta de certificados: {e}")
            return []

    def extract_and_process_info(self, file_path):
        datos = {
            "shipper": "",
            "fecha": "",
            "direccion_origen": DIRECCION_ORIGEN,
            "direccion_destino": "",
            "articulos": []
        }
        try:
            with pdfplumber.open(file_path) as pdf:
                text = ""
                all_tables = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    tables = page.extract_tables()
                    if tables:
                        all_tables.extend(tables)
        except Exception as e:
            datos["error"] = f"Error al leer PDF: {e}"
            return datos

        # SHIPPER
        datos["shipper"] = self.find_first_match(os.path.basename(file_path), r"shipper[\s\-]*([0-9]+)", group=1)
        if not datos["shipper"]:
            datos["shipper"] = self.find_first_match(text, r"SHIPPER\s*:?[\s\-]*([0-9]+)", group=1)
        if not datos["shipper"]:
            datos["shipper"] = self.find_first_match(text, r"RA[\s\-:]*([0-9]+)", group=1)

        # FECHA
        datos["fecha"] = self.find_first_match(text, r"Fecha de Retorno:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", group=1)
        if not datos["fecha"]:
            datos["fecha"] = self.find_first_match(text, r"Date:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", group=1)
        if not datos["fecha"]:
            datos["fecha"] = self.find_first_match(text, r"Vigencia del eshipper:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", group=1)

        # DIRECCIÓN DESTINO
        datos["direccion_destino"] = self.extract_destination_address(text)

        # ARTÍCULOS
        datos["articulos"] = self.extract_items_from_table(all_tables)

        return datos

    def extract_destination_address(self, text):
        # Lista de posibles encabezados para la dirección de destino
        possible_headers = ["consigned to", "ship to", "deliver to", "sold to"]
        lines = text.splitlines()
        
        for i, line in enumerate(lines):
            for header in possible_headers:
                if header in line.lower():
                    self.log_message(f"Encabezado de dirección encontrado: '{header}'")
                    address_lines = []
                    # Tomar las siguientes 6 líneas como posible dirección
                    for l in lines[i+1:i+7]:
                        l_clean = l.strip()
                        # Detenerse si encontramos una línea vacía o una palabra clave que indique el fin de la dirección
                        if not l_clean or re.match(r"shipped by|order|marks|exportation|country|terms|weight|signature|date|incoterms", l_clean, re.IGNORECASE):
                            break
                        address_lines.append(l_clean)
                    return "\n".join(address_lines)
        return ""

    def extract_items_from_table(self, tables):
        """
        Extrae artículos de tablas con encabezados en varias filas (como Commercial Invoice).
        Devuelve una lista de diccionarios con cantidad, tipo, descripción, unitario y total.
        """
        items = []
        
        for table in tables:
            # Unifica encabezados si hay más de una fila de encabezado
            if len(table) > 2 and any("qty" in (cell or "").lower() for cell in table[0]) and any("kind" in (cell or "").lower() for cell in table[1]):
                headers = []
                for i in range(len(table[0])):
                    h1 = (table[0][i] or "").strip().lower()
                    h2 = (table[1][i] or "").strip().lower() if i < len(table[1]) else ""
                    header = h1
                    if h2 and h2 not in h1:
                        header = f"{h1} {h2}".strip()
                    headers.append(header)
                data_rows = table[2:]
            else:
                headers = [cell.lower().strip() if cell else "" for cell in table[0]]
                data_rows = table[1:]

            idx_qty = next((i for i, h in enumerate(headers) if "qty" in h or "cantidad" in h), None)
            idx_tipo = next((i for i, h in enumerate(headers) if "kind" in h or "unidad" in h), None)
            idx_desc = next((i for i, h in enumerate(headers) if "description" in h or "contents" in h or "descripción" in h), None)
            idx_unit = next((i for i, h in enumerate(headers) if "unit" in h), None)
            idx_total = next((i for i, h in enumerate(headers) if "total" in h), None)

            current_item = {}
            print("\n--- Iniciando procesamiento de tabla de artículos ---")
            
            # --- NUEVA LÓGICA PARA DESGLOSAR FILAS FUSIONADAS ---
            processed_rows = []
            for row in data_rows:
                # Revisa si alguna celda contiene saltos de línea, indicando filas fusionadas
                if any('\n' in (cell or '') for cell in row):
                    # Divide cada celda por el salto de línea
                    split_cells = [str(cell or '').split('\n') for cell in row]
                    # Determina cuántas filas se fusionaron (el máximo de líneas en cualquier celda)
                    num_new_rows = max(len(sc) for sc in split_cells)
                    
                    # Reconstruye las filas individuales
                    for i in range(num_new_rows):
                        new_row = []
                        for sc in split_cells:
                            # Si una celda tiene menos líneas, usa un string vacío
                            new_row.append(sc[i] if i < len(sc) else '')
                        processed_rows.append(new_row)
                else:
                    # Si no hay saltos de línea, la fila es normal
                    processed_rows.append(row)
            # --- FIN DE LA NUEVA LÓGICA ---

            for i, row in enumerate(processed_rows): # Ahora iteramos sobre las filas procesadas
                print(f"\n[Fila {i+1}] Procesando fila: {row}")

                # Ignorar filas completamente vacías
                if not any(cell and cell.strip() for cell in row):
                    print(f"[Fila {i+1}] -> Fila vacía, ignorando.")
                    continue

                # Extraer datos de la fila de forma segura
                def get_cell(idx):
                    return row[idx].strip() if idx is not None and idx < len(row) and row[idx] else ""

                cantidad = get_cell(idx_qty)
                tipo = get_cell(idx_tipo)
                descripcion = get_cell(idx_desc)
                unitario = get_cell(idx_unit)
                total = get_cell(idx_total)
                print(f"[Fila {i+1}] Datos extraídos: Cant='{cantidad}', Tipo='{tipo}', Desc='{descripcion[:40]}...', Unit='{unitario}', Total='{total}'")

                # REGLA PRINCIPAL: Un nuevo artículo empieza si:
                # 1. La descripción comienza con "PT" O
                # 2. Hay una nueva cantidad válida (no vacía) Y ya tenemos un artículo en proceso
                is_new_pt_article = descripcion.strip().upper().startswith('PT')
                has_valid_quantity = cantidad and cantidad.strip()
                
                print(f"[Fila {i+1}] Condiciones: is_new_pt_article={is_new_pt_article}, has_valid_quantity={has_valid_quantity}")

                # Si es un nuevo artículo PT, guardamos el anterior y empezamos uno nuevo
                if is_new_pt_article:
                    print(f"[Fila {i+1}] -> Lógica: Nuevo artículo 'PT' detectado.")
                    # Guardar el artículo anterior si existe
                    if current_item and any(current_item.values()):
                        print(f"[Fila {i+1}] -> Acción: Guardando artículo anterior: {current_item}")
                        items.append(current_item)
                    
                    # Iniciar nuevo artículo con todos los datos de esta fila
                    current_item = {
                        "cantidad": cantidad,
                        "tipo": tipo,
                        "descripcion": descripcion,
                        "unitario": unitario,
                        "total": total
                    }
                    print(f"[Fila {i+1}] -> Acción: Creando nuevo artículo: {current_item}")
                
                # Si hay una nueva cantidad válida y ya tenemos un artículo en proceso, es un nuevo artículo
                elif has_valid_quantity and current_item and any(current_item.values()):
                    print(f"[Fila {i+1}] -> Lógica: Nueva cantidad en artículo existente detectada.")
                    # Guardar el artículo anterior
                    print(f"[Fila {i+1}] -> Acción: Guardando artículo anterior: {current_item}")
                    items.append(current_item)
                    # Iniciar nuevo artículo
                    current_item = {
                        "cantidad": cantidad,
                        "tipo": tipo,
                        "descripcion": descripcion,
                        "unitario": unitario,
                        "total": total
                    }
                    print(f"[Fila {i+1}] -> Acción: Creando nuevo artículo: {current_item}")
                
                # Si no es un nuevo artículo pero tenemos un artículo en proceso, podría ser continuación de descripción
                elif current_item and descripcion and not has_valid_quantity:
                    print(f"[Fila {i+1}] -> Lógica: Continuación de descripción detectada.")
                    # Solo concatenar si no es un nuevo artículo PT y no hay nueva cantidad
                    current_item['descripcion'] = current_item.get('descripcion', '') + ' ' + descripcion
                    current_item['descripcion'] = current_item['descripcion'].strip()
                    print(f"[Fila {i+1}] -> Acción: Descripción actualizada: {current_item['descripcion']}")
                
                # Si no hay artículo en proceso pero tenemos datos, empezamos uno nuevo
                elif not current_item and (cantidad or descripcion):
                    print(f"[Fila {i+1}] -> Lógica: Primer artículo detectado en la tabla.")
                    current_item = {
                        "cantidad": cantidad,
                        "tipo": tipo,
                        "descripcion": descripcion,
                        "unitario": unitario,
                        "total": total
                    }
                    print(f"[Fila {i+1}] -> Acción: Creando primer artículo: {current_item}")
                else:
                    print(f"[Fila {i+1}] -> Lógica: Fila no cumple ninguna condición principal, se ignora para iniciar/continuar artículo.")

            # Después de procesar todas las filas, guardar el último artículo si existe
            if current_item and any(current_item.values()):
                print(f"\n--- Fin del bucle. Guardando último artículo pendiente: {current_item} ---")
                items.append(current_item)
        print("\n--- Procesamiento de tabla finalizado. Artículos encontrados: ---")
        print(tabulate(items, headers="keys", tablefmt="grid"))
        return items

    def format_export_summary(self, datos):
        """
        Devuelve una lista de tuplas (texto, tag) para insertar en el Text widget con formato.
        Los artículos se muestran como tabla alineada y legible.
        """
        if "error" in datos:
            return [("Error: " + datos["error"], None)]
        resumen = []
        if datos["shipper"]:
            resumen.append((f"********** SHIPPER: {datos['shipper']} **********\n\n", "bold"))
        if datos["fecha"]:
            resumen.append(("Fecha: ", "bold"))
            resumen.append((f"{datos['fecha']}\n", None))
        if datos["direccion_origen"]:
            resumen.append(("Dirección de origen:\n", "bold"))
            resumen.append((f"{datos['direccion_origen']}\n", None))
        if datos["direccion_destino"]:
            resumen.append(("Dirección de destino:\n", "bold"))
            resumen.append((f"{datos['direccion_destino']}\n", None))
        if datos.get("articulos"):
            resumen.append(("\nArtículos:\n", "bold"))
            
            # --- Lógica para tabla dinámica ---
            # Ancho del widget de texto en caracteres (aproximado)
            try:
                font_size_str = self.info_text.cget("font").split(" ")[-1]
                font_size = int(font_size_str)
                widget_width = self.info_text.winfo_width() // (font_size * 0.6) # 0.6 es un factor de ajuste para fuentes monoespaciadas
            except (ValueError, ZeroDivisionError):
                widget_width = 80 # Valor por defecto en caso de error
            widget_width = max(80, int(widget_width)) # Ancho mínimo

            # Anchos fijos para columnas no descriptivas
            qty_w, tipo_w, unit_w, total_w = 10, 10, 15, 15 # Estos anchos son en caracteres
            # El ancho de la descripción es el resto, menos el espacio para los bordes de la tabla
            desc_w = widget_width - (qty_w + tipo_w + unit_w + total_w + 15) # Aumentamos el margen para dar más espacio a la descripción
            desc_w = max(30, desc_w) # Ancho mínimo para descripción, aumentado de 20 a 30

            headers = ["Cantidad", "Tipo", "Descripción", "Unitario", "Total"]
            table_data = []
            for item in datos["articulos"]:
                # Limpia y ajusta el texto de la descripción al ancho calculado
                descripcion_limpia = ' '.join(item.get('descripcion', '').split())
                descripcion_ajustada = '\n'.join(textwrap.wrap(descripcion_limpia, width=desc_w))

                table_data.append([
                    item.get('cantidad', ''),
                    item.get('tipo', ''),
                    descripcion_ajustada,
                    item.get('unitario', ''),
                    item.get('total', '')
                ])
            
            # Generar tabla formateada usando tabulate
            tabla = tabulate(table_data, headers=headers, tablefmt="grid", numalign="right", stralign="left", colalign=("right", "left", "left", "right", "right"))
            resumen.append((f"{tabla}\n", None))

        if not resumen:
            resumen = [("No se pudo extraer información clave de este PDF", None)]
        return resumen

    def generate_final_pdf(self):
        self.log_message("Iniciando generación de PDF final...")
        print("Archivos seleccionados:", self.files)  # Verifica los archivos seleccionados

        # --- LÓGICA DE VALIDACIÓN CONDICIONAL ---
        # La "Carta de General Motors" (RMA) es opcional solo para Flint.
        is_flint_export = self.selected_cert.get() == "Shively flint T-MEC 2025.pdf"

        # 1. La Factura Comercial (self.files[1]) siempre es requerida.
        if not self.files[1]:
            messagebox.showerror("Error", "Falta la 'Factura Comercial'. Por favor, sube el archivo.")
            self.log_message("Error: Falta la Factura Comercial.")
            return

        # 2. La Carta de GM (self.files[0]) es requerida A MENOS que sea para Flint.
        if not is_flint_export and not self.files[0]:
            messagebox.showerror("Error", "Falta la 'Carta de General Motors'. Por favor, sube el archivo.")
            self.log_message("Error: Falta la Carta de General Motors para una exportación que no es de Flint.")
            return

        # 2. Crear la lista de PDFs a unir, empezando por los certificados seleccionados.
        pdfs_to_merge = []
        certificados_folder = self.parent.folder_manager.get_certificados_folder_path()
        
        cert_name = self.selected_cert.get()
        if cert_name:  # Si se seleccionó un certificado
            cert_path = os.path.join(certificados_folder, cert_name)
            pdfs_to_merge.append(str(cert_path))
            print("Certificado seleccionado:", cert_path)  # Verifica el certificado seleccionado
        
        # Añadir los archivos subidos por el usuario explícitamente
        if self.files[0]: # Añadir la carta de GM solo si se seleccionó
            pdfs_to_merge.append(self.files[0])
        pdfs_to_merge.append(self.files[1]) # La factura comercial siempre se añade
        if self.files[2]:  # Añadir el archivo opcional si fue seleccionado
            pdfs_to_merge.append(self.files[2])

        print("Archivos para unir:", pdfs_to_merge)  # Verifica la lista de archivos para unir

        # --- Generar Packing List y agregarlo a la lista ---
        try:
            # Obtener los items de la factura comercial (índice 1 en self.files)
            commercial_invoice_data = self.extracted_data_cache[1]
            if not commercial_invoice_data or not commercial_invoice_data.get("articulos"):
                raise ValueError("No se encontraron artículos en la factura comercial")
            
            # Convertir los artículos extraídos al formato necesario para el packing slip
            items = []
            for articulo in commercial_invoice_data["articulos"]:
                items.append({
                    "cantidad": articulo["cantidad"],
                    "descripcion": articulo["descripcion"],
                    "unitario": articulo.get("unitario", ""),
                    "total": articulo.get("total", "")
                })

            if not items:
                raise ValueError("No se pudieron procesar los artículos de la factura comercial")

            self.log_message(f"Se procesaron {len(items)} artículos de la factura comercial")

            # Definir las direcciones según el certificado
            addresses = {
                "SuperAbrasivos T-MEC 2025.pdf": {
                    "ship_to": "SuperAbrasives, Inc. (248) 348-7670\nSarah Foster\n28047 Grand Oaks Ct.\nWixom, MI 48393-3340"
                },
                "Certificado Saint Gobain.pdf": {
                    "ship_to": "SAINT-GOBAIN ABRASIVES INC.\n200 E FULLERTON\nCAROL STREAM IL 60188\nUSA"
                },
                "TOOLINK - USMCA-2025-CERTIFICATE OF ORIGIN.pdf": {
                    "ship_to": "TOOLINK ENGINEERING INC, Todd Rued (720) 442-6610\n4699 Nautilus Court South #206\nBoulder, CO. 80301\nUSA"
                },
                "Shively flint T-MEC 2025.pdf": {
                    "ship_to": "SHIVELY BROS INC.\n2919 S GRAND TRAVERSE\nFLINT, MI 48507\nUSA"
                }
            }

            # Obtener la dirección correcta según el certificado seleccionado
            cert_name = self.selected_cert.get()
            selected_address = addresses.get(cert_name, addresses["SuperAbrasivos T-MEC 2025.pdf"])

            # Construir los datos para el Packing List
            packing_data = {
                "shipper": "SHIVELYBROS MEXICO",
                "shipper_address": "CALLE FRESNOS #184 COLONIA LAS ARBOLEDAS\nSALTILLO, COAHUILA C.P. 25200\nTeléfono: (844) 450 6324\nWhasat: (844) 285 0679",
                "bill_to": "SHIVELYBROS MEXICO\nCALLE FRESNOS #184\nCOLONIA LAS ARBOLEDAS\nSALTILLO, COAHUILA C.P. 25200\n(844) 450 6324",
                "ship_to": selected_address["ship_to"],
                "invoice_date": datetime.now().strftime("%m/%d/%Y"),
                "ship_date": datetime.now().strftime("%m/%d/%Y"),
                "items": items
            }

            print("Datos para el Packing List:", packing_data)  # Verifica los datos enviados al Packing List

            # --- CORRECCIÓN: Usar la carpeta de la semana de exportación para el Packing List temporal ---
            current_year = self.parent.folder_manager.current_year
            week_num = self.parent.selected_week.get()
            output_folder = os.path.join(self.parent.folder_manager.exportacion_base_path, current_year, f"semana {week_num}")
            os.makedirs(output_folder, exist_ok=True)
            
            packing_list_path = os.path.join(output_folder, "packing_slip_temp.pdf")

            # Generar el Packing List
            generate_packing_slip(packing_data, packing_list_path)
            pdfs_to_merge.append(str(packing_list_path))
            self.log_message(f"Packing List generado y agregado: {os.path.basename(packing_list_path)}")
        except Exception as e:
            self.log_message(f"Error generando Packing List: {e}")
            messagebox.showerror("Error Packing List", f"Ocurrió un error al generar el Packing List: {e}")
            return

        # --- MODO DEPURACIÓN: Mostrar la lista final de archivos a unir ---
        self.log_message("\n--- Archivos a incluir en el PDF final: ---")
        for f in pdfs_to_merge:
            self.log_message(f"- {os.path.basename(f)}")
        print("Archivos finales para unir:", pdfs_to_merge)  # Verifica los archivos finales para unir
        self.log_message("------------------------------------------\n")

        # 5. Validar que todos los archivos en la lista existen antes de unir
        try:
            for file_path in pdfs_to_merge:
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"El archivo seleccionado no se encuentra en la ruta: {file_path}")
        except FileNotFoundError as e:
            self.log_message(f"Error de validación: {e}")
            messagebox.showerror("Archivo no encontrado", str(e))
            return

        # 6. Unir los PDFs
        merger = PdfWriter()
        try:
            for pdf_path in pdfs_to_merge:
                self.log_message(f"Añadiendo al merge: {os.path.basename(pdf_path)}")
                merger.append(pdf_path)

            # 7. Guardar el archivo final en una carpeta de historial dentro del proyecto
            # --- USAREMOS EL FOLDER MANAGER PARA OBTENER LA RUTA CORRECTA ---
            # La ruta será: ...\Logistica\exportacion\[año_actual]
            current_year = self.parent.folder_manager.current_year
            week_num = self.parent.selected_week.get()
            output_folder = os.path.join(self.parent.folder_manager.exportacion_base_path, current_year, f"semana {week_num}")
            os.makedirs(output_folder, exist_ok=True)
            
            # --- Crear un nombre de archivo personalizado (LÓGICA MEJORADA) ---
            # Busca el shipper en todos los archivos cargados, dando prioridad a la Carta de GM y luego a la Factura.
            shipper_number = "SIN_SHIPPER"
            if self.extracted_data_cache[0] and self.extracted_data_cache[0].get("shipper"):
                shipper_number = self.extracted_data_cache[0]["shipper"]
            elif self.extracted_data_cache[1] and self.extracted_data_cache[1].get("shipper"):
                shipper_number = self.extracted_data_cache[1]["shipper"]
            elif self.extracted_data_cache[2] and self.extracted_data_cache[2].get("shipper"):
                shipper_number = self.extracted_data_cache[2]["shipper"]
            
            # Formatear la fecha actual
            date_str = datetime.now().strftime("%m-%d-%Y")
            
            output_filename = f"{shipper_number}_{date_str}.pdf"
            output_path = os.path.join(output_folder, output_filename)

            merger.write(str(output_path))
            merger.close()
            self.log_message(f"PDF final generado exitosamente en: {output_path}")
            print("PDF final generado:", output_path)  # Verifica la ruta del PDF final generado
            messagebox.showinfo("Éxito", f"El archivo '{output_filename}' ha sido guardado en:\n{output_folder}")
        except Exception as e:
            self.log_message(f"Error al unir los PDFs: {e}")
            messagebox.showerror("Error de Fusión", f"Ocurrió un error al generar el PDF final: {e}")

    def export_to_excel(self):
        self.log_message("Iniciando exportación de datos de rastreo a Excel...")

        # Validar que la factura comercial esté cargada, ya que contiene los artículos
        if not self.files[1] or not self.extracted_data_cache[1]:
            messagebox.showerror("Error", "Falta la 'Factura Comercial'. Por favor, sube el archivo para poder generar el reporte de rastreo.")
            self.log_message("Error: No se encontró la Factura Comercial para la exportación.")
            return

        datos = self.extracted_data_cache[1] # Usamos los datos de la factura comercial

        # Determinar datos basados en el certificado
        cert_name = self.selected_cert.get().lower()
        destino = ""
        fraccion = ""
        if "saint gobain" in cert_name:
            destino = "SAINT-GOBAIN"
            fraccion = "68042291"
        elif "superabrasivos" in cert_name:
            destino = "SUPER ABRASIVES"
            fraccion = "68042291"
        elif "toolink" in cert_name:
            destino = "TOOLINK"
            fraccion = "PENDIENTE"

        # Construir datos para la tabla de rastreo
        rastreo_headers = [
            "Fecha", "Documento", "Cantidad", "UM",
            "Descripcion", "Destino", "Direccion", "Programa", "Fraccion",
            "Clave SAT", "Certificado"
        ]
        rastreo_data = []
        for item in datos.get("articulos", []):
            rastreo_data.append({
                "Fecha": datos.get("fecha", ""),
                "Documento": datos.get("shipper", ""),
                "Cantidad": item.get("cantidad", 0),
                "UM": item.get("tipo", "PIEZA"),
                "Descripcion": item.get("descripcion", ""),
                "Destino": destino,
                "Direccion": datos.get("direccion_destino", "").replace('\n', ' '), # Dirección en una sola línea
                "Programa": "",
                "Fraccion": fraccion,
                "Clave SAT": "31191500",
                "Certificado": destino
            })

        if not rastreo_data:
            messagebox.showwarning("Sin datos", "No se encontraron artículos en la factura comercial para exportar.")
            self.log_message("Advertencia: No se encontraron artículos para exportar.")
            return

        # Crear un DataFrame de pandas
        df = pd.DataFrame(rastreo_data, columns=rastreo_headers)

        # Pedir al usuario la ubicación para guardar el archivo
        try:
            shipper_number = datos.get("shipper", "RASTREO")
            date_str = datetime.now().strftime("%Y%m%d")
            default_filename = f"{shipper_number}_{date_str}.xlsx"

            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
                initialfile=default_filename,
                title="Guardar reporte de rastreo"
            )

            if file_path:
                df.to_excel(file_path, index=False)
                self.log_message(f"Reporte de rastreo exportado exitosamente a: {file_path}")
                messagebox.showinfo("Éxito", f"El archivo ha sido guardado correctamente en:\n{file_path}")
        except Exception as e:
            self.log_message(f"Error al exportar a Excel: {e}")
            messagebox.showerror("Error de Exportación", f"Ocurrió un error al guardar el archivo de Excel: {e}")

    def log_message(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.update()

    def add_back_button(self):
        back_btn = ttk.Button(self, text="Regresar", bootstyle="danger", command=self.on_back)
        back_btn.pack(anchor="ne", padx=10, pady=10)

    def on_back(self):
        self.destroy()

    def find_first_match(self, text, pattern, group=1):
        import re
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(group).strip()
        return ""

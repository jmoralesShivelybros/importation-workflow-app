import streamlit as st
import pdfplumber
from datetime import datetime
import os
import re
import sys
import pandas as pd
from io import BytesIO
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

@st.cache_data
def get_certificate_files(_folder_manager):
        """Obtiene la lista de archivos PDF de la carpeta de certificados."""
        try:
            # Usamos el FolderManager para obtener la ruta correcta y centralizada
            cert_folder = _folder_manager.get_certificados_folder_path()
            if not os.path.exists(cert_folder):
                st.warning(f"La carpeta de certificados no se encontró en {cert_folder}")
                return []
            return sorted([f for f in os.listdir(cert_folder) if f.lower().endswith('.pdf') and not f.startswith('~$')])
        except Exception as e:
            st.error(f"Error al leer la carpeta de certificados: {e}")
            return []

@st.cache_data(show_spinner="Extrayendo información del PDF...")
def extract_and_process_info(file_content, file_name):
        datos = {
            "shipper": "",
            "fecha": "",
            "direccion_origen": DIRECCION_ORIGEN,
            "direccion_destino": "",
            "articulos": []
        }
        try:
            with pdfplumber.open(BytesIO(file_content)) as pdf:
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
        datos["shipper"] = find_first_match(file_name, r"shipper[\s\-]*([0-9]+)", group=1)
        if not datos["shipper"]:
            datos["shipper"] = find_first_match(text, r"SHIPPER\s*:?[\s\-]*([0-9]+)", group=1)
        if not datos["shipper"]:
            datos["shipper"] = find_first_match(text, r"RA[\s\-:]*([0-9]+)", group=1)

        # FECHA
        datos["fecha"] = find_first_match(text, r"Fecha de Retorno:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", group=1)
        if not datos["fecha"]:
            datos["fecha"] = find_first_match(text, r"Date:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", group=1)
        if not datos["fecha"]:
            datos["fecha"] = find_first_match(text, r"Vigencia del eshipper:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", group=1)

        # DIRECCIÓN DESTINO
        datos["direccion_destino"] = extract_destination_address(text)

        # ARTÍCULOS
        datos["articulos"] = extract_items_from_table(all_tables)

        return datos

def extract_destination_address(text):
        # Lista de posibles encabezados para la dirección de destino
        possible_headers = ["consigned to", "ship to", "deliver to", "sold to"]
        lines = text.splitlines()
        
        for i, line in enumerate(lines):
            for header in possible_headers:
                if header in line.lower():
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

def extract_items_from_table(tables):
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

def format_export_summary(datos, widget_width=80):
        """
        Devuelve una lista de tuplas (texto, tag) para insertar en el Text widget con formato.
        Los artículos se muestran como tabla alineada y legible.
        """
        if "error" in datos:
            return f"Error: {datos['error']}"
        resumen = []
        if datos["shipper"]:
            resumen.append(f"************ SHIPPER: {datos['shipper']} **********\\n**")
        if datos["fecha"]:
            resumen.append(f"**Fecha:** {datos['fecha']}")
        if datos["direccion_origen"]:
            resumen.append(f"**Dirección de origen:**\n{datos['direccion_origen']}")
        if datos["direccion_destino"]:
            resumen.append(f"**Dirección de destino:**\n{datos['direccion_destino']}")
        if datos.get("articulos"):
            resumen.append("\n**Artículos:**")
            
            # --- Lógica para tabla dinámica ---
            # Ancho del widget de texto en caracteres (aproximado)

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
            resumen.append(f"```\n{tabla}\n```")

        if not resumen:
            return "No se pudo extraer información clave de este PDF."
        return "\n".join(resumen)

def find_first_match(text, pattern, group=1):
    import re
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(group).strip()
    return ""

def render_exportation_page(folder_manager, week_num):
    st.header("Generar Exportación")
    
    log_placeholder = st.expander("Log de eventos", expanded=False)

    st.subheader("Sube los archivos requeridos para la exportación:")

    # --- Carga de archivos ---
    file_gm = st.file_uploader("Carta de General Motors (PDF)", type="pdf")
    file_factura = st.file_uploader("Factura Comercial (PDF)", type="pdf")
    file_custom = st.file_uploader("Custom Order (PDF) (opcional)", type="pdf")

    # --- Procesamiento y cacheo de datos ---
    data_gm = extract_and_process_info(file_gm.getvalue(), file_gm.name) if file_gm else None
    data_factura = extract_and_process_info(file_factura.getvalue(), file_factura.name) if file_factura else None
    data_custom = extract_and_process_info(file_custom.getvalue(), file_custom.name) if file_custom else None

    # --- Mostrar información extraída ---
    st.subheader("Información de la exportación")
    with st.container(border=True):
        if data_gm:
            st.markdown(format_export_summary(data_gm))
            st.divider()
        if data_factura:
            st.markdown(format_export_summary(data_factura))
            st.divider()
        if data_custom:
            st.markdown(format_export_summary(data_custom))

    # --- Sección para Certificados de Origen ---
    st.subheader("Seleccionar Certificado de Origen")
    certificate_files = get_certificate_files(folder_manager)
    selected_cert = st.selectbox(
        "Certificado:",
        options=[""] + certificate_files,
        index=0,
        help="Selecciona el certificado de origen a incluir en el PDF final."
    )

    # --- Botones de acción ---
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        if st.button("✓ Generar PDF Final", type="primary", use_container_width=True):
            generate_final_pdf(
                folder_manager, week_num,
                [file_gm, file_factura, file_custom],
                [data_gm, data_factura, data_custom],
                selected_cert,
                log_placeholder
            )
    
    with col2:
        if st.button("Exportar Tabla a Excel", use_container_width=True):
            export_to_excel(
                data_factura,
                selected_cert,
                log_placeholder
            )

def generate_final_pdf(folder_manager, week_num, files, extracted_data, selected_cert, log_placeholder):
    # 1. Escribir los mensajes de log DENTRO del expander
    with log_placeholder:
        st.write("Iniciando generación de PDF final...")

        # --- Lógica de validación ---
        # La "Carta de General Motors" (RMA) es opcional solo para Flint.
        is_flint_export = selected_cert == "Shively flint T-MEC 2025.pdf"

        # 1. La Factura Comercial (self.files[1]) siempre es requerida.
        if not files[1]:
            st.error("Falta la 'Factura Comercial'. Por favor, sube el archivo.")
            st.write("Error: Falta la Factura Comercial.")
            return

        # 2. La Carta de GM (self.files[0]) es requerida A MENOS que sea para Flint.
        if not is_flint_export and not files[0]:
            st.error("Falta la 'Carta de General Motors'. Por favor, sube el archivo.")
            st.write("Error: Falta la Carta de General Motors para una exportación que no es de Flint.")
            return

        # Crear la lista de PDFs a unir
        pdfs_to_merge = []
        certificados_folder = folder_manager.get_certificados_folder_path()

        cert_name = selected_cert
        if cert_name:  # Si se seleccionó un certificado
            cert_path = os.path.join(certificados_folder, cert_name)
            pdfs_to_merge.append(str(cert_path))
            print("Certificado seleccionado:", cert_path)  # Verifica el certificado seleccionado
        
        # Añadir los archivos subidos por el usuario explícitamente
        if files[0]: # Añadir la carta de GM solo si se seleccionó
            pdfs_to_merge.append(files[0])
        pdfs_to_merge.append(files[1]) # La factura comercial siempre se añade
        if files[2]:  # Añadir el archivo opcional si fue seleccionado
            pdfs_to_merge.append(files[2])

        # --- Generar Packing List y agregarlo a la lista ---
        try:
            # Obtener los items de la factura comercial (índice 1 en self.files)
            commercial_invoice_data = extracted_data[1]
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

            st.write(f"Se procesaron {len(items)} artículos de la factura comercial")

            # Definir las direcciones según el certificado
            addresses = {
                "SuperAbrasivos T-MEC 2025.pdf": {
                    "ship_to": "SuperAbrasives, Inc. (248) 348-7670\nSarah Foster\n28047 Grand Oaks Ct.\nWixom, MI 48393-3340"
                },
                "Certificado Saint Gobain.pdf": {
                    "ship_to": "SAINT-GOBAIN ABRASIVES, INC\nONE NEW BOND STREET \nWORCESTER, MA 01615-0008\nUSA"
                },
                "TOOLINK - USMCA-2025-CERTIFICATE OF ORIGIN.pdf": {
                    "ship_to": "TOOLINK ENGINEERING INC, Todd Rued (720) 442-6610\n4699 Nautilus Court South #206\nBoulder, CO. 80301\nUSA"
                },
                "Shively flint T-MEC 2025.pdf": {
                    "ship_to": "SHIVELY BROS INC.\n2919 S GRAND TRAVERSE\nFLINT, MI 48507\nUSA"
                }
            }

            # Obtener la dirección correcta según el certificado seleccionado
            cert_name = selected_cert
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

            # --- CORRECCIÓN: Usar la carpeta de la semana de exportación para el Packing List temporal ---
            current_year = folder_manager.current_year
            output_folder = os.path.join(folder_manager.exportacion_base_path, current_year, f"semana {week_num}")
            os.makedirs(output_folder, exist_ok=True)
            
            packing_list_path = os.path.join(output_folder, "packing_slip_temp.pdf")

            # Generar el Packing List
            generate_packing_slip(packing_data, packing_list_path)
            pdfs_to_merge.append(str(packing_list_path))
            st.write(f"Packing List generado y agregado: {os.path.basename(packing_list_path)}")
        except Exception as e:
            st.write(f"Error generando Packing List: {e}")
            st.error(f"Ocurrió un error al generar el Packing List: {e}")
            return

        # Mostrar la lista de archivos a unir en el log
        st.write("\n--- Archivos a incluir en el PDF final: ---")
        for item in pdfs_to_merge:
            if hasattr(item, 'name'): # Es un objeto UploadedFile
                st.write(f"- {item.name}")
            else: # Es una ruta de texto (string)
                st.write(f"- {os.path.basename(item)}")
        st.write("------------------------------------------\n")

        try:
            for file_path in pdfs_to_merge:
                # Solo validamos la existencia si es una ruta de texto (string)
                # Los objetos UploadedFile ya existen en memoria.
                if isinstance(file_path, str) and not os.path.exists(file_path):
                    raise FileNotFoundError(f"El archivo seleccionado no se encuentra en la ruta: {file_path}")
        except FileNotFoundError as e:
            st.write(f"Error de validación: {e}")
            st.error(str(e))
            return

    # 2. Unir y guardar el PDF FUERA del expander de logs
    merger = PdfWriter()
    try:
        for pdf_path in pdfs_to_merge:
            merger.append(pdf_path)

        # Guardar el archivo final
        current_year = folder_manager.current_year
        output_folder = os.path.join(folder_manager.exportacion_base_path, current_year, f"semana {week_num}")
        os.makedirs(output_folder, exist_ok=True)
        
        # Crear un nombre de archivo personalizado
        shipper_number = "SIN_SHIPPER"
        if extracted_data[0] and extracted_data[0].get("shipper"):
            shipper_number = extracted_data[0]["shipper"]
        elif extracted_data[1] and extracted_data[1].get("shipper"):
            shipper_number = extracted_data[1]["shipper"]
        elif extracted_data[2] and extracted_data[2].get("shipper"):
            shipper_number = extracted_data[2]["shipper"]
        
        date_str = datetime.now().strftime("%m-%d-%Y")
        output_filename = f"{shipper_number}_{date_str}.pdf"
        output_path = os.path.join(output_folder, output_filename)

        merger.write(str(output_path))
        merger.close()

    except Exception as e:
        with log_placeholder:
            st.write(f"Error al unir los PDFs: {e}")
        st.error(f"Ocurrió un error al generar el PDF final: {e}")
        return # Detener la ejecución si hay un error

    # 3. Mostrar los resultados al usuario FUERA del expander
    st.toast(f'¡PDF "{output_filename}" generado!', icon='📄')

    # Leemos el archivo que acabamos de crear en memoria para el botón de descarga
    with open(output_path, "rb") as pdf_file:
        pdf_bytes = pdf_file.read()

    # Mostramos el botón de descarga
    st.download_button(
        label=f"📄 Descargar {output_filename}",
        data=pdf_bytes,
        file_name=output_filename,
        mime="application/pdf"
    )
    st.info(f"El archivo también fue guardado en la ruta:\n`{output_path}`")


def export_to_excel(data_factura, selected_cert, log_placeholder):
    # 1. Validar y preparar los datos. Los mensajes de log se quedan en el expander.
    with log_placeholder:
        st.write("Iniciando exportación de datos de rastreo a Excel...")

        if not data_factura:
            st.warning("Falta la 'Factura Comercial'. Por favor, sube el archivo para poder generar el reporte de rastreo.")
            st.write("Error: No se encontró la Factura Comercial para la exportación.")
            return

        datos = data_factura # Usamos los datos de la factura comercial

        # Determinar datos basados en el certificado
        cert_name = selected_cert.lower()
        destino = ""
        fraccion = ""
        direccion_especifica = ""

        if "saint gobain" in cert_name:
            destino = "SAINT-GOBAIN"
            fraccion = "68042291"
            direccion_especifica = "SAINT-GOBAIN ABRASIVES, INC ONE NEW BOND STREET WORCESTER, MA 01615-0008 USA"
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
            # Usar la dirección específica si se definió, de lo contrario usar la extraída del PDF
            direccion_final = direccion_especifica if direccion_especifica else datos.get("direccion_destino", "").replace('\n', ' ')

            rastreo_data.append({
                "Fecha": datos.get("fecha", ""),
                "Documento": datos.get("shipper", ""),
                "Cantidad": item.get("cantidad", 0),
                "UM": item.get("tipo", "PIEZA"),
                "Descripcion": item.get("descripcion", ""),
                "Destino": destino,
                "Direccion": direccion_final,
                "Programa": "",
                "Fraccion": fraccion,
                "Clave SAT": "31191500",
                "Certificado": destino
            })

        if not rastreo_data:
            st.warning("No se encontraron artículos en la factura comercial para exportar.")
            st.write("Advertencia: No se encontraron artículos para exportar.")
            return
    
    # 2. Crear el archivo Excel en memoria FUERA del expander de logs.
    try:
        df = pd.DataFrame(rastreo_data, columns=rastreo_headers)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Rastreo')
        excel_bytes = output.getvalue()
    except Exception as e:
        st.error(f"Error al crear el archivo Excel: {e}")
        return

    # 3. Mostrar la notificación y el botón de descarga al usuario.
    file_name = f"{datos.get('shipper', 'RASTREO')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    st.toast(f'¡Excel "{file_name}" listo para descargar!', icon='📊')

    st.download_button(
        label=f"📊 Descargar {file_name}",
        data=excel_bytes,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

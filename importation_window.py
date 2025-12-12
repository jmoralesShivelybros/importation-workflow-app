# importation_window.py

import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
import re
import sys
import os
import cv2 # Importa la librería OpenCV
import numpy as np
from io import BytesIO # Para manejar imágenes en memoria
# --- IA DE GOOGLE ---
import google.generativeai as genai
import pandas as pd # Importamos pandas para exportar a Excel
import json
# -------------------------------------------

# --- CONFIGURACIÓN DE TESSERACT ---
# Le decimos a pytesseract dónde encontrar el ejecutable de Tesseract OCR
# que está en nuestra carpeta 'vendor'.
def _configure_tesseract():
    # Esta configuración solo es necesaria para el desarrollo local en Windows.
    # En Streamlit Community Cloud, Tesseract se instala a través de packages.txt y está en el PATH.
    if sys.platform == "win32":
        base_path = get_base_path()
        tesseract_path = os.path.join(base_path, 'vendor', 'Tesseract-OCR', 'tesseract.exe')
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

def get_base_path():
    """ Obtiene la ruta base para encontrar los recursos, tanto en desarrollo como en el ejecutable."""
    if getattr(sys, 'frozen', False):
        # Si la aplicación está "congelada" (es un .exe), la ruta base es el directorio del ejecutable
        return os.path.dirname(sys.executable)
    else:
        # Si está en modo de desarrollo, la ruta base es el directorio del script actual
        return os.path.dirname(os.path.abspath(__file__))

# Ejecutamos la configuración al cargar el módulo
_configure_tesseract()

@st.cache_data(show_spinner="Extrayendo datos del PDF...")
def extract_data_from_pdf_logic(pdf_file):
        """
        Extrae datos de la primera página de un PDF (que contiene una imagen) usando OCR.
        """
        text = ""
        try:
            poppler_path = _get_poppler_path()
            # En la nube de Streamlit, poppler_path será None, lo cual está bien
            # porque poppler-utils lo pone en el PATH del sistema.
            if sys.platform == "win32" and not poppler_path:
                # Si no se encontró Poppler, devuelve un error claro. (Adaptado para Streamlit)
                return {"error": "No se encontró la carpeta de Poppler en el directorio 'vendor'."}, ""

            # 1. Convierte la primera página del PDF a una imagen con mayor resolución (DPI)
            images = convert_from_bytes(
                pdf_file.getvalue(),
                # Solo pasamos la ruta si estamos en Windows y la encontramos.
                poppler_path=poppler_path if sys.platform == "win32" else None,
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
            "docfile": os.path.splitext(pdf_file.name)[0],
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
            # --- CONFIGURACIÓN DE LA API DE GEMINI (Segura para Deploy) ---
            # Intenta obtener la API key de los "Secrets" de Streamlit.
            # Si no está en los secrets, la busca en las variables de entorno locales.
            try:
                google_api_key = st.secrets["GOOGLE_API_KEY"]
            except (FileNotFoundError, KeyError):
                google_api_key = os.environ.get("GOOGLE_API_KEY")

            if not google_api_key:
                 return {"error": "No se encontró la GOOGLE_API_KEY. Configúrala en los Secrets de Streamlit o como variable de entorno local."}, ""

            genai.configure(api_key=google_api_key)
            model = genai.GenerativeModel('gemini-flash-latest') # Cambiado a un modelo más rápido y con cuota separada.

            # --- Preparamos TODAS las imágenes para enviarlas a Gemini ---
            # Corregimos el envío de imágenes: cada imagen debe ser codificada a JPEG en memoria.
            image_parts = []
            for img in images:
                buffered = BytesIO()
                img.save(buffered, format="JPEG")
                image_parts.append({
                    "mime_type": "image/jpeg",
                    "data": buffered.getvalue()
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

def _get_poppler_path():
    """Función auxiliar para encontrar la ruta de Poppler."""
    base_path = get_base_path()
    # Solo buscamos en la carpeta 'vendor' si estamos en Windows.
    if sys.platform == "win32":
        vendor_path = os.path.join(base_path, 'vendor')
        if os.path.exists(vendor_path):
            for item in os.listdir(vendor_path):
                if item.lower().startswith('poppler'):
                    potential_path1 = os.path.join(vendor_path, item, 'bin')
                    potential_path2 = os.path.join(vendor_path, item, 'Library', 'bin')
                    if os.path.exists(potential_path1):
                        return potential_path1
                    elif os.path.exists(potential_path2):
                        return potential_path2
    return None

def render_importation_page(folder_manager, week_num):
    st.header("Generar Importación")

    # Inicializar el estado de la sesión para los datos de la tabla
    if 'importation_data' not in st.session_state:
        st.session_state.importation_data = []

    # --- Carga de archivos ---
    uploaded_files = st.file_uploader(
        "1. Seleccionar PDFs de Reporte de Entrada",
        type="pdf",
        accept_multiple_files=True
    )

    if uploaded_files:
        # Procesar archivos solo si no han sido procesados antes
        # Creamos un ID único para cada archivo para evitar reprocesamiento
        new_files_to_process = []
        if 'processed_files' not in st.session_state:
            st.session_state.processed_files = set()

        for f in uploaded_files:
            file_id = f.name + str(f.size)
            if file_id not in st.session_state.processed_files:
                new_files_to_process.append(f)
                st.session_state.processed_files.add(file_id)

        if new_files_to_process:
            log_placeholder = st.empty()
            log_messages = ["--- INICIO DEL PROCESAMIENTO ---"]
            log_placeholder.code('\n'.join(log_messages))

            for i, file in enumerate(new_files_to_process):
                log_messages.append(f"\n[ {i+1}/{len(new_files_to_process)} ] Escaneando: {file.name}...")
                log_placeholder.code('\n'.join(log_messages))
                
                # La lógica de extracción ahora es una función independiente
                data, ocr_text = extract_data_from_pdf_logic(file)
                
                if "error" in data:
                    log_messages.append(f"  -> ERROR: {data['error']}")
                else:
                    log_messages.append(f"  -> Datos extraídos para OM: {data.get('om', 'N/A')}")
                    st.session_state.importation_data.append(data)
                
                log_placeholder.code('\n'.join(log_messages))
            
            log_messages.append("\n--- PROCESAMIENTO FINALIZADO ---")
            log_placeholder.code('\n'.join(log_messages))

    st.subheader("Resultados")

    # --- Botones de acción ---
    col1, col2, col3 = st.columns([2,2,1])
    with col1:
        if st.session_state.importation_data:
            df = pd.DataFrame(st.session_state.importation_data)
            
            # --- Convertir DataFrame a Excel en memoria ---
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Importacion')
            excel_bytes = output.getvalue()

            st.download_button(
                label="📊 Exportar a Excel",
                data=excel_bytes,
                file_name=f"Reporte_Importacion_Semana_{week_num}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    with col3:
        if st.button("Limpiar Tabla", type="primary"):
            st.session_state.importation_data = []
            st.session_state.processed_files = set()
            st.rerun()

    # --- Mostrar la tabla de datos ---
    if st.session_state.importation_data:
        # Usamos st.data_editor para que la tabla sea editable
        edited_df = st.data_editor(
            pd.DataFrame(st.session_state.importation_data),
            num_rows="dynamic",
            key="importation_editor"
        )
        # Actualizar el estado de la sesión con los datos editados
        st.session_state.importation_data = edited_df.to_dict('records')
    else:
        st.info("La tabla está vacía. Sube archivos PDF para comenzar.")
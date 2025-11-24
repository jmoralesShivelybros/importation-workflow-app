import pytesseract
from pdf2image import convert_from_path
import re

# --- ¡IMPORTANTE! ---
# Asegúrate de que Tesseract-OCR esté instalado en esta ruta.
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_data_from_pdf(pdf_path):
    """
    Extrae datos de la primera página de un PDF (que contiene una imagen) usando OCR.
    """
    text = ""
    try:
        # 1. Convierte la primera página del PDF a una imagen
        images = convert_from_path(pdf_path, first_page=1, last_page=1)
        if not images:
            return {"error": "No se pudo convertir el PDF a imagen."}, ""

        # 2. Extrae el texto de la imagen usando OCR
        text = pytesseract.image_to_string(images[0], lang='spa') # 'spa' para español
        if not text:
            return {"error": "OCR no pudo extraer texto de la imagen del PDF."}, ""

    except Exception as e:
        return {"error": f"Error en OCR o conversión de PDF: {e}"}, ""

    # Diccionario para almacenar los datos extraídos
    data = {
        "status": "PTE",
        "docfile": pdf_path.split("/")[-1].split("\\")[-1],
        "fecha_reporte": "",
        "om": "",
        "po_guia": "",
        "cantidad": "",
        "descripcion": "",
        "proveedor": "",
        "programa": "",
        "costo": "",
        "factura": "",
        "pk": "1 CAJA"
    }

    # --- Búsqueda de patrones con Expresiones Regulares ---

    # FECHA (busca formatos como DD/MM/YYYY o DD-MM-YYYY)
    fecha_match = re.search(r'FECHA:\s*(\d{2}[/-]\d{2}[/-]\d{4})', text, re.IGNORECASE)
    if fecha_match:
        data["fecha_reporte"] = fecha_match.group(1)

    # REFERENCIA OM
    om_match = re.search(r'REFERENCIA\s*OM-\s*(\w+)', text, re.IGNORECASE)
    if om_match:
        data["om"] = om_match.group(1)

    # PO/GUIA (Línea y Talón)
    linea_match = re.search(r'(FEDEX|UPS|DHL|ESTAFETA)', text, re.IGNORECASE)
    talon_match = re.search(r'GUIA:\s*([A-Z0-9]{10,})', text, re.IGNORECASE)
    if linea_match and talon_match:
        data["po_guia"] = f"{linea_match.group(1)} {talon_match.group(1)}"

    # CANTIDAD
    cantidad_match = re.search(r'CANTIDAD:\s*(\d+)', text, re.IGNORECASE)
    if cantidad_match:
        data["cantidad"] = cantidad_match.group(1)

    return data, text # Devolvemos también el texto para el log
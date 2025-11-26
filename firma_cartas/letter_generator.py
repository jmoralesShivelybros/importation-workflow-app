import os
from reportlab.lib.pagesizes import letter
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.graphics.shapes import Line, Drawing


def get_template_path():
    """Devuelve la ruta a la carpeta de plantillas."""
    # La ruta es relativa a la ubicación de este archivo.
    return os.path.join(os.path.dirname(__file__), 'plantillas_cartas')

def get_available_templates():
    """Escanea la carpeta de plantillas y devuelve una lista de nombres de plantillas disponibles."""
    template_dir = get_template_path()
    if not os.path.exists(template_dir):
        return []
    # Devuelve los nombres de archivo sin la extensión .txt
    return sorted([os.path.splitext(f)[0] for f in os.listdir(template_dir) if f.endswith('.txt')])

def generate_letter_content(template_name, invoices_str):
    """
    Genera el contenido de una carta de norma reemplazando los placeholders.

    Args:
        template_name (str): El nombre de la plantilla de la norma (ej. "NOM-001-SCFI-2018").
        invoices_str (str): Una cadena de texto con los números de factura separados por coma.

    Returns:
        str: El contenido completo de la carta con los datos insertados.
    """
    template_file = os.path.join(get_template_path(), f"{template_name}.txt")

    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: No se encontró la plantilla '{template_name}.txt'."

    # Reemplazamos los placeholders con datos reales o dinámicos.
    today_date = datetime.now().strftime("%d de %B de %Y")
    
    content = content.replace("[FECHA_ACTUAL]", today_date)
    content = content.replace("[NUMEROS_FACTURA]", invoices_str.replace(",", ", "))
    content = content.replace("[NOMBRE_NORMA]", template_name)

    return content

def _build_table_based_pdf(elements, styles, template_content, invoices_str):
    """
    CONSTRUCTOR PARA CARTAS CON TABLA: Construye los elementos para cartas como NOM-050 y NOM-004.

    Args:
        template_content (str): El contenido ya leído del archivo de plantilla.
    """
    # --- Marcadores para diferentes tipos de cartas con tabla ---
    marker1 = 'Declaro bajo protesta de decir verdad que la mercancía importada con factura y proveedor:'
    marker2 = 'POR MEDIO DE LA PRESENTE Y BAJO PROTESTA DE DECIR VERDAD QUE LA MERCANCÍA QUE AMPARAN LA FACTURAS:'

    if marker1 in template_content:
        parts = template_content.split(marker1)
    else:
        parts = template_content.split(marker2)

    intro_text = parts[0]
    outro_text = parts[1] if len(parts) > 1 else ""

    for line in intro_text.strip().split('\n'):
        elements.append(Paragraph(line.strip(), styles['Normal']))
        elements.append(Spacer(1, 6))

    elements.append(Spacer(1, 12))

    table_data = [['PROVEEDOR', 'FACTURA']]
    invoice_list = [inv.strip() for inv in invoices_str.split(',') if inv.strip()]
    for invoice in invoice_list:
        table_data.append(['SHIVELYBROS INC.', invoice])

    # Creamos la tabla y le damos estilo
    invoice_table = Table(table_data)
    invoice_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), '#CCCCCC'), # Encabezado gris
        ('TEXTCOLOR', (0, 0), (-1, 0), '#000000'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # Encabezado en negrita
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), '#FFFFFF'),
        ('GRID', (0, 0), (-1, -1), 1, '#000000') # Bordes de la tabla
    ]))
    elements.append(invoice_table)
    elements.append(Spacer(1, 12))

    # Volvemos a añadir el marcador que usamos para dividir
    if marker1 in template_content:
        elements.append(Paragraph(marker1, styles['Normal']))
    else:
        elements.append(Paragraph(marker2, styles['Normal']))
    elements.append(Spacer(1, 12))

    for line in outro_text.strip().split('\n'):
        # Procesamos solo el texto del cuerpo, deteniéndonos antes del bloque de la firma
        if line.strip():
            elements.append(Paragraph(line.strip(), styles['Normal']))
            # Añadimos un espacio después de cada párrafo para mejor legibilidad
            elements.append(Spacer(1, 6))

def _add_signature_block(elements, styles):
    """Añade el bloque de firma estandarizado al final del documento."""
    # Espacio antes de la firma
    elements.append(Spacer(1, 48))

    # Nombre de la empresa y RFC
    elements.append(Paragraph("Shivelybros Mexico, S. de R.L de C.V.", styles['CenterAlign']))
    elements.append(Paragraph("RFC: SME071109RR7", styles['CenterAlign']))
    elements.append(Spacer(1, 72)) # Espacio generoso para la firma física (aumentado)

    # Línea para la firma
    line = Line(0, 0, 180, 0) # x1, y1, x2, y2
    drawing = Drawing(180, 1) # Un lienzo de 180 de ancho y 1 de alto
    drawing.add(line)
    drawing.hAlign = 'CENTER'
    elements.append(drawing)

    # Nombre y título del representante legal
    elements.append(Paragraph("Ma. Elena Moreno Lopez", styles['CenterAlign']))
    elements.append(Paragraph("Representante Legal", styles['CenterAlign']))

def _build_default_pdf(elements, styles, template_content, invoices_str):
    """
    CONSTRUCTOR POR DEFECTO: Construye un PDF simple a partir de una plantilla de texto.
    Ideal para cartas que no necesitan formato complejo.

    Args:
        template_content (str): El contenido ya leído del archivo de plantilla.
        invoices_str (str): Cadena con las facturas.
    """

    # Añadir cada línea como un párrafo
    for line in template_content.split('\n'):
        # Procesamos solo hasta antes del bloque de la firma, que se añadirá después
        if "Shivelybros Mexico" in line:
            break
        if line.strip():
            elements.append(Paragraph(line.strip(), styles['Normal']))

def generate_letter_pdf(template_name, invoices_str, output_path):
    """
    DIRECTOR: Genera un archivo PDF para una carta de norma, eligiendo el constructor adecuado.

    Args:
        template_name (str): El nombre de la plantilla (ej. "NOM-050").
        invoices_str (str): Cadena con las facturas separadas por comas.
        output_path (str): La ruta donde se guardará el PDF.
    """
    print(f"[DEBUG] Iniciando generate_letter_pdf para plantilla: {template_name}")
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=18)
    
    # --- Estilos de Párrafo (comunes para todos los constructores) ---
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='RightAlign', parent=styles['Normal'], alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='CenterAlign', parent=styles['Normal'], alignment=TA_CENTER))

    elements = []

    # --- Elementos Comunes para TODAS las cartas ---

    # Logo (Centrado al inicio)
    print("[DEBUG] Añadiendo logo...")
    logo_path = os.path.join(os.path.dirname(__file__), 'logo', 'logo_shively.png')
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=450, height=100) 
        logo_img.hAlign = 'CENTER'
        elements.append(logo_img)
        elements.append(Spacer(1, 36))
    else:
        print(f"Advertencia: No se encontró el logo en {logo_path}")

    # Fecha (Alineada a la derecha)
    print("[DEBUG] Añadiendo fecha...")
    today_date_str = f"Saltillo, Coah. a {datetime.now().strftime('%d de %B de %Y')}"
    elements.append(Paragraph(today_date_str, styles['RightAlign']))
    elements.append(Spacer(1, 24))

    # --- Detección Automática de Formato y Selección de Constructor ---
    template_file = os.path.join(get_template_path(), f"{template_name}.txt")
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            template_content = f.read()
    except FileNotFoundError:
        elements.append(Paragraph(f"Error: No se encontró la plantilla '{template_name}.txt'.", styles['Normal']))
        doc.build(elements)
        return

    # Reemplazar placeholders comunes en el contenido de la plantilla
    template_content = template_content.replace("[FECHA_ACTUAL]", datetime.now().strftime("%d de %B de %Y"))
    template_content = template_content.replace("[NUMEROS_FACTURA]", invoices_str.replace(",", ", "))
    template_content = template_content.replace("[NOMBRE_NORMA]", template_name)

    # Marcadores que identifican las plantillas con tabla
    table_marker_keyword1 = 'factura y proveedor:'
    table_marker_keyword2 = 'mercancía que amparan las facturas:'

    # --- EXCEPCIÓN ESPECIAL PARA NOM-004 ---
    # Forzamos el uso del constructor de tablas para NOM-004 para evitar problemas de detección.
    if template_name == "NOM-004":
        print("[DEBUG] EXCEPCIÓN: Forzando el uso de _build_table_based_pdf para NOM-004.")
        _build_table_based_pdf(elements, styles, template_content, invoices_str)
    elif table_marker_keyword1 in template_content or table_marker_keyword2 in template_content:
        # Si encuentra el marcador, usa el constructor de tablas
        print("[DEBUG] Plantilla con tabla detectada. Usando _build_table_based_pdf.")
        _build_table_based_pdf(elements, styles, template_content, invoices_str)
    else:
        # Si no, usa el constructor por defecto
        print("[DEBUG] Plantilla simple detectada. Usando _build_default_pdf.")
        _build_default_pdf(elements, styles, template_content, invoices_str)

    # Añadimos el bloque de firma estandarizado
    print("[DEBUG] Añadiendo bloque de firma...")
    _add_signature_block(elements, styles)

    # Construir el PDF
    print("[DEBUG] Construyendo el documento PDF final.")
    doc.build(elements)

from pathlib import Path # Esta línea es crucial
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

def generate_packing_slip(data, filename):
    # Márgenes ajustados para aprovechar el espacio
    doc = SimpleDocTemplate(filename, pagesize=letter, leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    green = colors.Color(0, 0.7, 0.2)
    light_green = colors.Color(0.93, 1, 0.93)

    # --- ESTILOS PERSONALIZADOS ---
    header_style = ParagraphStyle(
        'header',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=green,
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    right_header_style = ParagraphStyle(
        'right_header',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    label_style = ParagraphStyle(
        'label',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.white,
        alignment=TA_LEFT,
    )
    label_green_style = ParagraphStyle(
        'label_green',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=green,
        alignment=TA_LEFT,
    )
    normal_style = ParagraphStyle(
        'normal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        textColor=colors.black,
        alignment=TA_LEFT,
    )
    normal_center = ParagraphStyle(
        'normal_center',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        textColor=colors.black,
        alignment=TA_CENTER,
    )

    elements = []

    # --- CABECERA: SHIPPER Y PACKING LIST ---
    header_table = Table([
        [
            Paragraph(data['shipper'], header_style),
            Paragraph('PACKING LIST', right_header_style)
        ]
    ], colWidths=[380, 220], rowHeights=40)
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (1,0), (1,0), green),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 1, green),
    ]))
    elements.append(header_table)

    # --- DIRECCIÓN Y FECHAS ---
    shipper_address = Paragraph(data['shipper_address'].replace('\n', '<br/>'), normal_style)
    info_table = Table([
        [Paragraph(f"<b>{data.get('packing_number', '58')}</b>", label_green_style)],
        [Paragraph('<b>Fecha de factura:</b> <font color="#009933">%s</font>' % data["invoice_date"], label_green_style)],
        [Paragraph('<b>Fecha del envío:</b> <font color="#009933">%s</font>' % data["ship_date"], label_green_style)],
    ], colWidths=[220], rowHeights=[24, 24, 24])
    info_table.setStyle(TableStyle([
        ('TEXTCOLOR', (0,0), (-1,-1), green),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOX', (0,0), (-1,-1), 1, green),
        ('INNERGRID', (0,0), (-1,-1), 1, green),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    # Tabla principal de dirección y fechas
    address_table = Table([
        [shipper_address, info_table]
    ], colWidths=[380, 220], rowHeights=[100])
    address_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, green),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(address_table)

    # --- ESPACIO EXTRA ENTRE SECCIONES ---
    elements.append(Spacer(1, 20))  # Espacio entre dirección y COBRAR A / ENVIAR A

    # --- COBRAR A / ENVIAR A ---
    bill_to = Paragraph(data['bill_to'].replace('\n', '<br/>'), normal_style)
    ship_to = Paragraph(data['ship_to'].replace('\n', '<br/>'), normal_style)
    bill_ship_table = Table([
        [
            Paragraph('COBRAR A:', label_style),
            Paragraph('ENVIAR A:', label_style)
        ],
        [bill_to, ship_to]
    ], colWidths=[300, 300], rowHeights=[26, 70])  # <-- Aumenta la altura de la fila para que encaje bien
    bill_ship_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), green),
        ('TEXTCOLOR', (0,0), (1,0), colors.white),
        ('BOX', (0,0), (-1,-1), 1, green),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (-1,0), 'LEFT'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('FONTSIZE', (0,1), (-1,1), 11),
    ]))
    elements.append(bill_ship_table)

    # --- ESPACIO EXTRA ANTES DE LA TABLA DE ARTÍCULOS ---
    elements.append(Spacer(1, 30))  # <-- Aumenta el espacio para mover la tabla de descripción hacia abajo

    # --- TABLA DE ARTÍCULOS ---
    # Calcula el total de productos escaneados
    total_cantidad = sum(int(item["cantidad"]) for item in data["items"] if str(item["cantidad"]).isdigit())

    item_data = [
        [
            Paragraph('DESCRIPCIÓN', label_style),
            Paragraph('ORDEN QTY', label_style),
            Paragraph('ENVIADO QTY', label_style)
        ]
    ]
    for item in data["items"]:
        item_data.append([
            Paragraph('<font color="#4CAF50">%s</font>' % item["descripcion"], normal_style),
            Paragraph(str(item["cantidad"]), normal_center),
            Paragraph(str(item["cantidad"]), normal_center)
        ])
    item_data.append([
        Paragraph('<b>TOTAL ENVIADO</b>', normal_style),
        Paragraph(f"<b>{total_cantidad}</b>", normal_center),
        Paragraph(f"<b>{total_cantidad}</b>", normal_center)
    ])
    t3 = Table(item_data, colWidths=[380, 110, 110], rowHeights=24)
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), green),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (-1,-2), 'CENTER'),
        ('ALIGN', (1,-1), (-1,-1), 'CENTER'),
        ('FONTSIZE', (0,0), (-1,0), 11),
        ('FONTSIZE', (0,1), (-1,-1), 10),
        ('GRID', (0,0), (-1,-1), 0.7, green),
        ('BACKGROUND', (0,1), (-1,1), light_green),
        ('BACKGROUND', (0,2), (-1,6), colors.whitesmoke),
        ('BACKGROUND', (0,-1), (-1,-1), colors.white),
        ('LINEBELOW', (0,-2), (-1,-2), 1, green),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t3)

    doc.build(elements)
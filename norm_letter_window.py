import streamlit as st

# Importamos las funciones de lógica
from firma_cartas.letter_generator import generate_letter_content, get_available_templates, generate_letter_pdf
import os

def render_norm_letter_page(folder_manager, week_num):
    st.header("Generador de Cartas de Norma")

    # Cargamos dinámicamente las plantillas disponibles desde la carpeta
    letter_templates = get_available_templates()

    with st.container(border=True):
        st.subheader("Datos de la Carta")

        # Menú desplegable para seleccionar la plantilla
        selected_template = st.selectbox(
            "Selecciona la plantilla de la carta:",
            options=["Selecciona una opción..."] + letter_templates,
            index=0
        )

        # Campo para ingresar números de factura
        invoice_numbers = st.text_input(
            "Ingresa los números de factura (separados por coma):",
            placeholder="Ej: 12345, 67890"
        )

        # Botón para generar y guardar el PDF
        if st.button("Generar y Guardar PDF", type="primary", use_container_width=True):
            save_as_pdf(folder_manager, week_num, selected_template, invoice_numbers)

def save_as_pdf(folder_manager, week_num, template, invoices):
        # 1. Validar que los datos necesarios estén seleccionados
        if not template or template == "Selecciona una opción..." or not invoices:
            st.warning("Por favor, selecciona una plantilla e ingresa los números de factura.")
            return

        try:
            # 2. Obtener la ruta de la carpeta 'Cartas' usando el FolderManager
            output_folder = folder_manager.get_cartas_folder_path(week_num)
            os.makedirs(output_folder, exist_ok=True) # Asegurarse de que la carpeta exista

            # 3. Crear el nombre del archivo y la ruta completa
            filename = f"{template}_{invoices.replace(',', '_').replace(' ', '')}.pdf"
            file_path = os.path.join(output_folder, filename)

            # 4. Generar y guardar el PDF
            generate_letter_pdf(template, invoices, file_path)

            # 5. Mostrar notificación y botón de descarga (el nuevo estándar)
            st.toast(f'¡Carta "{filename}" generada!', icon='✉️')

            # Leemos el archivo que acabamos de crear en memoria
            with open(file_path, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()

            # Mostramos el botón de descarga
            st.download_button(
                label=f"✉️ Descargar {filename}",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf"
            )
            st.info(f"El archivo también fue guardado en la ruta:\n`{file_path}`")
        except Exception as e:
            st.error(f"No se pudo guardar el PDF. Error: {e}")
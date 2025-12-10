import streamlit as st
import pandas as pd
from io import BytesIO
import os

def render_excel_to_txt_page():
    """
    Renderiza la página de Streamlit para convertir archivos Excel a TXT.
    """
    st.header("Convertidor de Excel a TXT")

    st.info(
        "Sube un archivo de Excel (.xlsx) para convertirlo a un archivo de texto plano (.txt) "
        "con valores separados por tabulaciones (TSV)."
    )

    uploaded_file = st.file_uploader(
        "1. Selecciona un archivo de Excel",
        type=['xlsx']
    )

    if uploaded_file:
        try:
            # Leer el archivo de Excel
            df = pd.read_excel(uploaded_file)

            st.subheader("Vista Previa de los Datos")
            st.dataframe(df.head())

            # --- Convertir DataFrame a TXT en memoria ---
            output_txt = BytesIO()
            # Usamos to_csv con separador de tabulación para crear un archivo TSV/TXT
            df.to_csv(output_txt, sep='\t', index=False, header=True, encoding='utf-8')
            txt_bytes = output_txt.getvalue()

            original_filename = os.path.splitext(uploaded_file.name)[0]
            
            st.download_button(
                label="📥 Descargar Archivo TXT",
                data=txt_bytes,
                file_name=f"{original_filename}.txt",
                mime="text/plain",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Ocurrió un error al procesar el archivo: {e}")
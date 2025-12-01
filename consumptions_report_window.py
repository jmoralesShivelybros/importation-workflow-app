import streamlit as st
import pandas as pd
import os
import re # Importamos el módulo de expresiones regulares
from io import StringIO, BytesIO

# Importamos la lógica refactorizada de tu script original
from reporte_consumos.enriquecer_csv import procesar_datos_en_memoria

def clean_illegal_chars_for_excel(df):
    """
    Limpia un DataFrame de caracteres ilegales para XML/Excel.
    Aplica la limpieza solo a las columnas que son de tipo 'object' (strings).
    """
    # Expresión regular para encontrar caracteres de control XML ilegales
    illegal_xml_chars_re = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
    
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).apply(lambda x: illegal_xml_chars_re.sub('', x))
    return df

def render_consumptions_report_page():
    st.header("Generador de Reporte de Consumos (Beta)")

    st.info(
        "Esta herramienta enriquece un archivo CSV de consumos utilizando un archivo maestro como referencia. "
        "Completa información faltante del fabricante, calcula precios extendidos y estandariza columnas."
    )

    # --- Carga de archivos ---
    with st.container(border=True):
        st.subheader("1. Cargar Archivo a Modificar")
        file_to_modify = st.file_uploader(
            "Selecciona el reporte de consumos (ej. `CSV PARA MODIFICAR.csv`)",
            type="csv",
            help="Este es el reporte de consumos que tiene datos faltantes o incorrectos."
        )

    # --- Punto 2: Vista Previa de los Datos ---
    if file_to_modify:
        try:
            # Leemos solo las primeras 11 filas para la vista previa (10 datos + cabecera)
            df_preview = pd.read_csv(file_to_modify, nrows=10, encoding='utf-8-sig')
            file_to_modify.seek(0) # Regresamos el puntero al inicio del archivo para el procesamiento real
            
            with st.expander("Verificar Vista Previa del Archivo Cargado", expanded=True):
                st.dataframe(df_preview)
                st.caption("Mostrando las primeras 10 filas. Confirma que las columnas y datos son correctos.")
        except Exception as e:
            st.warning(f"No se pudo generar la vista previa. El archivo podría estar vacío o tener un formato inesperado. Error: {e}")

    # --- Procesamiento y Resultados ---
    if file_to_modify:
        if st.button("▶️ Procesar Archivo", type="primary", use_container_width=True):
            # --- CORRECCIÓN DE RUTA ---
            # Construimos la ruta al archivo maestro de forma relativa al script actual.
            # Esto asegura que funcione tanto en local como en la web.
            current_dir = os.path.dirname(os.path.abspath(__file__))
            master_file_path = os.path.join(current_dir, "reporte_consumos", "TEST CSV.csv")
            
            if not os.path.exists(master_file_path):
                st.error(f"Error crítico: No se encontró el archivo maestro en la ruta esperada: {master_file_path}")
                return

            to_modify_content = StringIO(file_to_modify.getvalue().decode('utf-8-sig'))

            with st.spinner("Procesando y enriqueciendo los datos..."):
                try:
                    # Llamamos a la función de lógica que procesa los datos en memoria
                    df_completo, df_errores, df_formato, resumen = procesar_datos_en_memoria(master_file_path, to_modify_content)

                    st.session_state.df_completo = df_completo
                    st.session_state.df_errores = df_errores
                    st.session_state.df_formato = df_formato
                    st.session_state.resumen = resumen
                    st.toast("¡Proceso completado con éxito!", icon="✅")

                except Exception as e:
                    st.error(f"Ocurrió un error durante el procesamiento: {e}")
                    # Limpiamos el estado si hay un error
                    if 'df_completo' in st.session_state: del st.session_state.df_completo
                    if 'df_errores' in st.session_state: del st.session_state.df_errores
                    if 'df_formato' in st.session_state: del st.session_state.df_formato
                    if 'resumen' in st.session_state: del st.session_state.resumen

    # --- Mostrar resultados y botones de descarga ---
    if 'df_completo' in st.session_state:
        with st.container(border=True):
            st.subheader("2. Resultados del Procesamiento")
            
            # Mostramos el resumen
            st.code(st.session_state.resumen, language="text")

            # --- ¡NUEVO! Limpiamos los DataFrames antes de ofrecer la descarga ---
            st.session_state.df_completo = clean_illegal_chars_for_excel(st.session_state.df_completo.copy())
            st.session_state.df_errores = clean_illegal_chars_for_excel(st.session_state.df_errores.copy())

            # --- Botones de Descarga ---
            st.write("#### Descargar Reporte Completo")
            col_completo1, col_completo2 = st.columns(2)

            # --- Botón para descargar CSV completo ---
            with col_completo1:
                output_csv_completo = BytesIO()
                st.session_state.df_completo.to_csv(output_csv_completo, index=False, encoding='utf-8-sig')
                output_csv_completo.seek(0)
                st.download_button(
                    label="📥 Descargar CSV Completo",
                    data=output_csv_completo,
                    file_name="CSV_MODIFICADO_COMPLETO.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            # --- Botón para descargar Excel completo ---
            with col_completo2:
                output_excel_completo = BytesIO()
                with pd.ExcelWriter(output_excel_completo, engine='openpyxl') as writer:
                    st.session_state.df_completo.to_excel(writer, index=False, sheet_name='Reporte Completo')
                output_excel_completo.seek(0)
                st.download_button(
                    label="📊 Descargar Excel Completo",
                    data=output_excel_completo,
                    file_name="REPORTE_MODIFICADO_COMPLETO.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            # --- Botones para descargar el archivo de errores (si existe) ---
            if not st.session_state.df_errores.empty:
                st.divider()
                st.write("#### Descargar Registros No Encontrados")
                col_errores1, col_errores2 = st.columns(2)

                # --- Botón para descargar CSV de errores ---
                with col_errores1:
                    output_csv_errores = BytesIO()
                    st.session_state.df_errores.to_csv(output_csv_errores, index=False, encoding='utf-8-sig')
                    output_csv_errores.seek(0)
                    st.download_button(
                        label="⚠️ Descargar CSV de Errores",
                        data=output_csv_errores,
                        file_name="REGISTROS_NO_ENCONTRADOS.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                # --- Botón para descargar Excel de errores ---
                with col_errores2:
                    output_excel_errores = BytesIO()
                    st.session_state.df_errores.to_excel(output_excel_errores, index=False, sheet_name='Errores')
                    output_excel_errores.seek(0)
                    st.download_button(
                        label="📊 Descargar Excel de Errores",
                        data=output_excel_errores,
                        file_name="REGISTROS_NO_ENCONTRADOS.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )            
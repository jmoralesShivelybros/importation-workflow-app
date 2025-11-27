import streamlit as st
import json
from datetime import datetime
import tempfile
import sys
import os
# --- Importamos las funciones que renderizarán cada "página" ---
# (Estos archivos los modificaremos a continuación)
from firma_cartas import letter_generator # Importar desde el subpaquete firma_cartas
from folder_manager import FolderManager
from importation_window import render_importation_page
from norm_letter_window import render_norm_letter_page
from exportation_window import render_exportation_page
# --- NUEVO: Importamos la lógica de datos del master, pero no la ventana ---
from master.master_data import MasterDataManager

def main():
    st.set_page_config(layout="wide", page_title="Sistema de Logística")
    st.title("📦 Sistema de Logística Web")

    # --- Lógica para despliegue en la nube ---
    # Usamos un directorio temporal para actuar como la carpeta "Logistica"
    # Este directorio se crea por sesión de usuario.
    if 'temp_dir' not in st.session_state:
        st.session_state.temp_dir = tempfile.mkdtemp()
    
    logistica_root_path = st.session_state.temp_dir
    folder_manager = FolderManager(logistica_root_path)    
    
    # --- Barra lateral para navegación ---
    with st.sidebar:
        st.header("Navegación")
        
        # Selección de semana
        current_week = datetime.now().isocalendar()[1]
        # Usamos st.session_state para mantener el valor entre recargas
        if 'selected_week' not in st.session_state:
            st.session_state.selected_week = current_week
            
        st.session_state.selected_week = st.number_input(
            "Número de semana", 
            min_value=1, 
            max_value=53, 
            value=st.session_state.selected_week,
            step=1
        )
        
        # Creamos la carpeta de la semana automáticamente para simplificar.
        folder_manager.create_week_folder(st.session_state.selected_week)

        st.divider()

        # --- Sección para subir archivos ---
        st.header("Cargar Archivos")
        uploaded_files = st.file_uploader(
            "Sube aquí tus facturas o archivos PDF",
            accept_multiple_files=True,
            type=['pdf']
        )

        if uploaded_files:
            week_folder = folder_manager.get_week_folder_path(st.session_state.selected_week)
            for uploaded_file in uploaded_files:
                with open(os.path.join(week_folder, uploaded_file.name), "wb") as f:
                    f.write(uploaded_file.getbuffer())
            st.success(f"{len(uploaded_files)} archivo(s) cargado(s) para la semana {st.session_state.selected_week}.")
        
        st.divider()
        
        # Menú de acciones
        app_mode = st.radio(
            "Selecciona una acción",
            ("Generar Importación (Beta)", "Generar Exportación", "Generar Carta de Norma", "Actualizar Archivo Master")
        )

    # --- Renderizado de la página seleccionada ---
    if app_mode == "Generar Importación (Beta)":
        render_importation_page(folder_manager, st.session_state.selected_week)
    elif app_mode == "Generar Exportación":
        render_exportation_page(folder_manager, st.session_state.selected_week)
    elif app_mode == "Generar Carta de Norma":
        render_norm_letter_page(folder_manager, st.session_state.selected_week)
    # --- NUEVO: Renderizado para la página del Master File ---
    elif app_mode == "Actualizar Archivo Master":
        render_master_update_page()

def render_master_update_page():
    """
    Renderiza la página para actualizar el archivo Master usando componentes de Streamlit.
    """
    st.header("Actualizar Archivo Master en SharePoint")

    # --- Manejo de credenciales y configuración de SharePoint ---
    # Usamos los secrets de Streamlit para las credenciales, es más seguro.
    try:
        site_url = st.secrets["sharepoint"]["SITE_URL"]
        file_relative_url = st.secrets["sharepoint"]["FILE_RELATIVE_URL"]
        username = st.secrets["sharepoint"]["USERNAME"]
        password = st.secrets["sharepoint"]["PASSWORD"]
    except (KeyError, FileNotFoundError):
        st.error("Error: Las credenciales de SharePoint no están configuradas en los Secrets de Streamlit.")
        st.info("Añade un archivo .streamlit/secrets.toml con la sección [sharepoint] y las claves necesarias.")
        st.stop()

    # --- Interfaz de usuario con Streamlit ---
    sheet_name = st.text_input("Nombre de la Pestaña:", value="Hoja1")
    cell_address = st.text_input("Celda (ej. B5):", value="A1")
    text_to_write = st.text_input("Texto a Escribir:", value="Prueba de conexión exitosa desde Streamlit")

    if st.button("Escribir en Excel de SharePoint", type="primary"):
        if not all([sheet_name, cell_address, text_to_write]):
            st.warning("Por favor, completa todos los campos.")
        else:
            try:
                with st.spinner("Conectando y escribiendo en SharePoint..."):
                    data_manager = MasterDataManager(site_url, file_relative_url, username, password)
                    data_manager.write_single_cell(sheet_name, cell_address, text_to_write)
                st.success(f"¡Éxito! Se ha escrito '{text_to_write}' en la celda {cell_address} de la hoja '{sheet_name}'.")
            except Exception as e:
                st.error(f"Error al escribir en SharePoint: {e}")

if __name__ == "__main__":
    main()
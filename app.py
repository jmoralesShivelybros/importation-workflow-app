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
            ("Generar Importación (Beta)", "Generar Exportación", "Generar Carta de Norma")
        )

    # --- Renderizado de la página seleccionada ---
    if app_mode == "Generar Importación (Beta)":
        render_importation_page(folder_manager, st.session_state.selected_week)
    elif app_mode == "Generar Exportación":
        render_exportation_page(folder_manager, st.session_state.selected_week)
    elif app_mode == "Generar Carta de Norma":
        render_norm_letter_page(folder_manager, st.session_state.selected_week)

if __name__ == "__main__":
    main()
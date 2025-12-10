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
from consumptions_report_window import render_consumptions_report_page
# --- NUEVO: Importamos la lógica de datos del master, pero no la ventana ---
# from master.master_data import MasterDataManager # Comentamos esta línea

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

        # Menú de acciones
        app_mode = st.radio(
            "Selecciona una acción",
            ("Generar Importación", "Generar Exportación", "Generar Carta de Norma", "Generar Reporte de Consumos")
        )

    # --- Renderizado de la página seleccionada ---
    if app_mode == "Generar Importación":
        render_importation_page(folder_manager, st.session_state.selected_week)
    elif app_mode == "Generar Exportación":
        render_exportation_page(folder_manager, st.session_state.selected_week)
    elif app_mode == "Generar Carta de Norma":
        render_norm_letter_page(folder_manager, st.session_state.selected_week)
    elif app_mode == "Generar Reporte de Consumos":
        render_consumptions_report_page()
    # --- NUEVO: Renderizado para la página del Master File ---
    # elif app_mode == "Actualizar Archivo Master": # Comentamos el renderizado de la página
    #     render_master_update_page()


if __name__ == "__main__":
    main()
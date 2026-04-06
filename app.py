import streamlit as st
import json
from datetime import datetime
import tempfile
import sys
import os
# --- Importamos las funciones que renderizarán cada "página" ---
from folder_manager import FolderManager
from warehouse_window import render_warehouse_page
# --- NUEVO: Importamos la lógica de datos del master, pero no la ventana ---
# from master.master_data import MasterDataManager # Comentamos esta línea

def set_main_view():
    """Función de callback para establecer la vista principal."""
    st.session_state.current_view = 'main'

def set_converter_view():
    """Función de callback para establecer la vista del convertidor."""
    st.session_state.current_view = "convertir_excel"

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

        st.info("Módulo de Almacén Activo")
        app_mode = st.radio(
            "Acciones disponibles",
            ("Recepción de Material", "Gestión y Rutas", "Historial"),
            key="almacen_radio"
        )
        st.session_state.app_mode = app_mode

    # --- Lógica de renderizado principal ---
    if app_mode:
        render_warehouse_page(folder_manager, section=app_mode)

if __name__ == "__main__":
    main()
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
from excel_to_txt_converter import render_excel_to_txt_page
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
    app_mode = st.session_state.get('app_mode')
    if app_mode != "Monitor TV":
        st.title("📦 Sistema de Logística Web")

    # Usamos la ruta base del proyecto para que las carpetas sean relativas.
    # Esto evita el uso de carpetas /tmp aleatorias y mantiene la estructura local.
    # Nota: Streamlit Cloud borra los archivos locales al reiniciar la aplicación.
    logistica_root_path = os.path.dirname(os.path.abspath(__file__))
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

        # Botón para la funcionalidad de conversión, ahora es de acceso general
        st.button("Convertir Excel a TXT", use_container_width=True, on_click=set_converter_view)
        st.divider()

        # --- Menú de acciones jerárquico ---
        # 1. Selección del Módulo/Área
        module = st.selectbox(
            "Selecciona el área de trabajo",
            ("Logística", "Almacenes"),
            on_change=set_main_view # Al cambiar de módulo, volvemos a la vista principal
        )

        # Variable para controlar la vista principal
        app_mode = None

        # 2. Muestra las acciones específicas para el módulo seleccionado
        if module == "Logística":
            app_mode = st.radio(
                "Acciones de Logística",
                ("Generar Importación", "Generar Exportación", "Generar Carta de Norma", "Generar Reporte de Consumos"),
                key="logistica_radio", # Clave para el widget
                on_change=set_main_view # Al cambiar de acción, volvemos a la vista principal
            )
            st.session_state.app_mode = app_mode
        
        elif module == "Almacenes":
            # Establecemos un modo específico para almacenes
            app_mode = st.radio(
                "Acciones de Almacén",
                ("Recepción de Material", "Gestión y Rutas", "Monitor TV", "Historial"),
                key="almacen_radio",
                on_change=set_main_view
            )
            st.session_state.app_mode = app_mode

    # --- Lógica de renderizado principal ---
    # Damos prioridad a la vista de conversión si fue seleccionada
    if st.session_state.get('current_view') == "convertir_excel":
        # Si la vista actual es la del convertidor, la renderizamos.
        render_excel_to_txt_page()
    elif app_mode:
        # Si no, obtenemos el modo de la sesión (que fue establecido por el radio de Logística)
        current_app_mode = st.session_state.get('app_mode')
        # Si no, y si hay un modo de aplicación seleccionado (ej. "Generar Importación"),
        # usamos la función auxiliar para renderizar la página del módulo correspondiente.
        render_module_page(current_app_mode, folder_manager, st.session_state.selected_week)

def render_module_page(app_mode, folder_manager, week_num):
    """Función auxiliar para renderizar la página del módulo seleccionado."""
    if app_mode == "Generar Importación":
        render_importation_page(folder_manager, week_num)
    elif app_mode == "Generar Exportación":
        render_exportation_page(folder_manager, week_num)
    elif app_mode == "Generar Carta de Norma":
        render_norm_letter_page(folder_manager, week_num)
    elif app_mode == "Generar Reporte de Consumos":
        render_consumptions_report_page()
    elif app_mode in ["Recepción de Material", "Gestión y Rutas", "Monitor TV", "Historial"]:
        render_warehouse_page(folder_manager, section=app_mode)

if __name__ == "__main__":
    main()
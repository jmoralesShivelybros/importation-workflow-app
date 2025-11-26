import streamlit as st
import json
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__))) # Añade la raíz del proyecto al sys.path

# --- Importamos las funciones que renderizarán cada "página" ---
# (Estos archivos los modificaremos a continuación)
from firma_cartas import letter_generator # Importar desde el subpaquete firma_cartas
from folder_manager import FolderManager
from importation_window import render_importation_page
from norm_letter_window import render_norm_letter_page
from exportation_window import render_exportation_page


def get_base_path():
    """ Obtiene la ruta base para encontrar los recursos, tanto en desarrollo como en el ejecutable."""
    if getattr(sys, 'frozen', False):
        # Si la aplicación está "congelada" (es un .exe), la ruta base es el directorio del ejecutable
        return os.path.dirname(sys.executable)
    else:
        # Si está en modo de desarrollo, la ruta base es el directorio del script actual
        return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(get_base_path(), "config.json")

def load_or_create_config():
    """Carga la configuración de la ruta de logística desde config.json."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        if "logistica_root" in config and os.path.exists(config["logistica_root"]):
            return config["logistica_root"]
    except (FileNotFoundError, json.JSONDecodeError):
        # Si el archivo no existe o está corrupto, no devolvemos nada.
        # La app principal se encargará de solicitar la configuración.
        return None

def save_config(new_path):
    """Guarda la nueva ruta en el archivo config.json."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"logistica_root": new_path}, f, indent=4)

def render_config_setup():
    """Muestra la interfaz para la configuración inicial o el cambio de carpeta."""
    st.warning("⚠️ **Configuración Requerida**")
    st.info("Parece que es la primera vez que usas la aplicación o la carpeta de trabajo no es válida. Por favor, configura la ruta a tu carpeta 'Logistica'.")
    
    st.markdown("""
    **Instrucciones:**
    1. En tu explorador de archivos, navega hasta tu carpeta `Logistica`.
    2. Haz clic derecho sobre la carpeta y selecciona "Copiar como ruta de acceso" (o similar).
    3. Pega la ruta en el campo de abajo y presiona "Guardar Configuración".
    """)
    
    new_path = st.text_input("Pega aquí la ruta a tu carpeta 'Logistica':", placeholder="Ej: C:\\Users\\TuUsuario\\Documentos\\Logistica")
    
    if st.button("Guardar Configuración", type="primary"):
        if new_path and os.path.isdir(new_path):
            save_config(new_path)
            st.success("¡Configuración guardada! La aplicación se recargará.")
            st.rerun()
        else:
            st.error("La ruta que ingresaste no es una carpeta válida. Por favor, inténtalo de nuevo.")

def main():
    st.set_page_config(layout="wide", page_title="Sistema de Logística")
    st.title("📦 Sistema de Logística Web")

    # --- NUEVO: Mostrar notificación si viene de una recarga de configuración ---
    if st.session_state.get("show_config_toast"):
        st.toast("¡Carpeta de trabajo actualizada!", icon="📁")
        # Limpiamos la bandera para que no se muestre de nuevo
        st.session_state.show_config_toast = False

    # --- Carga de configuración ---
    logistica_root_path = load_or_create_config()
    
    # Si no hay configuración, mostramos el asistente y detenemos la app principal.
    if not logistica_root_path:
        render_config_setup()
        st.stop()

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
        
        if st.button("Crear carpeta de semana"):
            created = folder_manager.create_week_folder(st.session_state.selected_week)
            if created:
                st.success(f"Carpeta para semana {st.session_state.selected_week} creada.")
            else:
                st.info(f"La carpeta para la semana {st.session_state.selected_week} ya existe.")

        st.divider()

        # --- NUEVO: Sección para cambiar la carpeta de trabajo ---
        with st.expander("Configuración de Carpeta"):
            st.caption(f"Actual: `{logistica_root_path}`")
            new_path = st.text_input("Nueva ruta a la carpeta 'Logistica':", key="new_path_input")
            if st.button("Guardar Nueva Carpeta"):
                if new_path and os.path.isdir(new_path):
                    save_config(new_path)
                    # Preparamos la notificación para DESPUÉS de la recarga
                    st.session_state.show_config_toast = True
                    st.rerun()
                else:
                    st.error("La ruta no es una carpeta válida.")
        
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
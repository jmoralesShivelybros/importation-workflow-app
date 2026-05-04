import streamlit as st
from datetime import datetime

def render_auto_page(folder_manager, week_num):
    st.header("Formulario Automóvil")

    # Fecha automática
    current_date = datetime.now().strftime("%Y-%m-%d")
    fecha = st.text_input("Fecha", value=current_date, disabled=True)

    # Hora de inicio
    hora_inicio = st.time_input("Hora de Inicio")

    # Kilómetros al inicio
    km_inicio = st.number_input("Kilómetros al Inicio", min_value=0)

    # Inspección del vehículo
    inspeccion = st.text_area("Inspección del Vehículo")

    # Fecha de retorno
    fecha_retorno = st.date_input("Fecha de Retorno")

    # Hora del retorno
    hora_retorno = st.time_input("Hora del Retorno")

    # Kilómetros al terminar
    km_terminar = st.number_input("Kilómetros al Terminar", min_value=0)

    # Tanque lleno
    tanque_lleno = st.radio("Tanque Lleno", ("Sí", "No"))

    # Destino o razón de viaje
    destino = st.text_input("Destino o Razón de Viaje")

    # Usuario
    usuario = st.text_input("Usuario")

    # For now, just display the form, no submit button or functionality
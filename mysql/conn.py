import streamlit as st
import mysql.connector

def get_db_connection():
    """
    Crea y devuelve una conexión a la base de datos MySQL.
    Maneja errores de conexión y los muestra en la interfaz de Streamlit.
    """
    try:
        conn = mysql.connector.connect(
            host="sql100.infinityfree.com",
            user="if0_40787007",
            password=st.secrets["Password_db"],
            database="if0_40787007",
            port=3306
        )
        return conn
    except mysql.connector.Error as err:
        st.error(f"Error de conexión a la base de datos: {err}")
        return None
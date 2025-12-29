import streamlit as st
import mysql.connector

def get_db_connection():
    """
    Crea y devuelve una conexión a la base de datos MySQL.
    Maneja errores de conexión y los muestra en la interfaz de Streamlit.
    """
    try:
        conn = mysql.connector.connect(
            host="gateway01.us-east-1.prod.aws.tidbcloud.com",
            user="3jortA3asNPfVCt.root",
            password=st.secrets["Password_db"],
            database="test",
            port=4000
        )
        return conn
    except mysql.connector.Error as err:
        if err.errno == 2003:
            st.error("⚠️ No se pudo conectar al servidor TiDB Cloud.")
            st.info("💡 **Posible causa:** Tu IP actual no está autorizada. Ve a la consola de TiDB > Clusters > Connect > IP Access y agrega tu IP (o 0.0.0.0/0 para pruebas).")
        else:
            st.error(f"Error de conexión a la base de datos: {err}")
        return None
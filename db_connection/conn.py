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
        if err.errno == 2003 or "No address associated with hostname" in str(err):
            st.warning("⚠️ No se puede conectar a la base de datos externa.")
            st.info("💡 **Nota:** Si usas InfinityFree, recuerda que **bloquean conexiones externas**. Necesitas un proveedor como TiDB Cloud o Aiven que permita acceso remoto.")
        else:
            st.error(f"Error de conexión a la base de datos: {err}")
        return None
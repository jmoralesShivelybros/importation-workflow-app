import streamlit as st
import pandas as pd
from datetime import datetime
from db_connection.conn import get_db_connection

def init_auto_db():
    """Inicializa la tabla de registros de vehículos si no existe."""
    conn = get_db_connection()
    if not conn: return
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicle_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                fecha DATE,
                hora_inicio TIME,
                km_inicio INT,
                inspeccion TEXT,
                fecha_retorno DATE,
                hora_retorno TIME,
                km_terminar INT,
                tanque_lleno VARCHAR(10),
                destino VARCHAR(255),
                usuario VARCHAR(100),
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    finally:
        conn.close()

def render_auto_page(folder_manager, week_num):
    st.header("Formulario Automóvil")
    
    # Inicializar DB
    init_auto_db()

    with st.form("form_vehiculo", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # Fecha automática (se guarda como objeto date)
            current_date = datetime.now().date()
            fecha = st.date_input("Fecha", value=current_date, disabled=True)
            hora_inicio = st.time_input("Hora de Inicio")
            km_inicio = st.number_input("Kilómetros al Inicio", min_value=0, step=1)
            inspeccion = st.text_area("Inspección del Vehículo")

        with col2:
            fecha_retorno = st.date_input("Fecha de Retorno")
            hora_retorno = st.time_input("Hora del Retorno")
            km_terminar = st.number_input("Kilómetros al Terminar", min_value=0, step=1)
            tanque_lleno = st.radio("Tanque Lleno", ("Sí", "No"))

        destino = st.text_input("Destino o Razón de Viaje")
        usuario = st.text_input("Usuario")

        submitted = st.form_submit_button("Registrar Uso de Vehículo", type="primary", use_container_width=True)

        if submitted:
            if not destino or not usuario:
                st.error("Por favor, completa los campos de Destino y Usuario.")
            else:
                # Preparar datos para la BD
                new_log = {
                    "fecha": fecha,
                    "hora_inicio": hora_inicio,
                    "km_inicio": km_inicio,
                    "inspeccion": inspeccion,
                    "fecha_retorno": fecha_retorno,
                    "hora_retorno": hora_retorno,
                    "km_terminar": km_terminar,
                    "tanque_lleno": tanque_lleno,
                    "destino": destino,
                    "usuario": usuario
                }
                
                if save_to_db(new_log):
                    st.success("✅ Registro guardado correctamente en la base de datos.")
                else:
                    st.error("❌ Hubo un error al conectar con la base de datos.")

    # --- Sección de Visualización de Registros ---
    st.divider()
    st.subheader(f"Registros de {datetime.now().strftime('%B %Y')}")
    df_logs = get_month_logs()
    if df_logs is not None and not df_logs.empty:
        st.dataframe(df_logs, use_container_width=True, hide_index=True)
    else:
        st.info("No se encontraron registros para el mes actual.")

def save_to_db(data):
    """Inserta los datos del formulario en la tabla vehicle_logs."""
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO vehicle_logs 
            (fecha, hora_inicio, km_inicio, inspeccion, fecha_retorno, hora_retorno, km_terminar, tanque_lleno, destino, usuario)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            data['fecha'], data['hora_inicio'], data['km_inicio'], data['inspeccion'],
            data['fecha_retorno'], data['hora_retorno'], data['km_terminar'],
            data['tanque_lleno'], data['destino'], data['usuario']
        )
        cursor.execute(query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"Error en save_to_db: {e}")
        return False
    finally:
        conn.close()

def get_month_logs():
    """Obtiene los registros del mes actual de la base de datos."""
    conn = get_db_connection()
    if not conn: return None
    try:
        # Consulta filtrando por el mes y año actual (usando funciones nativas de MySQL)
        query = """
            SELECT fecha, hora_inicio, km_inicio, destino, usuario, fecha_retorno, hora_retorno, km_terminar, tanque_lleno, inspeccion
            FROM vehicle_logs 
            WHERE MONTH(fecha) = MONTH(CURDATE()) 
            AND YEAR(fecha) = YEAR(CURDATE())
            ORDER BY fecha DESC, id DESC
        """
        return pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"Error al obtener logs: {e}")
        return None
    finally:
        conn.close()
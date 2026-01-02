import streamlit as st
import pandas as pd
import os
from datetime import datetime
import time
import uuid
from db_connection.conn import get_db_connection # Importar la función centralizada

try:
    from almacen.control_almacen import inicializar_db, agregar_registro_diario, obtener_historial_diario
except ImportError:
    inicializar_db = None
    agregar_registro_diario = None
    obtener_historial_diario = None

# --- Constantes ---
PROGRAMAS = ["Genv danna", "Edu prismaticos Dianei", "CSS erika", "Edu engranes Mayela", "Otro"]
ESTATUS_OPCIONES = ["Recibido", "En Mesa/Clasificado", "Etiquetado", "En proceso de entrega", "Entregado a Planta"]
ALMACENISTAS = ["Jorge", "Fernando", "Prettel"]

def init_db():
    """Inicializa la base de datos y las tablas si no existen."""
    conn = get_db_connection()
    if not conn: return # Si la conexión falla, no hacer nada
    cursor = conn.cursor()
    
    # Tabla de inventario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id VARCHAR(50) PRIMARY KEY,
            pc VARCHAR(50),
            proveedor VARCHAR(100),
            factura VARCHAR(50),
            consecutivo VARCHAR(50),
            programa VARCHAR(100),
            numero_parte VARCHAR(50),
            descripcion TEXT,
            cantidad DECIMAL(10,2),
            precio_unitario DECIMAL(10,2),
            valor_total DECIMAL(10,2),
            estatus VARCHAR(50),
            fecha_entrada DATETIME,
            ultima_actualizacion DATETIME
        )
    ''')
    
    # Tabla de logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME,
            item_id VARCHAR(50),
            accion VARCHAR(50),
            detalle TEXT,
            usuario VARCHAR(100)
        )
    ''')
    
    # Tabla de rutas (NUEVO)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME,
            destino VARCHAR(255),
            vehiculo VARCHAR(255),
            usuario VARCHAR(100),
            estatus VARCHAR(50) DEFAULT 'En Tránsito'
        )
    ''')
    
    # Tabla de relación items-ruta (NUEVO)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS route_items (
            route_id INT,
            item_id VARCHAR(50)
        )
    ''')
    
    # --- MIGRACIONES (Actualizar tablas existentes si faltan columnas) ---
    # Intentamos agregar las columnas nuevas. Si fallan es porque ya existen.
    try:
        cursor.execute("ALTER TABLE routes ADD COLUMN usuario VARCHAR(100)")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE inventory ADD COLUMN usuario_recepcion VARCHAR(100)")
    except Exception:
        pass
    try:
        # Asegurar que el ID sea AUTO_INCREMENT si no lo era
        cursor.execute("ALTER TABLE routes MODIFY id INT AUTO_INCREMENT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE routes ADD COLUMN estatus VARCHAR(50) DEFAULT 'En Tránsito'")
    except Exception:
        pass

    conn.commit()
    conn.close()

def load_data():
    """Carga el inventario desde MySQL."""
    conn = get_db_connection()
    if not conn: return pd.DataFrame() # Devuelve un DF vacío si no hay conexión
    try:
        df = pd.read_sql_query("SELECT * FROM inventory", conn)
    except Exception:
        df = pd.DataFrame(columns=[
            "id", "pc", "proveedor", "factura", "consecutivo", "programa",
            "numero_parte", "descripcion", "cantidad", "precio_unitario", "valor_total",
            "estatus", "fecha_entrada", "ultima_actualizacion"
        ])
    finally:
        conn.close()
    return df

def log_movement(item_id, accion, detalle, usuario="Almacenista"):
    """Registra un movimiento en la tabla de logs."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    if not conn: return # Si la conexión falla, no hacer nada
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO logs (timestamp, item_id, accion, detalle, usuario)
        VALUES (%s, %s, %s, %s, %s)
    ''', (timestamp, item_id, accion, detalle, usuario))
    conn.commit()
    conn.close()

def render_warehouse_page(folder_manager, section="Recepción de Material"):
    st.header(f"🏭 Almacén: {section}")

    # Inicializar DB (crear tablas si no existen)
    init_db()

    # Cargar datos
    df_inventory = load_data()

    # --- SECCIÓN: RECEPCIÓN DE MATERIAL ---
    if section == "Recepción de Material":
        st.subheader("Registro de Entrada (PC Shively)")
        
        # Selección de usuario
        col_u1, _ = st.columns([1, 3])
        with col_u1:
            usuario_recepcion = st.selectbox("Recibido por:", options=ALMACENISTAS, key="user_recepcion")

        col1, col2 = st.columns(2)
        with col1:
            pc_number = st.text_input("Número de PC (Pedido de Compra):", placeholder="Ej: PC123")
            invoice_number = st.text_input("Factura del Proveedor:", placeholder="Ej: F-998877")
        
        with col2:
            consecutivo = st.text_input("Número Consecutivo (Etiqueta Blanca):", placeholder="Ej: 20005")
            programa = st.selectbox("Programa / Destino:", options=PROGRAMAS)

        st.markdown("### Detalles de los Artículos (Tabla de la PC)")
        st.info("Ingresa los ítems que vienen en la tabla de la PC (Code, Description, Qty, Unit Price).")

        # Editor de datos para ingresar múltiples líneas de la PC
        if 'items_entry' not in st.session_state:
            st.session_state.items_entry = pd.DataFrame(columns=["Code (PT)", "Description", "Qty", "Unit Price"])

        edited_items = st.data_editor(
            st.session_state.items_entry,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_recepcion"
        )

        if st.button("Registrar Entrada", type="primary", use_container_width=True):
            if not pc_number or not invoice_number or edited_items.empty:
                st.error("Por favor completa el PC, Factura y agrega al menos un artículo.")
            else:
                new_rows = []
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                for index, row in edited_items.iterrows():
                    # Validar fila vacía
                    if not row["Code (PT)"] or not row["Qty"]:
                        continue

                    qty = float(row["Qty"]) if row["Qty"] else 0
                    price = float(row["Unit Price"]) if row["Unit Price"] else 0
                    
                    new_row = {
                        "id": str(uuid.uuid4())[:8], # ID corto único
                        "pc": pc_number,
                        "proveedor": "Shively Bros", # Siempre es Shively según requerimiento
                        "factura": invoice_number,
                        "consecutivo": consecutivo,
                        "programa": programa,
                        "numero_parte": row["Code (PT)"],
                        "descripcion": row["Description"],
                        "cantidad": qty,
                        "precio_unitario": price,
                        "valor_total": qty * price,
                        "estatus": "Recibido",
                        "fecha_entrada": timestamp,
                        "ultima_actualizacion": timestamp,
                        "usuario_recepcion": usuario_recepcion
                    }
                    new_rows.append(new_row)
                    # Log
                    log_movement(new_row["id"], "ENTRADA", f"Recepción PC: {pc_number}, PT: {row['Code (PT)']}", usuario=usuario_recepcion)

                if new_rows:
                    # Insertar en base de datos
                    conn = get_db_connection()
                    if not conn: return # Salir si no hay conexión
                    cursor = conn.cursor()
                    cursor.executemany('''
                        INSERT INTO inventory (
                            id, pc, proveedor, factura, consecutivo, programa, 
                            numero_parte, descripcion, cantidad, precio_unitario, 
                            valor_total, estatus, fecha_entrada, ultima_actualizacion,
                            usuario_recepcion
                        ) VALUES (
                            %(id)s, %(pc)s, %(proveedor)s, %(factura)s, %(consecutivo)s, %(programa)s, 
                            %(numero_parte)s, %(descripcion)s, %(cantidad)s, %(precio_unitario)s, 
                            %(valor_total)s, %(estatus)s, %(fecha_entrada)s, %(ultima_actualizacion)s,
                            %(usuario_recepcion)s
                        )
                    ''', new_rows)
                    conn.commit()
                    conn.close()
                    
                    st.success(f"✅ Se registraron {len(new_rows)} artículos correctamente.")
                    # Limpiar el editor reiniciando el estado
                    st.session_state.items_entry = pd.DataFrame(columns=["Code (PT)", "Description", "Qty", "Unit Price"])
                    time.sleep(1)
                    st.rerun()

    # --- SECCIÓN: GESTIÓN Y ESTATUS ---
    elif section == "Gestión y Rutas":
        st.subheader("Gestión de Materiales y Rutas de Salida")
        
        # Definición explícita de las 3 pestañas para asegurar que se muestren
        tabs_list = ["📦 Crear Nueva Ruta", "🚚 Rutas Activas", "🏁 Rutas Terminadas"]
        tab_crear, tab_activas, tab_terminadas = st.tabs(tabs_list)

        with tab_crear:
            # Filtros
            filtro_estatus = st.multiselect("Filtrar por Estatus:", options=ESTATUS_OPCIONES, default=["Recibido"], key="filtro_estatus_crear")
            
            # Filtrar datos
            if filtro_estatus:
                df_view = df_inventory[df_inventory["estatus"].isin(filtro_estatus)]
            else:
                df_view = df_inventory

            st.write(f"Mostrando {len(df_view)} registros.")
            st.info("💡 **Modo Ruta:** Selecciona varios materiales en la tabla (casillas a la izquierda) para procesar su salida o cambio de estatus en grupo.")
            
            # Tabla con selección activada
            event = st.dataframe(
                df_view[["id", "pc", "numero_parte", "descripcion", "programa", "estatus", "consecutivo"]],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row"
            )

            selected_rows = event.selection.rows
            
            if selected_rows:
                st.divider()
                st.markdown(f"### 🚚 Generar Ruta / Actualización Masiva")
                
                # Obtener items seleccionados
                selected_df = df_view.iloc[selected_rows]
                
                st.write(f"Has seleccionado **{len(selected_df)} materiales** para mover.")
                with st.expander("Ver detalles de la selección", expanded=False):
                    st.dataframe(selected_df[["pc", "numero_parte", "descripcion", "estatus"]], use_container_width=True)

                # Campos para la ruta
                st.markdown("#### 📍 Datos de la Ruta (Opcional)")
                col_r1, col_r2, col_r3 = st.columns(3)
                with col_r1:
                    destino_ruta = st.text_input("Destino / Planta:", placeholder="Ej. Planta Ramos")
                with col_r2:
                    vehiculo_ruta = st.text_input("Vehículo:", placeholder="Ej. Nissan NP300")
                with col_r3:
                    usuario_ruta = st.selectbox("Responsable de Ruta:", options=ALMACENISTAS, key="user_ruta")

                col_act1, col_act2 = st.columns([2, 1])
                with col_act1:
                    new_status = st.selectbox("Nuevo Estatus para la selección:", options=ESTATUS_OPCIONES, index=3, key="bulk_status_select") # Index 3 es "En proceso de entrega"
                
                with col_act2:
                    st.write("")
                    st.write("")
                    if st.button("✅ Procesar Ruta", type="primary", use_container_width=True):
                        ids_to_update = selected_df["id"].tolist()
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()
                            
                            # 0. Crear Ruta si hay datos (Destino, Vehículo o si se seleccionó un chofer diferente al default)
                            route_info_str = "" # Inicializar variable para evitar error si no se entra al if
                            if destino_ruta or vehiculo_ruta:
                                cursor.execute('''
                                    INSERT INTO routes (timestamp, destino, vehiculo, usuario, estatus)
                                    VALUES (%s, %s, %s, %s, 'En Tránsito')
                                ''', (timestamp, destino_ruta, vehiculo_ruta, usuario_ruta))
                                route_id = cursor.lastrowid
                                route_info_str = f" | Ruta #{route_id}: {destino_ruta} ({vehiculo_ruta})"
                                
                                # Asociar items a la ruta
                                route_items_data = [(route_id, item_id) for item_id in ids_to_update]
                                cursor.executemany('''
                                    INSERT INTO route_items (route_id, item_id) VALUES (%s, %s)
                                ''', route_items_data)

                            # 1. Actualizar Inventario (Bulk Update)
                            # Generar placeholders para la cláusula IN (%s, %s, ...)
                            placeholders = ', '.join(['%s'] * len(ids_to_update))
                            query = f"UPDATE inventory SET estatus = %s, ultima_actualizacion = %s WHERE id IN ({placeholders})"
                            params = [new_status, timestamp] + ids_to_update
                            
                            cursor.execute(query, params)
                            
                            # 2. Registrar Logs (Bulk Insert)
                            log_entries = []
                            for item_id in ids_to_update:
                                log_entries.append((timestamp, item_id, "CAMBIO_ESTATUS_MASIVO", f"Cambio a '{new_status}'{route_info_str}", usuario_ruta))
                                
                            cursor.executemany('''
                                INSERT INTO logs (timestamp, item_id, accion, detalle, usuario)
                                VALUES (%s, %s, %s, %s, %s)
                            ''', log_entries)
                            
                            conn.commit()
                            conn.close()
                            
                            st.success(f"✅ Se actualizaron {len(ids_to_update)} ítems a '{new_status}' correctamente.")
                            time.sleep(1.5)
                            st.rerun()
            else:
                st.caption("👈 Selecciona uno o más ítems en la tabla para ver las opciones de ruta.")

        with tab_activas:
            st.markdown("### 🚚 Rutas en Curso")
            st.caption("Aquí puedes ver las rutas activas y marcarlas como completadas cuando el vehículo regrese o se confirme la entrega.")
            
            conn = get_db_connection()
            if conn:
                try:
                    # Consultar rutas activas (no completadas)
                    query_routes = """
                        SELECT id, timestamp, destino, vehiculo, usuario 
                        FROM routes 
                        WHERE estatus IS NULL OR estatus != 'Completada'
                        ORDER BY timestamp DESC
                    """
                    df_active_routes = pd.read_sql_query(query_routes, conn)
                    
                    if not df_active_routes.empty:
                        for index, route in df_active_routes.iterrows():
                            # Formatear fecha
                            try:
                                fecha_str = pd.to_datetime(route['timestamp']).strftime("%m/%d/%Y %I:%M %p")
                            except:
                                fecha_str = str(route['timestamp'])

                            with st.container(border=True):
                                c1, c2, c3 = st.columns([3, 1, 1])
                                with c1:
                                    st.markdown(f"**Ruta #{route['id']}** | 📍 {route['destino']}")
                                    st.caption(f"🚛 {route['vehiculo']} | 👤 {route['usuario']} | 🕒 Salida: {fecha_str}")
                                
                                # Consultar items de esta ruta
                                query_items = f"""
                                    SELECT i.pc, i.numero_parte, i.descripcion, i.cantidad, i.estatus 
                                    FROM route_items ri
                                    JOIN inventory i ON ri.item_id = i.id
                                    WHERE ri.route_id = {route['id']}
                                """
                                df_route_items = pd.read_sql_query(query_items, conn)
                                
                                with c2:
                                    st.metric("Items", len(df_route_items))
                                
                                with c3:
                                    # Botón grande para terminar ruta
                                    if st.button("✅ Terminar Ruta", key=f"btn_finish_{route['id']}", use_container_width=True, type="primary"):
                                        cursor = conn.cursor()
                                        timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        
                                        # 1. Marcar ruta como completada
                                        cursor.execute("UPDATE routes SET estatus = 'Completada' WHERE id = %s", (route['id'],))
                                        
                                        # 2. Actualizar items a "Entregado a Planta"
                                        cursor.execute("""
                                            UPDATE inventory i 
                                            JOIN route_items ri ON i.id = ri.item_id 
                                            SET i.estatus = 'Entregado a Planta', i.ultima_actualizacion = %s
                                            WHERE ri.route_id = %s
                                        """, (timestamp_now, route['id']))
                                        
                                        # 3. Log de cierre
                                        cursor.execute("""
                                            INSERT INTO logs (timestamp, item_id, accion, detalle, usuario)
                                            VALUES (%s, %s, %s, %s, %s)
                                        """, (timestamp_now, f"RUTA-{route['id']}", "RUTA_COMPLETADA", f"Ruta #{route['id']} finalizada.", route['usuario']))
                                        
                                        conn.commit()
                                        st.toast(f"Ruta #{route['id']} completada exitosamente.")
                                        time.sleep(1)
                                        st.rerun()
                                
                                with st.expander("Ver contenido de la carga"):
                                    st.dataframe(df_route_items, use_container_width=True)
                    else:
                        st.info("✅ No hay rutas pendientes. Todo ha sido entregado o no hay salidas activas.")
                
                except Exception as e:
                    st.error(f"Error al cargar rutas activas: {e}")
                finally:
                    conn.close()

        with tab_terminadas:
            st.markdown("### 🏁 Historial de Rutas Terminadas")
            
            if st.button("🔄 Actualizar Historial", key="refresh_hist"):
                st.rerun()
            
            # --- Filtros ---
            with st.container(border=True):
                st.markdown("#### 🔍 Filtros de Búsqueda")
                col_f1, col_f2, col_f3 = st.columns(3)
                with col_f1:
                    search_material = st.text_input("📦 Material (PT o Descripción):", key="hist_search_mat", placeholder="Ej. 12345")
                with col_f2:
                    filter_user = st.selectbox("👤 Almacenista:", options=["Todos"] + ALMACENISTAS, key="hist_filter_user")
                with col_f3:
                    enable_date = st.checkbox("Filtrar por Fecha", key="hist_enable_date")
                    filter_date = st.date_input("Fecha", label_visibility="collapsed", key="hist_date_val") if enable_date else None

            # --- Paginación y Consulta ---
            ITEMS_PER_PAGE = 15
            if 'hist_page' not in st.session_state:
                st.session_state.hist_page = 1

            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    
                    # Construcción de Query Dinámica
                    base_query = "FROM routes r"
                    where_clauses = ["r.estatus = 'Completada'"]
                    params = []

                    # Filtro Material (requiere JOIN)
                    if search_material:
                        base_query += " JOIN route_items ri ON r.id = ri.route_id JOIN inventory i ON ri.item_id = i.id"
                        where_clauses.append("(i.numero_parte LIKE %s OR i.descripcion LIKE %s)")
                        params.extend([f"%{search_material}%", f"%{search_material}%"])
                    
                    # Filtro Usuario
                    if filter_user and filter_user != "Todos":
                        where_clauses.append("r.usuario = %s")
                        params.append(filter_user)
                    
                    # Filtro Fecha
                    if filter_date:
                        where_clauses.append("DATE(r.timestamp) = %s")
                        params.append(filter_date)

                    where_str = " WHERE " + " AND ".join(where_clauses)

                    # 1. Contar total de registros (para paginación)
                    count_query = f"SELECT COUNT(DISTINCT r.id) {base_query} {where_str}"
                    cursor.execute(count_query, tuple(params))
                    total_routes = cursor.fetchone()[0]
                    total_pages = (total_routes + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
                    
                    # Validar página actual
                    if st.session_state.hist_page > total_pages:
                        st.session_state.hist_page = max(1, total_pages)
                    
                    # 2. Consultar datos paginados
                    offset = (st.session_state.hist_page - 1) * ITEMS_PER_PAGE
                    data_query = f"""
                        SELECT DISTINCT r.id, r.timestamp, r.destino, r.vehiculo, r.usuario 
                        {base_query} 
                        {where_str} 
                        ORDER BY r.timestamp DESC 
                        LIMIT {ITEMS_PER_PAGE} OFFSET {offset}
                    """
                    
                    # Usamos pandas para traer los resultados de la página
                    df_routes_hist = pd.read_sql_query(data_query, conn, params=tuple(params))
                    
                    # --- Controles de Paginación ---
                    col_p1, col_p2, col_p3 = st.columns([1, 3, 1])
                    with col_p1:
                        if st.button("◀ Anterior", disabled=st.session_state.hist_page <= 1, key="btn_prev_hist"):
                            st.session_state.hist_page -= 1
                            st.rerun()
                    with col_p2:
                        st.markdown(f"<div style='text-align: center; padding-top: 5px;'><b>Página {st.session_state.hist_page} de {max(1, total_pages)}</b> (Total: {total_routes} rutas)</div>", unsafe_allow_html=True)
                    with col_p3:
                        if st.button("Siguiente ▶", disabled=st.session_state.hist_page >= total_pages, key="btn_next_hist"):
                            st.session_state.hist_page += 1
                            st.rerun()
                    
                    st.divider()

                    # --- Mostrar Resultados ---
                    if not df_routes_hist.empty:
                        for index, route in df_routes_hist.iterrows():
                            # Formatear fecha
                            try:
                                fecha_str = pd.to_datetime(route['timestamp']).strftime("%d/%m/%Y %I:%M %p")
                            except:
                                fecha_str = str(route['timestamp'])

                            with st.expander(f"✅ Ruta #{route['id']} | {route['destino']} ({fecha_str})"):
                                c1, c2 = st.columns([3, 1])
                                with c1:
                                    st.caption(f"🚛 Vehículo: **{route['vehiculo']}** | 👤 Responsable: **{route['usuario']}**")
                                
                                # Consultar items de esta ruta específica
                                query_items = f"""
                                    SELECT i.pc, i.numero_parte, i.descripcion, i.cantidad, i.estatus 
                                    FROM route_items ri
                                    JOIN inventory i ON ri.item_id = i.id
                                    WHERE ri.route_id = {route['id']}
                                """
                                df_items = pd.read_sql_query(query_items, conn)
                                st.dataframe(df_items, use_container_width=True)
                    else:
                        st.info("No se encontraron rutas terminadas con los criterios seleccionados.")

                except Exception as e:
                    st.error(f"Error al cargar historial de rutas: {e}")
                finally:
                    conn.close()
            else:
                st.error("⚠️ No hay conexión con la base de datos. No se puede cargar el historial.")

    # --- SECCIÓN: MONITOR TV ---
    elif section == "Monitor TV":
        st.markdown("### 📺 Monitor de Rutas y Salidas")
        
        auto_refresh = st.checkbox("🔄 Auto-refrescar (Modo TV)", value=False)
        
        # Métricas Generales
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("En Recepción", len(df_inventory[df_inventory["estatus"] == "Recibido"]))
        m2.metric("En Mesa", len(df_inventory[df_inventory["estatus"] == "En Mesa/Clasificado"]))
        m3.metric("Por Entregar", len(df_inventory[df_inventory["estatus"] == "Etiquetado"]))
        total_inventario = df_inventory["cantidad"].sum() if not df_inventory.empty else 0
        m4.metric("Total Inventario", f"{total_inventario:,.0f}")

        st.divider()

        # --- VISTA POR RUTAS ---
        conn = get_db_connection()
        if conn:
            try:
                # Consultar rutas y sus items uniendo las 3 tablas
                query = """
                    SELECT 
                        r.id as route_id,
                        r.timestamp,
                        r.destino,
                        r.vehiculo,
                        r.usuario,
                        i.pc,
                        i.numero_parte,
                        i.descripcion,
                        i.cantidad,
                        i.estatus
                    FROM routes r
                    JOIN route_items ri ON r.id = ri.route_id
                    JOIN inventory i ON ri.item_id = i.id
                    WHERE (r.estatus != 'Completada' OR r.estatus IS NULL) 
                       OR (r.estatus = 'Completada' AND DATE(r.timestamp) = CURDATE())
                    ORDER BY r.timestamp DESC
                    LIMIT 50
                """
                df_routes = pd.read_sql_query(query, conn)
                conn.close()

                if not df_routes.empty:
                    st.markdown("#### 🚚 Rutas en Tránsito / Recientes")
                    
                    # Agrupar por ID de ruta para mostrar una tarjeta por ruta
                    unique_routes = df_routes['route_id'].unique()
                    
                    for r_id in unique_routes:
                        # Filtrar items que pertenecen a esta ruta específica
                        items_ruta = df_routes[df_routes['route_id'] == r_id]
                        info_ruta = items_ruta.iloc[0]
                        
                        # Formatear fecha a Mes/Día/Año
                        try:
                            fecha_str = pd.to_datetime(info_ruta['timestamp']).strftime("%m/%d/%Y %I:%M %p")
                        except:
                            fecha_str = str(info_ruta['timestamp'])
                        
                        with st.container(border=True):
                            # Encabezado de la Ruta
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                st.subheader(f"📍 Ruta #{r_id} | {info_ruta['destino']}")
                                st.caption(f"🚛 Vehículo: {info_ruta['vehiculo']} | 👤 Responsable: {info_ruta['usuario']} | 🕒 Salida Aprox: {fecha_str}")
                            with c2:
                                st.metric("Items", len(items_ruta))
                            
                            # Tabla de items dentro de la ruta
                            st.dataframe(
                                items_ruta[["pc", "numero_parte", "descripcion", "cantidad", "estatus"]],
                                use_container_width=True,
                                hide_index=True
                            )
                else:
                    st.info("No hay rutas registradas recientemente.")
            except Exception as e:
                st.error(f"Error al cargar rutas: {e}")
                if conn: conn.close()

        # Lógica de Auto-refresco
        if auto_refresh:
            time.sleep(10) # Refrescar cada 10 segundos
            st.rerun()

    # --- SECCIÓN: HISTORIAL ---
    elif section == "Historial":
        st.header("📚 Historial y Bitácora")

        # --- 1. BITÁCORA DIARIA (EXCEL REPLICA) ---
        if inicializar_db is None:
            st.error("⚠️ El módulo 'sqlalchemy' no está instalado o falló su carga.")
            st.info("Por favor instala el paquete ejecutando: `pip install sqlalchemy`")
            return

        st.subheader("📋 Bitácora Diaria (Registro Manual)")
        
        # Inicializar DB y Sesión
        Session = inicializar_db()
        session = Session()

        # Formulario para agregar registros
        with st.expander("➕ Agregar Nuevo Registro a Bitácora", expanded=False):
            with st.form("form_bitacora"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    factura = st.text_input("Factura")
                    fecha = st.date_input("Fecha", datetime.today())
                    n_bc = st.text_input("N BC")
                    proveedor = st.text_input("Proveedor")
                    shipper = st.text_input("Shipper")
                with c2:
                    customer = st.text_input("Customer")
                    recepcion = st.text_input("Recep")
                    remision = st.text_input("Remisión")
                    status = st.selectbox("Status", ["Pendiente", "Revisado", "Entregado", "Cancelado"])
                    nombre = st.text_input("Nombre")
                with c3:
                    cantidad = st.number_input("Cantidad", min_value=0.0, step=0.01)
                    descripcion = st.text_area("Descripción", height=100)
                    comentarios = st.text_area("Comentarios", height=100)
                
                if st.form_submit_button("💾 Guardar Registro"):
                    datos = {
                        "factura": factura, "fecha": fecha, "n_bc": n_bc, "descripcion": descripcion,
                        "cantidad": cantidad, "proveedor": proveedor, "shipper": shipper,
                        "customer": customer, "recepcion": recepcion, "remision": remision,
                        "status": status, "comentarios": comentarios, "nombre": nombre
                    }
                    agregar_registro_diario(session, datos)
                    st.success("Registro guardado exitosamente.")
                    time.sleep(1)
                    st.rerun()

        # Tabla de Registros Diarios
        registros = obtener_historial_diario(session)
        if registros:
            df_diario = pd.DataFrame([r.to_dict() for r in registros])
            st.dataframe(df_diario, use_container_width=True)
        else:
            st.info("No hay registros en la bitácora diaria.")
        
        session.close()

        st.divider()
        
        # --- 2. HISTORIAL DE TRAZABILIDAD (SISTEMA) ---
        st.subheader("🔍 Historial de Trazabilidad (Sistema)")
        st.caption("Movimientos automáticos registrados por el sistema.")
        
        conn = get_db_connection()
        if not conn: return # Salir si no hay conexión
        try:
            df_log = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 10", conn)
        except Exception:
            df_log = pd.DataFrame()
        conn.close()

        if not df_log.empty:
            # Formatear fecha a Mes/Día/Año
            if 'timestamp' in df_log.columns:
                try:
                    df_log['timestamp'] = pd.to_datetime(df_log['timestamp']).dt.strftime('%m/%d/%Y %I:%M %p')
                except:
                    pass
            st.dataframe(df_log, use_container_width=True)
            
            # Botón para descargar historial
            csv = df_log.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Descargar Historial Completo (CSV)",
                csv,
                "historial_almacen.csv",
                "text/csv",
                key='download-csv'
            )
        else:
            st.info("Aún no hay historial registrado.")
    else:
        st.warning(f"⚠️ Sección desconocida: '{section}'. Verifica que el nombre en el menú coincida con 'Gestión y Rutas'.")
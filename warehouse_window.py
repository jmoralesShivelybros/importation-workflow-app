import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import time
import uuid
from db_connection.conn import get_db_connection # Importar la función centralizada
import numpy as np
import mysql.connector

# --- Constantes ---
PROGRAMAS = ["Genv Diego", "Edu prismaticos Dianei", "CSS Erika", "Edu engranes Mayela", "Ventas Directas","Otro"]
ESTATUS_OPCIONES = ["Recibido", "En Mesa/Clasificado", "Etiquetado", "En proceso de entrega", "Entregado a Planta"]
ALMACENISTAS = ["Fernando Gomez", "Nahum Prettel", "Juan Hinojosa", "Administrador Javier morales"]

def ensure_sequencing(df):
    """Asegura que la columna 'No.' sea secuencial y esté al inicio."""
    if df is None: return df
    cols = [c for c in df.columns if c != "No."]
    new_df = df[cols].copy()
    new_df.insert(0, "No.", range(1, len(new_df) + 1))
    return new_df

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
            ultima_actualizacion DATETIME,
            shipper VARCHAR(100),
            usuario_recepcion VARCHAR(100)
        )
    ''')

    # Tabla de bitácora diaria (Aseguramos su creación al inicio)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pc VARCHAR(100),
            factura VARCHAR(100),
            fecha DATE,
            n_bc VARCHAR(100),
            numero_parte VARCHAR(100),
            descripcion TEXT,
            cantidad DECIMAL(10,2),
            proveedor VARCHAR(150),
            shipper VARCHAR(100),
            customer VARCHAR(150),
            recepcion VARCHAR(100),
            remision VARCHAR(100),
            status VARCHAR(50),
            comentarios TEXT,
            nombre VARCHAR(150),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            inventory_item_id VARCHAR(50)
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
    
    # --- MIGRACIONES ROBUSTAS PARA MYSQL ---
    def column_exists(table, column):
        cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
        return cursor.fetchone() is not None

    # --- MIGRACIONES ROBUSTAS PARA MYSQL ---
    def column_exists(table, column):
        cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
        return cursor.fetchone() is not None

    if not column_exists('routes', 'usuario'): cursor.execute("ALTER TABLE routes ADD COLUMN usuario VARCHAR(100)")
    if not column_exists('inventory', 'usuario_recepcion'): cursor.execute("ALTER TABLE inventory ADD COLUMN usuario_recepcion VARCHAR(100)")
    if not column_exists('inventory', 'shipper'): cursor.execute("ALTER TABLE inventory ADD COLUMN shipper VARCHAR(100)")

    try: cursor.execute("ALTER TABLE routes MODIFY id INT AUTO_INCREMENT")
    except: pass

    if not column_exists('routes', 'estatus'): cursor.execute("ALTER TABLE routes ADD COLUMN estatus VARCHAR(50) DEFAULT 'En Tránsito'")
    if not column_exists('daily_logs', 'numero_parte'): cursor.execute("ALTER TABLE daily_logs ADD COLUMN numero_parte VARCHAR(100)")
    if not column_exists('daily_logs', 'inventory_item_id'): cursor.execute("ALTER TABLE daily_logs ADD COLUMN inventory_item_id VARCHAR(50)")
    if not column_exists('daily_logs', 'pc'): 
        try: cursor.execute("ALTER TABLE daily_logs ADD COLUMN pc VARCHAR(100)")
        except: pass

    try:
        conn.commit()
    except Exception:
        # En MySQL, el DDL (CREATE/ALTER) hace commit automático.
        # Si falla el commit manual aquí, es probable que los cambios ya estén aplicados.
        pass
    finally:
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
            "estatus", "fecha_entrada", "ultima_actualizacion", "shipper"
        ])
    finally:
        conn.close()
    return df

def get_known_descriptions():
    """Obtiene un diccionario de mapeo {numero_parte/BC: descripcion} desde el inventario existente."""
    conn = get_db_connection()
    mapping = {}
    if not conn:
        return mapping
    try:
        cursor = conn.cursor()
        # Buscamos combinaciones únicas de número de parte y descripción
        cursor.execute("SELECT DISTINCT numero_parte, descripcion FROM inventory WHERE numero_parte IS NOT NULL AND numero_parte != ''")
        for (np, desc) in cursor.fetchall():
            if np and desc:
                mapping[str(np).strip()] = str(desc).strip()
    finally:
        conn.close()
    return mapping

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

    # Inicializar DB solo una vez por sesión para evitar saturar la conexión
    if 'db_initialized' not in st.session_state:
        init_db()
        st.session_state.db_initialized = True

    # Inicializar contador de iteración para resetear formularios
    if 'form_iter' not in st.session_state:
        st.session_state.form_iter = 0

    # Cargar datos
    df_inventory = load_data()

    # --- SECCIÓN: RECEPCIÓN DE MATERIAL ---
    if section == "Recepción de Material":
        tab1, tab2, tab3 = st.tabs(["Entrada a Inventario (Por PC)", "Registro Manual / Venta Directa", "📤 Importar Historial (Excel)"])

        with tab1:
            # --- FORMULARIO DE ENTRADA A INVENTARIO (PC) ---
            st.subheader("Entrada a Inventario (Por PC)")
            usuario_recepcion_pc = st.selectbox("Recibido por:", options=ALMACENISTAS, key="user_recepcion_pc")
            col1, col2 = st.columns(2)
            with col1:
                pc_number = st.text_input("Número de PC (Pedido de Compra):", placeholder="Ej: PC123", key=f"pc_in_{st.session_state.form_iter}")
                invoice_number_pc = st.text_input("Factura del Proveedor:", placeholder="Ej: F-998877", key=f"inv_in_{st.session_state.form_iter}")
            with col2:
                consecutivo_pc = st.text_input("Número Consecutivo (Etiqueta Blanca):", placeholder="Ej: 20005", key=f"cons_in_{st.session_state.form_iter}")
                programa_pc = st.selectbox("Programa / Destino:", options=[p for p in PROGRAMAS if p != "Ventas Directas"], key="programa_pc")

            with st.container(border=True):
                st.markdown("###### Detalles de los Artículos")
                if 'items_entry' not in st.session_state:
                    st.session_state.items_entry = pd.DataFrame(columns=["No.", "No. BC", "Description", "Shipper", "Qty", "Unit Price"])

                # Forzar numeración secuencial antes de mostrar
                st.session_state.items_entry = ensure_sequencing(st.session_state.items_entry)

                # Obtener catálogo de descripciones conocidas
                bc_catalog = get_known_descriptions()

                edited_items = st.data_editor(
                    st.session_state.items_entry,
                    num_rows="dynamic",
                    hide_index=True,
                    width="stretch",
                    key="editor_recepcion",
                    column_config={
                        "No.": st.column_config.NumberColumn("No.", disabled=True, width="small"),
                    }
                )

                # --- LÓGICA DE AUTOCOMPLETADO (PC) ---
                if not edited_items.equals(st.session_state.items_entry):
                    edited_items = ensure_sequencing(edited_items)
                    has_changes = False
                    for idx, row in edited_items.iterrows():
                        bc_val = str(row["No. BC"]).strip() if pd.notna(row["No. BC"]) else ""
                        desc_val = str(row["Description"]).strip() if pd.notna(row["Description"]) else ""
                        
                        if bc_val and not desc_val and bc_val in bc_catalog:
                            edited_items.at[idx, "Description"] = bc_catalog[bc_val]
                            has_changes = True
                    
                    if has_changes:
                        st.session_state.items_entry = edited_items
                        st.rerun()
                    else:
                        st.session_state.items_entry = edited_items

                submitted_pc = st.button("Registrar Entrada de PC", type="primary", use_container_width=True)
        
        with tab2:
            # --- FORMULARIO DE VENTA DIRECTA / MANUAL ---
            st.subheader("Registro Manual / Venta Directa")
            st.info("Use este formulario para ventas directas o material que no sigue una ruta de producción. Agregue múltiples registros en la tabla.")
            
            vd_nombre = st.selectbox("Nombre (Registra)", options=ALMACENISTAS, key="vd_nombre_multi")

            with st.container(border=True):
                if 'items_vd' not in st.session_state:
                    st.session_state.items_vd = pd.DataFrame(columns=["No.", "No. Factura", "PC", "No. BC", "No. Parte (PT)", "Proveedor", "Descripcion", "Comentarios"])

                # Forzar numeración secuencial antes de mostrar
                st.session_state.items_vd = ensure_sequencing(st.session_state.items_vd)

                edited_items_vd = st.data_editor(
                    st.session_state.items_vd,
                    num_rows="dynamic",
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "No.": st.column_config.NumberColumn("No.", disabled=True, width="small"),
                        "Descripcion": st.column_config.TextColumn("Descripción", width="large"),
                        "Comentarios": st.column_config.TextColumn("Comentarios", width="large"),
                    },
                    key="editor_vd"
                )

                # --- LÓGICA DE AUTOCOMPLETADO (Manual/VD) ---
                if not edited_items_vd.equals(st.session_state.items_vd):
                    edited_items_vd = ensure_sequencing(edited_items_vd)
                    bc_catalog = get_known_descriptions()
                    has_changes_vd = False
                    for idx, row in edited_items_vd.iterrows():
                        bc_val = str(row["No. BC"]).strip() if pd.notna(row["No. BC"]) else ""
                        pt_val = str(row["No. Parte (PT)"]).strip() if pd.notna(row["No. Parte (PT)"]) else ""
                        desc_val = str(row["Descripcion"]).strip() if pd.notna(row["Descripcion"]) else ""
                        
                        # Busca por BC o por PT
                        match_key = bc_val if bc_val in bc_catalog else (pt_val if pt_val in bc_catalog else None)
                        
                        if match_key and not desc_val:
                            edited_items_vd.at[idx, "Descripcion"] = bc_catalog[match_key]
                            has_changes_vd = True
                    
                    if has_changes_vd:
                        st.session_state.items_vd = edited_items_vd
                        st.rerun()
                    else:
                        st.session_state.items_vd = edited_items_vd
            
            submitted_vd = st.button("Registrar en Bitácora", use_container_width=True)

        with tab3:
            # --- IMPORTACIÓN MASIVA DESDE EXCEL ---
            st.subheader("Importación Masiva de Recepciones Antiguas")
            
            auth_pwd = st.text_input("🔑 Ingrese la contraseña de autorización:", type="password", key="auth_import_pwd")
            
            if auth_pwd == "0612":
                st.success("Acceso autorizado.")

                # --- BOTÓN PARA VACIAR LA BASE DE DATOS ---
                with st.expander("🛠️ Zona de Peligro: Mantenimiento de Base de Datos"):
                    st.warning("Esta acción eliminará TODOS los registros de inventario, bitácora, rutas y logs. Esta acción no se puede deshacer.")
                    if st.button("🧨 Vaciar TODA la Base de Datos", type="secondary", use_container_width=True):
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()
                            try:
                                # Borramos en orden para evitar problemas de integridad (aunque no hay FK estrictas)
                                cursor.execute("DELETE FROM route_items")
                                cursor.execute("DELETE FROM routes")
                                cursor.execute("DELETE FROM daily_logs")
                                cursor.execute("DELETE FROM inventory")
                                cursor.execute("DELETE FROM logs")
                                conn.commit()
                                st.success("✅ La base de datos ha sido vaciada completamente.")
                                time.sleep(2)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al vaciar la base de datos: {e}")
                            finally:
                                conn.close()
                
                st.divider()
                st.info("Sube un archivo Excel para cargar registros históricos. Se les asignará automáticamente el estatus **'Entregado'**.")
                
                col_imp1, col_imp2 = st.columns(2)
                with col_imp1:
                    import_user = st.selectbox("Usuario que realiza la importación:", options=ALMACENISTAS, key="import_user_name")
                    uploaded_file = st.file_uploader("Selecciona el archivo Excel (.xlsx)", type=["xlsx"], key="excel_importer")
                with col_imp2:
                    # Permitir elegir el estatus inicial para pruebas
                    import_status = st.selectbox("Estatus inicial para estos registros:", options=ESTATUS_OPCIONES + ["Entregado"], index=5, key="import_status_choice")
                
                st.divider()
                with st.expander("📖 Cargar Catálogo Maestro (BC + Descripción)"):
                    st.info("Utilice esta herramienta para cargar masivamente las descripciones asociadas a los números de BC. El Excel debe tener al menos las columnas: **'No. BC'** y **'Description'**.")
                    catalog_file = st.file_uploader("Subir archivo de Catálogo", type=["xlsx"], key="catalog_uploader")
                    
                    if catalog_file:
                        df_cat = pd.read_excel(catalog_file)
                        st.dataframe(df_cat.head(), use_container_width=True)
                        
                        if st.button("📥 Importar Catálogo", type="primary"):
                            conn = get_db_connection()
                            if conn:
                                cursor = conn.cursor()
                                try:
                                    # Mapeo flexible de nombres de columna
                                    def find_col(df, options):
                                        for opt in options:
                                            matches = [c for c in df.columns if opt.lower() in c.lower()]
                                            if matches: return matches[0]
                                        return None

                                    col_bc = find_col(df_cat, ["BC", "parte", "numero", "codigo"])
                                    col_desc = find_col(df_cat, ["desc", "item", "nombre"])

                                    if not col_bc or not col_desc:
                                        st.error(f"No se encontraron columnas de BC o Descripción. Columnas detectadas: {list(df_cat.columns)}")
                                    else:
                                        catalog_records = []
                                        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        
                                        for _, row in df_cat.iterrows():
                                            bc_val = str(row[col_bc]).strip()
                                            desc_val = str(row[col_desc]).strip()
                                            
                                            if bc_val and desc_val and bc_val != "nan" and desc_val != "nan":
                                                catalog_records.append((
                                                    str(uuid.uuid4())[:8], # id
                                                    bc_val,                # numero_parte
                                                    desc_val,              # descripcion
                                                    "CATALOGO",            # estatus
                                                    ts,                    # fecha_entrada
                                                    import_user            # usuario_recepcion
                                                ))
                                        
                                        if catalog_records:
                                            sql = "INSERT INTO inventory (id, numero_parte, descripcion, estatus, fecha_entrada, usuario_recepcion) VALUES (%s, %s, %s, %s, %s, %s)"
                                            cursor.executemany(sql, catalog_records)
                                            conn.commit()
                                            st.success(f"✅ Se han cargado {len(catalog_records)} descripciones al catálogo.")
                                            time.sleep(1.5)
                                            st.rerun()
                                        else:
                                            st.warning("No se encontraron registros válidos para importar.")
                                except Exception as e:
                                    st.error(f"Error al importar catálogo: {e}")
                                finally:
                                    conn.close()

                    st.caption("Nota: 'Entregado' marcará los registros como cerrados históricamente.")
                
                if uploaded_file:
                    try:
                        df_excel = pd.read_excel(uploaded_file)
                        st.write("### Vista previa del archivo")
                        st.dataframe(df_excel.head(), width="stretch")

                        if st.button("🚀 Confirmar e Importar a Bitácora", type="primary", use_container_width=True):
                            with st.spinner("Procesando importación masiva..."):
                                conn = get_db_connection()
                                if conn:
                                    cursor = conn.cursor()
                                    records = []
                                    
                                    # Función auxiliar para buscar columnas con nombres similares (Case Insensitive)
                                    def get_val(row, possible_names):
                                        # Creamos un mapa de columnas en minúsculas para búsqueda flexible
                                        cols_map = {c.lower(): c for c in df_excel.columns}
                                        for name in possible_names:
                                            if name.lower() in cols_map:
                                                val = row[cols_map[name.lower()]]
                                                return val if pd.notna(val) else ""
                                        return ""

                                    for _, row in df_excel.iterrows():
                                        # Procesar fecha para evitar error 1292 (formatos DD/MM/YY y DD/MM/YYYY)
                                        raw_date = get_val(row, ["Fecha", "FECHA", "date"])
                                        try:
                                            if pd.notna(raw_date) and raw_date != "":
                                                # pd.to_datetime con dayfirst=True maneja automáticamente '25' o '2025'
                                                clean_date = pd.to_datetime(raw_date, dayfirst=True).date()
                                            else:
                                                clean_date = datetime.now().date()
                                        except Exception:
                                            clean_date = datetime.now().date()

                                        # Limpieza segura de cantidad para evitar errores como 'yc'
                                        raw_qty = get_val(row, ["Cantidad", "QTY", "qty", "cantidad"])
                                        try:
                                            # Si el valor está vacío o no es un número válido (ej. 'yc'), usamos 0.0
                                            clean_qty = float(raw_qty) if raw_qty != "" else 0.0
                                        except (ValueError, TypeError):
                                            clean_qty = 0.0

                                        # Mapeo flexible de columnas incluyendo la nueva columna PC
                                        records.append((
                                            str(get_val(row, ["Factura", "invoice", "No. Factura"])),
                                            clean_date,
                                            str(get_val(row, ["N BC", "CONS", "n_bc", "Consecutivo"])),
                                            str(get_val(row, ["PC", "Pedido de Compra", "P.C."])),
                                            str(get_val(row, ["PT", "PT#", "No. Parte", "Part Number", "numero_parte"])),
                                            str(get_val(row, ["Descripción", "Descripcion", "description", "DESCRIPCION"])),
                                            clean_qty,
                                            str(get_val(row, ["Proveedor", "proveedor", "Vendor"])),
                                            str(get_val(row, ["Shipper", "shipper"])),
                                            str(get_val(row, ["Customer", "customer", "Cliente", "CSSR"])),
                                            str(get_val(row, ["Recepción", "recepcion", "RECEP"])),
                                            str(get_val(row, ["Remisión", "remision"])),
                                            import_status, 
                                            "Importación masiva de historial antiguo",
                                            import_user
                                        ))

                                    if records:
                                        sql = "INSERT INTO daily_logs (factura, fecha, n_bc, pc, numero_parte, descripcion, cantidad, proveedor, shipper, customer, recepcion, remision, status, comentarios, nombre) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                                        cursor.executemany(sql, records)
                                        conn.commit()
                                        log_movement("IMPORT-EXCEL", "IMPORTACION_MASIVA", f"Se importaron {len(records)} registros antiguos.", usuario=import_user)
                                        st.success(f"✅ Se han importado {len(records)} registros con éxito.")
                                        time.sleep(2)
                                        st.rerun()
                                    conn.close()
                    except Exception as e:
                        st.error(f"Error al procesar el archivo: {e}")
            elif auth_pwd != "":
                st.error("Contraseña incorrecta. Acceso denegado.")
            else:
                st.warning("Se requiere autorización para acceder a esta función.")

        # --- LÓGICA DE PROCESAMIENTO PARA FORMULARIO 1 (PC) ---
        if submitted_pc:
            if not pc_number or not invoice_number_pc or edited_items.empty:
                st.error("Para entradas de PC, completa el PC, Factura y agrega al menos un artículo.")
            else:
                with st.spinner("Procesando entrada de PC..."):
                    # (Lógica de procesamiento para entradas de PC)
                 
                    new_rows = []
                    daily_log_rows = []
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    for index, row in edited_items.iterrows():
                        if not row["No. BC"] or not row["Qty"]: continue
                        
                        try:
                            qty = float(row["Qty"]) if row["Qty"] else 0.0
                            price = float(row["Unit Price"]) if row["Unit Price"] else 0.0
                        except (ValueError, TypeError):
                            qty = 0.0
                            price = 0.0
                        
                        item_id = str(uuid.uuid4())[:8]

                        # Priorizar No. BC de la tabla, si no, usar el general del form
                        bc_final = row["No. BC"] if pd.notna(row["No. BC"]) and str(row["No. BC"]).strip() != "" else consecutivo_pc

                        raw_desc = str(row['Description']).strip() if pd.notna(row['Description']) else ""
                        bc_val = str(row['No. BC']).strip() if pd.notna(row['No. BC']) else ""

                        new_row = {
                            "id": item_id, "pc": pc_number, "proveedor": "", "factura": invoice_number_pc,
                            "consecutivo": bc_final, "programa": programa_pc, "numero_parte": bc_val,
                            "descripcion": raw_desc, "shipper": row["Shipper"], "cantidad": qty,
                            "precio_unitario": price, "valor_total": qty * price, "estatus": "Recibido",
                            "fecha_entrada": timestamp, "ultima_actualizacion": timestamp, "usuario_recepcion": usuario_recepcion_pc
                        }
                        new_rows.append(new_row)
                        
                        daily_log_rows.append({ 
                            "factura": invoice_number_pc, "fecha": timestamp.split(' ')[0], "n_bc": bc_final, "pc": pc_number,
                            "numero_parte": bc_val, 
                            "descripcion": raw_desc, "shipper": row["Shipper"],
                            "cantidad": qty, "proveedor": "", "status": "Pendiente", "nombre": usuario_recepcion_pc,
                            "inventory_item_id": item_id, "customer": ""
                        })
                        log_movement(new_row["id"], "ENTRADA", f"Recepción PC: {pc_number}, No. BC: {bc_val}", usuario=usuario_recepcion_pc)

                    if new_rows:
                        conn = get_db_connection()
                        if conn:
                            cursor = conn.cursor()
                            cursor.executemany('''
                                INSERT INTO inventory (id, pc, proveedor, factura, consecutivo, programa, numero_parte, descripcion, cantidad, precio_unitario, valor_total, estatus, fecha_entrada, ultima_actualizacion, usuario_recepcion, shipper)
                                VALUES (%(id)s, %(pc)s, %(proveedor)s, %(factura)s, %(consecutivo)s, %(programa)s, %(numero_parte)s, %(descripcion)s, %(cantidad)s, %(precio_unitario)s, %(valor_total)s, %(estatus)s, %(fecha_entrada)s, %(ultima_actualizacion)s, %(usuario_recepcion)s, %(shipper)s)
                            ''', new_rows)
                            if daily_log_rows:
                                cursor.executemany('''
                                    INSERT INTO daily_logs (factura, fecha, n_bc, pc, numero_parte, descripcion, cantidad, proveedor, status, nombre, shipper, inventory_item_id, customer)
                                    VALUES (%(factura)s, %(fecha)s, %(n_bc)s, %(pc)s, %(numero_parte)s, %(descripcion)s, %(cantidad)s, %(proveedor)s, %(status)s, %(nombre)s, %(shipper)s, %(inventory_item_id)s, %(customer)s)
                                ''', daily_log_rows)
                            conn.commit()
                            conn.close()
                            st.success(f"✅ Se registraron {len(new_rows)} artículos en inventario.")
                            # Resetear tabla y aumentar iterador para limpiar campos de texto
                            st.session_state.items_entry = pd.DataFrame(columns=["No.", "No. BC", "Description", "Shipper", "Qty", "Unit Price"])
                            st.session_state.form_iter += 1
                            
                            time.sleep(1)
                            st.rerun()

        # --- LÓGICA DE PROCESAMIENTO PARA FORMULARIO 2 (VENTA DIRECTA) ---
        if submitted_vd:
            if edited_items_vd.empty:
                st.error("Por favor, agregue al menos un registro en la tabla para guardar.")
            # Check for required fields in the table
            elif edited_items_vd["No. Factura"].isnull().all() or edited_items_vd["Descripcion"].isnull().all():
                st.error("Para cada registro, por favor completa al menos 'No. Factura' y 'Descripción'.")
            else:
                with st.spinner("Registrando en bitácora..."):
                    conn = get_db_connection()
                    if not conn: return
                    
                    try:
                        cursor = conn.cursor()
                        timestamp = datetime.now()
                        
                        entries_to_insert = []
                        for index, row in edited_items_vd.iterrows():
                            # Skip empty rows that might be added in the editor
                            if pd.isna(row.get("No. Factura")) or pd.isna(row.get("Descripcion")):
                                continue

                            pt_val = str(row.get("No. Parte (PT)", "")).strip()
                            desc_val = str(row.get("Descripcion", "")).strip()

                            vals = (
                                row.get("No. Factura"),
                                timestamp.date(),
                                row.get("No. BC"),
                                row.get("PC"),
                                pt_val,
                                desc_val,
                                row.get("Proveedor"),
                                "Venta Directa",
                                row.get("Comentarios"),
                                vd_nombre # The name from the selectbox
                            )
                            entries_to_insert.append(vals)

                        if entries_to_insert:
                            sql = '''INSERT INTO daily_logs ( # Insertar en daily_logs con PT en la descripción
                                        factura, fecha, n_bc, pc, numero_parte, descripcion, proveedor, 
                                        status, comentarios, nombre
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
                            
                            cursor.executemany(sql, entries_to_insert)
                            conn.commit()

                            log_detail = f"Registro Manual en Bitácora de {len(entries_to_insert)} items."
                            log_movement(f"BIT-BATCH", "REGISTRO_MANUAL_MASIVO", log_detail, usuario=vd_nombre)
                            
                            st.success(f"✅ {len(entries_to_insert)} registros guardados en la bitácora correctamente.")
                            st.session_state.items_vd = pd.DataFrame(columns=["No.", "No. Factura", "PC", "No. BC", "No. Parte (PT)", "Proveedor", "Descripcion", "Comentarios"])
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.warning("No se encontraron registros válidos para guardar. Asegúrate de llenar 'No. Factura' y 'Descripción'.")

                    except Exception as e:
                        st.error(f"Error al registrar en bitácora: {e}")
                    finally:
                        if conn.is_connected():
                            conn.close()

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
                width="stretch",
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
                    st.dataframe(selected_df[["pc", "numero_parte", "descripcion", "estatus"]], width="stretch")

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

                            # 2. Actualizar Bitácora Diaria (daily_logs)
                            log_placeholders = ', '.join(['%s'] * len(ids_to_update))
                            log_query = f"UPDATE daily_logs SET status = %s WHERE inventory_item_id IN ({log_placeholders})"
                            log_params = [new_status] + ids_to_update
                            cursor.execute(log_query, log_params)
                            
                            # 3. Registrar Logs (Bulk Insert)
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
                                    SELECT i.pc, i.numero_parte, i.descripcion, i.cantidad, i.estatus, i.shipper 
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

                                        # 3. Actualizar Bitácora Diaria (daily_logs) a "Entregado"
                                        cursor.execute("""
                                            UPDATE daily_logs
                                            SET status = 'Entregado'
                                            WHERE inventory_item_id IN (SELECT item_id FROM route_items WHERE route_id = %s)
                                        """, (route['id'],))

                                        # 4. Log de cierre
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
                                    SELECT i.pc, i.numero_parte, i.descripcion, i.cantidad, i.estatus, i.shipper 
                                    FROM route_items ri
                                    JOIN inventory i ON ri.item_id = i.id
                                    WHERE ri.route_id = {route['id']}
                                """
                                df_items = pd.read_sql_query(query_items, conn)
                                st.dataframe(df_items, width="stretch")
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
                        i.estatus,
                        i.shipper
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
                                st.caption(f"🚛 Vehículo: {info_ruta['vehiculo']} | 👤 Responsable: {info_ruta['usuario']}")
                            with c2:
                                st.metric("Items", len(items_ruta))
                            
                            # Tabla de items dentro de la ruta
                            st.dataframe(
                                items_ruta[["pc", "numero_parte", "descripcion", "cantidad", "estatus", "shipper"]],
                                width="stretch",
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

        st.subheader("📋 Bitácora Diaria (General)")
        st.caption("📝 Edita directamente en la tabla. Agrega filas al final. Los cambios se guardan automáticamente.")
        
        # --- FILTRO DE TIEMPO (Para mantener limpio) ---
        with st.container(border=True):
            col_f1, col_f2 = st.columns([2, 1])
            with col_f1:
                # --- CÁLCULO AUTOMÁTICO: Mes actual y mes pasado ---
                hoy = datetime.now()
                # Primer día del mes actual
                primer_dia_mes_actual = hoy.replace(day=1)
                # Último día del mes pasado
                ultimo_dia_mes_pasado = primer_dia_mes_actual - timedelta(days=1)
                # Primer día del mes pasado
                primer_dia_mes_pasado = ultimo_dia_mes_pasado.replace(day=1)

                date_range = st.date_input(
                    "Filtrar por rango de fechas:",
                    value=(primer_dia_mes_pasado.date(), hoy.date()),
                    key="bitacora_date_range"
                )
            with col_f2:
                st.info("📅")

        # Validar el rango de fechas para la consulta SQL
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = datetime.now() - timedelta(days=60)
            end_date = datetime.now()

        # --- Lógica de CRUD con st.data_editor para la bitácora general ---
        def update_daily_logs(editor_key="editor_bitacora", snapshot_key="df_bitacora_snapshot"):
            """Callback para guardar cambios en la BD cuando se edita la tabla."""
            changes = st.session_state.get(editor_key)
            snapshot = st.session_state.get(snapshot_key)
            
            if not changes or snapshot is None: return
            
            conn = get_db_connection()
            if not conn: return
            cursor = conn.cursor()
            
            try:
                # 1. Insertar nuevas filas
                if changes["added_rows"]:
                    for row in changes["added_rows"]:
                        # Validar fecha (si está vacía usar hoy)
                        fecha_val = row.get("fecha")
                        if not fecha_val:
                            fecha_val = datetime.today().strftime('%Y-%m-%d')

                        # --- FIX: Conversión segura a float para evitar errores de texto ---
                        try:
                            cantidad_val = float(row.get("cantidad") or 0.0)
                        except (ValueError, TypeError):
                            cantidad_val = 0.0

                        # Determinar status default según la tabla que se edita
                        default_status = "Venta Directa" if editor_key == "editor_ventas_directas" else "Pendiente"
                        status_val = row.get("status") or default_status

                        sql = '''INSERT INTO daily_logs (
                            factura, fecha, n_bc, pc, numero_parte, descripcion, cantidad, proveedor, 
                            shipper, customer, recepcion, remision, status, comentarios, nombre
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
                        vals = (
                            row.get("factura", ""), fecha_val, row.get("n_bc", ""), row.get("pc", ""), row.get("numero_parte", ""),
                            row.get("descripcion", ""), cantidad_val, row.get("proveedor", ""),
                            row.get("shipper", ""), row.get("customer", ""), row.get("recepcion", ""),
                            row.get("remision", ""), status_val, 
                            row.get("comentarios", ""), row.get("nombre", "")
                        )
                        cursor.execute(sql, vals)
                
                # 2. Actualizar filas editadas
                if changes["edited_rows"]:
                    for idx_str, updates in changes["edited_rows"].items():
                        idx = int(idx_str)
                        # Usamos el snapshot para obtener el ID real de la fila editada
                        if idx < len(snapshot):
                            row_id = snapshot.iloc[idx]["id"]
                            
                            # --- FIX: Asegurar que el ID sea un tipo nativo de Python (int), no numpy.int64 ---
                            if isinstance(row_id, (np.integer, np.floating)):
                                row_id = row_id.item()

                            set_clauses = []
                            vals = []
                            for col, val in updates.items():
                                set_clauses.append(f"{col} = %s")

                                # --- FIX: Convertir tipos de numpy a nativos de Python ---
                                processed_val = val
                                if isinstance(val, (np.integer, np.floating)):
                                    processed_val = val.item() # .item() convierte a tipo nativo de Python
                                
                                vals.append(processed_val)

                            if set_clauses:
                                vals.append(row_id)
                                sql = f"UPDATE daily_logs SET {', '.join(set_clauses)} WHERE id = %s"
                                cursor.execute(sql, tuple(vals))
                
                # 3. Borrar filas eliminadas
                if changes["deleted_rows"]:
                    for idx in changes["deleted_rows"]:
                        if idx < len(snapshot):
                            row_id = snapshot.iloc[idx]["id"]
                            # Convertir tipos de numpy a nativos de Python para la consulta
                            if isinstance(row_id, (np.integer, np.floating)):
                                row_id = row_id.item()
                            cursor.execute("DELETE FROM daily_logs WHERE id = %s", (row_id,))

                conn.commit()
                st.toast("✅ Bitácora actualizada correctamente")
            except Exception as e:
                st.error(f"Error al guardar cambios: {e}")
            finally:
                conn.close()

        # Cargar datos actuales
        conn = get_db_connection()
        if conn:
            # Consulta filtrada por el rango de fechas seleccionado
            # Orden solicitado: Fecha, No. BC, Descripción, Cantidad, Proveedor, PC, Customer, Recepcion, Remision, Comentarios, Nombre
            query = """
                SELECT `id`, `fecha`, `n_bc`, `descripcion`, `cantidad`, `proveedor`, `pc`, `customer`, `recepcion`, `remision`, `comentarios`, `nombre`, `numero_parte`, `factura`, `status`, `shipper`, `timestamp`, `inventory_item_id` 
                FROM daily_logs 
                WHERE fecha BETWEEN %s AND %s 
                ORDER BY fecha DESC, id DESC"""
            df_logs_all = pd.read_sql_query(query, conn, params=(start_date, end_date))
            
            # Configuración de columnas para el editor
            column_cfg = {
                "id": None, # Ocultar ID
                "inventory_item_id": None, # Ocultar ID de inventario
                "timestamp": None, # Ocultar Timestamp
                "fecha": st.column_config.DateColumn("Fecha", format="YYYY-MM-DD", width="small"),
                "n_bc": st.column_config.TextColumn("No. BC", width="medium", help="Número de Etiqueta Blanca (Consecutivo)"),
                "descripcion": st.column_config.TextColumn("Descripción", width="large"),
                "cantidad": st.column_config.NumberColumn("Cantidad", format="%.2f"),
                "proveedor": st.column_config.TextColumn("Proveedor"),
                "pc": st.column_config.TextColumn("PC", width="small", help="Pedido de Compra (PC)"),
                "customer": st.column_config.SelectboxColumn(
                    "Customer",
                    options=["LCHARLES", "DCHARLES", "EJIMENES", "MFUENTES", "DCEPEDA", "DRIVERA"],
                    required=False
                ),
                "recepcion": st.column_config.TextColumn("Recepción"),
                "remision": st.column_config.TextColumn("Remisión"),
                "comentarios": st.column_config.TextColumn("Comentarios", width="large"),
                "nombre": st.column_config.TextColumn("Nombre"),
                "numero_parte": None, # Ocultar PT (Ya está en descripción)
                "factura": st.column_config.TextColumn("Factura Prov.", width="small", help="Factura del Proveedor"),
                "status": st.column_config.SelectboxColumn("Status", options=["Pendiente", "En proceso de entrega", "Revisado", "Entregado", "Cancelado", "Venta Directa"], required=True),
                "shipper": None,
            }
            
            st.data_editor(
                df_logs_all,
                key="editor_bitacora",
                column_config=column_cfg,
                num_rows="dynamic", # Permite agregar filas
                width="stretch",
                hide_index=True,
                on_change=update_daily_logs,
                args=["editor_bitacora", "df_bitacora_snapshot"]
            )
            
            # Guardar snapshot para que el callback sepa qué IDs corresponden a qué filas
            st.session_state["df_bitacora_snapshot"] = df_logs_all

            st.divider()

            # --- NUEVA TABLA PARA VENTAS DIRECTAS ---
            st.subheader("📈 Bitácora Diaria Ventas Directas")
            
            # Filtrar el dataframe en memoria para obtener solo 'Venta Directa'
            df_ventas_directas = df_logs_all[df_logs_all['status'] == 'Venta Directa'].copy()

            # Guardar snapshot para ventas directas
            st.session_state["df_ventas_directas_snapshot"] = df_ventas_directas

            st.data_editor(
                df_ventas_directas,
                key="editor_ventas_directas",
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                column_config={
                    "id": None, "timestamp": None, "cantidad": None, "customer": None, "recepcion": None, "remision": None, "status": None, "inventory_item_id": None,
                    "fecha": st.column_config.DateColumn("Fecha", format="YYYY-MM-DD", width="small"),
                    "numero_parte": st.column_config.TextColumn("PT", width="medium"),
                    "n_bc": st.column_config.TextColumn("Consecutivo", width="small"),
                    "factura": st.column_config.TextColumn("Factura", width="small"),
                    "descripcion": st.column_config.TextColumn("Descripción", width="large"),
                    "proveedor": st.column_config.TextColumn("Proveedor"),
                    "comentarios": st.column_config.TextColumn("Comentarios", width="large"),
                },
                on_change=update_daily_logs,
                args=["editor_ventas_directas", "df_ventas_directas_snapshot"]
            )
            
            conn.close()
        else:
            st.error("No se pudo conectar a la base de datos.")
        
        st.divider()
        
        # --- 2. HISTORIAL DE TRAZABILIDAD (SISTEMA) ---
        st.subheader("🔍 Historial de Trazabilidad ")
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
            st.dataframe(df_log, width="stretch")
            
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
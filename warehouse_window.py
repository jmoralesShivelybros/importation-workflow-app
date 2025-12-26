import streamlit as st
import pandas as pd
import os
from datetime import datetime
import time
import uuid

# --- Constantes ---
PROGRAMAS = ["Genv danna", "Edu prismaticos Dianei", "CSS erika", "Edu engranes Mayela", "Otro"]
ESTATUS_OPCIONES = ["Recibido", "En Mesa/Clasificado", "Etiquetado", "En proceso de entrega", "Entregado a Planta"]

def load_data(file_path):
    """Carga la base de datos de inventario o crea una vacía si no existe."""
    if os.path.exists(file_path):
        try:
            return pd.read_csv(file_path)
        except Exception:
            pass
    
    # Estructura base
    return pd.DataFrame(columns=[
        "id", "pc", "proveedor", "factura", "consecutivo", "programa",
        "numero_parte", "descripcion", "cantidad", "precio_unitario", "valor_total",
        "estatus", "fecha_entrada", "ultima_actualizacion"
    ])

def save_data(df, file_path):
    """Guarda el DataFrame en CSV."""
    df.to_csv(file_path, index=False)

def log_movement(log_path, item_id, accion, detalle, usuario="Almacenista"):
    """Registra un movimiento en el historial."""
    new_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "item_id": item_id,
        "accion": accion,
        "detalle": detalle,
        "usuario": usuario
    }
    
    if os.path.exists(log_path):
        df_log = pd.read_csv(log_path)
    else:
        df_log = pd.DataFrame(columns=["timestamp", "item_id", "accion", "detalle", "usuario"])
    
    df_log = pd.concat([df_log, pd.DataFrame([new_entry])], ignore_index=True)
    df_log.to_csv(log_path, index=False)

def render_warehouse_page(folder_manager, section="Recepción de Material"):
    st.header(f"🏭 Almacén: {section}")

    # Rutas de archivos
    db_path = folder_manager.get_warehouse_db_path()
    log_path = folder_manager.get_warehouse_log_path()

    # Cargar datos
    df_inventory = load_data(db_path)

    # --- SECCIÓN: RECEPCIÓN DE MATERIAL ---
    if section == "Recepción de Material":
        st.subheader("Registro de Entrada (PC Shively)")
        
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
                        "ultima_actualizacion": timestamp
                    }
                    new_rows.append(new_row)
                    # Log
                    log_movement(log_path, new_row["id"], "ENTRADA", f"Recepción PC: {pc_number}, PT: {row['Code (PT)']}")

                if new_rows:
                    df_new = pd.DataFrame(new_rows)
                    df_inventory = pd.concat([df_inventory, df_new], ignore_index=True)
                    save_data(df_inventory, db_path)
                    st.success(f"✅ Se registraron {len(new_rows)} artículos correctamente.")
                    # Limpiar el editor reiniciando el estado
                    st.session_state.items_entry = pd.DataFrame(columns=["Code (PT)", "Description", "Qty", "Unit Price"])
                    time.sleep(1)
                    st.rerun()

    # --- SECCIÓN: GESTIÓN Y ESTATUS ---
    elif section == "Gestión y Estatus":
        st.subheader("Gestión de Materiales en Almacén")
        
        # Filtros
        filtro_estatus = st.multiselect("Filtrar por Estatus:", options=ESTATUS_OPCIONES, default=["Recibido", "Etiquetado", "En Mesa/Clasificado"])
        
        # Filtrar datos
        if filtro_estatus:
            df_view = df_inventory[df_inventory["estatus"].isin(filtro_estatus)]
        else:
            df_view = df_inventory

        # Mostrar tabla editable para cambios rápidos (solo algunas columnas)
        st.write(f"Mostrando {len(df_view)} registros.")
        
        # Usamos columnas para mostrar acciones por fila es complicado en Streamlit nativo,
        # así que usaremos un selector de ID para actualizar estatus.
        
        st.dataframe(
            df_view[["id", "pc", "numero_parte", "descripcion", "programa", "estatus", "consecutivo"]],
            use_container_width=True,
            hide_index=True
        )

        st.divider()
        st.markdown("#### 🛠️ Actualizar Estatus")
        
        col_act1, col_act2, col_act3 = st.columns(3)
        with col_act1:
            # Obtener lista de IDs activos para el selectbox
            ids_disponibles = df_view["id"].tolist()
            selected_id = st.selectbox("Seleccionar ID de Artículo:", options=ids_disponibles)
        
        with col_act2:
            new_status = st.selectbox("Nuevo Estatus:", options=ESTATUS_OPCIONES)
        
        with col_act3:
            st.write("") # Espacio
            st.write("") # Espacio
            if st.button("Actualizar Estatus", type="primary"):
                if selected_id:
                    # Actualizar en el DataFrame
                    idx = df_inventory[df_inventory["id"] == selected_id].index
                    if not idx.empty:
                        old_status = df_inventory.loc[idx[0], "estatus"]
                        df_inventory.loc[idx[0], "estatus"] = new_status
                        df_inventory.loc[idx[0], "ultima_actualizacion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        save_data(df_inventory, db_path)
                        log_movement(log_path, selected_id, "CAMBIO_ESTATUS", f"De '{old_status}' a '{new_status}'")
                        st.toast(f"Estatus actualizado a: {new_status}")
                        time.sleep(1)
                        st.rerun()

    # --- SECCIÓN: MONITOR TV ---
    elif section == "Monitor TV":
        st.markdown("### 📺 Monitor de Entradas Recientes")
        
        auto_refresh = st.checkbox("🔄 Auto-refrescar (Modo TV)", value=False)
        
        # Filtrar lo que queremos mostrar en la TV (ej. todo lo que no esté Finalizado)
        df_tv = df_inventory[df_inventory["estatus"] != "Finalizado"].sort_values(by="ultima_actualizacion", ascending=False)

        # Métricas Generales
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("En Recepción", len(df_inventory[df_inventory["estatus"] == "Recibido"]))
        m2.metric("En Mesa", len(df_inventory[df_inventory["estatus"] == "En Mesa/Clasificado"]))
        m3.metric("Por Entregar", len(df_inventory[df_inventory["estatus"] == "Etiquetado"]))
        m4.metric("Total Activos", len(df_tv))

        st.divider()

        # Vista tipo Carrusel (Simulada con columnas y contenedores grandes)
        if not df_tv.empty:
            # Mostramos los 3 más recientes destacados
            st.markdown("#### 🔥 Últimos Movimientos")
            
            for i, row in df_tv.head(5).iterrows():
                # Asignar íconos según el estatus
                icon = "📦"
                if row["estatus"] == "Recibido": icon = "📥"
                elif row["estatus"] == "En Mesa/Clasificado": icon = "🧐"
                elif row["estatus"] == "Etiquetado": icon = "🏷️"
                elif row["estatus"] == "En proceso de entrega": icon = "🚚"
                elif row["estatus"] == "Entregado a Planta": icon = "✅"

                color_border = "blue"
                if row["estatus"] == "Entregado a Planta": color_border = "green"
                elif row["estatus"] == "Recibido": color_border = "red"
                
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([1, 3, 2, 2])
                    with c1:
                        st.markdown(f"**PC:** {row['pc']}")
                        st.caption(row['id'])
                    with c2:
                        st.markdown(f"**PT:** {row['numero_parte']}")
                        st.write(f"{row['descripcion']}")
                    with c3:
                        st.markdown(f"**Programa:** {row['programa']}")
                        st.markdown(f"**Cant:** {row['cantidad']}")
                    with c4:
                        st.markdown(f"### {icon} {row['estatus']}")
                        st.caption(f"Act: {row['ultima_actualizacion']}")
        else:
            st.info("No hay materiales activos en el sistema.")

        # Lógica de Auto-refresco
        if auto_refresh:
            time.sleep(10) # Refrescar cada 10 segundos
            st.rerun()

    # --- SECCIÓN: HISTORIAL ---
    elif section == "Historial":
        st.subheader("Historial de Trazabilidad")
        if os.path.exists(log_path):
            df_log = pd.read_csv(log_path).sort_values(by="timestamp", ascending=False)
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
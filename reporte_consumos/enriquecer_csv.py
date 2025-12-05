# c:\Users\Javier\Downloads\enriquecer_csv.py
import csv
import os
import pandas as pd
import re

def limpiar_valor(valor):
    """Limpia espacios y comillas de un valor."""
    if valor is None:
        return ""
    return str(valor).strip().strip('"')

def es_valido(valor):
    """
    Verifica si un valor no es nulo, vacío o un placeholder como #N/D.
    """
    if not valor:
        return False
    if valor.strip().lower() in ('', '#n/d'):
        return False
    return True

def es_fabricante_valido(valor):
    """
    Verifica si un nombre de fabricante es válido (no es 'TA').
    """
    if not es_valido(valor):
        return False
    if valor.strip().lower() == 'ta':
        return False
    return True

def es_gm_plant_id_valido(valor):
    """Verifica si un GM Plant ID es válido."""
    if not valor:
        return False
    return valor.strip().upper() in ('RECSS', 'REEDU', 'REGENV', 'TA', 'TC')

def extraer_pt_de_descripcion(descripcion):
    """
    Intenta extraer el PT# de la descripción.
    Busca un patrón como 'PT' seguido de caracteres alfanuméricos.
    """
    if not descripcion:
        return None
    
    # Busca un patrón que empiece con PT seguido de letras y/o números.
    match = re.search(r'PT[a-zA-Z0-9]+', descripcion)
    if match:
        return limpiar_valor(match.group(0))
    return None

def extraer_fabricante_de_descripcion(descripcion):
    """
    Extrae el nombre del fabricante de la descripción.
    Asume que la descripción tiene el formato "PT# FABRICANTE ...".
    """
    if not descripcion:
        return None
    partes = descripcion.strip().split()
    # Si la descripción tiene al menos 2 partes (ej. "12345 ABC"), la segunda es el fabricante.
    return partes[1] if len(partes) > 1 else None

def procesar_datos_en_memoria(archivo_maestro_path, archivo_a_modificar_stream):
    """
    Enriquece datos de un CSV (en memoria) usando un maestro, y devuelve DataFrames.
    :param archivo_maestro_path: Ruta (string) al archivo CSV maestro.
    :param archivo_a_modificar_stream: Stream del archivo a modificar.
    :return: Tuple (DataFrame completo, DataFrame de errores, str resumen).
    """
    
    master_data = {}
    description_to_parttype_map = {} # Nuevo diccionario para Description -> PartType LOV
    description_to_pt_map = {} # ¡NUEVO! Diccionario para Description -> PT#
    pt_duplicados_maestro = []
    try:
        with open(archivo_maestro_path, mode='r', encoding='utf-8-sig') as f_maestro:
            # --- Punto 4: Manejo de Duplicados en el Archivo Maestro ---
            lector_csv = csv.reader(f_maestro, quotechar='"', delimiter=',', skipinitialspace=True)
            cabeceras_maestro_sucias = next(lector_csv)
            cabeceras_maestro_limpias = [h.strip() for h in cabeceras_maestro_sucias]
            
            f_maestro.seek(0)
            next(f_maestro)
            
            lector_maestro = csv.DictReader(f_maestro, fieldnames=cabeceras_maestro_limpias)
            
            for fila in lector_maestro:
                if not fila: continue

                pt_numero = limpiar_valor(fila.get('PT#', ''))
                descripcion = limpiar_valor(fila.get('Description', ''))
                part_type = limpiar_valor(fila.get('PartType LOV', ''))
                
                if es_valido(pt_numero):
                    nombre_fabricante = limpiar_valor(fila.get('Manufacturer/OEM', ''))
                    if not es_fabricante_valido(nombre_fabricante):
                        nombre_fabricante = extraer_fabricante_de_descripcion(descripcion)

                    if pt_numero not in master_data:
                        master_data[pt_numero] = {
                            'id': limpiar_valor(fila.get('Manufacturer/OEM ID#', '')),
                            'nombre': nombre_fabricante or '',
                            'gm_plant_id': limpiar_valor(fila.get('GM Plant ID', ''))
                        }
                    else:
                        # Si el PT# ya existe, lo registramos como duplicado
                        if pt_numero not in pt_duplicados_maestro:
                            pt_duplicados_maestro.append(pt_numero)
                
                if es_valido(descripcion) and es_valido(part_type):
                    if descripcion not in description_to_parttype_map:
                        description_to_parttype_map[descripcion] = part_type
                
                # ¡NUEVO! Llenamos el mapa de Descripción a PT#
                if es_valido(descripcion) and es_valido(pt_numero):
                    if descripcion not in description_to_pt_map:
                        description_to_pt_map[descripcion] = pt_numero
            
            if len(master_data) == 0:
                raise ValueError("No se cargó ningún dato del archivo maestro. Verifique el formato.")

    except FileNotFoundError:
        raise IOError(f"No se encontró el archivo maestro en la ruta: {archivo_maestro_path}")
    except Exception as e:
        raise IOError(f"Error al leer el archivo maestro: {e}")
    
    registros_corregidos = 0
    parttype_corregidos = 0 # Nuevo contador para PartType LOV
    gm_plant_id_corregidos = 0 # NUEVO: Contador para GM Plant ID
    id_reemplazado_con_pt = 0 # NUEVO: Contador para reemplazos de ID con PT#
    pt_extraidos_desc = 0 # NUEVO: Contador para PT# extraídos de la descripción
    ext_price_calculados = 0 # NUEVO: Contador para precios extendidos calculados
    pt_rescatados_desc = 0 # ¡NUEVO! Contador para PT# rescatados de la descripción
    total_filas = 0
    filas_no_encontradas = []
    filas_salida = []

    # --- NUEVA LÓGICA: Definimos las cabeceras de salida deseadas ---
    cabeceras_salida = [
        "PT#", "Description", "Manufacturer/OEM ID#", "GM Plant ID", 
        "Manufacturer/OEM", "Unit price", "QTY", "Ext Price", "DATE", 
        "COMMENTS", "PartType LOV", "Platform (LOV)"
    ]

    try:
        lector_csv = csv.reader(archivo_a_modificar_stream, quotechar='"', delimiter=',', skipinitialspace=True)
        
        cabeceras_entrada = next(lector_csv)
        cabeceras_limpias_entrada = [h.strip() for h in cabeceras_entrada]

        try:
            idx_pt = cabeceras_limpias_entrada.index('PT#')
            idx_id = cabeceras_limpias_entrada.index('Manufacturer/OEM ID#')
            idx_oem = cabeceras_limpias_entrada.index('Manufacturer/OEM')
            idx_gm_plant = cabeceras_limpias_entrada.index('GM Plant ID')
            idx_desc = cabeceras_limpias_entrada.index('Description')
            idx_parttype = cabeceras_limpias_entrada.index('PartType LOV')
            idx_unit_price = cabeceras_limpias_entrada.index('Unit price')
            idx_qty = cabeceras_limpias_entrada.index('QTY')
            idx_ext_price = cabeceras_limpias_entrada.index('Ext Price')
            idx_date = cabeceras_limpias_entrada.index('DATE')
            idx_comments = cabeceras_limpias_entrada.index('COMMENTS')
            idx_platform = cabeceras_limpias_entrada.index('Platform (LOV)')

            mapa_indices = {
                "PT#": idx_pt, "Description": idx_desc, "Manufacturer/OEM ID#": idx_id, "GM Plant ID": idx_gm_plant,
                "Manufacturer/OEM": idx_oem, "Unit price": idx_unit_price, "QTY": idx_qty, "Ext Price": idx_ext_price,
                "DATE": idx_date, "COMMENTS": idx_comments, "PartType LOV": idx_parttype, "Platform (LOV)": idx_platform
            }
        except ValueError as e:
            raise ValueError(f"No se encontró la columna requerida en el archivo a modificar: {e}")

        for i, fila_entrada in enumerate(lector_csv):
            total_filas += 1
            
            if len(fila_entrada) <= max(mapa_indices.values()):
                continue

            pt_numero = limpiar_valor(fila_entrada[idx_pt])
            
            # --- LÓGICA DE EXTRACCIÓN DE PT# MEJORADA ---
            # 1. Intentar extraer de la descripción si el PT# está vacío
            if not es_valido(pt_numero):
                pt_numero = extraer_pt_de_descripcion(limpiar_valor(fila_entrada[idx_desc]))
                if es_valido(pt_numero):
                    pt_extraidos_desc += 1
                    fila_entrada[idx_pt] = pt_numero # ¡CORRECCIÓN! Asignar el PT# extraído a la fila.
            
            descripcion_fila = limpiar_valor(fila_entrada[idx_desc]) # Limpiamos la descripción una vez
            # 2. Si aún no hay PT#, buscar la descripción en el mapa del maestro
            if not es_valido(pt_numero) and descripcion_fila in description_to_pt_map:
                pt_numero = description_to_pt_map[descripcion_fila]
                fila_entrada[idx_pt] = pt_numero # Asignamos el PT# encontrado desde el maestro
            
            corregido_en_esta_fila = False
            if es_valido(pt_numero):
                if pt_numero in master_data:
                    datos_maestros = master_data[pt_numero]
                    
                    if es_valido(datos_maestros['id']):
                        fila_entrada[idx_id] = datos_maestros['id']
                        corregido_en_esta_fila = True
                    
                    if es_valido(datos_maestros['nombre']):
                        fila_entrada[idx_oem] = datos_maestros['nombre']
                        corregido_en_esta_fila = True
                    
                    if es_gm_plant_id_valido(datos_maestros['gm_plant_id']):
                        fila_entrada[idx_gm_plant] = datos_maestros['gm_plant_id'].upper()
                        gm_plant_id_corregidos += 1
            
            if not es_fabricante_valido(fila_entrada[idx_oem]):
                nombre_fabricante_desc = extraer_fabricante_de_descripcion(descripcion_fila)
                if es_fabricante_valido(nombre_fabricante_desc):
                    fila_entrada[idx_oem] = nombre_fabricante_desc
                    corregido_en_esta_fila = True
            
            if corregido_en_esta_fila:
                registros_corregidos += 1

            if not es_valido(fila_entrada[idx_id]):
                if es_valido(pt_numero):
                    fila_entrada[idx_id] = pt_numero
                    id_reemplazado_con_pt += 1

            # --- CORRECCIÓN CRÍTICA DE LÓGICA DE PRECIOS ---
            # Guardamos el precio del usuario ANTES de cualquier posible modificación.
            # Esto asegura que el cálculo SIEMPRE use el precio del archivo de entrada.
            precio_usuario = limpiar_valor(fila_entrada[idx_unit_price])
            if not es_valido(precio_usuario):
                precio_usuario = '0'

            try:
                qty = float(limpiar_valor(fila_entrada[idx_qty]) or 0)
                unit_price = float(precio_usuario)
                ext_price = qty * unit_price
                fila_entrada[idx_ext_price] = f"{ext_price:.2f}"
                ext_price_calculados += 1
            except (ValueError, IndexError):
                # Si hay un error (ej. QTY no es un número), se asigna 0.00 para evitar fallos.
                fila_entrada[idx_ext_price] = '0.00'

            fila_entrada[idx_parttype] = pt_numero
            parttype_corregidos += 1
            
            if (not es_valido(fila_entrada[idx_id]) or not es_fabricante_valido(fila_entrada[idx_oem])) and pt_numero not in master_data:
                # --- ¡NUEVO! Lógica de Rescate desde la Descripción ---
                descripcion = fila_entrada[idx_desc]
                match = re.search(r'(PT\w+)', descripcion) # Busca un patrón como PT...
                
                pt_rescatado = None
                if match:
                    pt_potencial = match.group(1)
                    if pt_potencial in master_data:
                        pt_rescatado = pt_potencial

                if pt_rescatado:
                    # ¡Rescatado! Enriquecemos la fila con el PT# encontrado
                    pt_rescatados_desc += 1
                    fila_entrada[idx_pt] = pt_rescatado # Actualizamos el PT# en la fila
                    info_maestra = master_data[pt_rescatado]
                    fila_entrada[idx_id] = info_maestra['id']
                    fila_entrada[idx_oem] = info_maestra['nombre']
                    fila_entrada[idx_gm_plant] = info_maestra['gm_plant_id']
                else:
                    # Si ni así se encuentra, ahora sí se marca como error
                    filas_no_encontradas.append(fila_entrada)

            # --- CORRECCIÓN CLAVE ---
            # Creamos un diccionario con los datos de la fila procesada para un mapeo seguro.
            datos_fila_procesada = {cabeceras_limpias_entrada[i]: val for i, val in enumerate(fila_entrada)}

            fila_salida = ["" for _ in cabeceras_salida]
            for j, cabecera in enumerate(cabeceras_salida):
                fila_salida[j] = datos_fila_procesada.get(cabecera, "")
            filas_salida.append(fila_salida)

        # Construir el string de resumen
        resumen = (
            f"¡Proceso completado!\n"
            f"---------------------------------------------------\n"
            f"Se procesaron {total_filas} filas.\n"
            f"Se completaron datos de 'Fabricante' en {registros_corregidos} registros.\n"
            f"Se completaron datos de 'PartType LOV' en {parttype_corregidos} registros.\n"
            f"Se corrigieron datos de 'GM Plant ID' en {gm_plant_id_corregidos} registros.\n"
            f"Se reemplazó 'Manufacturer/OEM ID#' con 'PT#' en {id_reemplazado_con_pt} registros.\n"
            f"Se calculó el 'Ext Price' para {ext_price_calculados} registros.\n"
            f"Se extrajo el 'PT#' desde la descripción en {pt_extraidos_desc} registros.\n"
            f"Registros rescatados extrayendo PT# de la descripción: {pt_rescatados_desc}\n"
            f"---------------------------------------------------\n"

        )

        if filas_no_encontradas:
            resumen += f"ATENCIÓN: Se encontraron {len(filas_no_encontradas)} registros que no estaban en el maestro."
        else:
            resumen += "¡Excelente! Todos los registros fueron encontrados y corregidos."

        # Convertir listas a DataFrames de Pandas
        df_completo = pd.DataFrame(filas_salida, columns=cabeceras_salida)
        df_errores = pd.DataFrame(filas_no_encontradas, columns=cabeceras_limpias_entrada)
        
        df_formato = pd.DataFrame() # Devolvemos un DataFrame vacío como placeholder

        # Reordenar columnas del df de errores para que coincida con la salida
        if not df_errores.empty:
            columnas_ordenadas_error = [col for col in cabeceras_salida if col in df_errores.columns]
            df_errores = df_errores[columnas_ordenadas_error]

        return df_completo, df_errores, df_formato, resumen

    except Exception as e:
        raise RuntimeError(f"Ocurrió un error inesperado al procesar el archivo: {e}")

import datetime
from sqlalchemy import create_engine, Column, Integer, String, Date, Text, Float, DateTime
try:
    from sqlalchemy.orm import sessionmaker, declarative_base
except ImportError:
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.declarative import declarative_base

# Asumiendo que tienes una base compartida, si no, definimos una nueva.
Base = declarative_base()
class RegistroDiarioAlmacen(Base):
    """
    Tabla que replica la estructura del Excel de almacén.
    """
    __tablename__ = 'registro_diario_almacen'

    id = Column(Integer, primary_key=True, autoincrement=True)
    factura = Column(String(100), nullable=True)
    fecha = Column(Date, default=datetime.date.today)
    n_bc = Column(String(100), nullable=True)
    descripcion = Column(Text, nullable=True)
    cantidad = Column(Float, default=0.0)
    proveedor = Column(String(200), nullable=True)
    shipper = Column(String(200), nullable=True)
    customer = Column(String(200), nullable=True)
    recepcion = Column(String(200), nullable=True) # Quién recibe o dato de recepción
    remision = Column(String(100), nullable=True)
    status = Column(String(50), default='Pendiente')
    comentarios = Column(Text, nullable=True)
    nombre = Column(String(150), nullable=True) # Nombre de quien registra
    created_at = Column(DateTime, default=datetime.datetime.now)

    def to_dict(self):
        """Helper para convertir el objeto a diccionario (útil para dataframes/excel)"""
        return {
            "Factura": self.factura,
            "Fecha": self.fecha,
            "N BC": self.n_bc,
            "Descripción": self.descripcion,
            "Cantidad": self.cantidad,
            "Proveedor": self.proveedor,
            "Shipper": self.shipper,
            "Customer": self.customer,
            "Recepción": self.recepcion,
            "Remisión": self.remision,
            "Status": self.status,
            "Comentarios": self.comentarios,
            "Nombre": self.nombre
        }

# --- Lógica de Control ---

def inicializar_db(db_url='sqlite:///almacen.db'):
    """Crea la tabla si no existe."""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

def agregar_registro_diario(session, datos_dict):
    """
    Recibe un diccionario con las claves correspondientes al modelo
    y guarda un nuevo registro.
    """
    nuevo_registro = RegistroDiarioAlmacen(
        factura=datos_dict.get('factura'),
        fecha=datos_dict.get('fecha', datetime.date.today()),
        n_bc=datos_dict.get('n_bc'),
        descripcion=datos_dict.get('descripcion'),
        cantidad=datos_dict.get('cantidad', 0.0),
        proveedor=datos_dict.get('proveedor'),
        shipper=datos_dict.get('shipper'),
        customer=datos_dict.get('customer'),
        recepcion=datos_dict.get('recepcion'),
        remision=datos_dict.get('remision'),
        status=datos_dict.get('status', 'Pendiente'),
        comentarios=datos_dict.get('comentarios'),
        nombre=datos_dict.get('nombre')
    )
    session.add(nuevo_registro)
    session.commit()
    return nuevo_registro

def obtener_historial_diario(session):
    """
    Retorna todos los registros ordenados por fecha descendente.
    Ideal para mostrar en la tabla principal de la UI.
    """
    return session.query(RegistroDiarioAlmacen).order_by(RegistroDiarioAlmacen.fecha.desc()).all()

# --- Integración con UI (Ejemplo conceptual) ---
# Cuando construyas tu vista en la app:
# 1. Llama a obtener_historial_diario(session)
# 2. Muestra estos datos en una tabla/grid principal (Primer Plano).
# 3. Coloca el 'Historial de Trazabilidad' antiguo debajo de esta tabla o en una pestaña secundaria (Segundo Plano).

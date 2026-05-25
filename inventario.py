import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt

app = FastAPI(title="Microservicio de Inventario", version="3.0")

# --- CONFIGURACIÓN DE SEGURIDAD JWT ---
SECRET_KEY = "secret_password_login_super_segura_32"
ALGORITHM = "HS256"
security = HTTPBearer()

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o corrupto.")

# --- CONFIGURACIÓN DE BASE DE DATOS ---
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://shopnow_663n_user:mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl@dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com/shopnow_663n"
)

def obtener_conexion():
    try:
        return psycopg2.connect(DATABASE_URL)
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Error de conexión a la BD: {e}")

# --- MODELOS DE DATOS ---
class AltaInventario(BaseModel):
    id_producto: int = Field(..., description="ID del producto existente en el catálogo")
    cantidad_inicial: int = Field(ge=0, description="Cantidad física inicial en almacén")

class AgregarStock(BaseModel):
    cantidad_a_sumar: int = Field(gt=0, description="Cantidad de unidades a ingresar")

# --- ENDPOINTS ---
@app.get("/inventario", dependencies=[Depends(verificar_token)])
def obtener_inventario():
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id_producto, cantidad FROM inventario;")
            inventario_raw = cur.fetchall()
            
            # Cruzamos los datos de inventario con productos para mostrar la descripción
            cur.execute("SELECT id_producto, descripcion FROM productos WHERE activo = true;")
            productos_dict = {p['id_producto']: p['descripcion'] for p in cur.fetchall()}
            
            resultado = []
            for item in inventario_raw:
                if item['id_producto'] in productos_dict:
                    resultado.append({
                        "id_producto": item['id_producto'],
                        "descripcion": productos_dict[item['id_producto']],
                        "cantidad": item['cantidad']
                    })
            return resultado
    finally:
        conn.close()

@app.post("/inventario/alta", dependencies=[Depends(verificar_token)])
def registrar_alta_inventario(datos: AltaInventario):
    """Inicializa el stock de un producto que ya existe en el catálogo"""
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            # Validamos que el producto exista y esté activo en el catálogo
            cur.execute("SELECT id_producto FROM productos WHERE id_producto = %s AND activo = true;", (datos.id_producto,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="El producto no existe en el catálogo o está inactivo.")
            
            cur.execute(
                "INSERT INTO inventario (id_producto, cantidad) VALUES (%s, %s);", 
                (datos.id_producto, datos.cantidad_inicial)
            )
            conn.commit()
            return {"mensaje": "Inventario inicializado correctamente"}
            
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Este producto ya cuenta con un registro de inventario activo.")
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error transaccional SQL: {e}")
    finally:
        conn.close()

@app.patch("/inventario/{id_producto}/agregar", dependencies=[Depends(verificar_token)])
def agregar_stock(id_producto: int, datos: AgregarStock):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_producto FROM inventario WHERE id_producto = %s;", (id_producto,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="El producto no está registrado en el inventario.")
            
            cur.execute("CALL KHC_Inventario_AgregarStock(%s, %s);", (id_producto, datos.cantidad_a_sumar))
            conn.commit()
            return {"mensaje": f"Se sumaron {datos.cantidad_a_sumar} unidades al producto {id_producto}"}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error transaccional SQL: {e}")
    finally:
        conn.close()
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt

app = FastAPI(title="Microservicio de Inventario", version="3.0")

# --- CONFIGURACIÓN DE SEGURIDAD JWT ---
SECRET_KEY = "secret_password_login_super_segura_32"
ALGORITHM = "HS256"
security = HTTPBearer()

# URL para el botón "Authorize" en Swagger (Puedes cambiarla por la URL de tu servicio de clientes en Render)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="https://clientes-db-fbz3.onrender.com/login")

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
class AltaProductoInventario(BaseModel):
    descripcion: str
    precio: float
    cantidad_inicial: int = Field(ge=0, description="El stock inicial no puede ser negativo")

class AgregarStock(BaseModel):
    cantidad_a_sumar: int = Field(gt=0, description="Debes sumar al menos 1 artículo")

# --- ENDPOINTS (Protegidos con JWT) ---

@app.get("/inventario", dependencies=[Depends(verificar_token)])
def consultar_inventario():
    """Obtiene todo el stock disponible"""
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM KHC_Inventario_Consultar();")
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/inventario/alta", dependencies=[Depends(verificar_token)])
def alta_producto_e_inventario(datos: AltaProductoInventario):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT KHC_Inventario_Alta(%s, %s, %s);", 
                (datos.descripcion, datos.precio, datos.cantidad_inicial)
            )
            id_generado = cur.fetchone()[0]
            conn.commit()
            return {"mensaje": "Producto e inventario creados", "id_producto": id_generado}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error transaccional SQL: {e}")
    finally:
        conn.close()

@app.patch("/inventario/{id_producto}/agregar", dependencies=[Depends(verificar_token)])
def agregar_stock(id_producto: int, datos: AgregarStock):
    """Suma stock al inventario existente de un producto"""
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            # Validar que el producto exista en el inventario
            cur.execute("SELECT id_producto FROM inventario WHERE id_producto = %s;", (id_producto,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="El producto no está registrado en el inventario.")
            
            # Ejecutar SP para sumar stock
            cur.execute("CALL KHC_Inventario_AgregarStock(%s, %s);", (id_producto, datos.cantidad_a_sumar))
            conn.commit()
            return {"mensaje": f"Se sumaron {datos.cantidad_a_sumar} unidades al producto {id_producto}"}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la transacción SQL: {e}")
    finally:
        conn.close()
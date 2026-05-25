import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
import jwt

app = FastAPI(title="Microservicio de Productos", version="3.0")

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

# ==========================================
# MODELOS DE DATOS (VERSIONAMIENTO)
# ==========================================
class ProductoAltaV1(BaseModel):
    descripcion: str = Field(..., max_length=100, description="Descripción del artículo")
    precio: float = Field(..., gt=0, description="El precio debe ser mayor a 0")

class ProductoUpdateV1(BaseModel):
    descripcion: Optional[str] = Field(None, max_length=100)
    precio: Optional[float] = Field(None, gt=0)
    activo: Optional[bool] = None

class ProductoAltaV2(BaseModel):
    descripcion: str = Field(..., max_length=100, description="Descripción del artículo")
    costo_unitario: float = Field(..., gt=0, description="Costo unitario del producto")

class ProductoUpdateV2(BaseModel):
    descripcion: Optional[str] = Field(None, max_length=100)
    costo_unitario: Optional[float] = Field(None, gt=0)
    activo: Optional[bool] = None

# ==========================================
# ENDPOINTS VERSIÓN 1 (/v1/productos)
# ==========================================
@app.get("/v1/productos", dependencies=[Depends(verificar_token)])
def obtener_productos_v1():
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM KHC_Productos_Consultar();")
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/v1/productos", dependencies=[Depends(verificar_token)])
def registrar_producto_v1(datos: ProductoAltaV1):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT KHC_Productos_Alta(%s, %s);", (datos.descripcion, datos.precio))
            id_generado = cur.fetchone()[0]
            conn.commit()
            return {"mensaje": "Producto registrado (V1)", "id_producto": id_generado}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error transaccional SQL: {e}")
    finally:
        conn.close()

@app.patch("/v1/productos/{id_producto}", dependencies=[Depends(verificar_token)])
def modificar_producto_v1(id_producto: int, datos: ProductoUpdateV1):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_producto FROM productos WHERE id_producto = %s;", (id_producto,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Producto no encontrado.")
            cur.execute("CALL KHC_Productos_Actualizar(%s, %s, %s, %s);", (id_producto, datos.descripcion, datos.precio, datos.activo))
            conn.commit()
            return {"mensaje": "Atributos actualizados correctamente (V1)"}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la transacción SQL: {e}")
    finally:
        conn.close()

@app.delete("/v1/productos/{id_producto}", dependencies=[Depends(verificar_token)])
def dar_baja_producto_v1(id_producto: int):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_producto FROM productos WHERE id_producto = %s;", (id_producto,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Producto no encontrado.")
            cur.execute("CALL KHC_Productos_Eliminar(%s);", (id_producto,))
            conn.commit()
            return {"mensaje": f"Baja lógica aplicada (V1) al producto {id_producto}"}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la transacción SQL: {e}")
    finally:
        conn.close()

# ==========================================
# ENDPOINTS VERSIÓN 2 (/v2/productos)
# ==========================================
@app.get("/v2/productos", dependencies=[Depends(verificar_token)])
def obtener_productos_v2():
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM KHC_Productos_Consultar();")
            productos = cur.fetchall()
            for prod in productos:
                prod["costo_unitario"] = prod.pop("precio")
            return productos
    finally:
        conn.close()

@app.post("/v2/productos", dependencies=[Depends(verificar_token)])
def registrar_producto_v2(datos: ProductoAltaV2):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT KHC_Productos_Alta(%s, %s);", (datos.descripcion, datos.costo_unitario))
            id_generado = cur.fetchone()[0]
            conn.commit()
            return {"mensaje": "Producto registrado usando costo_unitario (V2)", "id_producto": id_generado}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error transaccional SQL: {e}")
    finally:
        conn.close()

@app.patch("/v2/productos/{id_producto}", dependencies=[Depends(verificar_token)])
def modificar_producto_v2(id_producto: int, datos: ProductoUpdateV2):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_producto FROM productos WHERE id_producto = %s;", (id_producto,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Producto no encontrado.")
            cur.execute("CALL KHC_Productos_Actualizar(%s, %s, %s, %s);", (id_producto, datos.descripcion, datos.costo_unitario, datos.activo))
            conn.commit()
            return {"mensaje": "Atributos actualizados correctamente (V2)"}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la transacción SQL: {e}")
    finally:
        conn.close()

@app.delete("/v2/productos/{id_producto}", dependencies=[Depends(verificar_token)])
def dar_baja_producto_v2(id_producto: int):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_producto FROM productos WHERE id_producto = %s;", (id_producto,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Producto no encontrado.")
            cur.execute("CALL KHC_Productos_Eliminar(%s);", (id_producto,))
            conn.commit()
            return {"mensaje": f"Baja lógica aplicada (V2) al producto {id_producto}"}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la transacción SQL: {e}")
    finally:
        conn.close()
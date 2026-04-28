from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer
import requests
import jwt

from datos import Producto, db_productos

app = FastAPI(title="Microservicio de productos", version="1.0")

URL_INVENTARIO = "http://productos:8003"

# --- CONFIGURACIONES ---

SECRET_KEY = "secret_password_login_super_segura_32"
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://clientes:8001/login")

class ProductoUpdate(BaseModel):
    descripcion: Optional[str] = None

# --- FUNCIONES ---

def guardar_productos(productos_actuales: List[Producto]):
    with open("productos.txt", "w", encoding="utf-8") as f:
        f.write("id_producto|descripcion\n")
        for p in productos_actuales:
            f.write(f"{p.id_producto}|{p.descripcion}\n")

def verificar_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="El token ha expirado. Por favor, inicia sesión de nuevo."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token inválido o corrupto."
        )

@app.get("/productos", dependencies=[Depends(verificar_token)])
def obtener_productos():
    return db_productos

@app.post("/productos", dependencies=[Depends(verificar_token)])
def registrar_producto(nuevo_producto: Producto):
    if any(p.id_producto == nuevo_producto.id_producto for p in db_productos):
        raise HTTPException(status_code=400, detail="Error (PK): El producto ya existe en el catálogo.")
    db_productos.append(nuevo_producto)
    guardar_productos(db_productos) 
    return {"mensaje": "Producto registrado y guardado"}

@app.patch("/productos/{id_producto}", dependencies=[Depends(verificar_token)])
def actualizar_producto(id_producto: int, datos_nuevos: ProductoUpdate):
    producto_actual = next((p for p in db_productos if p.id_producto == id_producto), None)
    
    if not producto_actual:
        raise HTTPException(status_code=404, detail=f"No se encontró el producto con ID {id_producto}")
    
    if datos_nuevos.descripcion is not None:
        producto_actual.descripcion = datos_nuevos.descripcion
        
    guardar_productos(db_productos)
    return {"mensaje": "Producto actualizado correctamente", "datos": producto_actual}

@app.delete("/productos/{id_producto}", dependencies=[Depends(verificar_token)])
def eliminar_producto(id_producto: int):
    producto_a_borrar = next((p for p in db_productos if p.id_producto == id_producto), None)
    if not producto_a_borrar:
        raise HTTPException(status_code=404, detail=f"No se encontró el producto con ID {id_producto}")

    # Validar con Inventario
    try:
        resp_inventario = requests.get(f"{URL_INVENTARIO}/inventario")
        if resp_inventario.status_code == 200:
            lista_inventario = resp_inventario.json()
            # Si el producto tiene stock en el inventario, bloquear borrado
            if any(i["id_producto"] == id_producto for i in lista_inventario):
                raise HTTPException(
                    status_code=400, 
                    detail="Error de Integridad: No puedes borrar este producto porque tiene stock asignado en el Inventario. Borra su stock primero."
                )
    except requests.exceptions.ConnectionError:
        # Si la ventana del inventario está cerrada, evitar el borrado por seguridad
        raise HTTPException(
            status_code=503, 
            detail="El servicio de Inventario no responde. No es seguro borrar el producto ahora."
        )
    db_productos.remove(producto_a_borrar)
    guardar_productos(db_productos)
    
    return {"mensaje": f"Producto {id_producto} eliminado exitosamente y de forma segura"}
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import requests
from datos import Inventario, db_inventario 

app = FastAPI(title="Microservicio de inventario", version="2.0")

URL_PRODUCTOS = "http://inventario:8002"

# --- MODELOS ---
class OrdenDescuento(BaseModel):
    cantidad: int

class InventarioUpdate(BaseModel):
    cantidad: Optional[int] = Field(None, ge=0, description="El nuevo stock no puede ser negativo")

class InventarioV2(BaseModel):
    id_producto: int
    cantidad: int
    costo_unitario: int

# --- FUNCIONES AUXILIARES ---
def guardar_inventario(inventario: List[Inventario]):
    with open("inventario.txt", "w", encoding="utf-8") as f:
        f.write("id_producto|cantidad|precio\n")
        for p in inventario:
            f.write(f"{p.id_producto}|{p.cantidad}|{p.precio}\n")

#               VERSIÓN 1 (v1)

@app.get("/inventario/v1")
def obtener_inventario_v1():
    return db_inventario

@app.post("/inventario/v1")
def registrar_inventario_v1(nuevo_registro: Inventario):
    try:
        resp_productos = requests.get(f"{URL_PRODUCTOS}/productos")
        if resp_productos.status_code == 200:
            lista_productos = resp_productos.json()
            if not any(p["id_producto"] == nuevo_registro.id_producto for p in lista_productos):
                raise HTTPException(status_code=404, detail="Error: El producto no existe en el catálogo.")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="El servicio de Productos no responde.")

    if any(i.id_producto == nuevo_registro.id_producto for i in db_inventario):
        raise HTTPException(status_code=400, detail="Error: Ya existe inventario para este producto.")
        
    db_inventario.append(nuevo_registro)
    guardar_inventario(db_inventario)
    return {"mensaje": "Stock inicial registrado (V1)"}

@app.put("/inventario/v1/descontar/{id_producto}")
def descontar_stock_v1(id_producto: int, orden: OrdenDescuento):
    item = next((i for i in db_inventario if i.id_producto == id_producto), None)
    if not item:
        raise HTTPException(status_code=404, detail="El producto no tiene stock registrado.")
    if item.cantidad < orden.cantidad:
        raise HTTPException(status_code=400, detail=f"Stock insuficiente. Quedan {item.cantidad}.")
        
    item.cantidad -= orden.cantidad
    guardar_inventario(db_inventario) 
    return {"mensaje": "Stock actualizado tras descuento (V1)", "stock_restante": item.cantidad}

@app.patch("/inventario/v1/{id_producto}")
def actualizar_inventario_v1(id_producto: int, datos_nuevos: InventarioUpdate):
    item_actual = next((i for i in db_inventario if i.id_producto == id_producto), None)
    if not item_actual:
        raise HTTPException(status_code=404, detail=f"No hay inventario registrado para el producto {id_producto}")
    if datos_nuevos.cantidad is not None:
        item_actual.cantidad = datos_nuevos.cantidad

    guardar_inventario(db_inventario)
    return {"mensaje": "Stock actualizado correctamente (V1)", "datos": item_actual}

@app.delete("/inventario/v1/{id_producto}")
def eliminar_inventario_v1(id_producto: int):
    item_a_borrar = next((i for i in db_inventario if i.id_producto == id_producto), None)
    if not item_a_borrar:
        raise HTTPException(status_code=404, detail=f"No hay inventario registrado para el producto {id_producto}")

    db_inventario.remove(item_a_borrar)
    guardar_inventario(db_inventario)
    return {"mensaje": f"Registro de inventario del producto {id_producto} eliminado exitosamente (V1)"}

#               VERSIÓN 2 (v2)

@app.get("/inventario/v2")
def obtener_inventario_v2():
    # Convertimos precio a costo_unitario
    inventario_v2 = []
    for item in db_inventario:
        inventario_v2.append({
            "id_producto": item.id_producto,
            "cantidad": item.cantidad,
            "costo_unitario": item.precio 
        })
    return inventario_v2

@app.post("/inventario/v2")
def registrar_inventario_v2(nuevo_registro: InventarioV2):
    try:
        resp_productos = requests.get(f"{URL_PRODUCTOS}/productos")
        if resp_productos.status_code == 200:
            lista_productos = resp_productos.json()
            if not any(p["id_producto"] == nuevo_registro.id_producto for p in lista_productos):
                raise HTTPException(status_code=404, detail="Error: El producto no existe en el catálogo.")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="El servicio de Productos no responde.")

    if any(i.id_producto == nuevo_registro.id_producto for i in db_inventario):
        raise HTTPException(status_code=400, detail="Error: Ya existe inventario para este producto.")
        
    registro_bd = Inventario(
        id_producto=nuevo_registro.id_producto,
        cantidad=nuevo_registro.cantidad,
        precio=nuevo_registro.costo_unitario 
    )
    
    db_inventario.append(registro_bd)
    guardar_inventario(db_inventario)
    return {"mensaje": "Stock inicial registrado usando costo_unitario (V2)"}

@app.put("/inventario/v2/descontar/{id_producto}")
def descontar_stock_v2(id_producto: int, orden: OrdenDescuento):
    item = next((i for i in db_inventario if i.id_producto == id_producto), None)
    if not item:
        raise HTTPException(status_code=404, detail="El producto no tiene stock registrado.")
    if item.cantidad < orden.cantidad:
        raise HTTPException(status_code=400, detail=f"Stock insuficiente. Quedan {item.cantidad}.")
        
    item.cantidad -= orden.cantidad
    guardar_inventario(db_inventario) 
    return {"mensaje": "Stock actualizado tras descuento (V2)", "stock_restante": item.cantidad}

@app.patch("/inventario/v2/{id_producto}")
def actualizar_inventario_v2(id_producto: int, datos_nuevos: InventarioUpdate):
    item_actual = next((i for i in db_inventario if i.id_producto == id_producto), None)
    if not item_actual:
        raise HTTPException(status_code=404, detail=f"No hay inventario registrado para el producto {id_producto}")
    if datos_nuevos.cantidad is not None:
        item_actual.cantidad = datos_nuevos.cantidad

    guardar_inventario(db_inventario)
    
    datos_v2 = {
        "id_producto": item_actual.id_producto,
        "cantidad": item_actual.cantidad,
        "costo_unitario": item_actual.precio
    }
    return {"mensaje": "Stock actualizado correctamente (V2)", "datos": datos_v2}

@app.delete("/inventario/v2/{id_producto}")
def eliminar_inventario_v2(id_producto: int):
    # La lógica de borrado es idéntica a la V1
    item_a_borrar = next((i for i in db_inventario if i.id_producto == id_producto), None)
    if not item_a_borrar:
        raise HTTPException(status_code=404, detail=f"No hay inventario registrado para el producto {id_producto}")

    db_inventario.remove(item_a_borrar)
    guardar_inventario(db_inventario)
    return {"mensaje": f"Registro de inventario del producto {id_producto} eliminado exitosamente (V2)"}
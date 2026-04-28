import json
import pika
import jwt
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional

from datos import Pedido, db_pedidos 

app = FastAPI(title="Microservicio de Pedidos", version="1.0")

RABBITMQ_HOST = "host.docker.internal"

# --- SEGURIDAD JWT ---
SECRET_KEY = "secret_password_login_super_segura_32"
ALGORITHM = "HS256"
security = HTTPBearer()

# Apunta al microservicio de clientes para que Swagger sepa dónde hacer login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://clientes:8001/login")

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials # Extrae el string del token puro
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")
    
# --- MODELOS EXTRA ---
class PedidoUpdate(BaseModel):
    cantidad: Optional[int] = Field(None, gt=0, description="La nueva cantidad debe ser mayor a 0")

class EstadoUpdate(BaseModel):
    estado: str

# --- FUNCIONES ---
def guardar_pedidos(pedidos_actuales: List[Pedido]):
    with open("pedidos.txt", "w", encoding="utf-8") as f:
        # Se agrega la columna 'estado' al archivo de texto
        f.write("id_pedido|id_producto|cantidad|id_cliente|estado\n")
        for p in pedidos_actuales:
            f.write(f"{p.id_pedido}|{p.id_producto}|{p.cantidad}|{p.id_cliente}|{p.estado}\n")

def publicar_pedido_en_cola(datos_pedido: dict):
    try:
        credenciales = pika.PlainCredentials('guest', 'guest')
        parametros = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credenciales)
        conexion = pika.BlockingConnection(parametros)
        canal = conexion.channel()
        # durable=True asegura que la cola no se borre si RabbitMQ se reinicia
        canal.queue_declare(queue='cola_procesamiento_pedidos', durable=True)
        canal.basic_publish(
            exchange='',
            routing_key='cola_procesamiento_pedidos',
            body=json.dumps(datos_pedido),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        conexion.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al encolar en RabbitMQ: {e}")

# --- ENDPOINTS ---

@app.get("/pedidos", dependencies=[Depends(verificar_token)])
def obtener_pedidos():
    return db_pedidos

@app.post("/pedidos", dependencies=[Depends(verificar_token)])
def registrar_pedido(nuevo_pedido: Pedido):
    if any(p.id_pedido == nuevo_pedido.id_pedido for p in db_pedidos):
        raise HTTPException(status_code=400, detail="El pedido ya existe.")

    # Aseguramos que siempre nazca como PENDIENTE
    nuevo_pedido.estado = "PENDIENTE"
    
    db_pedidos.append(nuevo_pedido)
    guardar_pedidos(db_pedidos)
    
    datos_dict = nuevo_pedido.model_dump() 
    publicar_pedido_en_cola(datos_dict)
    
    return {"mensaje": "Pedido recibido. Está en cola para validación y procesamiento.", "datos": nuevo_pedido}

@app.patch("/pedidos/{id_pedido}/estado")
def actualizar_estado(id_pedido: int, datos: EstadoUpdate):
    pedido = next((p for p in db_pedidos if p.id_pedido == id_pedido), None)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    
    pedido.estado = datos.estado
    guardar_pedidos(db_pedidos)
    return {"mensaje": f"Estado actualizado a {datos.estado}"}

@app.delete("/pedidos/{id_pedido}", dependencies=[Depends(verificar_token)])
def eliminar_pedido(id_pedido: int):
    pedido = next((p for p in db_pedidos if p.id_pedido == id_pedido), None)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    
    db_pedidos.remove(pedido)
    guardar_pedidos(db_pedidos)
    return {"mensaje": f"Pedido {id_pedido} cancelado/eliminado de la base."}
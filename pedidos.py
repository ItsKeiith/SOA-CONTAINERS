import os
import json
import pika
import jwt
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

app = FastAPI(title="Microservicio de Pedidos", version="3.0")

# --- CONFIGURACIONES ---
# Preparado para la nube: Si no encuentra la variable, usa tu entorno local de Docker
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "host.docker.internal")

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://shopnow_663n_user:mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl@dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com/shopnow_663n"
)

# --- SEGURIDAD JWT ---
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

def obtener_conexion():
    try:
        return psycopg2.connect(DATABASE_URL)
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Error de conexión a la BD: {e}")

# --- MODELOS DE DATOS ---
class Pedido(BaseModel):
    id_pedido: int
    id_cliente: int
    id_producto: int
    cantidad: int = Field(gt=0, description="La cantidad debe ser mayor a 0")

# --- RABBITMQ ---
def publicar_pedido_en_cola(datos_pedido: dict):
    try:
        # Si usas una URL en la nube (como CloudAMQP), pika la parsea automáticamente
        parametros = pika.URLParameters(RABBITMQ_URL) if "amqp" in RABBITMQ_URL else pika.ConnectionParameters(host=RABBITMQ_URL)
        conexion = pika.BlockingConnection(parametros)
        canal = conexion.channel()
        
        canal.queue_declare(queue='cola_procesamiento_pedidos', durable=True)
        canal.basic_publish(
            exchange='',
            routing_key='cola_procesamiento_pedidos',
            body=json.dumps(datos_pedido),
            properties=pika.BasicProperties(delivery_mode=2) # Hace el mensaje persistente
        )
        conexion.close()
    except Exception as e:
        # No bloqueamos el pedido en BD si Rabbit falla, pero lo notificamos en consola
        print(f"[Advertencia] El pedido se guardó en BD, pero RabbitMQ falló: {e}")

# --- ENDPOINTS ---

@app.get("/pedidos", dependencies=[Depends(verificar_token)])
def consultar_pedidos():
    """Obtiene todos los pedidos registrados en la base de datos"""
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM KHC_Pedidos_Consultar();")
            # Convertimos fechas a string para que FastAPI las serialice a JSON sin problemas
            pedidos = cur.fetchall()
            for p in pedidos:
                if 'created_at' in p and p['created_at']:
                    p['created_at'] = p['created_at'].isoformat()
            return pedidos
    finally:
        conn.close()

@app.post("/pedidos", dependencies=[Depends(verificar_token)])
def registrar_pedido(nuevo_pedido: Pedido):
    """Registra el pedido en Postgres, descuenta inventario y lo encola en RabbitMQ"""
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            # Control de duplicados (PK)
            cur.execute("SELECT id_pedido FROM pedidos WHERE id_pedido = %s;", (nuevo_pedido.id_pedido,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="El ID del pedido ya existe.")
            
            # 1. Guardar en BD y procesar inventario mediante el SP
            cur.execute(
                "CALL khc_pedidos_agregar(%s, %s, %s, %s);", 
                (nuevo_pedido.id_pedido, nuevo_pedido.id_cliente, nuevo_pedido.id_producto, nuevo_pedido.cantidad)
            )
            conn.commit()
            
            # 2. Publicar evento en RabbitMQ
            datos_dict = nuevo_pedido.model_dump()
            publicar_pedido_en_cola(datos_dict)
            
            return {
                "mensaje": "Pedido registrado, inventario descontado y encolado en RabbitMQ exitosamente.", 
                "datos": datos_dict
            }
            
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Error de Integridad: El cliente o el producto no existen en la base de datos.")
    except psycopg2.Error as e:
        conn.rollback()
        error_pg = str(e)
        
        # Interceptar excepciones personalizadas lanzadas desde PL/pgSQL
        if "ERR_STOCK_INSUFICIENTE" in error_pg:
            mensaje_limpio = error_pg.split("ERR_STOCK_INSUFICIENTE: ")[-1].split("\n")[0]
            raise HTTPException(status_code=400, detail=mensaje_limpio)
        
        elif "ERR_NO_INVENTARIO" in error_pg:
            raise HTTPException(status_code=404, detail="El producto solicitado no cuenta con un registro de inventario.")
            
        # Para cualquier otro error de base de datos no contemplado
        raise HTTPException(status_code=500, detail=f"Error transaccional SQL: {error_pg}")
    finally:
        conn.close()
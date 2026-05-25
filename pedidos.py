import os
import json
import pika
import jwt
import psycopg2
import threading
import time
import requests  # Importación para comunicación REST síncrona
from contextlib import asynccontextmanager
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

# --- CONFIGURACIONES ---
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "host.docker.internal")
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://shopnow_663n_user:mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl@dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com/shopnow_663n"
)
SECRET_KEY = "secret_password_login_super_segura_32"
ALGORITHM = "HS256"
security = HTTPBearer()

API_CLIENTES = os.getenv("API_CLIENTES", "https://inventario-db-h4jd.onrender.com")
API_PRODUCTOS = os.getenv("API_PRODUCTOS", "https://productos-db.onrender.com")

# --- LÓGICA DEL WORKER (RABBITMQ CONSUMER) ---
def procesar_mensaje(ch, method, properties, body):
    pedido = json.loads(body)
    print(f"\nNuevo pedido validado recibido en Worker: ID {pedido['id_pedido']}")
    
    try:
        # Lógica de post-procesamiento (Facturación / Logística)
        print(f"Procesamiento completado para el pedido {pedido['id_pedido']}.")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"Error interno procesando el pedido: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        time.sleep(5)

def iniciar_worker():
    try:
        servidor_impreso = RABBITMQ_URL.split('@')[-1] if '@' in RABBITMQ_URL else RABBITMQ_URL
        print(f"Hilo del Worker conectando a RabbitMQ en: {servidor_impreso}")
        
        if "amqp" in RABBITMQ_URL:
            parametros = pika.URLParameters(RABBITMQ_URL)
        else:
            parametros = pika.ConnectionParameters(host=RABBITMQ_URL)
            
        conexion = pika.BlockingConnection(parametros)
        canal = conexion.channel()
        canal.queue_declare(queue='cola_procesamiento_pedidos', durable=True)
        canal.basic_qos(prefetch_count=1)
        canal.basic_consume(queue='cola_procesamiento_pedidos', on_message_callback=procesar_mensaje)
        
        print("Hilo del Worker iniciado. Escuchando peticiones en segundo plano...")
        canal.start_consuming()
    except Exception as e:
        print(f"[Error Crítico en Hilo del Worker] No se pudo conectar a RabbitMQ: {e}")

# --- LIFESPAN (MANEJO DEL HILO AL ARRANCAR FASTAPI) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    thread_worker = threading.Thread(target=iniciar_worker, daemon=True)
    thread_worker.start()
    yield

app = FastAPI(title="Microservicio de Pedidos (Orquestador)", version="3.0", lifespan=lifespan)

# --- UTILIDADES API ---
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

def publicar_pedido_en_cola(datos_pedido: dict):
    try:
        parametros = pika.URLParameters(RABBITMQ_URL) if "amqp" in RABBITMQ_URL else pika.ConnectionParameters(host=RABBITMQ_URL)
        conexion = pika.BlockingConnection(parametros)
        canal = conexion.channel()
        
        canal.queue_declare(queue='cola_procesamiento_pedidos', durable=True)
        canal.basic_publish(
            exchange='',
            routing_key='cola_procesamiento_pedidos',
            body=json.dumps(datos_pedido),
            properties=pika.BasicProperties(delivery_mode=2) 
        )
        conexion.close()
    except Exception as e:
        print(f"[Advertencia] El pedido se guardó en BD, pero RabbitMQ falló: {e}")

# --- MODELOS ---
class Pedido(BaseModel):
    id_cliente: int
    id_producto: int
    amount: int = Field(gt=0, alias="cantidad", description="La cantidad debe ser mayor a 0")
    
    class Config:
        populate_by_name = True

# --- ENDPOINTS ---
@app.get("/pedidos", dependencies=[Depends(verificar_token)])
def consultar_pedidos():
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM KHC_Pedidos_Consultar();")
            pedidos = cur.fetchall()
            for p in pedidos:
                if 'created_at' in p and p['created_at']:
                    p['created_at'] = p['created_at'].isoformat()
            return pedidos
    finally:
        conn.close()

@app.post("/pedidos")
def registrar_pedido(nuevo_pedido: Pedido, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Orquestador: Valida datos síncronamente mediante REST y delega el flujo asíncrono"""
    
    token = credentials.credentials
    headers_internos = {"Authorization": f"Bearer {token}"}
    
    try:
        resp_clientes = requests.get(f"{API_CLIENTES}/clientes", headers=headers_internos, timeout=5)
        
        if resp_clientes.status_code == 503:
            raise HTTPException(status_code=503, detail="El departamento de Clientes no se encuentra operativo.")
        if resp_clientes.status_code != 200:
            raise HTTPException(status_code=resp_clientes.status_code, detail="Error al validar las credenciales del cliente.")
            
        lista_clientes = resp_clientes.json()
        cliente_valido = any(c.get("id_cliente") == nuevo_pedido.id_cliente and c.get("activo") is True for c in lista_clientes)
        
        if not cliente_valido:
            raise HTTPException(status_code=400, detail="El ID de cliente proporcionado no existe o está dado de baja.")
            
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Falla en cascada evitada: El microservicio de Clientes no responde. Intente más tarde."
        )

    try:
        resp_productos = requests.get(f"{API_PRODUCTOS}/v1/productos", headers=headers_internos, timeout=5)

        if resp_productos.status_code == 503:
            raise HTTPException(status_code=503, detail="El departamento de Productos no se encuentra operativo.")
        if resp_productos.status_code != 200:
            raise HTTPException(status_code=resp_productos.status_code, detail="Error al consultar el catálogo de productos.")
            
        lista_productos = resp_productos.json()

        producto_valido = any(p.get("id_producto") == nuevo_pedido.id_producto and p.get("activo") is True for p in lista_productos)
        
        if not producto_valido:
            raise HTTPException(status_code=400, detail="El ID de producto solicitado no existe en el catálogo o está inactivo.")
            
    except requests.exceptions.RequestException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Falla en cascada evitada: El microservicio de Productos no responde. Intente más tarde."
        )

    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT khc_pedidos_agregar(%s, %s, %s);", 
                (nuevo_pedido.id_cliente, nuevo_pedido.id_producto, nuevo_pedido.amount)
            )
            id_generado = cur.fetchone()[0]
            conn.commit()
            
            datos_dict = nuevo_pedido.model_dump(by_alias=True)
            datos_dict["id_pedido"] = id_generado
            publicar_pedido_en_cola(datos_dict)
            
            return {
                "mensaje": "Pedido validado por REST, registrado en BD y encolado en RabbitMQ exitosamente.", 
                "datos": datos_dict
            }
            
    except psycopg2.Error as e:
        conn.rollback()
        error_pg = str(e)
        if "ERR_STOCK_INSUFICIENTE" in error_pg:
            mensaje_limpio = error_pg.split("ERR_STOCK_INSUFICIENTE: ")[-1].split("\n")[0]
            raise HTTPException(status_code=400, detail=mensaje_limpio)
        elif "ERR_NO_INVENTARIO" in error_pg:
            raise HTTPException(status_code=404, detail="El producto no cuenta con registro de inventario inicial.")
            
        raise HTTPException(status_code=500, detail=f"Error transaccional SQL: {error_pg}")
    finally:
        conn.close()
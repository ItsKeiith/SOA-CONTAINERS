import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import pika
import json
import jwt
from datetime import datetime, timedelta, timezone

app = FastAPI(title="Microservicio de clientes", version="2.0")

# --- CONFIGURACIONES ---
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "host.docker.internal")
SECRET_KEY = "secret_password_login_super_segura_32"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Cadena de conexión a PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://shopnow_663n_user:mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl@dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com/shopnow_663n"
)

# --- MODELOS DE DATOS ---
class Cliente(BaseModel):
    id_cliente: int 
    nombre: str
    correo: EmailStr
    direccion: str
    telefono: str
    activo: bool = True

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[EmailStr] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    activo: Optional[bool] = None

class LoginData(BaseModel):
    correo: str
    telefono: str

# --- FUNCIONES DE BASE DE DATOS Y UTILIDADES ---
def obtener_conexion():
    try:
        return psycopg2.connect(DATABASE_URL)
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Error de conexión a la base de datos: {e}")

def publicar_evento_cliente(evento: str, datos: dict):
    try:
        credenciales = pika.PlainCredentials('guest', 'guest')
        parametros = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credenciales)
        conexion = pika.BlockingConnection(parametros)
        canal = conexion.channel()
        canal.queue_declare(queue='eventos_clientes')
        mensaje = {"evento": evento, "datos": datos}
        canal.basic_publish(exchange='', routing_key='eventos_clientes', body=json.dumps(mensaje))
        conexion.close()
    except Exception as e:
        print(f"[Error] Conexión a RabbitMQ fallida: {e}")

def crear_token_acceso(datos: dict):
    datos_a_codificar = datos.copy()
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    datos_a_codificar.update({"exp": expiracion})
    return jwt.encode(datos_a_codificar, SECRET_KEY, algorithm=ALGORITHM)

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

# --- ENDPOINTS REST ---

@app.post("/login")
def iniciar_sesion(credenciales: LoginData):
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM KHC_Login(%s, %s);", (credenciales.correo, credenciales.telefono))
            cliente_valido = cur.fetchone()
            
            if not cliente_valido:
                raise HTTPException(status_code=401, detail="Credenciales inválidas o usuario inactivo")
            
            datos_token = {"sub": cliente_valido["correo"], "id_cliente": cliente_valido["id_cliente"]}
            return {"access_token": crear_token_acceso(datos_token), "token_type": "bearer"}
    finally:
        conn.close()

@app.get("/clientes", dependencies=[Depends(verificar_token)])
def obtener_clientes():
    conn = obtener_conexion()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM KHC_Clientes_Obtener();")
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/clientes", dependencies=[Depends(verificar_token)])
def registrar_cliente(nuevo_cliente: Cliente):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            # Control de integridad de clave primaria
            cur.execute("SELECT id_cliente FROM clientes WHERE id_cliente = %s;", (nuevo_cliente.id_cliente,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Identificador de cliente duplicado.")
            
            cur.execute(
                "CALL KHC_Clientes_Agregar(%s, %s, %s, %s, %s, %s);", 
                (nuevo_cliente.id_cliente, nuevo_cliente.nombre, nuevo_cliente.correo, nuevo_cliente.direccion, nuevo_cliente.telefono, nuevo_cliente.activo)
            )
            conn.commit()
            
            publicar_evento_cliente("cliente_creado", {"id_cliente": nuevo_cliente.id_cliente, "nombre": nuevo_cliente.nombre})
            return {"mensaje": "Transacción de registro completada"}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la transacción SQL: {e}")
    finally:
        conn.close()

@app.delete("/clientes/{id_cliente}")
def eliminar_cliente(id_cliente: int):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_cliente FROM clientes WHERE id_cliente = %s;", (id_cliente,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Recurso no encontrado en la base de datos")
            
            # Ejecución de baja lógica
            cur.execute("CALL KHC_Clientes_Eliminar(%s);", (id_cliente,))
            conn.commit()
            
            publicar_evento_cliente("cliente_eliminado", {"id_cliente": id_cliente})
            return {"mensaje": "Baja lógica de cliente ejecutada"}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la transacción SQL: {e}")
    finally:
        conn.close()

@app.patch("/clientes/{id_cliente}")
def actualizar_cliente(id_cliente: int, datos_nuevos: ClienteUpdate):
    conn = obtener_conexion()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_cliente FROM clientes WHERE id_cliente = %s;", (id_cliente,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Recurso no encontrado en la base de datos")
            
            cur.execute(
                "CALL KHC_Clientes_Actualizar(%s, %s, %s, %s, %s, %s);", 
                (id_cliente, datos_nuevos.nombre, datos_nuevos.correo, datos_nuevos.direccion, datos_nuevos.telefono, datos_nuevos.activo)
            )
            conn.commit()
            return {"mensaje": "Actualización de atributos completada"}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la transacción SQL: {e}")
    finally:
        conn.close()
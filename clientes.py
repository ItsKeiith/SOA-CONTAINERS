from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import pika
import json
import jwt
from datetime import datetime, timedelta, timezone

from datos import Cliente, db_clientes 

app = FastAPI(title="Microservicio de clientes", version="1.0")

# --- CONFIGURACIONES ---

# Configuración básica para RabbitMQ en Docker local
RABBITMQ_HOST = "host.docker.internal"

# Configuración JWT
SECRET_KEY = "secret_password_login_super_segura_32"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[EmailStr] = None
    telefono: Optional[int] = None

class LoginData(BaseModel): #Parametros a recibir para logeo
    correo: str
    telefono: int

# --- FUNCIONES ---

def guardar_clientes(clientes: List[Cliente]):
    with open("clientes.txt", "w", encoding="utf-8") as f:
        f.write("id_cliente|nombre|correo|telefono\n")
        for c in clientes:
            f.write(f"{c.id_cliente}|{c.nombre}|{c.correo}|{c.telefono}\n")

def publicar_evento_cliente(evento: str, datos: dict):
    """Función para enviar mensajes a RabbitMQ con credenciales personalizadas"""
    try:
        credenciales = pika.PlainCredentials('guest', 'guest')
        parametros = pika.ConnectionParameters(
            host=RABBITMQ_HOST, 
            credentials=credenciales
        )
        conexion = pika.BlockingConnection(parametros)
        canal = conexion.channel()
        
        canal.queue_declare(queue='eventos_clientes')
        
        mensaje = {"evento": evento, "datos": datos}
        canal.basic_publish(
            exchange='',
            routing_key='eventos_clientes',
            body=json.dumps(mensaje)
        )
        conexion.close()
        print(f"[*] Evento '{evento}' publicado en RabbitMQ")
    except Exception as e:
        print(f"[!] Error al conectar con RabbitMQ: {e}")

def crear_token_acceso(datos: dict):
    datos_a_codificar = datos.copy()
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) #Cuando expira
    datos_a_codificar.update({"exp": expiracion})
    
    token_jwt = jwt.encode(datos_a_codificar, SECRET_KEY, algorithm=ALGORITHM) #Generar el token encriptado
    return token_jwt

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials # Extrae el string del token puro
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

# --- ENDPOINTS ---

@app.post("/login")
def iniciar_sesion(credenciales: LoginData):
    cliente_valido = next(
        (c for c in db_clientes if c.correo == credenciales.correo and c.telefono == credenciales.telefono), #Se busca al cliente en la base de datos
        None
    )
    
    if not cliente_valido: #Rechazar si no existe
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    datos_token = { #Recibir los datos que irán en el token
        "sub": cliente_valido.correo, 
        "id_cliente": cliente_valido.id_cliente
    }
    
    token = crear_token_acceso(datos_token)
    return {"access_token": token, "token_type": "bearer"} #Devolverlo en formato baerer

@app.get("/clientes", dependencies=[Depends(verificar_token)])
def obtener_clientes():
    return db_clientes

@app.post("/clientes", dependencies=[Depends(verificar_token)])
def registrar_cliente(nuevo_cliente: Cliente):
    if any(c.id_cliente == nuevo_cliente.id_cliente for c in db_clientes):
        raise HTTPException(status_code=400, detail="El cliente ya existe.")
    
    db_clientes.append(nuevo_cliente)
    guardar_clientes(db_clientes)
    
    publicar_evento_cliente(
        evento="cliente_creado", 
        datos={"id_cliente": nuevo_cliente.id_cliente, "nombre": nuevo_cliente.nombre}
    )
    
    return {"mensaje": "Cliente registrado exitosamente"}

@app.delete("/clientes/{id_cliente}")
def eliminar_cliente(id_cliente: int):
    cliente_a_borrar = next((c for c in db_clientes if c.id_cliente == id_cliente), None)
    if not cliente_a_borrar:
        raise HTTPException(status_code=404, detail=f"No se encontró el cliente con ID {id_cliente}")
    
    db_clientes.remove(cliente_a_borrar)
    guardar_clientes(db_clientes)
    
    publicar_evento_cliente(evento="cliente_eliminado", datos={"id_cliente": id_cliente})
    
    return {"mensaje": f"Cliente {id_cliente} eliminado exitosamente"}

@app.patch("/clientes/{id_cliente}")
def actualizar_cliente(id_cliente: int, datos_nuevos: ClienteUpdate):
    cliente_actual = next((c for c in db_clientes if c.id_cliente == id_cliente), None)
    if not cliente_actual:
        raise HTTPException(status_code=404, detail=f"No se encontró el cliente con ID {id_cliente}")

    if datos_nuevos.nombre is not None:
        cliente_actual.nombre = datos_nuevos.nombre        
    if datos_nuevos.correo is not None:
        cliente_actual.correo = datos_nuevos.correo
    if datos_nuevos.telefono is not None:
        cliente_actual.telefono = datos_nuevos.telefono
        
    guardar_clientes(db_clientes)
    return {"mensaje": "Cliente actualizado correctamente", "datos": cliente_actual}
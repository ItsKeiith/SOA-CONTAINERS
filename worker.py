import pika
import json
import time
import requests
import jwt
from datetime import datetime, timedelta, timezone

URL_CLIENTES = "http://cleintes:8001"
URL_PRODUCTOS = "http://productos:8002"
URL_INVENTARIO = "http://inventario:8003"
URL_PEDIDOS = "http://pedidos:8004" # Ajusta el puerto si tu pedidos.py corre en otro
RABBITMQ_HOST = "host.docker.internal"

SECRET_KEY = "secret_password_login_super_segura_32"
ALGORITHM = "HS256"

def generar_token_interno():
    """Genera un token válido para que el Worker pueda pasar la seguridad de los otros microservicios"""
    datos = {"sub": "worker_sistema", "rol": "admin"}
    expiracion = datetime.now(timezone.utc) + timedelta(minutes=60)
    datos.update({"exp": expiracion})
    return jwt.encode(datos, SECRET_KEY, algorithm=ALGORITHM)

def cambiar_estado_pedido(id_pedido: int, nuevo_estado: str):
    """Llama al microservicio de pedidos para actualizar cómo quedó la orden"""
    try:
        requests.patch(f"{URL_PEDIDOS}/pedidos/{id_pedido}/estado", json={"estado": nuevo_estado})
    except Exception as e:
        print(f"[!] No se pudo actualizar el estado del pedido en la base de datos: {e}")

def procesar_mensaje(ch, method, properties, body):
    pedido = json.loads(body)
    print(f"\n[*] Evaluando pedido ID {pedido['id_pedido']}...")

    # Preparamos los headers de seguridad para las peticiones
    headers = {"Authorization": f"Bearer {generar_token_interno()}"}

    try:
        # 1. Validar si el Cliente y el Producto existen
        resp_clientes = requests.get(f"{URL_CLIENTES}/clientes", headers=headers)
        resp_clientes.raise_for_status() 
        if not any(c["id_cliente"] == pedido["id_cliente"] for c in resp_clientes.json()):
            print("[-] Rechazado: El cliente no existe.")
            cambiar_estado_pedido(pedido["id_pedido"], "RECHAZADO_CLIENTE_INVALIDO")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
            
        resp_productos = requests.get(f"{URL_PRODUCTOS}/productos", headers=headers)
        resp_productos.raise_for_status()
        if not any(p["id_producto"] == pedido["id_producto"] for p in resp_productos.json()):
            print("[-] Rechazado: El producto no existe en catálogo.")
            cambiar_estado_pedido(pedido["id_pedido"], "RECHAZADO_PRODUCTO_INVALIDO")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # 2. Descontar Inventario
        datos_descuento = {"cantidad": pedido['cantidad']}
        resp_inv = requests.put(f"{URL_INVENTARIO}/inventario/v1/descontar/{pedido['id_producto']}", json=datos_descuento, headers=headers)
        
        if resp_inv.status_code == 200:
            print(f"[+] ÉXITO: Stock descontado. Pedido {pedido['id_pedido']} finalizado.")
            cambiar_estado_pedido(pedido["id_pedido"], "COMPLETADO")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            print(f"[-] Rechazado: {resp_inv.text}")
            cambiar_estado_pedido(pedido["id_pedido"], "RECHAZADO_SIN_STOCK")
            ch.basic_ack(delivery_tag=method.delivery_tag)

    except requests.exceptions.RequestException as e:
        # AQUÍ OCURRE LA MAGIA. Si Inventario/Clientes/Productos está apagado, cae aquí.
        print(f"[!] SERVICIOS CAÍDOS o INACCESIBLES. Reencolando para intentar más tarde...")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        time.sleep(5) 

def iniciar_worker():
    credenciales = pika.PlainCredentials('guest', 'guest')
    parametros = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credenciales)
    conexion = pika.BlockingConnection(parametros)
    canal = conexion.channel()
    
    canal.queue_declare(queue='cola_procesamiento_pedidos', durable=True)
    canal.basic_qos(prefetch_count=1)
    canal.basic_consume(queue='cola_procesamiento_pedidos', on_message_callback=procesar_mensaje)
    
    print(" [*] Escuchando la cola 'cola_procesamiento_pedidos'. Presiona CTRL+C para salir.")
    canal.start_consuming()

if __name__ == '__main__':
    iniciar_worker()
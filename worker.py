import os
import json
import pika
import time

RABBITMQ_URL = os.getenv("RABBITMQ_URL")

def procesar_mensaje(ch, method, properties, body):
    pedido = json.loads(body)
    print(f"\n[*] 📥 Nuevo pedido validado recibido: ID {pedido['id_pedido']}")
    
    try:
        # Como la BD ya validó y descontó el stock, aquí solo hacemos tareas secundarias.
        print(f"   [~] Generando factura para el cliente {pedido['id_cliente']}...")
        time.sleep(2) # Simulamos el tiempo de procesamiento
        
        print("   [~] Notificando al área de logística para el envío...")
        time.sleep(1)
        
        print(f"   [+]  Procesamiento completado para el pedido {pedido['id_pedido']}.")
        
        # Confirmamos a RabbitMQ que el mensaje fue procesado con éxito para que lo borre de la cola
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"   [!] Error interno procesando el pedido: {e}")
        # Si falla (ej. se cayó el servidor de correos), le decimos a RabbitMQ que reencole el mensaje
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        time.sleep(5)

def iniciar_worker():
    # Ocultamos la contraseña al imprimir en los logs
    servidor_impreso = RABBITMQ_URL.split('@')[-1] if '@' in RABBITMQ_URL else RABBITMQ_URL
    print(f"[*] Conectando a RabbitMQ en: {servidor_impreso}")
    
    if "amqp" in RABBITMQ_URL:
        parametros = pika.URLParameters(RABBITMQ_URL)
    else:
        parametros = pika.ConnectionParameters(host=RABBITMQ_URL)
        
    conexion = pika.BlockingConnection(parametros)
    canal = conexion.channel()
    
    canal.queue_declare(queue='cola_procesamiento_pedidos', durable=True)
    
    # Procesar un mensaje a la vez (Fair dispatch)
    canal.basic_qos(prefetch_count=1)
    canal.basic_consume(queue='cola_procesamiento_pedidos', on_message_callback=procesar_mensaje)
    
    print(" [*]  Worker iniciado. Escuchando la cola 'cola_procesamiento_pedidos'...")
    canal.start_consuming()

if __name__ == '__main__':
    iniciar_worker()
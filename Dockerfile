# Usamos una imagen de Python ligera
FROM python:3.12

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos primero el requirements y lo instalamos (esto optimiza la caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install fastapi uvicorn pika PyJWT psycopg2-binary

# Copiamos todo el resto del código (los .py y los .txt) al contenedor
COPY . .

# No ponemos un CMD aquí, porque se lo pasaremos desde el docker-compose dependiendo del servicio
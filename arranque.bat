@echo off
echo ===================================================
echo Iniciando Microservicios de ShopNow...
echo ===================================================

echo Iniciando Clientes (Puerto 8001)...
start "MS Clientes" cmd /k "python -m uvicorn clientes:app --port 8001 --reload"

echo Iniciando Productos en C# (Puerto 8002)...
:: Entramos a la carpeta del proyecto C# y lo ejecutamos
start "MS Productos (C#)" cmd /k "cd ProductosAPI && dotnet run"

echo Iniciando Inventario (Puerto 8003)...
start "MS Inventario" cmd /k "python -m uvicorn inventario:app --port 8003 --reload"

echo Iniciando API de Pedidos (Puerto 8004)...
start "MS Pedidos" cmd /k "python -m uvicorn pedidos:app --port 8004 --reload"

echo Iniciando Worker Asincrono de Pedidos...
:: Este es un script normal de Python, no usa uvicorn
start "Worker Pedidos" cmd /k "python worker_pedidos.py"

echo ===================================================
echo ¡Todos los servicios y el worker estan corriendo! 
echo Recuerda asegurarte de que tu contenedor de RabbitMQ este encendido en Docker.
echo Cierra las ventanas emergentes para apagar el servidor.
echo ===================================================
pause
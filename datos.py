from pydantic import BaseModel, EmailStr, Field

class Cliente(BaseModel):
    id_cliente: int 
    nombre: str
    correo: EmailStr
    telefono: int

class Producto(BaseModel):
    id_producto: int
    descripcion: str

class Inventario(BaseModel):
    id_producto: int
    cantidad: int = Field(ge=0, description="Mayor o igual a 0")
    precio: int

class Pedido(BaseModel):
    id_pedido: int
    id_cliente: int
    id_producto: int
    cantidad: int = Field(gt=0, description="No puede ser 0")
    estado: str = Field(default="PENDIENTE", description="Puede ser PENDIENTE, COMPLETADO o RECHAZADO")

def cargar_pedidos():
    lista = []
    try:
        with open("pedidos.txt", "r", encoding="utf-8") as f:
            for linea in f.readlines()[1:]:
                datos = linea.strip().split("|")
                # Ahora esperamos 5 datos porque agregamos el estado
                if len(datos) == 5: 
                    nuevo_pedido = Pedido(
                        id_pedido=int(datos[0]), 
                        id_producto=int(datos[1]), 
                        cantidad=int(datos[2]), 
                        id_cliente=int(datos[3]),
                        estado=datos[4]
                    )
                    lista.append(nuevo_pedido)
    except FileNotFoundError:
        pass
    return lista

def cargar_clientes():
    lista = []
    try:
        with open("clientes.txt", "r", encoding="utf-8") as f:
            for linea in f.readlines()[1:]:
                datos = linea.strip().split("|")
                if len(datos) == 4:
                    lista.append(Cliente(id_cliente=int(datos[0]), nombre=datos[1], correo=datos[2], telefono=int(datos[3])))
    except FileNotFoundError:
        pass
    return lista

def cargar_productos():
    lista = []
    try:
        with open("productos.txt", "r", encoding="utf-8") as f:
            for linea in f.readlines()[1:]:
                datos = linea.strip().split("|")
                if len(datos) == 2:
                    lista.append(Producto(id_producto=int(datos[0]), descripcion=datos[1]))
    except FileNotFoundError:
        pass
    return lista

def cargar_inventario():
    lista = []
    try:
        with open("inventario.txt", "r", encoding="utf-8") as f:
            for linea in f.readlines()[1:]:
                datos = linea.strip().split("|")
                if len(datos) == 3:
                    lista.append(Inventario(id_producto=int(datos[0]), cantidad=int(datos[1]), precio=int(datos[2])))
    except FileNotFoundError:
        pass
    return lista

db_clientes = cargar_clientes()
db_productos = cargar_productos()
db_inventario = cargar_inventario()
db_pedidos = cargar_pedidos()
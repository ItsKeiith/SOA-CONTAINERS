from nicegui import app, ui
import requests
import os

# Definición de URIs para la comunicación entre contenedores
API_CLIENTES = os.getenv("API_CLIENTES", "http://clientes:8001")
API_PRODUCTOS = os.getenv("API_PRODUCTOS", "http://productos:8002")
API_INVENTARIO = os.getenv("API_INVENTARIO", "http://inventario:8003")
API_PEDIDOS = os.getenv("API_PEDIDOS", "http://pedidos:8004")

def verificar_autenticacion():
    if not app.storage.user.get('token'):
        ui.navigate.to('/login')

def logout():
    app.storage.user['token'] = None
    ui.navigate.to('/login')

def get_headers():
    token = app.storage.user.get('token')
    return {"Authorization": f"Bearer {token}"}

def menu_superior():
    """Renderiza la barra de navegación estándar para el panel de administración."""
    with ui.header().classes('justify-between items-center bg-slate-800 p-4'):
        ui.label('Panel de Administración').classes('text-h6 text-white font-bold')
        with ui.row():
            ui.button('Clientes', on_click=lambda: ui.navigate.to('/')).props('flat text-color=white')
            ui.button('Productos', on_click=lambda: ui.navigate.to('/productos')).props('flat text-color=white')
            ui.button('Inventario', on_click=lambda: ui.navigate.to('/inventario')).props('flat text-color=white')
            ui.button('Pedidos', on_click=lambda: ui.navigate.to('/pedidos')).props('flat text-color=white')
            ui.button('Cerrar Sesión', on_click=logout).props('flat text-color=red-4')

@ui.page('/login')
def login_page():
    if app.storage.user.get('token'):
        ui.navigate.to('/')
        return

    with ui.card().classes('absolute-center w-96 shadow-lg'):
        ui.label('Acceso al Sistema').classes('text-h5 q-mb-md font-bold')
        usuario = ui.input('Usuario').classes('w-full q-mb-sm')
        password = ui.input('Contraseña', password=True, password_toggle_button=True).classes('w-full q-mb-sm')
        
        def intentar_login():
            try:
                res = requests.post(f"{API_CLIENTES}/login", json={"usuario": usuario.value, "password": password.value})
                if res.status_code == 200:
                    app.storage.user['token'] = res.json().get("access_token")
                    ui.notify('Acceso exitoso', color='positive')
                    ui.navigate.to('/')
                else:
                    ui.notify('Credenciales incorrectas', color='negative')
            except requests.exceptions.RequestException as e:
                ui.notify(f'Error de red: {e}', color='negative')

        ui.button('Entrar', on_click=intentar_login).classes('w-full q-mt-md bg-blue-600')

@ui.page('/pedidos')
def dashboard_pedidos():
    verificar_autenticacion()
    headers = get_headers()
    menu_superior()

    with ui.column().classes('w-full max-w-5xl mx-auto p-6'):
        with ui.row().classes('w-full justify-between items-center q-mb-md'):
            ui.label('Registro de Pedidos').classes('text-h4 font-bold text-gray-800')
            ui.button('Generar Pedido', on_click=lambda: dialog_crear_pedido.open(), icon='shopping_cart').classes('bg-green-600 text-white')

        columnas_ped = [
            {'name': 'id', 'label': 'N° Pedido', 'field': 'id_pedido', 'align': 'left'},
            {'name': 'cliente', 'label': 'ID Cliente', 'field': 'id_cliente', 'align': 'left'},
            {'name': 'producto', 'label': 'ID Producto', 'field': 'id_producto', 'align': 'left'},
            {'name': 'cantidad', 'label': 'Cantidad', 'field': 'cantidad', 'align': 'right'},
            {'name': 'estado', 'label': 'Estado', 'field': 'estado', 'align': 'center'}
        ]
        
        tabla_ped = ui.table(columns=columnas_ped, rows=[], row_key='id_pedido').classes('w-full shadow-md')

        def cargar_pedidos():
            try:
                res = requests.get(f"{API_PEDIDOS}/pedidos", headers=headers)
                if res.status_code == 200:
                    tabla_ped.rows = res.json()
                    tabla_ped.update()
            except requests.exceptions.RequestException:
                ui.notify('Error al conectar con el worker de pedidos', color='negative')

        # Dialog para Registrar Pedido
        with ui.dialog() as dialog_crear_pedido, ui.card().classes('w-96'):
            ui.label('Formulario de Pedido').classes('text-h6 font-bold')
            # Nota: En una iteración futura, estos inputs pueden ser ui.select cargados desde los microservicios respectivos.
            ped_cliente = ui.number('ID Cliente', format='%.0f').classes('w-full')
            ped_producto = ui.number('ID Producto', format='%.0f').classes('w-full')
            ped_cantidad = ui.number('Cantidad solicitada', format='%.0f').classes('w-full')
            
            def procesar_pedido():
                datos = {
                    "id_cliente": int(ped_cliente.value),
                    "id_producto": int(ped_producto.value),
                    "cantidad": int(ped_cantidad.value)
                }
                try:
                    res = requests.post(f"{API_PEDIDOS}/pedidos", json=datos, headers=headers)
                    if res.status_code == 200:
                        ui.notify('Pedido registrado y procesado en cola', color='positive')
                        dialog_crear_pedido.close()
                        cargar_pedidos()
                    else:
                        mensaje_error = res.json().get('detail', 'Error de procesamiento')
                        ui.notify(f'Fallo de integridad: {mensaje_error}', color='negative')
                except requests.exceptions.RequestException:
                    ui.notify('Error en la solicitud HTTP', color='negative')

            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('Cancelar', on_click=dialog_crear_pedido.close).props('flat')
                ui.button('Procesar', on_click=procesar_pedido).classes('bg-blue-600')

        cargar_pedidos()

@ui.page('/productos')
def dashboard_productos():
    verificar_autenticacion()
    headers = get_headers()
    menu_superior()

    with ui.column().classes('w-full max-w-5xl mx-auto p-6'):
        with ui.row().classes('w-full justify-between items-center q-mb-md'):
            ui.label('Catálogo de Productos').classes('text-h4 font-bold text-gray-800')
            ui.button('Nuevo Producto', on_click=lambda: dialog_crear_prod.open(), icon='add').classes('bg-green-600 text-white')

        columnas_prod = [
            {'name': 'id', 'label': 'ID', 'field': 'id_producto', 'align': 'left'},
            {'name': 'descripcion', 'label': 'Descripción', 'field': 'descripcion', 'align': 'left'},
            {'name': 'precio', 'label': 'Precio Unitario', 'field': 'precio', 'align': 'right'},
            {'name': 'activo', 'label': 'Estado', 'field': 'activo', 'align': 'center'}
        ]
        
        tabla_prod = ui.table(columns=columnas_prod, rows=[], row_key='id_producto', selection='single').classes('w-full shadow-md')

        def cargar_productos():
            try:
                res = requests.get(f"{API_PRODUCTOS}/productos", headers=headers)
                if res.status_code == 200:
                    tabla_prod.rows = res.json()
                    tabla_prod.update()
            except requests.exceptions.RequestException:
                ui.notify('Error de conexión con el servicio de productos', color='negative')

        # Dialog para Alta de Producto
        with ui.dialog() as dialog_crear_prod, ui.card().classes('w-96'):
            ui.label('Registrar Nuevo Producto').classes('text-h6 font-bold')
            p_desc = ui.input('Descripción').classes('w-full')
            p_precio = ui.number('Precio Unitario', format='%.2f').classes('w-full')
            
            def guardar_producto():
                datos = {"descripcion": p_desc.value, "precio": float(p_precio.value)}
                try:
                    res = requests.post(f"{API_PRODUCTOS}/productos", json=datos, headers=headers)
                    if res.status_code == 200:
                        ui.notify('Registro exitoso', color='positive')
                        dialog_crear_prod.close()
                        cargar_productos()
                        p_desc.value = ''
                        p_precio.value = None
                except requests.exceptions.RequestException:
                    ui.notify('Fallo en la transacción de red', color='negative')

            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('Cancelar', on_click=dialog_crear_prod.close).props('flat')
                ui.button('Guardar', on_click=guardar_producto).classes('bg-blue-600')

        cargar_productos()

@ui.page('/inventario')
def dashboard_inventario():
    verificar_autenticacion()
    headers = get_headers()
    menu_superior()

    with ui.column().classes('w-full max-w-5xl mx-auto p-6'):
        ui.label('Control de Inventario').classes('text-h4 font-bold text-gray-800 q-mb-md')

        columnas_inv = [
            {'name': 'id', 'label': 'ID Producto', 'field': 'id_producto', 'align': 'left'},
            {'name': 'descripcion', 'label': 'Descripción', 'field': 'descripcion', 'align': 'left'},
            {'name': 'stock', 'label': 'Stock Disponible', 'field': 'cantidad', 'align': 'right'}
        ]
        
        tabla_inv = ui.table(columns=columnas_inv, rows=[], row_key='id_producto', selection='single').classes('w-full shadow-md')

        def cargar_inventario():
            try:
                res = requests.get(f"{API_INVENTARIO}/inventario", headers=headers)
                if res.status_code == 200:
                    tabla_inv.rows = res.json()
                    tabla_inv.update()
            except requests.exceptions.RequestException:
                ui.notify('Error al obtener datos de inventario', color='negative')

        with ui.row().classes('w-full justify-start q-mt-md gap-4'):
            btn_sumar_stock = ui.button('Añadir Stock', icon='add_box').classes('bg-blue-500').props('disable')

        with ui.dialog() as dialog_stock, ui.card().classes('w-96'):
            ui.label('Ingreso de Mercancía').classes('text-h6 font-bold')
            s_id = ui.label().classes('hidden')
            s_cantidad = ui.number('Cantidad a sumar', value=1, format='%.0f').classes('w-full')

            def aplicar_stock():
                try:
                    res = requests.patch(
                        f"{API_INVENTARIO}/inventario/{s_id.text}/agregar", 
                        json={"cantidad_a_sumar": int(s_cantidad.value)}, 
                        headers=headers
                    )
                    if res.status_code == 200:
                        ui.notify('Stock actualizado en la base de datos', color='positive')
                        dialog_stock.close()
                        tabla_inv.selected.clear()
                        btn_sumar_stock.props(add='disable')
                        cargar_inventario()
                    else:
                        ui.notify('Error en la actualización de stock', color='negative')
                except Exception:
                    ui.notify('Error de red', color='negative')

            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('Cancelar', on_click=dialog_stock.close).props('flat')
                ui.button('Confirmar', on_click=aplicar_stock).classes('bg-blue-600')

        def abrir_modal_stock():
            if tabla_inv.selected:
                s_id.set_text(str(tabla_inv.selected[0]['id_producto']))
                s_cantidad.value = 1
                dialog_stock.open()

        btn_sumar_stock.on('click', abrir_modal_stock)

        def control_seleccion_inv():
            if tabla_inv.selected:
                btn_sumar_stock.props(remove='disable')
            else:
                btn_sumar_stock.props(add='disable')

        tabla_inv.on('selection', control_seleccion_inv)
        cargar_inventario()

@ui.page('/')
def dashboard_clientes():
    verificar_autenticacion()
    headers = get_headers()

    # Barra de navegación
    menu_superior()

    with ui.column().classes('w-full max-w-5xl mx-auto p-6'):
        with ui.row().classes('w-full justify-between items-center q-mb-md'):
            ui.label('Directorio de Clientes').classes('text-h4 font-bold text-gray-800')
            ui.button('Nuevo Cliente', on_click=lambda: dialog_crear.open(), icon='add').classes('bg-green-600 text-white')

        # Definición de la tabla
        columnas = [
            {'name': 'id', 'label': 'ID', 'field': 'id_cliente', 'align': 'left'},
            {'name': 'nombre', 'label': 'Nombre', 'field': 'nombre', 'align': 'left'},
            {'name': 'correo', 'label': 'Correo', 'field': 'correo', 'align': 'left'},
            {'name': 'telefono', 'label': 'Teléfono', 'field': 'telefono', 'align': 'left'},
            {'name': 'direccion', 'label': 'Dirección', 'field': 'direccion', 'align': 'left'},
            {'name': 'activo', 'label': 'Estado', 'field': 'activo', 'align': 'center'}
        ]
        
        # Tabla con selección de fila única
        tabla = ui.table(columns=columnas, rows=[], row_key='id_cliente', selection='single').classes('w-full shadow-md')

        def cargar_clientes():
            try:
                res = requests.get(f"{API_CLIENTES}/clientes", headers=headers)
                if res.status_code == 200:
                    tabla.rows = res.json()
                    tabla.update()
                elif res.status_code == 401:
                    logout()
            except requests.exceptions.RequestException:
                ui.notify('Error al conectar con el servidor de base de datos', color='negative')

        # --- LÓGICA DE CREACIÓN ---
        with ui.dialog() as dialog_crear, ui.card().classes('w-96'):
            ui.label('Registrar Nuevo Cliente').classes('text-h6 font-bold')
            c_nombre = ui.input('Nombre Completo').classes('w-full')
            c_correo = ui.input('Correo Electrónico').classes('w-full')
            c_telefono = ui.input('Teléfono').classes('w-full')
            c_direccion = ui.input('Dirección').classes('w-full')
            
            def guardar_nuevo():
                datos = {
                    "nombre": c_nombre.value,
                    "correo": c_correo.value,
                    "telefono": c_telefono.value,
                    "direccion": c_direccion.value,
                    "activo": True
                }
                try:
                    res = requests.post(f"{API_CLIENTES}/clientes", json=datos, headers=headers)
                    if res.status_code == 200:
                        ui.notify('Cliente registrado exitosamente', color='positive')
                        dialog_crear.close()
                        cargar_clientes()
                        # Limpiar campos
                        c_nombre.value = c_correo.value = c_telefono.value = c_direccion.value = ''
                    else:
                        ui.notify(f'Error: {res.json().get("detail", "Error desconocido")}', color='negative')
                except requests.exceptions.RequestException:
                    ui.notify('Fallo en la comunicación de red', color='negative')

            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('Cancelar', on_click=dialog_crear.close).props('flat')
                ui.button('Guardar', on_click=guardar_nuevo).classes('bg-blue-600')

        # --- LÓGICA DE EDICIÓN Y ELIMINACIÓN ---
        # Componentes condicionales que se activan al seleccionar una fila
        with ui.row().classes('w-full justify-start q-mt-md gap-4'):
            btn_editar = ui.button('Editar Seleccionado', icon='edit').classes('bg-orange-500').props('disable')
            btn_eliminar = ui.button('Dar de Baja', icon='delete').classes('bg-red-600').props('disable')

        with ui.dialog() as dialog_editar, ui.card().classes('w-96'):
            ui.label('Editar Cliente').classes('text-h6 font-bold')
            e_id = ui.label().classes('hidden') # Almacena el ID temporalmente
            e_nombre = ui.input('Nombre Completo').classes('w-full')
            e_correo = ui.input('Correo Electrónico').classes('w-full')
            e_telefono = ui.input('Teléfono').classes('w-full')
            e_direccion = ui.input('Dirección').classes('w-full')
            e_activo = ui.checkbox('Cliente Activo')

            def aplicar_edicion():
                id_cliente = e_id.text
                datos_nuevos = {
                    "nombre": e_nombre.value,
                    "correo": e_correo.value,
                    "telefono": e_telefono.value,
                    "direccion": e_direccion.value,
                    "activo": e_activo.value
                }
                try:
                    res = requests.patch(f"{API_CLIENTES}/clientes/{id_cliente}", json=datos_nuevos, headers=headers)
                    if res.status_code == 200:
                        ui.notify('Atributos actualizados', color='positive')
                        dialog_editar.close()
                        tabla.selected.clear()
                        actualizar_botones()
                        cargar_clientes()
                    else:
                        ui.notify('Error en la actualización', color='negative')
                except Exception as e:
                    ui.notify('Error de red', color='negative')

            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('Cancelar', on_click=dialog_editar.close).props('flat')
                ui.button('Actualizar', on_click=aplicar_edicion).classes('bg-orange-500')

        def abrir_edicion():
            if tabla.selected:
                cliente = tabla.selected[0]
                e_id.set_text(str(cliente['id_cliente']))
                e_nombre.value = cliente['nombre']
                e_correo.value = cliente['correo']
                e_telefono.value = cliente['telefono']
                e_direccion.value = cliente['direccion']
                e_activo.value = cliente['activo']
                dialog_editar.open()

        def ejecutar_baja():
            if tabla.selected:
                id_cliente = tabla.selected[0]['id_cliente']
                try:
                    res = requests.delete(f"{API_CLIENTES}/clientes/{id_cliente}", headers=headers)
                    if res.status_code == 200:
                        ui.notify('Baja lógica ejecutada', color='info')
                        tabla.selected.clear()
                        actualizar_botones()
                        cargar_clientes()
                except Exception:
                    ui.notify('Error al ejecutar la baja', color='negative')

        btn_editar.on('click', abrir_edicion)
        btn_eliminar.on('click', ejecutar_baja)

        # Control del estado de los botones según la selección
        def actualizar_botones():
            if tabla.selected:
                btn_editar.props(remove='disable')
                btn_eliminar.props(remove='disable')
            else:
                btn_editar.props(add='disable')
                btn_eliminar.props(add='disable')

        tabla.on('selection', actualizar_botones)

        # Carga inicial
        cargar_clientes()
        
puerto = int(os.getenv("PORT", 8080))
ui.run(host="0.0.0.0", port=puerto, storage_secret="super_secret_nicegui_key_123")
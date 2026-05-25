from nicegui import app, ui
from fastapi.responses import RedirectResponse
import requests
import os

# Definición de URIs para la comunicación entre contenedores
API_CLIENTES = os.getenv("API_CLIENTES", "http://clientes:8001")
API_PRODUCTOS = os.getenv("API_PRODUCTOS", "http://productos:8002")
API_INVENTARIO = os.getenv("API_INVENTARIO", "http://inventario:8003")
API_PEDIDOS = os.getenv("API_PEDIDOS", "http://pedidos:8004")

def verificar_autenticacion():
    """Retorna una redirección HTTP si el token no existe en el almacenamiento."""
    if not app.storage.user.get('token'):
        return RedirectResponse('/login')
    return None

def logout():
    app.storage.user['token'] = None
    ui.open('/login')

def get_headers():
    token = app.storage.user.get('token')
    return {"Authorization": f"Bearer {token}"}

def menu_superior():
    with ui.header().classes('justify-between items-center bg-slate-800 p-4'):
        ui.label('Panel de Administración').classes('text-h6 text-white font-bold')
        with ui.row():
            ui.button('Clientes', on_click=lambda: ui.open('/')).props('flat text-color=white')
            ui.button('Productos', on_click=lambda: ui.open('/productos')).props('flat text-color=white')
            ui.button('Inventario', on_click=lambda: ui.open('/inventario')).props('flat text-color=white')
            ui.button('Pedidos', on_click=lambda: ui.open('/pedidos')).props('flat text-color=white')
            ui.button('Cerrar Sesión', on_click=logout).props('flat text-color=red-4')

@ui.page('/login')
def login_page():
    if app.storage.user.get('token'):
        return RedirectResponse('/')

    with ui.card().classes('absolute-center w-96 shadow-lg'):
        ui.label('Acceso al Sistema').classes('text-h5 q-mb-md font-bold')
        usuario = ui.input('Usuario').classes('w-full q-mb-sm')
        password = ui.input('Contraseña', password=True, password_toggle_button=True).classes('w-full q-mb-sm')
        
        def intentar_login():
            try:
                payload = {
                    "usuario": usuario.value.strip(), 
                    "password": password.value.strip()
                }
                res = requests.post(f"{API_CLIENTES}/login", json=payload)
                
                if res.status_code == 200:
                    app.storage.user['token'] = res.json().get("access_token")
                    ui.notify('Acceso exitoso. Generando cookie de sesión...', color='positive')
                    ui.open('/')
                elif res.status_code == 401:
                    ui.notify('Credenciales rechazadas por el servidor (401)', color='negative')
                else:
                    try:
                        detalle_error = res.json().get('detail', 'Sin detalles')
                    except Exception:
                        detalle_error = res.text[:50]
                    ui.notify(f'Error del sistema ({res.status_code}): {detalle_error}', color='warning')
                    
            except requests.exceptions.RequestException as e:
                ui.notify(f'Fallo de conexión al microservicio: {e}', color='negative')

        ui.button('Entrar', on_click=intentar_login).classes('w-full q-mt-md bg-blue-600')

@ui.page('/pedidos')
def dashboard_pedidos():
    auth = verificar_autenticacion()
    if auth: return auth

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

        with ui.dialog() as dialog_crear_pedido, ui.card().classes('w-96'):
            ui.label('Formulario de Pedido').classes('text-h6 font-bold')
            ped_cliente = ui.number('ID Cliente', format='%.0f').classes('w-full')
            ped_producto = ui.number('ID Producto', format='%.0f').classes('w-full')
            ped_cantidad = ui.number('Cantidad solicitada', format='%.0f').classes('w-full')
            
            def procesar_pedido():
                datos = {"id_cliente": int(ped_cliente.value), "id_producto": int(ped_producto.value), "cantidad": int(ped_cantidad.value)}
                try:
                    res = requests.post(f"{API_PEDIDOS}/pedidos", json=datos, headers=headers)
                    if res.status_code == 200:
                        ui.notify('Pedido procesado', color='positive')
                        dialog_crear_pedido.close()
                        cargar_pedidos()
                    else:
                        ui.notify('Fallo de integridad', color='negative')
                except requests.exceptions.RequestException:
                    ui.notify('Error en solicitud HTTP', color='negative')

            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('Cancelar', on_click=dialog_crear_pedido.close).props('flat')
                ui.button('Procesar', on_click=procesar_pedido).classes('bg-blue-600')

        cargar_pedidos()

@ui.page('/productos')
def dashboard_productos():
    auth = verificar_autenticacion()
    if auth: return auth

    headers = get_headers()
    menu_superior()

    columnas_v1 = [
        {'name': 'id', 'label': 'ID', 'field': 'id_producto', 'align': 'left'},
        {'name': 'descripcion', 'label': 'Descripción', 'field': 'descripcion', 'align': 'left'},
        {'name': 'precio', 'label': 'Precio Unitario (V1)', 'field': 'precio', 'align': 'right'},
        {'name': 'activo', 'label': 'Estado', 'field': 'activo', 'align': 'center'}
    ]

    columnas_v2 = [
        {'name': 'id', 'label': 'ID', 'field': 'id_producto', 'align': 'left'},
        {'name': 'descripcion', 'label': 'Descripción', 'field': 'descripcion', 'align': 'left'},
        {'name': 'costo', 'label': 'Costo Unitario (V2)', 'field': 'costo_unitario', 'align': 'right'},
        {'name': 'activo', 'label': 'Estado', 'field': 'activo', 'align': 'center'}
    ]

    with ui.column().classes('w-full max-w-5xl mx-auto p-6'):
        with ui.row().classes('w-full justify-between items-center q-mb-md'):
            ui.label('Catálogo de Productos').classes('text-h4 font-bold text-gray-800')
            
            with ui.row().classes('items-center gap-4'):
                # Selector de versión para demostrar gobernabilidad en la UI
                version_select = ui.select(
                    options={'v1': 'Versión 1 (Precio)', 'v2': 'Versión 2 (Costo Unitario)'}, 
                    value='v1',
                    on_change=lambda e: alternar_version()
                ).classes('w-48')
                
                ui.button('Nuevo Producto', on_click=lambda: dialog_crear_prod.open(), icon='add').classes('bg-green-600 text-white')

        tabla_prod = ui.table(columns=columnas_v1, rows=[], row_key='id_producto', selection='single').classes('w-full shadow-md')

        def cargar_productos():
            version = version_select.value  
            try:
                res = requests.get(f"{API_PRODUCTOS}/{version}/productos", headers=headers)
                if res.status_code == 200:
                    tabla_prod.rows = res.json()
                    tabla_prod.update()
                else:
                    ui.notify(f'Error en Productos: {res.status_code} - {res.text}', color='negative', timeout=10000)
            except requests.exceptions.RequestException:
                ui.notify('Error de red al conectar con el servicio de productos', color='negative')

        def alternar_version():
            """Cambia la estructura de las columnas de la tabla según la versión seleccionada"""
            if version_select.value == 'v2':
                tabla_prod.columns = columnas_v2
            else:
                tabla_prod.columns = columnas_v1
            tabla_prod.update()
            cargar_productos()

        with ui.dialog() as dialog_crear_prod, ui.card().classes('w-96'):
            ui.label('Registrar Nuevo Producto').classes('text-h6 font-bold')
            p_desc = ui.input('Descripción').classes('w-full')
            p_valor = ui.number('Valor Monetario', format='%.2f').classes('w-full')
            
            def guardar_producto():
                version = version_select.value
                if version == 'v2':
                    datos = {"descripcion": p_desc.value, "costo_unitario": float(p_valor.value)}
                else:
                    datos = {"descripcion": p_desc.value, "precio": float(p_valor.value)}
                    
                try:
                    res = requests.post(f"{API_PRODUCTOS}/{version}/productos", json=datos, headers=headers)
                    if res.status_code == 200:
                        ui.notify(f'Registro exitoso en {version.upper()}', color='positive')
                        dialog_crear_prod.close()
                        cargar_productos()
                        p_desc.value = ''
                        p_valor.value = None
                except requests.exceptions.RequestException:
                    ui.notify('Fallo de red', color='negative')

            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('Cancelar', on_click=dialog_crear_prod.close).props('flat')
                ui.button('Guardar', on_click=guardar_producto).classes('bg-blue-600')

        with ui.row().classes('w-full justify-start q-mt-md gap-4'):
            btn_editar_prod = ui.button('Editar Seleccionado', icon='edit').classes('bg-orange-500').props('disable')
            btn_eliminar_prod = ui.button('Dar de Baja', icon='delete').classes('bg-red-600').props('disable')

        with ui.dialog() as dialog_editar_prod, ui.card().classes('w-96'):
            ui.label('Editar Producto').classes('text-h6 font-bold')
            e_id_prod = ui.label().classes('hidden')
            e_desc = ui.input('Descripción').classes('w-full')
            e_valor = ui.number('Valor Monetario', format='%.2f').classes('w-full')
            e_activo = ui.checkbox('Producto Activo')

            def aplicar_edicion_prod():
                version = version_select.value
                if version == 'v2':
                    datos_nuevos = {"descripcion": e_desc.value, "costo_unitario": float(e_valor.value) if e_valor.value else 0.0, "activo": e_activo.value}
                else:
                    datos_nuevos = {"descripcion": e_desc.value, "precio": float(e_valor.value) if e_valor.value else 0.0, "activo": e_activo.value}
                
                try:
                    res = requests.patch(f"{API_PRODUCTOS}/{version}/productos/{e_id_prod.text}", json=datos_nuevos, headers=headers)
                    if res.status_code == 200:
                        ui.notify('Actualización completada', color='positive')
                        dialog_editar_prod.close()
                        tabla_prod.selected.clear()
                        actualizar_botones_prod()
                        cargar_productos()
                except Exception:
                    ui.notify('Error de red', color='negative')

            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('Cancelar', on_click=dialog_editar_prod.close).props('flat')
                ui.button('Actualizar', on_click=aplicar_edicion_prod).classes('bg-orange-500')

        def abrir_edicion_prod():
            if tabla_prod.selected:
                prod = tabla_prod.selected[0]
                version = version_select.value
                e_id_prod.set_text(str(prod['id_producto']))
                e_desc.value = prod['descripcion']
                # Lee el campo correcto del diccionario según la versión activa en la UI
                e_valor.value = prod['costo_unitario'] if version == 'v2' else prod['precio']
                e_activo.value = prod['activo']
                dialog_editar_prod.open()

        def ejecutar_baja_prod():
            if tabla_prod.selected:
                version = version_select.value
                try:
                    res = requests.delete(f"{API_PRODUCTOS}/{version}/productos/{tabla_prod.selected[0]['id_producto']}", headers=headers)
                    if res.status_code == 200:
                        ui.notify('Baja ejecutada', color='info')
                        tabla_prod.selected.clear()
                        actualizar_botones_prod()
                        cargar_productos()
                except Exception:
                    ui.notify('Error en baja', color='negative')

        btn_editar_prod.on('click', abrir_edicion_prod)
        btn_eliminar_prod.on('click', ejecutar_baja_prod)

        def actualizar_botones_prod():
            if tabla_prod.selected:
                btn_editar_prod.props(remove='disable')
                btn_eliminar_prod.props(remove='disable')
            else:
                btn_editar_prod.props(add='disable')
                btn_eliminar_prod.props(add='disable')

        tabla_prod.on('selection', actualizar_botones_prod)
        
        cargar_productos()

@ui.page('/inventario')
def dashboard_inventario():
    auth = verificar_autenticacion()
    if auth: return auth

    headers = get_headers()
    menu_superior()

    with ui.column().classes('w-full max-w-5xl mx-auto p-6'):
        with ui.row().classes('w-full justify-between items-center q-mb-md'):
            ui.label('Control de Inventario').classes('text-h4 font-bold text-gray-800')
            # El botón ahora llama a una función específica para preparar el diálogo
            ui.button('Alta en Inventario', on_click=lambda: abrir_dialogo_alta(), icon='add_box').classes('bg-green-600 text-white')

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
                else:
                    ui.notify(f'Error en Inventario: {res.status_code} - {res.text}', color='negative', timeout=10000)
            except requests.exceptions.RequestException:
                ui.notify('Error al obtener datos', color='negative')

        # --- LÓGICA DE ALTA EN INVENTARIO (Corregida) ---
        with ui.dialog() as dialog_alta_inv, ui.card().classes('w-96'):
            ui.label('Inicializar Stock de Producto').classes('text-h6 font-bold')
            # Se cambia el input de texto por un menú desplegable
            a_producto = ui.select(options={}, label='Seleccionar Producto del Catálogo').classes('w-full')
            a_stock = ui.number('Stock Inicial Físico', format='%.0f').classes('w-full')

            def abrir_dialogo_alta():
                try:
                    res_prod = requests.get(f"{API_PRODUCTOS}/v1/productos", headers=headers)
                    if res_prod.status_code == 200:
                        todos_los_productos = res_prod.json()
                        
                        ids_en_inventario = [fila['id_producto'] for fila in tabla_inv.rows]
                        
                        # Cambio de seguridad: se usa p.get('activo') en lugar de 'is True' 
                        # para evitar conflictos de casteo entre PostgreSQL y Python
                        opciones_disponibles = {
                            p['id_producto']: f"[{p['id_producto']}] {p['descripcion']}" 
                            for p in todos_los_productos 
                            if p['id_producto'] not in ids_en_inventario and p.get('activo')
                        }
                        
                        if not opciones_disponibles:
                            ui.notify('Todos los productos activos ya tienen inventario inicializado.', color='warning')
                            return
                            
                        a_producto.options = opciones_disponibles
                        a_producto.update()
                        a_producto.value = None
                        a_stock.value = None
                        dialog_alta_inv.open()
                    else:
                        ui.notify('No se pudo cargar el catálogo de productos.', color='negative')
                except Exception:
                    ui.notify('Fallo de red al consultar productos.', color='negative')

            def guardar_alta_inv():
                if not a_producto.value:
                    ui.notify('Debe seleccionar un producto.', color='warning')
                    return
                    
                datos_alta = {
                    "id_producto": a_producto.value,
                    "cantidad_inicial": int(a_stock.value) if a_stock.value else 0
                }
                try:
                    res = requests.post(f"{API_INVENTARIO}/inventario/alta", json=datos_alta, headers=headers)
                    if res.status_code == 200:
                        ui.notify('Stock inicializado correctamente', color='positive')
                        dialog_alta_inv.close()
                        cargar_inventario()
                    else:
                        ui.notify(f'Fallo: {res.json().get("detail", "Error de integridad")}', color='negative')
                except Exception:
                    ui.notify('Fallo de red', color='negative')

            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('Cancelar', on_click=dialog_alta_inv.close).props('flat')
                ui.button('Guardar', on_click=guardar_alta_inv).classes('bg-blue-600')

        # --- LÓGICA PARA SUMAR STOCK (Permanece Intacta) ---
        with ui.row().classes('w-full justify-start q-mt-md gap-4'):
            btn_sumar_stock = ui.button('Añadir Stock', icon='inventory').classes('bg-blue-500').props('disable')

        with ui.dialog() as dialog_stock, ui.card().classes('w-96'):
            ui.label('Ingreso de Mercancía').classes('text-h6 font-bold')
            s_id = ui.label().classes('hidden')
            s_cantidad = ui.number('Cantidad a sumar', value=1, format='%.0f').classes('w-full')

            def aplicar_stock():
                try:
                    res = requests.patch(f"{API_INVENTARIO}/inventario/{s_id.text}/agregar", json={"cantidad_a_sumar": int(s_cantidad.value)}, headers=headers)
                    if res.status_code == 200:
                        ui.notify('Stock actualizado', color='positive')
                        dialog_stock.close()
                        tabla_inv.selected.clear()
                        btn_sumar_stock.props(add='disable')
                        cargar_inventario()
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
    auth = verificar_autenticacion()
    if auth: return auth

    headers = get_headers()
    menu_superior()

    with ui.column().classes('w-full max-w-5xl mx-auto p-6'):
        with ui.row().classes('w-full justify-between items-center q-mb-md'):
            ui.label('Directorio de Clientes').classes('text-h4 font-bold text-gray-800')
            ui.button('Nuevo Cliente', on_click=lambda: dialog_crear.open(), icon='add').classes('bg-green-600 text-white')

        columnas = [
            {'name': 'id', 'label': 'ID', 'field': 'id_cliente', 'align': 'left'},
            {'name': 'nombre', 'label': 'Nombre', 'field': 'nombre', 'align': 'left'},
            {'name': 'correo', 'label': 'Correo', 'field': 'correo', 'align': 'left'},
            {'name': 'telefono', 'label': 'Teléfono', 'field': 'telefono', 'align': 'left'},
            {'name': 'direccion', 'label': 'Dirección', 'field': 'direccion', 'align': 'left'},
            {'name': 'activo', 'label': 'Estado', 'field': 'activo', 'align': 'center'}
        ]
        
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
                ui.notify('Error al conectar con la base de datos', color='negative')

        with ui.dialog() as dialog_crear, ui.card().classes('w-96'):
            ui.label('Registrar Nuevo Cliente').classes('text-h6 font-bold')
            c_nombre = ui.input('Nombre Completo').classes('w-full')
            c_correo = ui.input('Correo Electrónico').classes('w-full')
            c_telefono = ui.input('Teléfono').classes('w-full')
            c_direccion = ui.input('Dirección').classes('w-full')
            
            def guardar_nuevo():
                datos = {"nombre": c_nombre.value, "correo": c_correo.value, "telefono": c_telefono.value, "direccion": c_direccion.value, "activo": True}
                try:
                    res = requests.post(f"{API_CLIENTES}/clientes", json=datos, headers=headers)
                    if res.status_code == 200:
                        ui.notify('Cliente registrado', color='positive')
                        dialog_crear.close()
                        cargar_clientes()
                        c_nombre.value = c_correo.value = c_telefono.value = c_direccion.value = ''
                except requests.exceptions.RequestException:
                    ui.notify('Fallo de red', color='negative')

            with ui.row().classes('w-full justify-end q-mt-md'):
                ui.button('Cancelar', on_click=dialog_crear.close).props('flat')
                ui.button('Guardar', on_click=guardar_nuevo).classes('bg-blue-600')

        with ui.row().classes('w-full justify-start q-mt-md gap-4'):
            btn_editar = ui.button('Editar Seleccionado', icon='edit').classes('bg-orange-500').props('disable')
            btn_eliminar = ui.button('Dar de Baja', icon='delete').classes('bg-red-600').props('disable')

        with ui.dialog() as dialog_editar, ui.card().classes('w-96'):
            ui.label('Editar Cliente').classes('text-h6 font-bold')
            e_id = ui.label().classes('hidden')
            e_nombre = ui.input('Nombre Completo').classes('w-full')
            e_correo = ui.input('Correo Electrónico').classes('w-full')
            e_telefono = ui.input('Teléfono').classes('w-full')
            e_direccion = ui.input('Dirección').classes('w-full')
            e_activo = ui.checkbox('Cliente Activo')

            def aplicar_edicion():
                datos_nuevos = {"nombre": e_nombre.value, "correo": e_correo.value, "telefono": e_telefono.value, "direccion": e_direccion.value, "activo": e_activo.value}
                try:
                    res = requests.patch(f"{API_CLIENTES}/clientes/{e_id.text}", json=datos_nuevos, headers=headers)
                    if res.status_code == 200:
                        ui.notify('Actualización completada', color='positive')
                        dialog_editar.close()
                        tabla.selected.clear()
                        actualizar_botones()
                        cargar_clientes()
                except Exception:
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
                try:
                    res = requests.delete(f"{API_CLIENTES}/clientes/{tabla.selected[0]['id_cliente']}", headers=headers)
                    if res.status_code == 200:
                        ui.notify('Baja ejecutada', color='info')
                        tabla.selected.clear()
                        actualizar_botones()
                        cargar_clientes()
                except Exception:
                    ui.notify('Error en baja', color='negative')

        btn_editar.on('click', abrir_edicion)
        btn_eliminar.on('click', ejecutar_baja)

        def actualizar_botones():
            if tabla.selected:
                btn_editar.props(remove='disable')
                btn_eliminar.props(remove='disable')
            else:
                btn_editar.props(add='disable')
                btn_eliminar.props(add='disable')

        tabla.on('selection', actualizar_botones)
        cargar_clientes()

puerto = int(os.getenv("PORT", 8080))
ui.run(host="0.0.0.0", port=puerto, storage_secret="super_secret_nicegui_key_123")
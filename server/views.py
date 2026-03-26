from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token

from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from .models import (
    Cliente,
    Productos,
    Turno,
    ListaPredefinida,
    Dom,
    ProductosDom,
    RegistroPlaneacion,
    RegistroAlmacen, 
    RegistroProduccion,
    RegistroTiempoProduccion,
    PausaTiempoProduccion,
    RegistroTratamiento, 
    PerfilUsuario,
    AuditoriaDom,
)

from .serializers import (
    UserSerializer,
    PerfilUsuarioSerializer,
    ClienteSerializer,
    FamiliaProductoSerializer,             # viaja dentro de ProductosSerializer
    ProductosSerializer,
    TurnoSerializer, 
    ListaPredefinidaSerializer, 
    ProductosDomSerializer,
    DomListSerializer,
    DomDetalleSerializer,
    EditarUsuarioSerializer,
    RegistroAlmacenSerializer,
    PausaTiempoProduccionSerializer,
    RegistroTiempoProduccionSerializer,
    RegistroProduccionSerializer,
    RegistroTratamientoSerializer,
    RegistroPlaneacionSerializer,
    AuditoriaDomSerializer,                 # viaja dentro de InformeAuditoriaSerializer
    LoginSerializer, 
    CambioPasswordSerializer,
    CrearUsuarioSerializer,
    DomReporteSerializer,
    ProductoPendienteDashBoardSerializer,   # viaja dentro de DashboardSerializer
    DashboardSerializer,
    ResumenCumplimientoEtapaSerializer,     # viaja dentro de InformeCumplimiento e InformeDespacho
    InformeCumplimientoPlaneacionSerializer, 
    InformeDespachoSerializer,
    InformeAuditoriaSerializer,             # se instancia directamente en InformeAuditoriaView
    RestablecerPasswordSerializer,
)


# INICIO HELPERS - Funciones reutilizables en todas las vistas, mayor eficiencia 

#  retorna el PerfilUsuario autenticado / referencia PerfilUsuario
def get_perfil(request):
    return request.user.perfil

# verifica que usuario autenticado tiene uno de los roles existentes en sistema 
def verificar_rol(request, roles_permitidos):
    try:
        perfil = get_perfil(request)
        return perfil.rol in roles_permitidos
    except PerfilUsuario.DoesNotExist: 
        return False

# Función helper para determinar el nivel de cumplimiento de la planeación 
# Retorna:
# 'CUMPLIÓ'     — todos los registros cumplieron
# 'PARCIAL'     — algunos registros cumplieron y otros no
# 'NO_CUMPLIÓ'  — ningún registro cumplió
# 'SIN_DATOS'   — no hay registros para evaluar

def calcular_cumplimiento(registros_ok, total_registros):
    if total_registros == 0:
        return 'SIN DATOS'
    if registros_ok == total_registros:
        return 'CUMPLIÓ'
    elif registros_ok == 0:
        return 'NO_CUMPLIÓ'
    else:
        return 'PARCIAL'

# Centraliza que  la creación de registros de AuditoriaDom ante accciones relevantes (creacion, edicion, bloqueo o desbloqueo etapa, eliminación)
def registrar_auditoria(dom, usuario, accion, etapa=None, campos_modificados=None):

    AuditoriaDom.objects.create(
        dom = dom,
        usuario = usuario,
        accion = accion, 
        etapa = etapa,
        campos_modificados = campos_modificados
    )

# FIN HELPERS

# INICIO MODULO 1 - VISTAS DE AUTENTICACIÓN

# Modulo 1 - Autenticación de usuarios / login, logout, perfil usuario autenticado, cambio de password, reestablecer password, creacion y eliminación usuarios (lo ultimo - manteniendo registro historico)

# POST /api/auth/login/
class LoginView(APIView):
    # Autenticación y token de acceso 
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        
        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos de acceso invalidos',
                    'detalle': serializer.errors
                },
                status = status.HTTP_400_BAD_REQUEST
            )

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        # verificación datos ingresados vs DB metodo aunthenticate
        user = authenticate(username=username, password=password)

        if not user:
            return Response(
                {'error' : 'Usuario o contraseña incorrecto'},
                status = status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'error' : 'Usuario inactivo, contacte al administrador'},
                status = status.HTTP_403_FORBIDDEN
            )
        
        # Verifica que el usuario tenga PerfilUsuario asignado
        try:
            perfil_data = PerfilUsuarioSerializer(user.perfil).data
        except PerfilUsuario.DoesNotExist:
            return Response(
                {'error' : 'Usuario sin perfil asignado, contacte al administrador del sistema'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Evita duplicados de token
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                'mensaje' : 'Inicio de sesión exitoso',
                'token' : token.key,
                'perfil' : perfil_data # incluye rol, username, nombre_completo
            },
            status = status.HTTP_200_OK
        )

# POST /api/auth/logout
class LogoutView(APIView):
    # Elimina el token de usuario autenticado al momento que este cierra sesión

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
            return Response(
                {'mensaje' : 'Sesion cerrada correctamente'},
                status=status.HTTP_200_OK
            )
        except Token.DoesNotExist: 
            return Response(
                {'error' : 'No se encontró una sesión activa'},
                status=status.HTTP_400_BAD_REQUEST
            )

# get /api/auth/perfil/
class PerfilView(APIView):

    # retorna perfil de usuario autenticado a través de JSON, verificación y consulta de datos pq5q logueo

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            perfil = get_perfil(request)
            serializer = PerfilUsuarioSerializer(perfil)
            return Response (
                {
                    'mensaje' : 'login de usuario exitoso',
                    'perfil': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except PerfilUsuario.DoesNotExist:
            return Response(
                {'error' : 'Perfil no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

class CambioPasswordView(APIView):
    # Vista para permitir a los usuarios cambiar su contraseña
    # Importante: Se construye lógica a nivel de Back; sin embargo, funcionalidad no se encuentra habilitada a nivel Front - escalabilidad futura del proyecto

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):

        serializer = CambioPasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error' : 'Datos invalidos',
                    'detalle' : serializer.errors
                },
                status = status.HTTP_400_BAD_REQUEST
                )
        
        user = request.user
    
    # Verificación de que password actual sea correcto antes de cambio. 
        if not user.check_password(serializer.validated_data['password_actual']):
            return Response(
                {'error': 'Contraseña incorrecta, por favor verifique'},
                status = status.HTTP_400_BAD_REQUEST
            )
    
    # Hasheo de nueva contraseña por motivos de seguridad
        user.set_password(serializer.validated_data['nuevo_password'])
        user.save()

    # Cambio de contraseña genera nuevo token por motivos de seguridad 
        request.user.auth_token.delete()
        nuevo_token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                'mensaje': 'Contraseña actualizada correctamente',
                'token': nuevo_token.key
            },
            status=status.HTTP_200_OK
        )

# Clase para la visualización del listado de usuarios y roles, y para creación de nuevos usuarios, exclusivo ADMIN
class UsuarioListView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):

        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'Usuario no autorizado para realizar esta acción'},
                status = status.HTTP_403_FORBIDDEN
            )
    
    # Query para obtener información de los usuarios evitando N+1 en queries
        usuarios = User.objects.select_related('perfil').all()
        data = []

        for user in usuarios:
            try:
                perfil_data = PerfilUsuarioSerializer(user.perfil).data
            except PerfilUsuario.DoesNotExist:
                # Usuario sin rol - asigna NULL para que el admin pueda visualizarlo y asignar rol 
                perfil_data = None
            
            data.append({
                **UserSerializer(user).data,
                'perfil': perfil_data,
                'sin_perfil': perfil_data is None # FrontEnd destaca users sin rol asignado
            })

        return Response(
            {
                'mensaje': 'usuarios obtenidos correctamente',
                'total': len(data),
                'usuarios': data
            },
            status=status.HTTP_200_OK
        )
    
    def post(self, request):

        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'Usuario no autorizado para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = CrearUsuarioSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos inválidos',
                    'detalle': serializer.errors
                },
                status = status.HTTP_400_BAD_REQUEST
            )
        
        # Crear User + PerfilUsuario en una sola operación
        user = serializer.save()

        return Response(
            {
                'mensaje' : f'Usuario {user.username} creado correctamente',
                'usuario': UserSerializer(user).data,
                'perfil': PerfilUsuarioSerializer(user.perfil).data
            },
            status = status.HTTP_201_CREATED
        )

#Edición de datos o rol en usuarios existentes - desactivación de un usuario - SOLO ADMIN
# Registros de usuarios desactivados no se eliminan
class UsuarioDetalleView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def put(self, request, user_id):

        if not verificar_rol(request, ['ADMIN']):
            return Response (
                {'error': 'Usuario no autorizado para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            user = User.objects.get(id=user_id)

        except User.DoesNotExist:
            return Response(
                {'error': 'Usuario no encontrado'},
                status = status.HTTP_404_NOT_FOUND
            )
        
        serializer = EditarUsuarioSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status = status.HTTP_400_BAD_REQUEST
            )
        
        # Actualiza campos del user de Django
        campos_user = ['first_name', 'last_name', 'email']
        for campo in campos_user:
            if campo in serializer.validated_data:
                setattr(user, campo, serializer.validated_data[campo])
        user.save()

        # actualización o creación PerfilUsuario si se envía rol
        if 'rol' in serializer.validated_data:
            perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
            perfil.rol = serializer.validated_data['rol']
            perfil.save()
        
        return Response(
            {
                'mensaje': f'Usuario {user.username} actualizado correctamente',
                'usuario': UserSerializer(user).data,
                'perfil': PerfilUsuarioSerializer(user.perfil).data
            },
            status = status.HTTP_200_OK
        )
    
    def delete(self, request, user_id):

        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes los permisos para realizar esta acción'},
                status = status.HTTP_403_FORBIDDEN
            )
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {'error' : 'Usuario no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Loop para evitar que el ADMIN se deshanilite a si mismo
        if user == request.user:
            return Response(
                {'error': 'No puedes descativar tu propio usuario'},
                status = status.HTTP_400_BAD_REQUEST
            )
        
        
        user.is_active = False
        user.save()

        return Response(
            {'mensaje': f'Usuario {user.username} desactivado correctamente'},
            status = status.HTTP_200_OK
        )

# Permite a admin el reestablecer la contraseña de cualquier usuario, sin necesidad de conocer la contraseña actual SOLO ADMIN 

class RestablecerPasswordView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):

        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': ' No tienes los permisos necesarios para realizar esta acción'},
                status = status.HTTP_403_FORBIDDEN
            )
        
        serializer = RestablecerPasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Búsqueda de usuario x ID
        try: 
            user = User.objects.get(id=serializer.validated_data['user_id'])
        except User.DoesNotExist:
            return Response(
                {'error' : 'Usuario no encontrado'},
                status = status.HTTP_404_NOT_FOUND
            )
        
        # Hasheo de contraseña una vez ADMIN ha realizado cambio 
        user.set_password(serializer.validated_data['nuevo_password'])
        user.save()

        # Invalida token activo de usuario por cambio de contraseña, usuario debe logearse de nuevo 
        Token.objects.filter(user=user).delete()

        return Response(
            {'mensaje': f'Contraseña de {user.username} reestablecida correctamente'},
            status = status.HTTP_200_OK
        )
    
# FIN MODULO 1 - VISTAS DE AUTENTICACIÓN

# INICIO MODULO 2 - MANEJO DE CATALOGOS / LISTAS PREDEFINIDAS
# Esta sección del views va enfocada al manejo de los listados predefinidos dentro del sistema 

from django.db import IntegrityError

# Catalogo No 1 - clientes
# para consulta (GET) todos los usuarios cuentan con acceso 
# creación nuevos clientes (POST) solo ADMIN

class ClienteListView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get (self, request):
        clientes = Cliente.objects.all()
       
        # Filtro por clientes activos, útil para que en los dropdown solo aparezcan clientes vigentes
        activo = request.query_params.get('activo', None)
        if activo is not None:
            clientes = clientes.filter(activo=activo.lower() == 'true')
        
        # Filtro opcional por nombre - busqueda parcial sin distinción entre mayusculas y minusculas 
        nombre = request.query_params.get('nombre', None)
        if nombre is not None:
            clientes= clientes.filter(nombre_cliente__icontains=nombre)

        # Filtro opcional por NIT - búsqueda parcial para facilitar busqueda fragmentada
        nit = request.query_params.get('nit', None)
        if nit is not None:
            clientes = clientes.filter(nit__icontains=nit)

        serializer = ClienteSerializer(clientes, many=True)
        return Response (
            {
                'mensaje': 'Clientes obtenidos correctamente',
                'total': clientes.count(),
                'clientes' : serializer.data
            },
            status = status.HTTP_200_OK
        )
    
    def post(self, request):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error' : 'No tiene permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ClienteSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status = status.HTTP_400_BAD_REQUEST
            )
        
        # Registro del admin que creo el cliente
        cliente = serializer.save(creado_por = request.user)

        return Response(
            {
                'mensaje': f'cliente {cliente.nombre_cliente} creado correctamente',
                'cliente': ClienteSerializer(cliente).data
            }, 
            status = status.HTTP_201_CREATED
        )

# Edición de clientes existentes - solo ADMIN / permite DELETE que no elimina los registros relacionados con el cliente 

class ClienteDetalleView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request, cliente_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes lo permisos necesarios para realizar esta acción'},
                status = status.HTTP_403_FORBIDDEN
            )
        
        try:
            cliente = Cliente.objects.get(cliente_id = cliente_id)    
        except Cliente.DoesNotExist:
            return Response (
                {'error': 'Cliente no encontrado'},
                status = status.HTTP_404_NOT_FOUND
            )
        
        serializer = ClienteSerializer(cliente, data=request.data, partial = True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status = status.HTTP_400_BAD_REQUEST
            )
        
        cliente = serializer.save()

        return Response(
            {
                'mensaje': f'cliente {cliente.nombre_cliente} actualizado correctamente',
                'cliente': ClienteSerializer(cliente).data
            },
            status = status.HTTP_200_OK
        )
    
    def delete(self, request, cliente_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes los permisos para realizar esta acción'},
                status = status.HTTP_403_FORBIDDEN
            )
        
        try:
            cliente = Cliente.objects.get(cliente_id=cliente_id)
        except Cliente.DoesNotExist:
            return Response(
                {'error': 'Cliente no encontrado'},
                status = status.HTTP_404_NOT_FOUND
            )
        
        cliente.activo = False
        cliente.save()

        return Response(
            {'mensaje': f'cliente {cliente.nombre_cliente} desactivado correctamente'},
            status = status.HTTP_200_OK
        )

# Catalogo No. 2 - productos
# para consulta (GET) todos los usuarios cuentan con acceso 
# creación nuevos productos (POST) solo ADMIN

class ProductoListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        activo = request.query_params.get('activo', None)
        productos = Productos.objects.all()

        if activo is not None:
            productos = productos.filter(activo = activo.lower() == 'true')

        serializer = ProductosSerializer(productos, many= True)
        return Response (
            {
                'mensaje': 'Productos obtenidos correctamente',
                'total': productos.count(),
                'productos': serializer.data
            },
            status = status.HTTP_200_OK
        )
    
    def post(self, request):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes los permisos para realizar esta acción'}
            )
        
        serializer = ProductosSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        producto = serializer.save(producto_creado_por=request.user)
        
        return Response (
            {
                'mensaje': f'producto {producto.nombre_producto} creado correctamente',
                'producto': ProductosSerializer(producto).data
            },

            status=status.HTTP_201_CREATED
        )

# Clase para edición de información o desactivación de producto / SOLO ADMIN

class ProductoDetalleView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def put (self, request, producto_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes los permisos necesarios para esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            producto = Productos.objects.select_related('familia_producto').get(producto_id=producto_id)
        except Productos.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ProductosSerializer(producto, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        producto = serializer.save()

        return Response(
            {
                'mensaje': f'producto {producto.nombre_producto} actualizado correctamente',
                'producto': ProductosSerializer(producto).data
            },
            status=status.HTTP_200_OK
        )
    
    def delete(self, request, producto_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                statis=status.HTTP_403_FORBIDDEN            
            )
        
        try:
            producto = Productos.objects.get(producto_id=producto_id)
        except Productos.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'},
                status = status.HTTP_404_NOT_FOUND
            )
        
        producto.activo = False 
        producto.save()

        return Response(
            {'mensaje': f'Producto {producto.nombre_producto} desactivado correctamente'},
            status = status.HTTP_200_OK
        )
    
# Catalogo No. 3 - turnos
# para consulta (GET) todos los usuarios cuentan con acceso 
# creación nuevos turnos (POST) solo ADMIN

class TurnoListView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        activo = request.query_params.get('activo', None)
        turnos = Turno.objects.all()

        if activo is not None:
            turnos = turnos.filter(activo=activo.lower () == 'true')

        serializer = TurnoSerializer(turnos, many=True)
        return Response (
            {
                'mensaje': 'turnos obtenidos correctamente',
                'total': turnos.count(),
                'turnos': serializer.data
            },
            status = status.HTTP_200_OK
        )
    
    def post(self, request):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar esta acción'},
                status = status.HTTP_403_FORBIDDEN
            )
        
        serializer = TurnoSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        turno = serializer.save(turno_creado_por=request.user)

        return Response(
            {
                'mensaje': f'turno {turno.nombre_turno} creado correctamente',
                'turno': TurnoSerializer(turno).data
            },
            status = status.HTTP_201_CREATED
        )

# Clase para edición de información o desactivación de turnos / SOLO ADMIN
class TurnoDetalleView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request, turno_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status = status.HTTP_403_FORBIDDEN
            )
    
        try:
            turno = Turno.objects.get(turno_id=turno_id)
            
        except Turno.DoesNotExist:
            return Response(
                {'error': 'Turno no encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = TurnoSerializer(turno, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response (
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status = status.HTTP_400_BAD_REQUEST
            )

        turno = serializer.save()

        return Response(
            {
                'mensaje': f'Turno {turno.nombre_turno} actualizado correctamente',
                'turno': TurnoSerializer(turno).data
            },
            status = status.HTTP_200_OK
        )

    def delete(self, request, turno_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response (
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            turno = Turno.objects.get(turno_id=turno_id)
        except Turno.DoesNotExist:
            return Response(
                {'error': 'Turno no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        turno.activo = False 
        turno.save()

        return Response(
            {'mensaje': f'turno{turno.nombre_turno} desactivado corrrectamente'},
            status = status.HTTP_200_OK
        )
    
# Catalogo No. 4 - listas predefinidas
# para consulta (GET) todos los usuarios cuentan con acceso 
# creación de nuevos registros dentro de un listado (POST) solo ADMIN

class ListaPredefinidaListView(APIView):
    
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        
        listas = ListaPredefinida.objects.all()

        # se hace el request del tipo de lista para poblar el dropdown que corresponda
        
        tipo = request.query_params.get('tipo', None)
        if tipo is not None:
            listas = listas.filter(tipo=tipo.upper())

        # Filtro opcional para que muestre solo listas activas
        activo = request.query_params.get('activo', None)
        if activo is not None:
            listas = listas.filter(activo=activo.lower() == 'true')

        serializer = ListaPredefinidaSerializer(listas, many = True)
        return Response(
            {
                'mensaje': 'Listas obtenidas correctamente',
                'total': listas.count(),
                'listas': serializer.data
            },

            status = status.HTTP_200_OK
        )
    
    def post (self, request):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                { 'error': 'No tienes permisos para realizar esta acción' },

                status = status.HTTP_403_FORBIDDEN
            )
        
        serializer = ListaPredefinidaSerializer(data = request.data)

        if not serializer.is_valid():
            return Response (
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },

                status = status.HTTP_400_BAD_REQUEST
            )
        
        # IntegrityError atributo 'tipo' del modelo ListaPredefinida tiene atributo unique = True no pueden haber listas duplicadas

        try:
            lista = serializer.save(creado_por=request.user)
        except IntegrityError:
            return Response(
                {'error': 'ya existe un registro de este tipo de lista'},
                status = status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            {
                'mensaje': f'Registro {lista.nombre} creado correctamente en {lista.get_tipo_display()}',
                'lista': ListaPredefinidaSerializer(lista).data
            },

            status = status.HTTP_201_CREATED
        )
    
# Clase para edición de información o desactivación de turnos / SOLO ADMIN

class ListaPredefinidaDetalleView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request, lista_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tiene permisos para realizar esta acción'},

                status = status.HTTP_403_FORBIDDEN
            )
        
        try:
            lista = ListaPredefinida.objects.get(lista_id = lista_id)
        except ListaPredefinida.DoesNotExist:
            return Response(
                {'error': 'Lista no encontrada'},

                status = status.HTTP_404_NOT_FOUND
            )
        
        serializer = ListaPredefinidaSerializer(lista, data = request.data, partial = True)

        if not serializer.is_valid():
            return Response (
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status = status.HTTP_400_BAD_REQUEST
            )
        
        lista = serializer.save()

        return Response(
            {
                'mensaje': f'Lista {lista.nombre} actualizada correctamente',
                'lista': ListaPredefinidaSerializer(lista).data
            },
            
            status = status.HTTP_200_OK
        )
    
    def delete(self, request, lista_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},

                status = status.HTTP_403_FORBIDDEN
            )
        
        try: 
            lista = ListaPredefinida.objects.get(lista_id = lista_id)
        except ListaPredefinida.DoesNotExist:
            return Response(
                {'error': 'Lista no encontrada'},

                status = status.HTTP_404_NOT_FOUND
            )
        
        lista.activo = False
        lista.save()

        return Response(
            {'mensaje': f'Lista {lista.nombre} desactivada correctamente'},

            status = status.HTTP_200_OK
        )

# FIN MODULO 2 CATALOGOS


# INICIO MODULO 3 - DOM'S
# LOGICA VIEWS DE LAS ETAPAS PLANEACIÓN ALMACEN PRODUCCION Y TRATAMIENTO EN MODULO 4
# SE MANEJA LOGICA DE LA CREACIÓN DEL DOM ASÍ COMO DE ETAPAS 1 Y 6

from django.db import transaction, IntegrityError

# Clase para obtener datos GET DomListView o listado de todos los DOMS del sistema todos los roles del sistema 
# Clase para creación de nuevo registro DOM ANALISTA_1 ANALISTA_2 ADMIN

class DomListView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get (self, request):
        doms = Dom.objects.select_related('nombre_cliente').prefetch_related('productos')

        # Filtro opcional por cliente - para dashboard y facilitar búsqueda por filtros especificos

        cliente_id = request.query_params.get('cliente', None)
        if cliente_id is not None:
            doms = doms.filter(nombre_cliente__cliente_id=cliente_id)

        # Filtro opcional por estado del dom 
        estado = request.query_params.get('estado', None)
        if estado is not None:
            doms = doms.filter(tipo_estado_dom=estado.upper())
        
        serializer = DomListSerializer(doms, many=True)
        return Response(
            {
                'mensaje': 'DOMs obtenidos correctamente',
                'total': doms.count(),
                'doms': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        if not verificar_rol(request, ['ADMIN', 'ANALISTA_1', 'ANALISTA_2']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
    # Variable extrae productos del body - deben enviarse como listado
        productos_data = request.data.get('productos', [])

        if not productos_data:
            return Response(
                {'error': 'El nuevo registro DOM debe contener al menos un producto'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = DomDetalleSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validación individua de cada producto antes de iniciar la transacción 
        productos_serializers=[]
        for producto_data in productos_data:
            producto_serializer = ProductosDomSerializer(data=producto_data)
            if not producto_serializer.is_valid():
                return Response(
                    {
                        'error': 'Datos de producto invalidos '
                    }
                )
            productos_serializers.append(producto_serializer)
        
        # operación que aplica atomicidad nuevo registro debe ser DOM + ProductosDoms juntos o ninguno, DOM sin productos sin proposito dentro del sistema
        try:
            with transaction.atomic():
                dom: Dom = serializer.save(creado_por=request.user)

                for producto_serializer in productos_serializers:
                    producto_serializer.save(productoDom=dom)

                # registro de auditoria de creación
                registrar_auditoria(
                    dom=dom,
                    usuario=request.user,
                    accion='CREACION',
                    etapa='etapa_0'
                )
        except Exception as e:
            return Response(
                {'error': f'Error al crear el DOM: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response(
            {
                'mensaje': f'DOM #{dom.dom_id} creado correctamente',
                'dom': DomDetalleSerializer(dom).data
            },
            status=status.HTTP_201_CREATED
        )


# Clase para consulta de todos los detalles del DOM una vez se ha seleccionado uno en especifico
# Clase para la edición de etapas según roles y permisos establecidos dentro del sistema:
# GERENCIA      → solo lectura
# ADMIN         → etapas 0, 1, 2, 3, 4, 5, 6 + usuarios y catálogos
# ANALISTA_1    → etapas 0, 1, 6
# ANALISTA_2    → etapas 0, 1, 6
# PLANEADOR     → etapa 2
# LIDER_PLANTA  → etapas 3, 4, 5

class DomDetalleView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, dom_id):
        try:
            dom = Dom.objects.select_related('nombre_cliente').prefetch_related('productos').get(dom_id=dom_id)
        except Dom.DoesNotExist:
            return Response(
                {'error': 'DOM no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = DomDetalleSerializer(dom)
        return Response(
            {
                'mensaje': 'DOM obtenido correctamente',
                'dom': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def put(self, request, dom_id):

        # Identificación de la etapa que se está modificando
        etapa = request.data.get('etapa', None)

        if etapa is None:
            return Response (
                {'error': 'Debe indicar la etapa que desea editar'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificación de permiso especifico por etapa via models

        try:
            perfil = get_perfil(request)
        except PerfilUsuario.DoesNotExist:
            return Response(
                {'error': 'El usuario no tienen perfil asignado'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not perfil.puede_editar_etapas(etapa):
            return Response(
                {'error': f'No tienes permiso para editar {etapa}'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            dom = Dom.objects.get(dom_id=dom_id)
        except Dom.DoesNotExist:
            return Response(
                {'error': 'DOM no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # permite cambiar el estado del campo TIPO O ESTADO DOM de la etapa 0 del formulario; Solo ADMIN y analistas de costos quedan facultados

        if 'tipo_estado_dom' in request.data:
            if not verificar_rol(request, ['ADMIN', 'ANALISTA_1', 'ANALISTA_2']):
                return Response(
                    {'error': f'No tienes permisos para cambiar el estado del DOM'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Verifica bloqueo de etapa antes de aplicar cambios
        bloqueos = {
            'etapa_1': dom.etapa_1_bloqueda,     # nota: nombre con typo en models.py(linea 246), no corregir sin actualizar ambos
            'etapa_6': dom.etapa_6_bloqueada,
        }
        if etapa in bloqueos and bloqueos[etapa]():
            return Response(
                {'error': f'La {etapa} de esta DOM está bloqueada y no puede ser modificada, contacte con el Administrador del sistema'},
                status=status.HTTP_400_BAD_REQUEST      
            )
        
        serializer = DomDetalleSerializer(dom, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        dom = serializer.save()

        # Registros de auditoria, primero se verifica que la etapa no esté bloqueada 
        accion = 'BLOQUEO_ETAPA' if etapa in bloqueos and bloqueos[etapa]() else 'EDICION'

        registrar_auditoria(
            dom=dom,
            usuario=request.user,
            accion=accion,
            etapa=etapa
        )

        return Response(
            {
                'mensaje': f'DOM #{dom.dom_id} actualizado correctamente',
                'dom': DomDetalleSerializer(dom).data
            },
            status=status.HTTP_200_OK
        )
        
# FIN MODULO 3 - DOMs


# INICIO MODULO 4 - ETAPAS 2, 3, 4, 5

# Ante necesidad de diseño de producto (1 registro planeación puede tener +N etapas 2 a 5 el manejo de estas se hace por fuera de DOMListView y DomDetalleView
# Permisos:
#   GET:               todos los roles autenticados
#   Etapa 2:           ADMIN, PLANEADOR
#   Etapas 3, 4, 5:    ADMIN, LIDER_PLANTA
        
# Etapa 2 - Planeación 

class RegistroPlaneacionListView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        registros = RegistroPlaneacion.objects.select_related(
            'dom', 'turno', 'dom_producto__tipo_producto'
        ).all()

    # Filtro necesario para que traiga registro de planeación de un DOM especifico, no N registros 
        dom_id = request.query_params.get('dom_id', None)
        if dom_id is not None:
            registros = registros.filter(dom__dom_id=dom_id)
        
        serializer = RegistroPlaneacionSerializer(registros, many=True)
        return Response(
            {
                'mensaje': 'Registros de planeación obtenidos correctamente',
                'total': registros.count(),
                'registros': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        if not verificar_rol(request, ['ADMIN', 'PLANEADOR']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        

        # Verifica existencia del DOM
        dom_id = request.data.get('dom_id', None)
        if dom_id is None:
            return Response(
                {'error': 'Debe indicar el DOM al que pertenece el registro'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            dom = Dom.objects.get(dom_id=dom_id)
        except Dom.DoesNotExist:
            return Response(
                {'error': 'DOM no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Asigna numero de registro (recordar se permiten N registros) - correlativo por DOM
        ultimo_registro = RegistroPlaneacion.objects.filter(dom=dom).order_by('-numero_registro').first()
        numero_registro = (ultimo_registro.numero_registro + 1) if ultimo_registro else 1 

        serializer = RegistroPlaneacionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos', 
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        registro = serializer.save(
            creado_por=request.user,
            numero_registro=numero_registro,
            dom=dom
        )

        registrar_auditoria(
            dom=dom, 
            usuario=request.user,
            accion='CREACION',
            etapa='etapa_2'
        )

        # Refresca el objeto con relaciones cargadas
        registro = RegistroPlaneacion.objects.select_related(
            'dom', 'turno', 'dom_producto__tipo_producto'
        ).get(id=registro.id)

        return Response(
            {
                'mensaje': f'registro de planeación #{registro.numero_registro} creado correctamente',
                'registro': RegistroPlaneacionSerializer(registro).data
            },
            status=status.HTTP_201_CREATED
        )
    
# Clase para obtener datos de los registros de planeación relacionados con un DOM todos los roles habilitados para consultar la información
# Permite edición etapa 2 unicamente a ADMIN, ANALISTA_1, ANALISTA_2

class RegistroPlaneacionDetalleView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, registro_id):
        try:
            registro = RegistroPlaneacion.objects.select_related(
                'dom', 'turno', 'dom_producto__tipo_producto'
            ).get(id=registro_id)
        except RegistroPlaneacion.DoesNotExist:
            return Response(
                {'error': 'Registro de planeación no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = RegistroPlaneacionSerializer(registro)
        return Response (
            {
                'mensaje': 'Registro de planeación obtenido correctamente',
                'registro': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def put(self, request, registro_id):
        if not verificar_rol(request, ['ADMIN', 'PLANEADOR']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            registro = RegistroPlaneacion.objects.get(id=registro_id)
        except RegistroPlaneacion.DoesNotExist:
            return Response (
                {'error': 'Registro de planeación no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificación de bloqueo de etapa
        if registro.etapa2_bloqueada():
            return Response(
                {'error': 'Este registro de planeación ya ha sido bloqueado para edición, contacte al Administrador del sistema'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = RegistroPlaneacionSerializer(registro, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        registro = serializer.save()

        accion = 'BLOQUEO_ETAPA' if registro.etapa2_bloqueada() else 'EDICION'

        registrar_auditoria(
            dom=registro.dom,
            usuario=request.user,
            accion=accion, 
            etapa='etapa_2'
        )
        
        # Refresca el objeto con relaciones cargadas
        registro = RegistroPlaneacion.objects.select_related(
        'dom', 'turno', 'dom_producto__tipo_producto'
        ).get(id=registro.id)

        return Response(
            {
                'mensaje': f'registro de planeacion #{registro.numero_registro} actualizado correctamente',
                'registro': RegistroPlaneacionSerializer(registro).data
            }, 
            status=status.HTTP_200_OK
        )
# Fin etapa 2 - planeación

# Inicio etapa 3 - almacen 


# clase para obtener todos los registros de almacen para consulta, todos los roles pueden acceder para lectura (GET)
# La clase permite igualmente creación de nuevo registro almacen solo ADMIN Y LIDER_PLANTA

class RegistroAlmacenListView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        registros = RegistroAlmacen.objects.select_related('registro_planeacion').all()

        # Filtro para obtener registros almacen asoaciados a una planeación especifica de un DOM especifico, evita que se traigan todos los registros de almacen del sistema
        planeacion_id = request.query_params.get('planeacion', None)
        if planeacion_id is not None:
            registros = registros.filter(registro_planeacion__id=planeacion_id)
        
        serializer = RegistroAlmacenSerializer(registros, many=True)
        
        return Response (
            {
                'mensaje': 'Registros de almacén obtenidos correctamente',
                'total': registros.count(),
                'registros': serializer.data
            },
            status=status.HTTP_200_OK
        )

    def post(self, request):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar está acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verifica que registro de planeación exista
        planeacion_id = request.data.get('registro_planeacion', None)
        if planeacion_id is None:
            return Response(
                {'error': 'Debe indicar el registro de pleneación al que pertenece'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            planeacion = RegistroPlaneacion.objects.get(id=planeacion_id)
        except RegistroPlaneacion.DoesNotExist:
            return Response(
                {'error': 'Registro de Planeación no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Asignma numero_regisyro automaticamente - correlativo a la planeación
        ultimo = RegistroAlmacen.objects.filter(registro_planeacion=planeacion).order_by('-numero_registro').first()
        numero_registro = (ultimo.numero_registro + 1) if ultimo else 1

        serializer = RegistroAlmacenSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Guarda en back datos no enviados desde front, generación automatica 
        registro = serializer.save(
            creado_por = request.user,
            numero_registro=numero_registro
        )

        registrar_auditoria(
            dom=planeacion.dom,
            usuario=request.user,
            accion='CREACION',
            etapa='etapa_3'
        )

        return Response(
            {
                'mensaje': f'Registro de almacén #{registro.numero_registro} creado correctamente',
                'registro': RegistroAlmacenSerializer(registro).data
            },
            status=status.HTTP_201_CREATED
        )

# Clase retorna detalles de registro almacen especifico, ligado a registro producción (GET)
# Clase permite actualizar datos registro almacen especifico ADMIN, LIDER_PLANTA

class RegistroAlmacenDetalleView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, registro_id):
        try:
            registro = RegistroAlmacen.objects.select_related('registro_planeacion').get(id=registro_id)
        except RegistroAlmacen.DoesNotExist:
            return Response (
                {'error': 'Registro de Almacén no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = RegistroAlmacenSerializer(registro)
        return Response(
            {
                'mensaje': 'Registro de almacén obtenido correctamente',
                'registro': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def put(self, request, registro_id):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # verificación registro de almacen existe 
        try:
            registro = RegistroAlmacen.objects.get(id=registro_id)
        except RegistroAlmacen.DoesNotExist:
            return Response (
                {'error': 'Registro de almacén no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # verificación de bloqueo por etapa
        if registro.etapa_3_bloqueada():
            return Response(
                {'error': 'Este registro de almacen se encuentra bloqueado. Por favor, contacte al administrador del sistema'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = RegistroAlmacenSerializer(registro, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos inválidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        registro = serializer.save()

        accion = 'BLOQUEO_ETAPA' if registro.etapa_3_bloqueada() else 'EDICION'

        registrar_auditoria(
            dom = registro.registro_planeacion.dom,
            usuario=request.user,
            accion=accion,
            etapa='etapa_3'
        )

        return Response(
            {
                'mensaje': f'Registro de almacén #{registro.numero_registro} actualizado correctamente',
                'registro': RegistroAlmacenSerializer(registro).data
            },
            status=status.HTTP_200_OK
        )
# Fin etapa 3 - almacén 

# Inicio etapa 4 - Producción

# Clase permite obtener registros de produccion (get). admite todos los roles autenticados, solo consulta a través de get
# Clase permite creacion de nuevos registros de produccion (put). Solo ADMIN y LIDER_PLANTA

class RegistroProduccionListView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        registros = RegistroProduccion.objects.select_related('registro_planeacion').all()

        # metodo filtra para que obtenga unicamente registros produccion asociados a un DOM especifico
        planeacion_id = request.query_params.get('planeacion', None)
        if planeacion_id is not None:
            registros = registros.filter(registro_planeacion__id=planeacion_id)
        
        serializer = RegistroProduccionSerializer(registros, many=True)
        return Response(
            {
                'mensaje': 'Registros de producción obtenidos correctamente',
                'total': registros.count(),
                'registros': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verifica que el registro de planeacion exista
        planeacion_id = request.data.get('registro_planeacion', None)
        if planeacion_id is None:
            return Response (
                {'error': 'Debe indicar el registro de planeación al que pertenece'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            planeacion = RegistroPlaneacion.objects.get(id=planeacion_id)
        except RegistroPlaneacion.DoesNotExist:
            return Response(
                {'error': 'Registro de planeacion no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Asigna numero_registro automaticamente. recordar se permiten N registros
        ultimo = RegistroProduccion.objects.filter(registro_planeacion=planeacion).order_by('-numero_registro').first()
        numero_registro = (ultimo.numero_registro + 1) if ultimo else 1

        serializer = RegistroProduccionSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        registro = serializer.save(
            creado_por=request.user,
            numero_registro=numero_registro
        )

        registrar_auditoria(
            dom=planeacion.dom,
            usuario=request.user,
            accion='CREACION',
            etapa='etapa_4'
        )

        return Response(
            {
                'mensaje': f'registro de producción #{registro.numero_registro} creado correctamente',
                'registro': RegistroProduccionSerializer(registro).data
            }, 
            status=status.HTTP_201_CREATED
        )

# Clase permite consultar los detalles de un registro de producción dentro de un registro DOM (metodo get). habilitado para todos usuarios registrados SOLO LECTURA
# Clase permite igualmente editar registros de produccion SOLO ADMIN Y LIDER_PLANTA

class RegistroProduccionDetalleView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, registro_id):
        try:
            registro = RegistroProduccion.objects.select_related('registro_planeacion').get(id=registro_id)
        except RegistroProduccion.DoesNotExist:
            return Response(
                {'error': 'Registro de producción no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = RegistroProduccionSerializer(registro)
        return Response(
            {
                'mensaje': 'Registro de producción obtenido correctamente',
                'registro': serializer.data
            }, 
            status=status.HTTP_200_OK
        )
    
    def put(self, request, registro_id):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            registro = RegistroProduccion.objects.get(id=registro_id)
        except RegistroProduccion.DoesNotExist:
            return Response(
                {'error': 'Registro de producción no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificación bloqueo etapa
        if registro.etapa_4_bloqueada():
            return Response(
                {'error': 'Este registro se encuentra actualmente bloqueado y no puede ser modificado. Por favor contacte al Administrador del sistema'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = RegistroProduccionSerializer(registro, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Daros invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        registro = serializer.save()

        accion = 'BLOQUEO_ETAPA' if registro.etapa_4_bloqueada() else 'EDICION'

        registrar_auditoria(
            dom=registro.registro_planeacion.dom,
            usuario=request.user,
            accion=accion,
            etapa='etapa_4'
        )

        return Response(
            {
                'mensaje': f'Registro de produccion #{registro.numero_registro} actualizado correctamente',
                'registro': RegistroProduccionSerializer(registro).data
            },
            status=status.HTTP_200_OK
        )

# Fin etapa 4 Produccion 

# Incio etapa 5 Tratamiento Fitosantario

# Clase permite obtener listados de registro de tratamiento. acceso para consulta a todos los usuarios autenticados (solo consulta) a través de meotod get
# Clase permite igualmente la creacion de nuevos registros de tratamiento. solo ADMIN y LIDER_PLANTA a través de metodo post 

class RegistroTratamientoListView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        registros = RegistroTratamiento.objects.select_related('registro_planeacion').all()

        # filtro opcional por registro de planeacion
        planeacion_id = request.query_params.get('planeacion', None)
        if planeacion_id is not None:
            registros = registros.filter(registro_planeacion__id=planeacion_id)

        serializer = RegistroTratamientoSerializer(registros, many=True)
        return Response(
            {
                'mensaje': 'Registros de tratamiento obtenidos correctamente',
                'total': registros.count(),
                'registros': serializer.data
            },
            status=status.HTTP_200_OK
        )

    def post(self, request):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verifica que el registro de planeacion exista
        planeacion_id = request.data.get('registro_planeacion', None)
        if planeacion_id is None:
            return Response(
                {'error': 'Debe indicar el registro de planeación al que pertenece'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            planeacion = RegistroPlaneacion.objects.get(id=planeacion_id)
        except RegistroPlaneacion.DoesNotExist:
            return Response(
                {'error': 'Registro de planeación no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Asigna numero_registro automáticamente — correlativo a la planeación
        ultimo = RegistroTratamiento.objects.filter(
            registro_planeacion=planeacion
        ).order_by('-numero_registro').first()
        numero_registro = (ultimo.numero_registro + 1) if ultimo else 1

        serializer = RegistroTratamientoSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos inválidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        registro = serializer.save(
            creado_por=request.user,
            numero_registro=numero_registro
        )

        registrar_auditoria(
            dom=planeacion.dom,
            usuario=request.user,
            accion='CREACION',
            etapa='etapa_5'
        )

        return Response(
            {
                'mensaje': f'Registro de tratamiento #{registro.numero_registro} creado correctamente',
                'registro': RegistroTratamientoSerializer(registro).data
            },
            status=status.HTTP_201_CREATED
        )


# RegistroTratamientoDetalleView — maneja un registro de tratamiento específico
# GET: todos los roles autenticados
# PUT: solo ADMIN y LIDER_PLANTA

class RegistroTratamientoDetalleView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, registro_id):
        try:
            registro = RegistroTratamiento.objects.select_related(
                'registro_planeacion'
            ).get(id=registro_id)
        except RegistroTratamiento.DoesNotExist:
            return Response(
                {'error': 'Registro de tratamiento no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RegistroTratamientoSerializer(registro)
        return Response(
            {
                'mensaje': 'Registro de tratamiento obtenido correctamente',
                'registro': serializer.data
            },
            status=status.HTTP_200_OK
        )

    def put(self, request, registro_id):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            registro = RegistroTratamiento.objects.get(id=registro_id)
        except RegistroTratamiento.DoesNotExist:
            return Response(
                {'error': 'Registro de tratamiento no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verificación bloqueo de etapa
        if registro.etapa_5_bloqueada():
            return Response(
                {'error': 'Este registro de tratamiento se encuentra bloqueado y no puede ser modificado. Por favor contacte al administrador del sistema'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = RegistroTratamientoSerializer(registro, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos inválidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        registro = serializer.save()

        accion = 'BLOQUEO_ETAPA' if registro.etapa_5_bloqueada() else 'EDICION'

        registrar_auditoria(
            dom=registro.registro_planeacion.dom,
            usuario=request.user,
            accion=accion,
            etapa='etapa_5'
        )

        return Response(
            {
                'mensaje': f'Registro de tratamiento #{registro.numero_registro} actualizado correctamente',
                'registro': RegistroTratamientoSerializer(registro).data
            },
            status=status.HTTP_200_OK
        )

# Fin etapa 5 - Tratamiento Fitosanitario
    
# FIN MODULO 4 - REGISTRO DE ETAPAS 2,3,4,5

# INICIO MODULO 5 - CRONOMETRO

#   Todas las operaciones: ADMIN, LIDER_PLANTA
#
# Flujo:
#   INICIAR  → crea RegistroTiempoProduccion (estado=EN_CURSO)
#   PAUSAR   → crea PausaTiempoProduccion (inicio_pausa) + estado=PAUSADO
#   REANUDAR → cierra pausa activa (fin_pausa, minutos_pausados) + estado=EN_CURSO
#   FINALIZAR→ cierra cronómetro (fin, minutos_totales) + estado=FINALIZADO
#              modelo.save() actualiza minutos_asignados en RegistroProduccion automáticamente

from django.utils import timezone

class CronometroIniciarView(APIView):

# Crea RegistroTiempoProduccion con estado=EN_CURSO e inicio=ahora.
# Valida que no exista ya un cronómetro EN_CURSO para ese registro.

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not verificar_rol (request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verificación que el registro de producción exista
        produccion_id = request.data.get('registro_produccion', None)
        if produccion_id is None:
            return Response(
                {'error': 'Debe indicar el registro de producción'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            registro_produccion = RegistroProduccion.objects.get(id=produccion_id)
        except RegistroProduccion.DoesNotExist:
            return Response(
                {'error': 'Registro de producción no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verifica que no exista cronómetro EN_CURSO para este registro
        cronometro_activo = RegistroTiempoProduccion.objects.filter(
            registro_produccion=registro_produccion,
            estado='EN_CURSO'
        ).first()

        if cronometro_activo:
            return Response(
                {'error': 'Ya existe un cronómetro en curso para este registro de producción'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Creación del cronometro
        cronometro = RegistroTiempoProduccion.objects.create(
            registro_produccion=registro_produccion,
            inicio=timezone.now(),
            estado='EN_CURSO',
            usuario=request.user
        )

        return Response(
            {
                'mensaje': 'Cronómetro inciado corrextamente',
                'cronometro': RegistroTiempoProduccionSerializer(cronometro).data
            },
            status=status.HTTP_201_CREATED
        )
    
# Clase pausa cronómetro
class CronometroPausaView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        cronometro_id = request.data.get('cronometro_id', None)
        if cronometro_id is None:
            return Response(
                {'error': 'Debe indicar el cronómetro a pausar'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cronometro = RegistroTiempoProduccion.objects.get(id=cronometro_id)
        except RegistroTiempoProduccion.DoesNotExist:
            return Response(
                {'error': 'Cronómetro no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    # Valida estado - solo se puede pausar si está EN_CURSO
        if cronometro.estado != 'EN_CURSO':
            return Response(
                {'error': f'No se puede pausar un cronómetro en estado {cronometro.estado}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crea pausa y actualiza estado
        PausaTiempoProduccion.objects.create(
            registro_tiempo=cronometro,
            inicio_pausa=timezone.now()
        )

        cronometro.estado = 'PAUSADO'
        cronometro.save()

        return Response(
            {
                'mensaje': 'Cronómetro pausado correctamente',
                'cronometro': RegistroTiempoProduccionSerializer(cronometro).data
            },
            status=status.HTTP_200_OK
        )

# Clase reanuda cronómetro en pausa
class CronometroReanudarView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar está accion'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        cronometro_id = request.data.get('cronometro_id', None)
        if cronometro_id is None:
            return Response(
                {'error': 'Debe indicar el cronómetro a reanudar'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cronometro = RegistroTiempoProduccion.objects.get(id=cronometro_id)
        except RegistroTiempoProduccion.DoesNotExist:
            return Response(
                {'error': 'Cronómetro no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
    
        # Valida estado - solo se puede reanudar si esta PAUSADO
        if cronometro.estado != 'PAUSADO':
            return Response(
                {'error': f'No se puede reanudar un cronómetro en estado {cronometro.estado}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Busca la pausa activa - la que no tienen fin_pausa
        pausa_activa = cronometro.pausas.filter(fin_pausa__isnull=True).first()

        if pausa_activa is None:
            return Response(
                {'error': 'No se encontró una pausa activa para este cronómetro'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Cierra la pausa - modelo.save() calcula minutos_pausados automáticamente
        pausa_activa.fin_pausa = timezone.now()
        pausa_activa.save()

        # Actualiza total_minutos_pausados en el cronómetro
        cronometro.total_segundos_pausados += pausa_activa.segundos_pausados or 0
        cronometro.estado = 'EN_CURSO'
        cronometro.save()

        return Response(
            {
                'mensaje': 'Cronómetro reanudado correctamente',
                'cronometro': RegistroTiempoProduccionSerializer(cronometro).data
            },
            status=status.HTTP_200_OK
        )

# Clase para finalizar cronometro 
class CronometroFinalizarView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
    
        cronometro_id = request.data.get('cronometro_id', None)
        if cronometro_id is None:
            return Response(
                {'error': 'Debe indicar el cronómetro a finalizar'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cronometro = RegistroTiempoProduccion.objects.get(id=cronometro_id)
        except RegistroTiempoProduccion.DoesNotExist:
            return Response(
                {'error': 'Cronómetro no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Valida estado - solo se puede finalizar si está EN_CURSO
        # No se puede finalizar si esta PAUSADO - usuario debe verificar primero

        if cronometro.estado != 'EN_CURSO':
            return Response(
                {'error': f'No se puede finalizar un cronometro en estado {cronometro.estado}. Reanude el cronómetro antes de finalizar'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Registra fin y calcula minutos_totales
        cronometro.fin = timezone.now()
        cronometro.estado = 'FINALIZADO'
        cronometro.minutos_totales = cronometro.calcular_minutos_totales()

        # modelo.save() actualiza minutos_asignados en RegistroProduccion Automáticamente

        cronometro.save()

        return Response(
            {
                'mensaje': 'Cronómetro finalizado correctamente',
                'cronometro': RegistroTiempoProduccionSerializer(cronometro).data
            },
            status = status.HTTP_200_OK
        )
        
# FIN MODULO 5 - CRONÓMETRO

# INICIO MODULO 6 - REPORTES Y DASHBOARD 

# Permisos:
# Todos los roles autenticados: interfaz de consulta, no puede modificarse ningún dato en ella. 

# Filtros:
#   InformeCumplimientoPlaneacionView: ?fecha_inicio & ?fecha_fin
#   InformeDespachoView:               ?fecha_inicio & ?fecha_fin
#   InformeAuditoriaView:              ?fecha_inicio & ?fecha_fin & ?dom_id & ?usuario


# DomReporteView view relacionada con el consolidado en PDF que, como requirimiento del sistema, debe generarse respecto de cada reporte DOM individual

#
# Nota: InformeCumplimientoPlaneacionView es el endpoint de mayor complejidad
#       del sistema — cruza RegistroPlaneacion con sus tres registros hijo
#       (almacen, produccion, tratamiento) y calcula métricas de cumplimiento.

from django.db.models import Sum, Count, Q

# Clase DashboardView
# Retorna métricas globales del sistema para la página de inicio.
# Incluye: resumen DOMs, métricas de producción, DOMs próximos a vencer,   DOMs vencidos y productos pendientes por categoría en los próximos 15 días.
# Todos los roles autenticados.

class DashboardView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        hoy = timezone.now().date()

        # Resumen global DOMs
        total_doms = Dom.objects.count()
        total_doms_activos = Dom.objects.filter(dom_liberado_cierre=False).count()
        total_doms_cerrados = Dom.objects.filter(dom_liberado_cierre=True).count()

        # DOMs por etapa - se constuye buscando compatibilidad gráfica con librearias gráficas React

        doms_por_etapa = [
            {
                'etapa': 'Etapa 1 - Comercial',
                'total': Dom.objects.filter(dom_relacionado_produccion=False, dom_liberado_cierre=False).count()
            },
            {
                'etapa': 'Etapa 2 - Planeación',
                'total': RegistroPlaneacion.objects.filter(planeacion_completa=False).values('dom').distinct().count()
            },
            {
                'etapa': 'Etapa 3 - Almacén',
                'total': RegistroAlmacen.objects.filter(materias_liberadas=False).values('registro_planeacion__dom').distinct().count()
            },
            {
                'etapa': 'Etapa 4 - Producción',
                'total': RegistroProduccion.objects.filter(cierre_produccion=False).values('registro_planeacion__dom').distinct().count()
            },
            {
                'etapa': 'Etapa 5 - Tratamiento',
                'total': RegistroTratamiento.objects.filter(tratamiento_completado=False).values('registro_planeacion__dom').distinct().count()
            },
            {
                'etapa': 'Etapa 6 - Despacho',
                'total': Dom.objects.filter(dom_relacionado_produccion=True, dom_liberado_cierre=False).count()
            },
        ]

        # Metricas de producción globales
        cantidad_elaborada_total = RegistroProduccion.objects.aggregate(
            total=Sum('cantidad_elaborada')
        )['total'] or 0

        cantidad_pedida_total = ProductosDom.objects.aggregate(
            total=Sum('cantidad_pedido')
        )['total'] or 0

        cantidad_pendiente_total = cantidad_pedida_total - cantidad_elaborada_total

        # DOMs proximos a vencer: crieterio es fecha solicitada proximos 7 dias

        fecha_limite_7 = hoy + timezone.timedelta(days=7)
        doms_proximos_vencer = Dom.objects.filter(
            fecha_solicitada_cliente__gte=hoy,
            fecha_solicitada_cliente__lte=fecha_limite_7,
            dom_liberado_cierre=False
        ).select_related('nombre_cliente').prefetch_related('productos')
        
        # DOMs vencidos: criterio es fecha_solicitada_cliente ya se pasó y no se han dado como cerrados
        doms_vencidos = Dom.objects.filter(
            fecha_solicitada_cliente__lt=hoy,
            dom_liberado_cierre=False
        ).select_related('nombre_cliente').prefetch_related('productos')

        # Productos pendientes por categoria en los próximos 15 dias
        fecha_limite_15 = hoy + timezone.timedelta(days=15)
        doms_proximos_15 = Dom.objects.filter(
            fecha_solicitada_cliente__lte=fecha_limite_15,
            dom_liberado_cierre=False
        )

        # Agrupa por producto y calcula pendientes
        productos_pendientes = []
        productos_ids = ProductosDom.objects.filter(
            productoDom__in=doms_proximos_15
        ).values('tipo_producto').distinct()

        for item in productos_ids:
            producto_id = item['tipo_producto']
            try:
                producto = Productos.objects.get(producto_id=producto_id)
            except Productos.DoesNotExist:
                continue

            doms_con_producto = doms_proximos_15.filter(
                productos__tipo_producto_id=producto_id
            ).distinct()

            cantidad_pedida = ProductosDom.objects.filter(
                productoDom__in=doms_con_producto,
                tipo_producto_id=producto_id
            ).aggregate(total=Sum('cantidad_pedido'))['total'] or 0

            cantidad_elaborada = RegistroProduccion.objects.filter(
                registro_planeacion__dom__in=doms_con_producto,
                registro_planeacion__dom_producto__tipo_producto_id=producto_id
            ).aggregate(total=Sum('cantidad_elaborada'))['total'] or 0

            cantidad_pendiente = cantidad_pedida - cantidad_elaborada

            if cantidad_pendiente > 0:
                productos_pendientes.append({
                    'nombre_producto': producto.nombre_producto,
                    'cantidad_pendiente': cantidad_pendiente,
                    'doms_involucrados': doms_con_producto.count()
                })
        
        # Calculo de metricas globales a tres niveles: si cumplió el dom como un global, si se cumplio la planeación (así como sus etapas hijas) y despachos

        doms_activos = Dom.objects.filter(
            dom_liberado_cierre=False
        ).prefetch_related(
            'registro_planeacion__registros_almacen',
            'registro_planeacion__registros_produccion',
            'registro_planeacion__registros_tratamiento'
        )

        almacen_ok_count = 0
        produccion_ok_count = 0
        tratamiento_ok_count = 0
        total_planeaciones_activas = 0

        for dom in doms_activos:
            for rp in dom.registro_planeacion.all():
                total_planeaciones_activas += 1
                almacenes = rp.registros_almacen.all()
                producciones = rp.registros_porduccion.all()
                tratamientos = rp.registros_tratamiento.all()
            
            if almacenes.exist() and all(a.dom_realizado_planeacion for a in almacenes):
                almacen_ok_count += 1
       
            if producciones.exist() and all(p.segun_planeacion for p in producciones):
                produccion_ok_count += 1

            if tratamientos.exist() and all(t.tratamiento_segun_planeacion for t in tratamientos):
                tratamiento_ok_count += 1
            
            # Nivel 2 cumplimiento por tipo de etapa 
            cumplimiento_almacen = calcular_cumplimiento(almacen_ok_count, total_planeaciones_activas)

            cumplimiento_produccion = calcular_cumplimiento(produccion_ok_count, total_planeaciones_activas)

            cumplimiento_tratamiento = calcular_cumplimiento(tratamiento_ok_count, total_planeaciones_activas)

            # Nivel 2 - cumplimiento etapa 6 despachos
            total_doms_activos_count = doms_activos.count()
            doms_entregados_ok = doms_activos.filter(dom_entregado_ok = True).count()
            cumplimiento_despacho = calcular_cumplimiento(doms_entregados_ok, total_doms_activos_count)

            # Nivel 3 consolidado global - medición cuatro etapas

            niveles = [cumplimiento_almacen, cumplimiento_produccion, cumplimiento_tratamiento, cumplimiento_despacho]
            if all (n == 'CUMPLIÓ' for n in niveles):
                cumplimiento_consolidado = 'CUMPLIÓ'
            elif all(n == 'NO_CUMPLIÓ' for n in niveles):
                cumplimiento_consolidado = 'NO_CUMPLIÓ'
            else:
                cumplimiento_consolidado = 'PARCIAL'

        data = {
            'total_doms': total_doms,
            'total_doms_activos': total_doms_activos,
            'total_doms_cerrados': total_doms_cerrados,
            'doms_por_etapa': doms_por_etapa,
            'cantidad_elaborada_total': cantidad_elaborada_total,
            'cantidad_pendiente_total': cantidad_pendiente_total,
            'doms_proximos_vencer': DomListSerializer(doms_proximos_vencer, many=True).data,
            'doms_vencidos': DomListSerializer(doms_vencidos, many=True).data,
            'productos_pendientes_15_dias': productos_pendientes,

            # datos de cumplimiento por etapa
            'cumplimiento_almacen': cumplimiento_almacen,
            'cumplimiento_produccion': cumplimiento_produccion,
            'cumplimiento_tratamiento': cumplimiento_tratamiento,
            'cumplimiento_despacho': cumplimiento_despacho,
            'cumplimiento_consolidado': cumplimiento_consolidado,
        }

        serializer = DashboardSerializer(data)
        return Response(
            {
                'mensaje': 'Dashboard obtenido correctamente',
                'dashboard': serializer.data
            },
            status=status.HTTP_200_OK
        )

class InformeCumplimientoPlaneacion(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        fecha_inicio = request.query_params.get('fecha_inicio', None)
        fecha_fin = request.query_params.get('fecha_fin', None)

        if not fecha_inicio or not fecha_fin:
            return Response(
                {'error': 'Debe indicae fecha_inicio y fecha_fin para generar el informe'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtiene registro de planeacion en el rango de fechas 
        registros = RegistroPlaneacion.objects.filter(
            fecha_planeacion__range=[fecha_inicio, fecha_fin]
        ).select_related(
            'dom__nombre_cliente',
            'dom_producto__tipo_producto',
            'turno'
        ).prefetch_related(
            'registros_almacen',
            'registros_produccion',
            'registros_tratamiento'
        )

        total_registros = registros.count()
        registros_segun_planeacion = []
        registros_no_segun_planeacion = []

        # Contadores para cumplimiento por tipo de etapa
        almacen_ok_count = 0
        produccion_ok_count = 0
        tratamiento_ok_count = 0

        for registro in registros:
            almacenes = registro.registros_almacen.all()
            producciones = registro.registros_produccion.all()
            tratamientos = registro.registros_tratamiento.all()

            # Nivel 1 - cumplimiento individual por etapa
            almacen_ok = all(a.dom_realizado_planeacion for a in almacenes) if almacenes.exists() else False
            produccion_ok = all(p.segun_planeacion for p in producciones) if producciones.exists() else False
            tratamiento_ok = all(t.tratamiento_segun_planeacion for t in tratamientos) if tratamientos.exists() else False

            if almacen_ok:
                almacen_ok_count += 1
            if produccion_ok:
                produccion_ok_count += 1
            if tratamiento_ok:
                tratamiento_ok_count += 1
            
            # cumplimiento global del registro - True solo si las 3 etapas cumplieron 
            cumplimiento_global = almacen_ok and produccion_ok and tratamiento_ok

            # concatena novedades individuales por DOM
            novedad_almacen = ' | '.join(
                a.novedad_cumplimiento_almacen for a in almacenes if a.novedad_cumplimiento_almacen
            ) or None

            novedad_produccion = ' | '.join(
                p.novedad_cumplimiento_produccion for p in producciones if p.novedad_cumplimiento_produccion
            ) or None

            novedad_tratamiento = ' | '.join(
                t.novedad_cumplimiento_tratamiento for t in tratamientos if t.novedad_cumplimiento_tratamiento
            ) or None

            resumen = {
                'dom_id': registro.dom.dom_id,
                'nombre_cliente': registro.dom.nombre_cliente.nombre_cliente,
                'almacen_segun_planeacion': almacen_ok,
                'novedad_almacen': novedad_almacen,
                'produccion_segun_planeacion': produccion_ok,
                'novedad_produccion': novedad_produccion,
                'tratamiento_segun_planeacion': tratamiento_ok,
                'novedad_tratamiento': novedad_tratamiento,
                'cumplimiento_global_registro': cumplimiento_global,
            }

            if cumplimiento_global:
                registros_segun_planeacion.append(resumen)
            else:
                registros_no_segun_planeacion.append(resumen)

        total_segun_planeacion = len(registros_segun_planeacion)
        total_no_segun_planeacion = len(registros_no_segun_planeacion)
        porcentaje_cumplimiento = round(
            (total_segun_planeacion / total_registros * 100) if total_registros > 0 else 0, 2
        )

        # Nivel 2 - cumplimiento por tipo de etapa 
        cumplimiento_almacen = calcular_cumplimiento(almacen_ok_count, total_registros)
        cumplimiento_produccion = calcular_cumplimiento(produccion_ok_count, total_registros)
        cumplimiento_tratamiento = calcular_cumplimiento(tratamiento_ok_count, total_registros)

        # Nivel 2 cumplimiento etapa 6
        doms_evaluados = Dom.objects.filter(
            registro_planeacion__fecha_planeacion__range=[fecha_inicio, fecha_fin]
        ).distinct()
        total_doms_evaluados = doms_evaluados.count()
        doms_entregados_ok = doms_evaluados.filter(dom_entregado_ok=True).count()
        cumplimiento_despacho = calcular_cumplimiento(doms_entregados_ok, total_doms_evaluados)

        # Nivel 3 - consolidado informe - se miden las cuatro etapas (produccion, almacen, tratamiento, despachos)
        niveles = [cumplimiento_almacen, cumplimiento_produccion, cumplimiento_tratamiento, cumplimiento_despacho]
        if all(n == 'CUMPLIÓ' for n in niveles):
            cumplimiento_consolidado = 'CUMPLIÓ'
        elif all(n == 'NO_CUMPLIÓ' for n in niveles):
            cumplimiento_consolidado = 'NO_CUMPLIÓ'
        else:
            cumplimiento_consolidado = 'PARCIAL'

        data = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'total_registros_evaluados': total_registros,
            'total_segun_planeacion': total_segun_planeacion,
            'total_no_segun_planeacion': total_no_segun_planeacion,
            'porcentaje_cumplimiento': porcentaje_cumplimiento,
            # Nivel 2 - cumplimiento por tipo de etapa
            'cumplimiento_almacen': cumplimiento_almacen,
            'cumplimiento_produccion': cumplimiento_produccion,
            'cumplimiento_tratamiento': cumplimiento_tratamiento,
            'cumplimiento_despacho': cumplimiento_despacho,
            # Nivel 3 - consolidado de informe
            'cumplimiento_consolidado': cumplimiento_consolidado,
            'registros_segun_planeacion': registros_segun_planeacion,
            'registros_no_segun_planeacion': registros_no_segun_planeacion,
        }

        serializer = InformeCumplimientoPlaneacionSerializer(data)
        return Response(
            {
                'mensaje': 'Informe de cumplimiento de planeación generado correctamente',
                'informe': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
# Clase relativa al informe de despacho - logica separada dado que no es hijo de plneación, entidad independiente

class InformeDespachoView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        fecha_inicio = request.query_params.get('fecha_inicio', None)
        fecha_fin = request.query_params.get('fecha_fin', None)

        if not fecha_inicio or not fecha_fin:
            return Response(
                {'error': 'Debe indicar fecha_inicio y fecha_fin para generar el informe'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        doms = Dom.objects.filter(
            fecha_entrega_pactada__range=[fecha_inicio, fecha_fin]
        ).select_related('nombre_cliente').prefetch_related('productos')

        total_doms = doms.count()
        total_entregados_ok = doms.filter(dom_entregado_ok=True).count()
        total_no_entregados_ok = doms.filter(dom_entregado_ok=False).count()
        porcentaje_cumplimiento = round(
            (total_entregados_ok / total_doms * 100) if total_doms > 0 else 0, 2
        )

        # Contrucción del resumen por DOM 

        registros_segun_planeacion = []
        registros_segun_no_planeacion = []

        for dom in doms:
            resumen = {
                'dom_id': dom.dom_id,
                'nombre_cliente': dom.nombre_cliente.nombre_cliente,
                'almacen_segun_planeacion': dom.dom_entregado_ok,
                'novedad_almacen': dom.novedades_cumplimiento,
                'produccion_segun_planeacion': dom.dom_entregado_ok,
                'novedad_produccion': None,
                'tratamiento_segun_planeacion': dom.dom_entregado_ok,
                'novedad_tratamiento': None,
                'cumplimiento_global_registro': dom.dom_entregado_ok,
            }

            if dom.dom_entregado_ok:
                registros_segun_planeacion.append(resumen)
            else: 
                registros_segun_no_planeacion.append(resumen)

        # Nivel 2 - cumplimiento por tipo de etapa
        cumplimiento_despacho = calcular_cumplimiento(total_entregados_ok, total_doms)

        # Nivel 3 - consolidado del informe
        if cumplimiento_despacho == 'CUMPLIÓ':
            cumplimiento_consolidado = 'CUMPLIÓ'
        elif cumplimiento_despacho == 'NO_CUMPLIÓ':
            cumplimiento_consolidado = 'NO_CUMPLIÓ'
        else:
            cumplimiento_consolidado = 'PARCIAL'
        
        data = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'total_doms_evaluados': total_doms,
            'total_entregados_ok': total_entregados_ok,
            'total_no_entregados_ok': total_no_entregados_ok,
            'porcentaje_cumplimiento': porcentaje_cumplimiento,
            'cumplimiento_despacho': cumplimiento_despacho,
            'cumplimiento_consolidado': cumplimiento_consolidado,
            'registros_segun_planeacion': registros_segun_planeacion,
            'registros_no_segun_planeacion': registros_segun_no_planeacion,
        }

        serializer = InformeDespachoSerializer(data)
        return Response(
            {
                'mensaje': 'Informe de auditoría generado correctamente',
                'informe': serializer.data
            },
            status=status.HTTP_200_OK
        )

# Clases relacionadas con el manejo del reporte PDF
# Retorna toda la información consolidada de un DOM específico para generación de reporte PDF en el frontend.
# Incluye: etapas 0, 1 y 6, productos, registros de planeación con sus etapas hijo anidadas, y métricas de tiempo proyectado vs tiempo real de ejecución.
# Todos los roles autenticados.

class DomReporteView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, dom_id):
        try:
            dom = Dom.objects.select_related(
                'nombre_cliente'
            ).prefetch_related(
                'productos__tipo_producto',
                'registro_planeacion__turno',
                'registro_planeacion__dom_producto__tipo_producto',
                'registro_planeacion__registros_almacen',
                'registro_planeacion__registros_produccion__registros_tiempo',
                'registro_planeacion__registros_tratamiento',
            ).get(dom_id=dom_id)
        except Dom.DoesNotExist:
            return Response(
                {'error': 'DOM no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Calculo de tiempos a nivel DOM individual
        
        # tiempo_proyectado_total — suma de tiempo_proyectado de todos los RegistroPlaneacion
        tiempo_proyectado_total = sum(
            rp.tiempo_proyectado or 0
            for rp in dom.registro_planeacion.all()
        )

        # tiempo_real_total — suma de minutos_totales de todos los RegistroTiempoProduccion
        tiempo_real_total = RegistroTiempoProduccion.objects.filter(
            registro_produccion__registro_planeacion__dom=dom,
            estado = 'FINALIZADO'
        ).aggregate(total=Sum('minutos_totales'))['total'] or 0

        # diferencia_tiempo — tiempo real vs tiempo proyectado
        diferencia_tiempo = tiempo_real_total - tiempo_proyectado_total

        # cumplimiento tiempo
        if diferencia_tiempo < 0:
            # tiempo real < proyectado — mejor de lo esperado
            cumplimiento_tiempo = 'POSITIVO'
            # tiempo salió según lo planeado
        elif diferencia_tiempo == 0:
            # tiempo real > proyectado — tardó más de lo esperado
            cumplimiento_tiempo = 'NEUTRO'
        else:
            cumplimiento_tiempo = 'NEGATIVO'
        
        # Lógica de tres niveles de cumplimiento
        planeaciones = dom.registro_planeacion.all().prefetch_related(
            'registros_almacen',
            'registros_produccion',
            'registros_tratamiento'
        )

        total_planeaciones = planeaciones.count()
        almacen_ok_count = 0
        produccion_ok_count = 0
        tratamiento_ok_count = 0

        for rp in planeaciones:
            almacenes = rp.registros_almacen.all()
            producciones = rp.registros_produccion.all()
            tratamientos = rp.registros_tratamiento.all()

            if almacenes.exists() and all(a.dom_realizado_planeacion for a in almacenes):
                almacen_ok_count += 1
            if producciones.exists() and all (p.segun_planeacion for p in producciones):
                produccion_ok_count += 1
            if tratamientos.exists() and all(t.tratamiento_segun_planeacion for t in tratamientos):
                tratamiento_ok_count += 1
            
        # Nivel 2 - cumplimiento por tipo de etapa
        cumplimiento_almacen = calcular_cumplimiento(almacen_ok_count, total_planeaciones)
        cumplimiento_produccion = calcular_cumplimiento(produccion_ok_count, total_planeaciones)
        cumplimiento_tratamiento = calcular_cumplimiento(tratamiento_ok_count, total_planeaciones)

        # Nivel 2 - cumplimiento etapa 6 campo directo del DOM
        cumplimiento_despacho = 'CUMPLIÓ' if dom.dom_entregado_ok else 'NO_CUMPLIÓ'

        # Nivel 3 - consolidado del DOM - cuatro etapas medibles
        niveles = [cumplimiento_almacen, cumplimiento_produccion, cumplimiento_tratamiento, cumplimiento_despacho]
        if all(n == 'CUMPLIÓ' for n in niveles):
            cumplimiento_consolidado_dom = 'CUMPLIÓ'
        elif all(n == 'NO_CUMPLIÓ' for n in niveles):
            cumplimiento_consolidado_dom = 'NO_CUMPLIÓ'
        else:
            cumplimiento_consolidado_dom = 'PARCIAL'

        
        # Serializa el DOM con toda su información anidada
        serializer = DomReporteSerializer(dom)

        # Construye respuesta agregando campos calculados
        data = serializer.data
        data['tiempo_proyectado_total'] = tiempo_proyectado_total
        data['tiempo_real_total'] = tiempo_real_total
        data['diferencia_tiempo'] = diferencia_tiempo
        data['cumplimiento_tiempo'] = cumplimiento_tiempo
        data['cumplimiento_almacen'] = cumplimiento_almacen
        data['cumplimiento_produccion'] = cumplimiento_produccion
        data['cumplimiento_tratamiento'] = cumplimiento_tratamiento
        data['cumplimiento_despacho'] = cumplimiento_despacho
        data['cumplimiento_consolidado_dom'] = cumplimiento_consolidado_dom

        return Response(
            {
                'mensaje': f'Reporte del DOM #{dom_id} generado correctamente',
                'reporte': data
            },
            status=status.HTTP_200_OK
        )
    

class InformeAuditoriaView(APIView):

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):

        # Solo ADMIN puede acceder a auditorias
        if not verificar_rol(request, ['ADMIN']):
            return Response (
                {'error': 'No tienes los permisos necesarios para consultar información relacionada con auditorias'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Parametros obligatorios 
        fecha_inicio = request.query_params.get('fecha_inicio', None)
        fecha_fin = request.query_params.get('fecha_fin', None)

        if not fecha_inicio or not fecha_fin:
            return Response(
                {'error': 'Debes indicar fecha_inicio y fecha_fin para generar el informe'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Filtro base: la consulta para auditoria este es el filtro base
        acciones = AuditoriaDom.objects.filter(
            timestamp__date__range=[fecha_inicio, fecha_fin]
        ).select_related('dom', 'dom_nombre_cliente', 'usuario').order_by('-timestamp')

        # Filtro opcional por DOM especifico 
        dom_id = request.query_params.get('dom_id', None)
        if dom_id is not None:
            acciones = acciones.filter(dom__dom_id=dom_id)

        # Filtro opcional por usuario
        usuario = request.query_params.get('usuario', None)
        if usuario is not None:
            acciones = acciones.filter(usuario__username__icontains=usuario)

        # Filtro opcional por cliente 
        cliente_id = request.query_params.get('cliente_id', None)
        if cliente_id is not None:
            acciones = acciones.filter(dom__nombre_cliente__cliente_=cliente_id)
        
        # Totales por tipo de acción 
        totales = acciones.aggregate(
            total_acciones=Count('id'),
            total_creaciones=Count('id', filter=Q(accion='CREACIÓN')),
            total_ediciones=Count('id', filter=Q(accion='EDICION')),
            total_bloqueos=Count('id', filter=Q(accion='BLOQUEO_ETAPA')),
            total_eliminaciones=Count('id', filter=Q(accion='ELIMINACIÓN'))
        )

        data = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'dom_id': dom_id,
            'usuario_filtro': usuario,
            'total_acciones': totales['total_acciones'], 
            'total_creaciones': totales['total_creaciones'],
            'total_ediciones': totales['total_ediciones'],
            'total_bloqueos': totales['total_bloqueos'],
            'total_eliminaciones': totales['total_eliminaciones'],
            'acciones': AuditoriaDomSerializer(acciones, many=True)
        }

        serializer = InformeAuditoriaSerializer(data)
        return Response(
            {
                'mensaje': 'Informe de auditoria generado correctamente',
                'informe': serializer.data
            },
            status=status.HTTP_200_OK
        )
    
# FIN MÓDULO 6 - REPORTES Y DASHBOARD

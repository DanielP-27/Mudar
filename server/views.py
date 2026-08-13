from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authtoken.models import Token

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import Coalesce

from .authentication import TOKEN_EXPIRY_MINUTES
from .models import (
    Cliente,
    FamiliaProducto,
    Productos,
    Turno,
    ListaPredefinida,
    Dom,
    ProductosDom,
    RegistroPlaneacion,
    ProductoPlaneacion,
    RegistroAlmacen,
    RegistroProduccion,
    ProductoProduccion,
    RegistroTiempoProduccion,
    PausaTiempoProduccion,
    RegistroTratamiento, 
    RegistroTurnoDia,
    PerfilUsuario,
    AuditoriaDom,

)

from .serializers import (
    UserSerializer,
    PerfilUsuarioSerializer,
    ClienteSerializer,
    FamiliaProductoSerializer,             # vistas propias + anidado en ProductosSerializer
    ProductosSerializer,
    TurnoSerializer, 
    ListaPredefinidaSerializer, 
    ProductosDomSerializer,
    DomListSerializer,
    DomDetalleSerializer,
    EditarUsuarioSerializer,
    RegistroAlmacenSerializer,
    RegistroTurnoDiaSerializer,
    PausaTiempoProduccionSerializer,
    RegistroTiempoProduccionSerializer,
    RegistroProduccionSerializer,
    RegistroTratamientoSerializer,
    RegistroPlaneacionSerializer,
    ProductoPlaneacionSerializer,
    ProductoProduccionSerializer,
    AuditoriaDomSerializer,                 # viaja dentro de InformeAuditoriaSerializer
    LoginSerializer, 
    CambioPasswordSerializer,
    CrearUsuarioSerializer,
    DomReporteSerializer,
    ProductoPendienteDashBoardSerializer,   # viaja dentro de DashboardSerializer
    DashboardSerializer,
    ResumenCumplimientoEtapaSerializer,     # viaja dentro de InformeCumplimiento
    InformeCumplimientoPlaneacionSerializer, 
    InformeDespachoSerializer,
    InformeAuditoriaSerializer,             # se instancia directamente en InformeAuditoriaView
    RestablecerPasswordSerializer,
)

# El predicado de cumplimiento vive fuera de las vistas para que la regla no
# dependa de que alguien abra una pantalla.
from .cumplimiento import (
    CUMPLIO,
    NO_CUMPLIO,
    PENDIENTE,
    veredicto_despacho,
    consolidar,
)


# INICIO HELPERS - Funciones reutilizables en todas las vistas, mayor eficiencia

# ── Criterio ÚNICO de vencimiento (fechas de entrega) ─────────────────────────
# Umbrales de negocio definidos UNA sola vez para que el dashboard y ListaDoms
# usen exactamente el mismo horizonte (si cambia el número, cambia en un solo lugar).
DIAS_PROXIMO_VENCER = 7          # ventana de "próximo a vencer"
DIAS_HORIZONTE_PRODUCCION = 15   # horizonte del cuadro de productos pendientes

# Fecha de entrega EFECTIVA del DOM: la proyectada en planeación es el criterio
# principal y, en su ausencia, la solicitada por el cliente (obligatoria, nunca
# null → la fecha efectiva nunca es null). Es el criterio de vencimiento del
# sistema; lo consumen el dashboard y ListaDoms para clasificar/ordenar por urgencia.
def fecha_entrega_efectiva():
    return Coalesce('fecha_entrega_proyectada', 'fecha_solicitada_cliente')

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

# Reemplaza los mensajes por defecto de DRF por textos amigables, según el CÓDIGO
# del error (no el texto, para no depender del idioma). null/blank/required se
# unifican como "vacío", que es como el usuario percibe un campo obligatorio sin llenar.
MENSAJES_AMIGABLES = {
    'null':     'Este campo no puede quedar vacío.',
    'blank':    'Este campo no puede quedar vacío.',
    'required': 'Este campo no puede quedar vacío.',
}

def errores_con_labels(serializer):
    # Remapea las claves de serializer.errors al label del campo (verbose_name),
    # para que el usuario vea "Cliente" en vez de "nombre_cliente", y suaviza los
    # mensajes por defecto. Deja non_field_errors, claves sin label y estructuras
    # anidadas (listas de dicts) tal cual.
    resultado = {}
    for clave, valor in serializer.errors.items():
        campo = serializer.fields.get(clave)
        etiqueta = str(campo.label) if (campo is not None and campo.label) else clave
        if isinstance(valor, list):
            valor = [
                MENSAJES_AMIGABLES.get(getattr(item, 'code', None), str(item))
                if isinstance(item, str) else item
                for item in valor
            ]
        resultado[etiqueta] = valor
    return resultado

# Función helper para determinar el nivel de cumplimiento de la planeación
# Retorna:
# 'CUMPLIÓ'     — todos los registros cumplieron
# 'PARCIAL'     — algunos registros cumplieron y otros no
# 'NO_CUMPLIÓ'  — ningún registro cumplió
# 'SIN_DATOS'   — no hay registros para evaluar

def calcular_cumplimiento(registros_ok, total_registros):
    if total_registros == 0:
        return 'SIN_DATOS'
    if registros_ok == total_registros:
        return 'CUMPLIÓ'
    elif registros_ok == 0:
        return 'NO_CUMPLIÓ'
    else:
        return 'PARCIAL'

# Igual que calcular_cumplimiento pero además expone el conteo y el porcentaje,
# para que el dashboard muestre el ratio (ej. "66.7% (8 de 12)") junto a la etiqueta.
def calcular_ratio_cumplimiento(registros_ok, total_registros):
    return {
        'nivel': calcular_cumplimiento(registros_ok, total_registros),
        'ok': registros_ok,
        'total': total_registros,
        'porcentaje': round(registros_ok / total_registros * 100, 1) if total_registros else None,
    }

# ─────────────────────────────────────────────────────────────────────────────
# SALVAGUARDA DE CIERRE DE ETAPA
# Una etapa no puede bloquearse sin el dato que esa etapa debía producir. El valor
# puede ser verdadero o falso según la realidad del negocio; lo que no se admite es
# que quede sin diligenciar: el DOM se vería cerrado para todos y el número que
# alimenta los informes nunca habría existido.
# ─────────────────────────────────────────────────────────────────────────────

def valor_efectivo(instancia, datos, campo):
    """Valor que tendrá el campo DESPUÉS de aplicar el payload.

    El veredicto y el candado viajan en el mismo PUT, así que mirar solo la base
    daría 'falta el dato' justo cuando el usuario acaba de marcarlo."""
    if campo in datos:
        return datos.get(campo)
    return getattr(instancia, campo, None)


def existe_turno_dia(inst, datos):
    """El turno-día no puede crearse sin operarios ni duración, así que su
    existencia acredita los dos datos."""
    return RegistroTurnoDia.objects.filter(
        turno=valor_efectivo(inst, datos, 'turno'),
        fecha=valor_efectivo(inst, datos, 'fecha_planeacion')
    ).exists()


# etapa → (campo_candado, [(campo, etiqueta)], [(comprobación, etiqueta)])
# Las etiquetas son el texto que lee el usuario cuando se rechaza el cierre.
REQUISITOS_CIERRE = {
    'etapa_2': ('planeacion_completa',
        [('turno',            'el turno'),
         ('fecha_planeacion', 'la fecha planeada')],
        [(existe_turno_dia, 'el número de operarios'),
         (existe_turno_dia, 'la duración del turno')]),
    'etapa_3': ('materias_liberadas',
        [('dom_realizado_planeacion',
          'la respuesta sobre si las actividades de almacén se realizaron según planeación')],
        []),
    'etapa_4': ('cierre_produccion',
        [('segun_planeacion',
          'la respuesta sobre si las actividades de producción se realizaron según planeación'),
         ('numero_personas_asignadas',
          'el número de personas asignadas a la producción')],
        [(lambda inst, datos: inst.registros_tiempo.filter(estado='FINALIZADO').exists(),
          'que el cronómetro de producción esté finalizado')]),
    'etapa_5': ('tratamiento_completado',
        [('tratamiento_segun_planeacion',
          'la respuesta sobre si el tratamiento térmico se realizó según planeación')],
        []),
    'etapa_6': ('dom_liberado_cierre',
        [('dom_entregado_ok',
          'la respuesta sobre si el DOM fue entregado según planeación'),
         # Se incluye la fecha de entrega pactada como campo obligatorio para el
         # cierre de la etapa 6 porque es dato fundamental del informe de despachos.
         ('fecha_entrega_pactada',
          'la fecha de entrega pactada')],
        []),
}


def validar_cierre(instancia, datos, etapa):
    """None si se puede cerrar; el mensaje de error si falta algo.

    Ausencia es el nulo y la cadena vacía, no la falsedad: False es una
    respuesta válida —significa que no cumplió— y cero personas también sería
    un dato."""
    campo_candado, campos, comprobaciones = REQUISITOS_CIERRE[etapa]

    # Si este PUT no está intentando cerrar, no hay nada que validar
    if valor_efectivo(instancia, datos, campo_candado) is not True:
        return None

    # Un campo de fecha que el usuario borra en el navegador envía '', no null.
    faltantes = [etiqueta for campo, etiqueta in campos
                 if valor_efectivo(instancia, datos, campo) in (None, '')]
    faltantes += [etiqueta for prueba, etiqueta in comprobaciones
                  if not prueba(instancia, datos)]

    if not faltantes:
        return None

    detalle = (faltantes[0] if len(faltantes) == 1
               else ', '.join(faltantes[:-1]) + ' y ' + faltantes[-1])
    return 'No es posible cerrar esta etapa sin %s.' % detalle

# Detrás de un proxy REMOTE_ADDR es el proxy: la IP real viaja en X-Forwarded-For
def obtener_ip(request):
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# Centraliza que  la creación de registros de AuditoriaDom ante accciones relevantes (creacion, edicion, bloqueo o desbloqueo etapa, eliminación)
def registrar_auditoria(dom, usuario, accion, request, etapa=None, campos_modificados=None):

    # objects.create() no valida choices: sin esta guarda entra cualquier cadena
    if accion not in dict(AuditoriaDom.ACTION_CHOICES):
        raise ValueError('Acción de auditoría no declarada: %r' % accion)

    AuditoriaDom.objects.create(
        dom = dom,
        usuario = usuario,
        accion = accion,
        etapa = etapa,
        campos_modificados = campos_modificados,
        ip = obtener_ip(request),
        agente = (request.META.get('HTTP_USER_AGENT') or '')[:255] or None,
    )

def instantanea(objeto, request_data):
    """Valores actuales de lo que vale la pena auditar: los campos que Django guarda
    en columna, más las claves del request — de ahí salen las propiedades calculadas,
    que no son columnas. Se omiten los auto_now: cambian en cada guardado sin informar.

    Recorrer los campos del modelo (y no solo lo que mandó el cliente) es lo que hace
    que queden auditados los cambios del servidor: numero_registro, creado_por, etc."""
    nombres = {f.name for f in objeto._meta.concrete_fields
               if not getattr(f, 'auto_now', False)} | set(request_data.keys())
    return {n: getattr(objeto, n, None) for n in nombres}


def foto_inicial(objeto):
    """Estado con el que nació un registro, se guarda como foto plana. cuando una
    edición posterior lleve un campo de None a un valor, las dos filas se encadenan."""
    return {f.name: str(getattr(objeto, f.name, None))
            for f in objeto._meta.concrete_fields
            if not getattr(f, 'auto_now', False)}


def calcular_campos_modificados(campos_antes, objeto_despues):
    campos = {}
    for nombre, valor_antes in campos_antes.items():
        if nombre == 'etapa':      # clave de enrutamiento del request, no es columna
            continue
        antes = str(valor_antes)
        despues = str(getattr(objeto_despues, nombre, None))
        if antes != despues:
            campos[nombre] = {'antes': antes, 'despues': despues}
    return campos if campos else None

# Cerrar una etapa y editar su contenido son dos hechos distintos, aunque el
# frontend los mande en el mismo PUT. Antes se auditaban como una sola fila
# etiquetada BLOQUEO_ETAPA, y los campos de contenido quedaban escondidos ahí
# dentro: invisibles como edición y sin contar en total_ediciones.
def registrar_edicion_y_bloqueo(dom, usuario, etapa, campos, campo_bloqueo, bloqueada, request):
    campos = dict(campos) if campos else {}
    candado = campos.pop(campo_bloqueo, None)

    # El 'or not candado' conserva el caso "guardó sin cambiar nada", que hoy
    # se registra como una edición con campos_modificados en None.
    if campos or not candado:
        registrar_auditoria(dom, usuario, 'EDICION', request, etapa, campos or None)

    if bloqueada and candado:
        registrar_auditoria(dom, usuario, 'BLOQUEO_ETAPA', request, etapa,
                            {campo_bloqueo: candado})

# FIN HELPERS

# INICIO MODULO 1 - VISTAS DE AUTENTICACIÓN

# Modulo 1 - Autenticación de usuarios / login, logout, perfil usuario autenticado, cambio de password, reestablecer password, creacion y eliminación usuarios (lo ultimo - manteniendo registro historico)

# POST /api/auth/login/
class LoginView(APIView):
    # Autenticación y token de acceso
    # Lista vacía = no autenticar. Es obligatorio: sin ella, la vista heredaría
    # ExpiringTokenAuthentication y un token vencido en la cabecera haría fallar
    # el login con 401, impidiendo reingresar justo a quien acaba de expirar.
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
        
        # Cada ingreso emite credencial nueva: invalida la sesión anterior del
        # usuario y evita duplicar aquí el umbral de caducidad.
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)

        return Response(
            {
                'mensaje' : 'Inicio de sesión exitoso',
                'token' : token.key,
                'perfil' : perfil_data, # incluye rol, username, nombre_completo
                'expira_en_minutos' : TOKEN_EXPIRY_MINUTES,
            },
            status = status.HTTP_200_OK
        )

# POST /api/auth/logout
class LogoutView(APIView):
    # Elimina el token de usuario autenticado al momento que este cierra sesión

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

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            perfil = get_perfil(request)
            serializer = PerfilUsuarioSerializer(perfil)
            return Response (
                {
                    'mensaje' : 'Perfil obtenido correctamente',
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

    permission_classes = [IsAuthenticated]

    def post(self, request):

        # El contexto lleva la petición: el serializer necesita request.user para
        # comprobar que la contraseña nueva no se parezca a los datos del usuario.
        serializer = CambioPasswordSerializer(data=request.data, context={'request': request})

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

    permission_classes = [IsAuthenticated]

    def get(self, request, cliente_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            cliente = Cliente.objects.get(cliente_id=cliente_id)
        except Cliente.DoesNotExist:
            return Response(
                {'error': 'Cliente no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = ClienteSerializer(cliente)
        return Response(
            {
                'mensaje': 'Cliente obtenido correctamente',
                'cliente': serializer.data
            },
            status=status.HTTP_200_OK
        )

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

    def patch(self, request, cliente_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            cliente = Cliente.objects.get(cliente_id=cliente_id)
        except Cliente.DoesNotExist:
            return Response(
                {'error': 'Cliente no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        activo = request.data.get('activo')
        if activo is None:
            return Response(
                {'error': 'Debe indicar el estado activo del registro'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cliente.activo = activo
        cliente.save()

        estado_txt = 'activado' if cliente.activo else 'desactivado'
        return Response(
            {'mensaje': f'Cliente {cliente.nombre_cliente} {estado_txt} correctamente'},
            status=status.HTTP_200_OK
        )

# Catálogo No. 1b - Familias de producto
# GET lista: todos los usuarios autenticados (dropdown productos)
# POST / PUT / DELETE: solo ADMIN

class FamiliaProductoListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        familias = FamiliaProducto.objects.all()

        activo = request.query_params.get('activo', None)
        if activo is not None:
            familias = familias.filter(activo=activo.lower() == 'true')

        nombre = request.query_params.get('nombre', None)
        if nombre is not None:
            familias = familias.filter(nombre_familia__icontains=nombre)

        serializer = FamiliaProductoSerializer(familias, many=True)
        return Response(
            {
                'mensaje': 'Familias obtenidas correctamente',
                'total': familias.count(),
                'familias': serializer.data
            },
            status=status.HTTP_200_OK
        )

    def post(self, request):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tiene permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = FamiliaProductoSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos inválidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        familia = serializer.save(creado_por=request.user)

        return Response(
            {
                'mensaje': f'Familia {familia.nombre_familia} creada correctamente',
                'familia': FamiliaProductoSerializer(familia).data
            },
            status=status.HTTP_201_CREATED
        )


class FamiliaProductoDetalleView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, familia_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            familia = FamiliaProducto.objects.get(familia_id=familia_id)
        except FamiliaProducto.DoesNotExist:
            return Response(
                {'error': 'Familia no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = FamiliaProductoSerializer(familia)
        return Response(
            {
                'mensaje': 'Familia obtenida correctamente',
                'familia': serializer.data
            },
            status=status.HTTP_200_OK
        )

    def put(self, request, familia_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            familia = FamiliaProducto.objects.get(familia_id=familia_id)
        except FamiliaProducto.DoesNotExist:
            return Response(
                {'error': 'Familia no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = FamiliaProductoSerializer(familia, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos inválidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        familia = serializer.save()

        return Response(
            {
                'mensaje': f'Familia {familia.nombre_familia} actualizada correctamente',
                'familia': FamiliaProductoSerializer(familia).data
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, familia_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes los permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            familia = FamiliaProducto.objects.get(familia_id=familia_id)
        except FamiliaProducto.DoesNotExist:
            return Response(
                {'error': 'Familia no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        productos_activos = Productos.objects.filter(
            familia_producto=familia, activo=True
        ).count()
        if productos_activos > 0:
            return Response(
                {
                    'error': f'No se puede desactivar. La familia tiene {productos_activos} producto(s) activo(s) asociado(s)'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        familia.activo = False
        familia.save()

        return Response(
            {'mensaje': f'Familia {familia.nombre_familia} desactivada correctamente'},
            status=status.HTTP_200_OK
        )

    def patch(self, request, familia_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes los permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            familia = FamiliaProducto.objects.get(familia_id=familia_id)
        except FamiliaProducto.DoesNotExist:
            return Response(
                {'error': 'Familia no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        activo = request.data.get('activo')
        if activo is None:
            return Response(
                {'error': 'Debe indicar el estado activo del registro'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Al desactivar, respeta la misma regla que delete: no permitir si tiene productos activos
        if activo is False:
            productos_activos = Productos.objects.filter(
                familia_producto=familia, activo=True
            ).count()
            if productos_activos > 0:
                return Response(
                    {'error': f'No se puede desactivar. La familia tiene {productos_activos} producto(s) activo(s) asociado(s)'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        familia.activo = activo
        familia.save()

        estado_txt = 'activada' if familia.activo else 'desactivada'
        return Response(
            {'mensaje': f'Familia {familia.nombre_familia} {estado_txt} correctamente'},
            status=status.HTTP_200_OK
        )


# Catalogo No. 2 - productos
# para consulta (GET) todos los usuarios cuentan con acceso 
# creación nuevos productos (POST) solo ADMIN

class ProductoListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        activo = request.query_params.get('activo', None)
        productos = Productos.objects.all()

        if activo is not None:
            productos = productos.filter(activo = activo.lower() == 'true')
        
        # Filtro adicional para aceptar busqueda estilo typehead (autocompletado)
        nombre = request.query_params.get('nombre', None)

        if nombre is not None:
            productos = productos.filter(nombre_producto__icontains=nombre)

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
                {'error': 'No tienes los permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
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

    permission_classes = [IsAuthenticated]

    def get(self, request, producto_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            producto = Productos.objects.select_related('familia_producto').get(producto_id=producto_id)
        except Productos.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = ProductosSerializer(producto)
        return Response(
            {
                'mensaje': 'Producto obtenido correctamente',
                'producto': serializer.data
            },
            status=status.HTTP_200_OK
        )

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
                status=status.HTTP_403_FORBIDDEN            
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

    def patch(self, request, producto_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes los permisos necesarios para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            producto = Productos.objects.get(producto_id=producto_id)
        except Productos.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        activo = request.data.get('activo')
        if activo is None:
            return Response(
                {'error': 'Debe indicar el estado activo del registro'},
                status=status.HTTP_400_BAD_REQUEST
            )

        producto.activo = activo
        producto.save()

        estado_txt = 'activado' if producto.activo else 'desactivado'
        return Response(
            {'mensaje': f'Producto {producto.nombre_producto} {estado_txt} correctamente'},
            status=status.HTTP_200_OK
        )
    
# Catalogo No. 3 - turnos
# para consulta (GET) todos los usuarios cuentan con acceso 
# creación nuevos turnos (POST) solo ADMIN

class TurnoListView(APIView):

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

    permission_classes = [IsAuthenticated]

    def get(self, request, turno_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
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
        serializer = TurnoSerializer(turno)
        return Response(
            {
                'mensaje': 'Turno obtenido correctamente',
                'turno': serializer.data
            },
            status=status.HTTP_200_OK
        )

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

    def patch(self, request, turno_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
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

        activo = request.data.get('activo')
        if activo is None:
            return Response(
                {'error': 'Debe indicar el estado activo del registro'},
                status=status.HTTP_400_BAD_REQUEST
            )

        turno.activo = activo
        turno.save()

        estado_txt = 'activado' if turno.activo else 'desactivado'
        return Response(
            {'mensaje': f'Turno {turno.nombre_turno} {estado_txt} correctamente'},
            status=status.HTTP_200_OK
        )
    
# Catalogo No. 4 - listas predefinidas
# para consulta (GET) todos los usuarios cuentan con acceso 
# creación de nuevos registros dentro de un listado (POST) solo ADMIN

class ListaPredefinidaListView(APIView):
    
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

    permission_classes = [IsAuthenticated]

    def get(self, request, lista_id):
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            lista = ListaPredefinida.objects.get(lista_id=lista_id)
        except ListaPredefinida.DoesNotExist:
            return Response(
                {'error': 'Lista no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = ListaPredefinidaSerializer(lista)
        return Response(
            {
                'mensaje': 'Lista obtenida correctamente',
                'lista': serializer.data
            },
            status=status.HTTP_200_OK
        )

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

# Opciones de vencimiento del selector "DOMs a mostrar" → nivel_urgencia que filtran.
# Las demas opciones ('activos', 'cerrados', 'todos') solo tocan el cierre.
MOSTRAR_URGENCIA = {
    'vencidos':  0,
    'proximos':  1,
    'a_tiempo':  2,
}


class DomListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Fecha de entrega efectiva anotada de entrada: la usan el filtro de rango,
        # el nivel de urgencia y el orden por fecha (criterio único de vencimiento).
        doms = Dom.objects.select_related('nombre_cliente').prefetch_related(
            'productos'
        ).annotate(fecha_criterio=fecha_entrega_efectiva())

        # Filtros existentes
        cliente_id = request.query_params.get('cliente', None)
        if cliente_id is not None:
            doms = doms.filter(nombre_cliente__cliente_id=cliente_id)

        estado = request.query_params.get('estado', None)
        if estado is not None:
            doms = doms.filter(tipo_estado_dom__iexact=estado)

        # Filtro por número de DOM (dom_id) — coincidencia exacta.
        # Valor no numérico → queryset vacío (no existe un DOM con ese número).
        numero_dom = request.query_params.get('numero_dom', None)
        if numero_dom:
            try:
                doms = doms.filter(dom_id=int(numero_dom))
            except (ValueError, TypeError):
                doms = doms.none()

        # Filtros nuevos
        responsable = request.query_params.get('responsable', None)
        if responsable is not None:
            doms = doms.filter(responsable__icontains=responsable)

        # ── DOMs a mostrar (selector unico del listado) ──────────────────
        # Cruza dos dimensiones en un solo parametro: el cierre (etapa 6) y el
        # vencimiento. Las opciones de vencimiento hablan SOLO de DOMs abiertos:
        # un DOM cerrado no tiene vencimiento, su reloj se detuvo al cerrarse.
        # El filtro por urgencia NO puede ir aqui — 'nivel_urgencia' aun no existe;
        # se aplica mas abajo, despues del annotate que lo crea.
        mostrar = request.query_params.get('mostrar', 'activos').lower()

        if mostrar == 'cerrados':
            doms = doms.filter(dom_liberado_cierre=True)
        elif mostrar != 'todos':
            # 'activos' + las tres de vencimiento + cualquier valor no reconocido
            doms = doms.filter(dom_liberado_cierre=False)

        fecha_inicio = request.query_params.get('fecha_inicio', None)
        if fecha_inicio is not None:
            doms = doms.filter(fecha_criterio__gte=fecha_inicio)

        fecha_fin = request.query_params.get('fecha_fin', None)
        if fecha_fin is not None:
            doms = doms.filter(fecha_criterio__lte=fecha_fin)

        fecha_planeacion = request.query_params.get('fecha_planeacion', None)
        if fecha_planeacion is not None:
            doms = doms.filter(
                registro_planeacion__fecha_planeacion=fecha_planeacion
            ).distinct()

        # ── Nivel de urgencia (criterio primario, SIEMPRE) ──────────────
        # 0 vencido · 1 próximo a vencer (≤ DIAS_PROXIMO_VENCER días) · 2 activo.
        # La fecha de entrega efectiva nunca es null (solicitada es obligatoria),
        # por eso no existe estado "sin fecha".
        hoy = timezone.localdate()
        limite_proximo = hoy + timedelta(days=DIAS_PROXIMO_VENCER)
        doms = doms.annotate(
            nivel_urgencia=Case(
                When(fecha_criterio__lt=hoy, then=0),
                When(fecha_criterio__lte=limite_proximo, then=1),
                default=2,
                output_field=IntegerField()
            )
        )

        # Corte por vencimiento del selector "DOMs a mostrar". Va aqui a la fuerza:
        # 'nivel_urgencia' es una anotacion, no una columna, y solo se puede filtrar
        # despues de que el annotate de arriba la registre en el queryset.
        if mostrar in MOSTRAR_URGENCIA:
            doms = doms.filter(nivel_urgencia=MOSTRAR_URGENCIA[mostrar])

        # ── Orden manual (lista blanca de campos permitidos) ──
        CAMPOS_ORDEN = {
            'fecha_entrega': 'fecha_criterio',
            'cliente':       'nombre_cliente__nombre_cliente',
            'dom':           'dom_id',
        }
        orden_param = request.query_params.get('orden') or 'fecha_entrega'
        if orden_param not in CAMPOS_ORDEN:
            orden_param = 'fecha_entrega'
        campo = CAMPOS_ORDEN[orden_param]
        if request.query_params.get('direccion') == 'desc':
            campo = '-' + campo

        # nivel_urgencia (vencidos primero) agrupa SOLO en el orden por fecha de
        # entrega, que es el criterio de negocio por defecto. Para 'cliente' y 'dom'
        # el orden es global y directo, sin agrupar por urgencia. dom_id como
        # desempate garantiza una paginación estable.
        if orden_param == 'fecha_entrega':
            doms = doms.order_by('nivel_urgencia', campo, 'dom_id')
        else:
            doms = doms.order_by(campo, 'dom_id')

        # Paginación
        total = doms.count()

        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        except (ValueError, TypeError):
            page_size = 20

        total_pages = max(1, -(-total // page_size))
        page = min(page, total_pages)
        offset = (page - 1) * page_size

        doms_page = doms[offset:offset + page_size]
        serializer = DomListSerializer(doms_page, many=True)

        return Response(
            {
                'mensaje': 'DOMs obtenidos correctamente',
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
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
        tipo_estado_dom = request.data.get('tipo_estado_dom', '')
        TIPOS_SIN_PRODUCTOS = ['ADP', 'Documentos']

        productos_data = request.data.get('productos', [])
        # ADP y Documentos son tipos administrativos que no requieren productos de fabricación
        if tipo_estado_dom not in TIPOS_SIN_PRODUCTOS and not productos_data:
            return Response(
                {'error': 'El nuevo registro DOM debe contener al menos un producto'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = DomDetalleSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': errores_con_labels(serializer)
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
                dom: Dom = serializer.save(creado_por=request.user, dom_relacionado_produccion=False)

                # save() devuelve el objeto creado; se conserva para auditarlo abajo
                productos_creados = []
                for producto_serializer in productos_serializers:
                    productos_creados.append(producto_serializer.save(productoDom=dom))

                # Registro de auditoría de creación. El DOM y cada uno de sus
                # productos son hechos distintos, así que cada uno deja su fila.
                registrar_auditoria(
                    dom=dom,
                    usuario=request.user,
                    accion='CREACION',
                    etapa='etapa_0',
                    campos_modificados=foto_inicial(dom),
                    request=request,
                )

                for producto in productos_creados:
                    registrar_auditoria(
                        dom=dom,
                        usuario=request.user,
                        accion='CREACION',
                        etapa='etapa_0',
                        campos_modificados=foto_inicial(producto),
                        request=request,
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

# Propiedad de cada campo editable del modelo Dom por etapa.
# Fuente de verdad: agrupación por etapa del DomDetalleSerializer.
# Solo campos ESCRIBIBLES; se excluyen PK, auto_now/auto_now_add,
# auditoría y calculados (nunca se escriben vía API).
CAMPOS_POR_ETAPA = {
    'etapa_0': [
        'nombre_cliente', 'descripcion', 'tipo_estado_dom',
        'fecha_solicitada_cliente', 'responsable',
    ],
    'etapa_1': [
        'orden_compra', 'tiempo_salida_almacen', 'rentabilidad',
        'campana_venta', 'numero_cotizacion', 'numero_factura',
        'dom_relacionado_produccion',        # bloqueo etapa 1
    ],
    'etapa_2': [
        'fecha_entrega_proyectada',          # movido desde etapa_6
    ],
    'etapa_6': [
        'fecha_entrega_pactada', 'fecha_entrega_planificada',
        'cantidad_empaques', 'empaque_servicio', 'tipo_negociacion',
        'materiales_externos', 'vehiculo', 'orden_entrega',
        'notas', 'novedades_cumplimiento', 'dom_entregado_ok',
        'dom_liberado_cierre',               # bloqueo etapa 6
    ],
}

class DomDetalleView(APIView):

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

        # Solo se bloquea si tipo_estado_dom REALMENTE cambia. El frontend envía el objeto
        # DOM completo en cada guardado (incluye tipo_estado_dom sin modificar), por lo que
        # verificar solo la presencia bloqueaba erróneamente a roles como PLANEADOR al editar
        # otras etapas (ej. fecha_entrega_proyectada en etapa_2, que sí pega contra este PUT).
        if 'tipo_estado_dom' in request.data and request.data.get('tipo_estado_dom') != dom.tipo_estado_dom:
            if not verificar_rol(request, ['ADMIN', 'ANALISTA_1', 'ANALISTA_2']):
                return Response(
                    {'error': 'No tienes permisos para cambiar el estado del DOM'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # ADP y Documentos son tipos administrativos; no pueden mezclarse con tipos productivos
        TIPOS_SIN_PRODUCTOS = ['ADP', 'Documentos']
        tipo_actual = dom.tipo_estado_dom
        tipo_nuevo = request.data.get('tipo_estado_dom', tipo_actual)

        if tipo_actual != tipo_nuevo:
            if tipo_actual in TIPOS_SIN_PRODUCTOS or tipo_nuevo in TIPOS_SIN_PRODUCTOS:
                return Response(
                    {'error': 'No es posible cambiar el tipo de DOM entre administrativo y productivo'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Verifica bloqueo de etapa antes de aplicar cambios.
        # etapa_1 se bloquea con dom_relacionado_produccion=True (reactivado 2026-07-06,
        # cableado por el modal de confirmación del frontend).
        # Cada etapa con candado guarda su verificador y el nombre del campo que lo
        # representa. El nombre lo necesita la auditoría más abajo para separar el
        # cierre de etapa de la edición de contenido.
        bloqueos = {
            'etapa_1': (dom.etapa_1_bloqueada, 'dom_relacionado_produccion'),
            'etapa_6': (dom.etapa_6_bloqueada, 'dom_liberado_cierre'),
        }
        # El valor por defecto permite desempacar sin comprobar antes si la etapa
        # tiene candado: la etapa_0 (comercial) no lo tiene.
        verificar_bloqueo, campo_bloqueo = bloqueos.get(etapa, (None, None))

        if verificar_bloqueo and verificar_bloqueo():
            return Response(
                {'error': f'La {etapa} de esta DOM está bloqueada y no puede ser modificada, contacte con el Administrador del sistema'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # No se puede cerrar la etapa sin el veredicto que esta etapa produce.
        # Este endpoint atiende las etapas 0, 1, 2 y 6. Los requisitos de la 2 son
        # del registro de planeación, no del DOM: los valida su propio endpoint.
        if etapa == 'etapa_6':
            error_cierre = validar_cierre(dom, request.data, etapa)
            if error_cierre:
                return Response({'error': error_cierre}, status=status.HTTP_400_BAD_REQUEST)

        # Filtrado por etapa: se conservan solo los campos que pertenecen a la
        # etapa declarada. El frontend envía el objeto completo del DOM en cada
        # guardado; esto evita que un guardado escriba campos de otra etapa.
        campos_validos = CAMPOS_POR_ETAPA.get(etapa, [])
        datos_filtrados = {k: v for k, v in request.data.items() if k in campos_validos}

        serializer = DomDetalleSerializer(dom, data=datos_filtrados, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campos_antes = instantanea(dom, datos_filtrados)

        dom = serializer.save()

        # Registros de auditoria, primero se verifica que la etapa no esté bloqueada 
        registrar_edicion_y_bloqueo(
            dom=dom,
            usuario=request.user,
            etapa=etapa,
            campos=calcular_campos_modificados(campos_antes, dom),
            campo_bloqueo=campo_bloqueo,
            bloqueada=bool(verificar_bloqueo and verificar_bloqueo()),
            request=request,
        )

        return Response(
            {
                'mensaje': f'DOM #{dom.dom_id} actualizado correctamente',
                'dom': DomDetalleSerializer(dom).data
            },
            status=status.HTTP_200_OK
        )
        
# FIN MODULO 3 - DOMs


# ─────────────────────────────────────────────────────────────────────────────
# DESBLOQUEO DE ETAPAS (exclusivo ADMIN)
# Reabre una etapa bloqueada para corregirla: baja a False el booleano de bloqueo
# del registro indicado y deja rastro en auditoría.
# ─────────────────────────────────────────────────────────────────────────────

# tipo → (Modelo, campo_lock, etiqueta_etapa, nombre_legible, cómo llegar al DOM para auditar)
# etiqueta_etapa es la clave técnica que se guarda en auditoría; nombre_legible es
# el único texto que ve el usuario (no exponer 'etapa_2' en mensajes).
MAPA_DESBLOQUEO = {
    'planeacion':  (RegistroPlaneacion,  'planeacion_completa',        'etapa_2', 'Planeación',                  lambda inst: inst.dom),
    'almacen':     (RegistroAlmacen,     'materias_liberadas',         'etapa_3', 'Almacén',                     lambda inst: inst.registro_planeacion.dom),
    'produccion':  (RegistroProduccion,  'cierre_produccion',          'etapa_4', 'Producción',                  lambda inst: inst.registro_planeacion.dom),
    'tratamiento': (RegistroTratamiento, 'tratamiento_completado',     'etapa_5', 'Tratamiento',                 lambda inst: inst.registro_planeacion.dom),
    'despacho':    (Dom,                 'dom_liberado_cierre',        'etapa_6', 'Despacho',                    lambda inst: inst),
    'dom_etapa1':  (Dom,                 'dom_relacionado_produccion', 'etapa_1', 'Gestión comercial y diseño',  lambda inst: inst),
}


class DesbloqueoEtapaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Solo el ADMIN puede desbloquear
        if not verificar_rol(request, ['ADMIN']):
            return Response(
                {'error': 'No tiene permisos para desbloquear etapas'},
                status=status.HTTP_403_FORBIDDEN
            )

        tipo = request.data.get('tipo')
        registro_id = request.data.get('registro_id')

        if tipo not in MAPA_DESBLOQUEO or registro_id is None:
            return Response(
                {'error': 'Debe indicar un tipo de etapa válido y el registro_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        Modelo, campo, etiqueta, nombre, obtener_dom = MAPA_DESBLOQUEO[tipo]

        # ValueError/TypeError: registro_id no convertible a entero (ej. "abc"); la
        # conversión falla antes de consultar, así que nunca se lanza DoesNotExist.
        try:
            instancia = Modelo.objects.get(pk=registro_id)
        except (Modelo.DoesNotExist, ValueError, TypeError):
            return Response(
                {'error': 'El registro indicado no existe'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Idempotencia: si ya estaba abierto, no hay nada que hacer
        if getattr(instancia, campo) is False:
            return Response(
                {'mensaje': f'La etapa de {nombre} no está bloqueada.'},
                status=status.HTTP_200_OK
            )

        # Desbloqueo: baja el candado y persiste solo ese campo
        setattr(instancia, campo, False)
        instancia.save(update_fields=[campo])

        # Auditoría
        dom = obtener_dom(instancia)
        registrar_auditoria(
            dom=dom,
            usuario=request.user,
            accion='DESBLOQUEO_ETAPA',
            etapa=etiqueta,
            campos_modificados={campo: {'antes': 'True', 'despues': 'False'}},
            request=request,
        )

        return Response(
            {'mensaje': f'La etapa de {nombre} del DOM #{dom.dom_id} quedó desbloqueada y puede editarse nuevamente.'},
            status=status.HTTP_200_OK
        )


# INICIO MODULO 4 - ETAPAS 2, 3, 4, 5

# Ante necesidad de diseño de producto (1 registro planeación puede tener +N etapas 2 a 5 el manejo de estas se hace por fuera de DOMListView y DomDetalleView
# Permisos:
#   GET:               todos los roles autenticados
#   Etapa 2:           ADMIN, PLANEADOR
#   Etapas 3, 4, 5:    ADMIN, LIDER_PLANTA
        
# Etapa 2 - Planeación 

class RegistroPlaneacionListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        registros = RegistroPlaneacion.objects.select_related(
            'dom', 'turno'
        ).prefetch_related(
            'productos_planeacion__dom_producto__tipo_producto'
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

        # El DOM se pasa por contexto para que RegistroPlaneacionSerializer.validate()
        # pueda comparar fecha_planeacion contra dom.fecha_entrega_pactada en creación
        # (en creación el registro aún no existe, así que validate() no puede tomarlo de la instancia).
        serializer = RegistroPlaneacionSerializer(data=request.data, context={'dom': dom})

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
            etapa='etapa_2',
            campos_modificados=foto_inicial(registro),
            request=request,
        )

        # Refresca el objeto con relaciones cargadas
        registro = RegistroPlaneacion.objects.select_related(
            'dom', 'turno'
        ).prefetch_related(
            'productos_planeacion__dom_producto__tipo_producto'
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

    permission_classes = [IsAuthenticated]

    def get(self, request, registro_id):
        try:
            registro = RegistroPlaneacion.objects.select_related(
                'dom', 'turno'
            ).prefetch_related(
                'productos_planeacion__dom_producto__tipo_producto'
            ).get(id=registro_id)
        except RegistroPlaneacion.DoesNotExist:
            return Response(
                {'error': 'Registro de planeación no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RegistroPlaneacionSerializer(registro)
        return Response(
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
        
        # Verificación de bloqueo de etapa — debe ocurrir antes de cualquier escritura (incl. RegistroTurnoDia)
        if registro.etapa2_bloqueada():
            return Response(
                {'error': 'Este registro de planeación ya ha sido bloqueado para edición, contacte al Administrador del sistema'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Valida capacidad si cambia turno o fecha_planeacion
        turno_nuevo = request.data.get('turno', None)
        fecha_nueva = request.data.get('fecha_planeacion', None)
        if turno_nuevo or fecha_nueva:
            turno_eval = turno_nuevo or (registro.turno.turno_id if registro.turno else None)
            fecha_eval  = fecha_nueva or registro.fecha_planeacion
            if turno_eval and fecha_eval:
                try:
                    turno_obj = Turno.objects.get(turno_id=turno_eval)
                except Turno.DoesNotExist:
                    return Response(
                        {'error': 'Turno no encontrado'},
                        status=status.HTTP_404_NOT_FOUND
                    )

                # Si es la primera vez que se usa este turno y fecha, crea el RegistroTurnoDia con los datos enviados
                registro_turno_dia = RegistroTurnoDia.objects.filter(
                    turno=turno_obj,
                    fecha=fecha_eval
                ).first()
                if registro_turno_dia is None:
                    numero_operarios = request.data.get('numero_operarios', None)
                    minutos_totales  = request.data.get('minutos_totales', None)
                    if not numero_operarios or not minutos_totales:
                        return Response(
                            {'error': 'Es el primer registro para este turno y fecha. Indique el número de operarios y la duración del turno.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    RegistroTurnoDia.objects.create(
                        turno=turno_obj,
                        fecha=fecha_eval,
                        numero_operarios=numero_operarios,
                        minutos_totales=minutos_totales,
                        registrado_por=request.user
                    )

                planeacion_temp = RegistroPlaneacion(turno=turno_obj, fecha_planeacion=fecha_eval)
                tiempo_total = sum(
                    pp.cantidad_proyectada * pp.tiempo_unitario_efectivo
                    for pp in registro.productos_planeacion.select_related('dom_producto__tipo_producto').all()
                    if pp.cantidad_proyectada and pp.dom_producto
                )
                disponible_actual, resultado = planeacion_temp.tiempo_disponible_turno(
                    tiempo_total, excluir_registro_id=registro.id
                )
                if resultado is not None and resultado < 0:
                    return Response(
                        {
                            'error': 'El turno no tiene capacidad suficiente para esta modificación.',
                            'tiempo_disponible': disponible_actual,
                            'tiempo_requerido': tiempo_total
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

        # Verificación de bloqueo de etapa
        if registro.etapa2_bloqueada():
            return Response(
                {'error': 'Este registro de planeación ya ha sido bloqueado para edición, contacte al Administrador del sistema'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # No se puede cerrar la etapa sin el dato que esta etapa produce
        error_cierre = validar_cierre(registro, request.data, 'etapa_2')
        if error_cierre:
            return Response({'error': error_cierre}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RegistroPlaneacionSerializer(registro, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campos_antes = instantanea(registro, request.data)

        registro = serializer.save()

        registrar_edicion_y_bloqueo(
            dom=registro.dom,
            usuario=request.user,
            etapa='etapa_2',
            campos=calcular_campos_modificados(campos_antes, registro),
            campo_bloqueo='planeacion_completa',
            bloqueada=registro.etapa2_bloqueada(),
            request=request,
        )
        
        # Refresca el objeto con relaciones cargadas
        registro = RegistroPlaneacion.objects.select_related(
            'dom', 'turno'
        ).prefetch_related(
            'productos_planeacion__dom_producto__tipo_producto'
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


# ── Endpoints ProductoPlaneacion ──────────────────────────────────────────────

class ProductoPlaneacionListView(APIView):
    permission_classes     = [IsAuthenticated]

    def post(self, request):
        if not verificar_rol(request, ['ADMIN', 'PLANEADOR']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        planeacion_id = request.data.get('registro_planeacion')
        if not planeacion_id:
            return Response(
                {'error': 'Debe indicar el registro de planeación'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            planeacion = RegistroPlaneacion.objects.get(id=planeacion_id)
        except RegistroPlaneacion.DoesNotExist:
            return Response(
                {'error': 'Registro de planeación no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        if planeacion.etapa2_bloqueada():
            return Response(
                {'error': 'La planeación está bloqueada y no permite modificaciones'},
                status=status.HTTP_400_BAD_REQUEST
            )

        dom_producto_id = request.data.get('dom_producto')
        cantidad_proyectada_nueva = request.data.get('cantidad_proyectada')

        if dom_producto_id and cantidad_proyectada_nueva is not None:
            try:
                dom_producto = ProductosDom.objects.get(id=dom_producto_id)
            except ProductosDom.DoesNotExist:
                return Response(
                    {'error': 'Producto del DOM no encontrado'},
                    status=status.HTTP_404_NOT_FOUND
                )

            ya_proyectado = ProductoPlaneacion.objects.filter(
                dom_producto=dom_producto,
                registro_planeacion__dom=planeacion.dom
            ).aggregate(total=Sum('cantidad_proyectada'))['total'] or 0

            if ya_proyectado + cantidad_proyectada_nueva > dom_producto.cantidad_pedido:
                return Response(
                    {
                        'error': 'La cantidad proyectada supera la cantidad pedida del producto',
                        'cantidad_pedida': dom_producto.cantidad_pedido,
                        'cantidad_ya_proyectada': ya_proyectado,
                        'cantidad_solicitada': cantidad_proyectada_nueva,
                        'disponible': dom_producto.cantidad_pedido - ya_proyectado
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Valida capacidad del turno: la nueva cantidad no puede dejar tiempo_restante_dia negativo
            tiempo_nuevo_producto = cantidad_proyectada_nueva * dom_producto.tipo_producto.tiempo_produccion_unitario
            tiempo_otros_productos = sum(
                pp.cantidad_proyectada * pp.tiempo_unitario_efectivo
                for pp in planeacion.productos_planeacion.select_related('dom_producto__tipo_producto').all()
                if pp.cantidad_proyectada and pp.dom_producto
            )
            disponible_actual, resultado = planeacion.tiempo_disponible_turno(
                tiempo_otros_productos + tiempo_nuevo_producto, excluir_registro_id=planeacion.id
            )
            if resultado is None:
                return Response(
                    {'error': 'Debe registrar el turno del día (número de operarios y '
                              'duración) para esta fecha antes de asignar cantidades a la planeación.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if resultado < 0:
                return Response(
                    {
                        'error': 'El turno no tiene capacidad suficiente para esta cantidad.',
                        'tiempo_disponible': disponible_actual,
                        'tiempo_requerido': tiempo_otros_productos + tiempo_nuevo_producto
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = ProductoPlaneacionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'detalle': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        producto_planeacion = serializer.save(registro_planeacion=planeacion)

        registrar_auditoria(
            dom=planeacion.dom,
            usuario=request.user,
            accion='CREACION',
            etapa='etapa_2',
            campos_modificados=foto_inicial(producto_planeacion),
            request=request,
        )

        return Response(
            {
                'mensaje': 'Producto agregado a la planeación correctamente',
                'producto': ProductoPlaneacionSerializer(producto_planeacion).data
            },
            status=status.HTTP_201_CREATED
        )


class ProductoPlaneacionDetalleView(APIView):
    permission_classes     = [IsAuthenticated]

    def put(self, request, producto_id):
        if not verificar_rol(request, ['ADMIN', 'PLANEADOR']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            producto = ProductoPlaneacion.objects.select_related(
                'registro_planeacion', 'dom_producto__tipo_producto'
            ).get(id=producto_id)
        except ProductoPlaneacion.DoesNotExist:
            return Response(
                {'error': 'Producto de planeación no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        if producto.registro_planeacion.etapa2_bloqueada():
            return Response(
                {'error': 'La planeación está bloqueada y no permite modificaciones'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cantidad_proyectada_nueva = request.data.get('cantidad_proyectada')
        if cantidad_proyectada_nueva is not None:
            ya_proyectado = ProductoPlaneacion.objects.filter(
                dom_producto=producto.dom_producto,
                registro_planeacion__dom=producto.registro_planeacion.dom
            ).exclude(id=producto_id).aggregate(total=Sum('cantidad_proyectada'))['total'] or 0

            if ya_proyectado + cantidad_proyectada_nueva > producto.dom_producto.cantidad_pedido:
                return Response(
                    {
                        'error': 'La cantidad proyectada supera la cantidad pedida del producto',
                        'cantidad_pedida': producto.dom_producto.cantidad_pedido,
                        'cantidad_ya_proyectada': ya_proyectado,
                        'cantidad_solicitada': cantidad_proyectada_nueva,
                        'disponible': producto.dom_producto.cantidad_pedido - ya_proyectado
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Valida capacidad del turno: la nueva cantidad no puede dejar tiempo_restante_dia negativo
            registro_planeacion = producto.registro_planeacion
            tiempo_nuevo_producto = cantidad_proyectada_nueva * producto.tiempo_unitario_efectivo
            tiempo_otros_productos = sum(
                pp.cantidad_proyectada * pp.tiempo_unitario_efectivo
                for pp in registro_planeacion.productos_planeacion.select_related('dom_producto__tipo_producto').exclude(id=producto_id)
                if pp.cantidad_proyectada and pp.dom_producto
            )
            disponible_actual, resultado = registro_planeacion.tiempo_disponible_turno(
                tiempo_otros_productos + tiempo_nuevo_producto, excluir_registro_id=registro_planeacion.id
            )
            if resultado is None:
                return Response(
                    {'error': 'Debe registrar el turno del día (número de operarios y '
                              'duración) para esta fecha antes de asignar cantidades a la planeación.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if resultado < 0:
                return Response(
                    {
                        'error': 'El turno no tiene capacidad suficiente para esta cantidad.',
                        'tiempo_disponible': disponible_actual,
                        'tiempo_requerido': tiempo_otros_productos + tiempo_nuevo_producto
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = ProductoPlaneacionSerializer(producto, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'detalle': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        campos_antes = instantanea(producto, request.data)

        producto = serializer.save()

        registrar_auditoria(
            dom=producto.registro_planeacion.dom,
            usuario=request.user,
            accion='EDICION',
            etapa='etapa_2',
            campos_modificados=calcular_campos_modificados(campos_antes, producto),
            request=request,
        )

        return Response(
            {
                'mensaje': 'Producto de planeación actualizado correctamente',
                'producto': ProductoPlaneacionSerializer(producto).data
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, producto_id):
        if not verificar_rol(request, ['ADMIN', 'PLANEADOR']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            producto = ProductoPlaneacion.objects.select_related(
                'registro_planeacion'
            ).get(id=producto_id)
        except ProductoPlaneacion.DoesNotExist:
            return Response(
                {'error': 'Producto de planeación no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        if producto.registro_planeacion.etapa2_bloqueada():
            return Response(
                {'error': 'La planeación está bloqueada y no permite modificaciones'},
                status=status.HTTP_400_BAD_REQUEST
            )

        dom = producto.registro_planeacion.dom

        producto.delete()

        registrar_auditoria(
            dom=dom,
            usuario=request.user,
            accion='ELIMINACION',
            etapa='etapa_2',
            campos_modificados={'dom_producto_id': str(producto.dom_producto.id)},
            request=request,
        )

        return Response(
            {'mensaje': 'Producto eliminado de la planeación correctamente'},
            status=status.HTTP_200_OK
        )


# ── Endpoint ProductoProduccion ───────────────────────────────────────────────

class ProductoProduccionListView(APIView):
    permission_classes     = [IsAuthenticated]

    def post(self, request):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        registro_produccion_id = request.data.get('registro_produccion')
        producto_planeacion_id = request.data.get('producto_planeacion')

        if not registro_produccion_id or not producto_planeacion_id:
            return Response(
                {'error': 'Debe indicar registro_produccion y producto_planeacion'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            registro = RegistroProduccion.objects.get(id=registro_produccion_id)
        except RegistroProduccion.DoesNotExist:
            return Response(
                {'error': 'Registro de producción no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        if registro.etapa_4_bloqueada():
            return Response(
                {'error': 'El registro de producción está bloqueado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            pp = ProductoPlaneacion.objects.get(id=producto_planeacion_id)
        except ProductoPlaneacion.DoesNotExist:
            return Response(
                {'error': 'Producto de planeación no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        cantidad_elaborada_nueva = request.data.get('cantidad_elaborada')
        if cantidad_elaborada_nueva is not None:
            disponible = registro.registro_planeacion.cantidad_disponible_produccion(
                pp,
                int(cantidad_elaborada_nueva)
            )
            if disponible < 0:
                return Response(
                    {
                        'error': 'La cantidad elaborada supera la cantidad proyectada del producto',
                        'cantidad_proyectada': pp.cantidad_proyectada,
                        'cantidad_ya_elaborada': pp.cantidad_elaborada,
                        'cantidad_solicitada': int(cantidad_elaborada_nueva),
                        'disponible': max(0, pp.cantidad_proyectada - pp.cantidad_elaborada)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = ProductoProduccionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'detalle': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        producto = serializer.save(registrado_por=request.user)

        registrar_auditoria(
            dom=registro.registro_planeacion.dom,
            usuario=request.user,
            accion='CREACION',
            etapa='etapa_4',
            campos_modificados=foto_inicial(producto),
            request=request,
        )

        return Response(
            {
                'mensaje': 'Cantidad elaborada registrada correctamente',
                'producto': ProductoProduccionSerializer(producto).data
            },
            status=status.HTTP_201_CREATED
        )


class ProductoProduccionDetalleView(APIView):
    permission_classes     = [IsAuthenticated]

    def put(self, request, producto_id):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            producto = ProductoProduccion.objects.select_related(
                'registro_produccion__registro_planeacion',
                'producto_planeacion'
            ).get(id=producto_id)
        except ProductoProduccion.DoesNotExist:
            return Response(
                {'error': 'Producto de producción no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        if producto.registro_produccion.etapa_4_bloqueada():
            return Response(
                {'error': 'El registro de producción está bloqueado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cantidad_elaborada_nueva = request.data.get('cantidad_elaborada')
        if cantidad_elaborada_nueva is not None:
            disponible = producto.registro_produccion.registro_planeacion.cantidad_disponible_produccion(
                producto.producto_planeacion,
                int(cantidad_elaborada_nueva),
                excluir_producto_produccion_id=producto_id
            )
            if disponible < 0:
                return Response(
                    {
                        'error': 'La cantidad elaborada supera la cantidad proyectada del producto',
                        'cantidad_proyectada': producto.producto_planeacion.cantidad_proyectada,
                        'cantidad_ya_elaborada': producto.producto_planeacion.cantidad_elaborada - producto.cantidad_elaborada,
                        'cantidad_solicitada': int(cantidad_elaborada_nueva),
                        'disponible': max(0, producto.producto_planeacion.cantidad_proyectada - (producto.producto_planeacion.cantidad_elaborada - producto.cantidad_elaborada))
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = ProductoProduccionSerializer(producto, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'detalle': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        campos_antes = instantanea(producto, request.data)

        producto = serializer.save()

        registrar_auditoria(
            dom=producto.registro_produccion.registro_planeacion.dom,
            usuario=request.user,
            accion='EDICION',
            etapa='etapa_4',
            campos_modificados=calcular_campos_modificados(campos_antes, producto),
            request=request,
        )

        return Response(
            {
                'mensaje': 'Cantidad elaborada actualizada correctamente',
                'producto': ProductoProduccionSerializer(producto).data
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, producto_id):
        if not verificar_rol(request, ['ADMIN', 'LIDER_PLANTA']):
            return Response(
                {'error': 'No tienes permisos para realizar esta acción'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            producto = ProductoProduccion.objects.select_related(
                'registro_produccion__registro_planeacion'
            ).get(id=producto_id)
        except ProductoProduccion.DoesNotExist:
            return Response(
                {'error': 'Producto de producción no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        if producto.registro_produccion.etapa_4_bloqueada():
            return Response(
                {'error': 'El registro de producción está bloqueado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        dom = producto.registro_produccion.registro_planeacion.dom

        producto.delete()

        registrar_auditoria(
            dom=dom,
            usuario=request.user,
            accion='ELIMINACION',
            etapa='etapa_4',
            campos_modificados={'producto_planeacion_id': str(producto.producto_planeacion.id)},
            request=request,
        )

        return Response(
            {'mensaje': 'Cantidad elaborada eliminada correctamente'},
            status=status.HTTP_200_OK
        )


# clase para obtener todos los registros de almacen para consulta, todos los roles pueden acceder para lectura (GET)
# La clase permite igualmente creación de nuevo registro almacen solo ADMIN Y LIDER_PLANTA

class RegistroAlmacenListView(APIView):

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
            etapa='etapa_3',
            campos_modificados=foto_inicial(registro),
            request=request,
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

        # No se puede cerrar la etapa sin el veredicto que esta etapa produce
        error_cierre = validar_cierre(registro, request.data, 'etapa_3')
        if error_cierre:
            return Response({'error': error_cierre}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RegistroAlmacenSerializer(registro, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos inválidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campos_antes = instantanea(registro, request.data)

        registro = serializer.save()

        registrar_edicion_y_bloqueo(
            dom=registro.registro_planeacion.dom,
            usuario=request.user,
            etapa='etapa_3',
            campos=calcular_campos_modificados(campos_antes, registro),
            campo_bloqueo='materias_liberadas',
            bloqueada=registro.etapa_3_bloqueada(),
            request=request,
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
            etapa='etapa_4',
            campos_modificados=foto_inicial(registro),
            request=request,
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

        # No se puede cerrar la etapa sin el dato que esta etapa produce
        error_cierre = validar_cierre(registro, request.data, 'etapa_4')
        if error_cierre:
            return Response({'error': error_cierre}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RegistroProduccionSerializer(registro, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Daros invalidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        campos_antes = instantanea(registro, request.data)

        registro = serializer.save()

        registrar_edicion_y_bloqueo(
            dom=registro.registro_planeacion.dom,
            usuario=request.user,
            etapa='etapa_4',
            campos=calcular_campos_modificados(campos_antes, registro),
            campo_bloqueo='cierre_produccion',
            bloqueada=registro.etapa_4_bloqueada(),
            request=request,
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
            etapa='etapa_5',
            campos_modificados=foto_inicial(registro),
            request=request,
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

        # No se puede cerrar la etapa sin el veredicto que esta etapa produce
        error_cierre = validar_cierre(registro, request.data, 'etapa_5')
        if error_cierre:
            return Response({'error': error_cierre}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RegistroTratamientoSerializer(registro, data=request.data, partial=True)

        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos inválidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        campos_antes = instantanea(registro, request.data)

        registro = serializer.save()

        registrar_edicion_y_bloqueo(
            dom=registro.registro_planeacion.dom,
            usuario=request.user,
            etapa='etapa_5',
            campos=calcular_campos_modificados(campos_antes, registro),
            campo_bloqueo='tratamiento_completado',
            bloqueada=registro.etapa_5_bloqueada(),
            request=request,
        )

        return Response(
            {
                'mensaje': f'Registro de tratamiento #{registro.numero_registro} actualizado correctamente',
                'registro': RegistroTratamientoSerializer(registro).data
            },
            status=status.HTTP_200_OK
        )

# Vista para consultar y corregir el registro de operarios de un turno/fecha
# Solo ADMIN y PLANEADOR puede modificar este dato una vez registrado

class RegistroTurnoDiaListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        registros = RegistroTurnoDia.objects.select_related('turno').all()
        turno_id = request.query_params.get('turno', None)
        fecha = request.query_params.get('fecha', None)
        excluir = request.query_params.get('excluir_planeacion', None)
        if turno_id:
            registros = registros.filter(turno__turno_id=turno_id)
        if fecha:
            registros = registros.filter(fecha=fecha)
        serializer = RegistroTurnoDiaSerializer(registros, many=True)

        # DOMs vinculados al turno+fecha (No. DOM, cliente, productos+cantidades) y los
        # minutos ya asignados por OTRAS planeaciones. Ambos se derivan de un ÚNICO
        # recorrido en RegistroPlaneacion.detalle_por_turno, que excluye la planeación en
        # edición (excluir) para no contarla dos veces ni listar el DOM actual.
        tiempo_asignado_otras = 0
        doms_vinculados = []
        if turno_id and fecha:
            doms_vinculados = RegistroPlaneacion.detalle_por_turno(turno_id, fecha, excluir)
            tiempo_asignado_otras = sum(d['minutos_ocupados'] for d in doms_vinculados)

        return Response(
            {
                'mensaje': 'Registros de turno del día obtenidos correctamente',
                'total': registros.count(),
                'registros': serializer.data,
                'tiempo_asignado_otras': tiempo_asignado_otras,
                'doms_vinculados': doms_vinculados,
            },
            status=status.HTTP_200_OK
        )


class RegistroTurnoDiaPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, registro_id):
        if not verificar_rol(request, ['ADMIN', 'PLANEADOR']):
            return Response(
                {'error': 'No tienes permisos para previsualizar cambios de capacidad del turno'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            registro = RegistroTurnoDia.objects.select_related('turno').get(id=registro_id)
        except RegistroTurnoDia.DoesNotExist:
            return Response(
                {'error': 'Registro de turno del día no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        numero_operarios_propuesto = request.query_params.get('numero_operarios', registro.numero_operarios)
        minutos_totales_propuesto = request.query_params.get('minutos_totales', registro.minutos_totales)
        try:
            numero_operarios_propuesto = int(numero_operarios_propuesto)
            minutos_totales_propuesto = int(minutos_totales_propuesto)
        except (TypeError, ValueError):
            return Response(
                {'error': 'numero_operarios y minutos_totales deben ser numéricos'},
                status=status.HTTP_400_BAD_REQUEST
            )

        preview = registro.preview_capacidad(numero_operarios_propuesto, minutos_totales_propuesto)
        return Response(
            {
                'mensaje': 'Previsualización de capacidad calculada correctamente',
                'preview': preview
            },
            status=status.HTTP_200_OK
        )


class RegistroTurnoDiaDetalleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, registro_id):
        try:
            registro = RegistroTurnoDia.objects.select_related('turno').get(id=registro_id)
        except RegistroTurnoDia.DoesNotExist:
            return Response(
                {'error': 'Registro de turno del día no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = RegistroTurnoDiaSerializer(registro)
        return Response(
            {
                'mensaje': 'Registro de turno del día obtenido correctamente',
                'registro': serializer.data
            },
            status=status.HTTP_200_OK
        )

    def put(self, request, registro_id):
        if not verificar_rol(request, ['ADMIN', 'PLANEADOR']):
            return Response(
                {'error': 'No tienes permisos para modificar los operarios de un turno'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            registro = RegistroTurnoDia.objects.get(id=registro_id)
        except RegistroTurnoDia.DoesNotExist:
            return Response(
                {'error': 'Registro de turno del día no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        capacidad_anterior = registro.numero_operarios * registro.minutos_totales

        serializer = RegistroTurnoDiaSerializer(registro, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {
                    'error': 'Datos inválidos',
                    'detalle': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        registro = serializer.save()

        impacto = registro.preview_capacidad(registro.numero_operarios, registro.minutos_totales)
        impacto['capacidad_actual'] = capacidad_anterior

        if impacto['turno_quedaria_negativo']:
            dom_ids = [d['dom_id'] for d in impacto['doms']]
            for dom in Dom.objects.filter(dom_id__in=dom_ids):
                registrar_auditoria(
                    dom=dom,
                    usuario=request.user,
                    accion='EDICION',
                    etapa='etapa_2',
                    campos_modificados={
                        'capacidad_turno_dia': {'antes': str(capacidad_anterior), 'despues': str(impacto['capacidad_propuesta'])},
                        'deficit_generado_minutos': {'antes': '0', 'despues': str(impacto['deficit_minutos'])},
                    },
                    request=request,
                )

        return Response(
            {
                'mensaje': 'Registro de turno del día actualizado correctamente',
                'registro': RegistroTurnoDiaSerializer(registro).data,
                'impacto': impacto,
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

        # Cero personas no es dato válido aquí, a diferencia del resto del sistema
        personas = registro_produccion.numero_personas_asignadas
        if personas is None or personas < 1:
            return Response(
                {'error': 'Debe registrar el número de personas asignadas antes de iniciar el cronómetro'},
                status=status.HTTP_400_BAD_REQUEST
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

        registrar_auditoria(
            dom=registro_produccion.registro_planeacion.dom,
            usuario=request.user,
            accion='CREACION',
            etapa='etapa_4',
            campos_modificados=foto_inicial(cronometro),
            request=request,
        )

        return Response(
            {
                'mensaje': 'Cronómetro iniciado correctamente',
                'cronometro': RegistroTiempoProduccionSerializer(cronometro).data
            },
            status=status.HTTP_201_CREATED
        )
    
# Clase pausa cronómetro
class CronometroPausaView(APIView):

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

        registrar_auditoria(
            dom=cronometro.registro_produccion.registro_planeacion.dom,
            usuario=request.user,
            accion='EDICION',
            etapa='etapa_4',
            campos_modificados={'estado': {'antes': 'EN_CURSO', 'despues': 'PAUSADO'}},
            request=request,
        )

        return Response(
            {
                'mensaje': 'Cronómetro pausado correctamente',
                'cronometro': RegistroTiempoProduccionSerializer(cronometro).data
            },
            status=status.HTTP_200_OK
        )

# Clase reanuda cronómetro en pausa
class CronometroReanudarView(APIView):

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

        registrar_auditoria(
            dom=cronometro.registro_produccion.registro_planeacion.dom,
            usuario=request.user,
            accion='EDICION',
            etapa='etapa_4',
            campos_modificados={'estado': {'antes': 'PAUSADO', 'despues': 'EN_CURSO'}},
            request=request,
        )

        return Response(
            {
                'mensaje': 'Cronómetro reanudado correctamente',
                'cronometro': RegistroTiempoProduccionSerializer(cronometro).data
            },
            status=status.HTTP_200_OK
        )

# Clase para finalizar cronometro 
class CronometroFinalizarView(APIView):

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
                {'error': f'No se puede finalizar un cronometro en estado {cronometro.estado}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Registra fin y calcula minutos_totales
        cronometro.fin = timezone.now()
        cronometro.estado = 'FINALIZADO'
        cronometro.minutos_totales = cronometro.calcular_minutos_totales()

        # modelo.save() actualiza minutos_asignados en RegistroProduccion Automáticamente

        cronometro.save()

        registrar_auditoria(
            dom=cronometro.registro_produccion.registro_planeacion.dom,
            usuario=request.user,
            accion='EDICION',
            etapa='etapa_4',
            campos_modificados={
                'estado': {'antes': 'EN_CURSO', 'despues': 'FINALIZADO'},
                'minutos_totales': {'antes': 'None', 'despues': str(cronometro.minutos_totales)},
            },
            request=request,
        )

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

from django.db.models import Sum, Count, Q, Case, When, IntegerField


# Desglose de productos pendientes por tipo para un conjunto de DOMs. Recibe un
# queryset de DOMs y devuelve, por cada tipo con pendiente > 0, cuánto falta por
# producir y en cuántos DOMs aparece. Se reutiliza en el dashboard para el
# horizonte de 15 días y para el backlog completo de DOMs activos.
def productos_pendientes_por_doms(doms_qs):
    resultado = []
    productos_ids = ProductosDom.objects.filter(
        productoDom__in=doms_qs
    ).values('tipo_producto').distinct()

    for item in productos_ids:
        producto_id = item['tipo_producto']
        try:
            producto = Productos.objects.get(producto_id=producto_id)
        except Productos.DoesNotExist:
            continue

        doms_con_producto = doms_qs.filter(
            productos__tipo_producto_id=producto_id
        ).distinct()

        cantidad_pedida = ProductosDom.objects.filter(
            productoDom__in=doms_con_producto,
            tipo_producto_id=producto_id
        ).aggregate(total=Sum('cantidad_pedido'))['total'] or 0

        cantidad_elaborada = ProductoProduccion.objects.filter(
            producto_planeacion__registro_planeacion__dom__in=doms_con_producto,
            producto_planeacion__dom_producto__tipo_producto_id=producto_id
        ).aggregate(total=Sum('cantidad_elaborada'))['total'] or 0

        cantidad_pendiente = cantidad_pedida - cantidad_elaborada

        if cantidad_pendiente > 0:
            resultado.append({
                'nombre_producto': producto.nombre_producto,
                'cantidad_pendiente': cantidad_pendiente,
                'doms_involucrados': doms_con_producto.count()
            })
    return resultado


# Clase DashboardView
# Retorna métricas globales del sistema para la página de inicio.
# Incluye: resumen DOMs, métricas de producción, DOMs próximos a vencer,   DOMs vencidos y productos pendientes por categoría en los próximos 15 días.
# Todos los roles autenticados.

class DashboardView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        hoy = timezone.localdate()

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

        # ── Consolidado HISTÓRICO (todo el tiempo, incluidos DOMs cerrados) ──
        # Unidades elaboradas en toda la historia. Métrica de volumen/throughput;
        # NO se usa para "pendiente" (un cierre con bajo-entrega inflaría el pendiente).
        unidades_elaboradas_historico = ProductoProduccion.objects.aggregate(
            total=Sum('cantidad_elaborada')
        )['total'] or 0

        # ── Consolidado DOMs ACTIVOS (dom_liberado_cierre=False) ──
        # Las tres cifras hablan del mismo universo (trabajo en curso), así
        # 'pendiente = pedida - elaborada' es coherente y accionable.
        cantidad_pedida_activos = ProductosDom.objects.filter(
            productoDom__dom_liberado_cierre=False
        ).aggregate(total=Sum('cantidad_pedido'))['total'] or 0

        cantidad_elaborada_activos = ProductoProduccion.objects.filter(
            producto_planeacion__registro_planeacion__dom__dom_liberado_cierre=False
        ).aggregate(total=Sum('cantidad_elaborada'))['total'] or 0

        cantidad_pendiente_activos = cantidad_pedida_activos - cantidad_elaborada_activos

        # DOMs próximos a vencer: fecha de entrega efectiva (proyectada, o solicitada
        # si no hay) dentro de los próximos DIAS_PROXIMO_VENCER días. El >= hoy excluye
        # los ya vencidos para que no se cuenten dos veces.
        fecha_limite_proximo = hoy + timezone.timedelta(days=DIAS_PROXIMO_VENCER)
        doms_proximos_vencer = Dom.objects.filter(
            dom_liberado_cierre=False
        ).annotate(
            fecha_criterio=fecha_entrega_efectiva()
        ).filter(
            fecha_criterio__gte=hoy,
            fecha_criterio__lte=fecha_limite_proximo
        ).select_related('nombre_cliente').prefetch_related('productos')

        # DOMs vencidos: la fecha de entrega efectiva ya pasó y el DOM sigue abierto.
        doms_vencidos = Dom.objects.filter(
            dom_liberado_cierre=False
        ).annotate(
            fecha_criterio=fecha_entrega_efectiva()
        ).filter(
            fecha_criterio__lt=hoy
        ).select_related('nombre_cliente').prefetch_related('productos')

        # Productos pendientes por categoría dentro del horizonte de producción:
        # DOMs con fecha de entrega efectiva <= hoy + DIAS_HORIZONTE_PRODUCCION
        # (sin borde inferior: incluye también los ya vencidos).
        fecha_limite_horizonte = hoy + timezone.timedelta(days=DIAS_HORIZONTE_PRODUCCION)
        doms_proximos_15 = Dom.objects.filter(
            dom_liberado_cierre=False
        ).annotate(
            fecha_criterio=fecha_entrega_efectiva()
        ).filter(
            fecha_criterio__lte=fecha_limite_horizonte
        )

        # Agrupa por producto y calcula pendientes (horizonte de 15 días).
        productos_pendientes = productos_pendientes_por_doms(doms_proximos_15)

        # Backlog completo de productos pendientes sobre TODOS los DOMs activos.
        productos_pendientes_activos = productos_pendientes_por_doms(
            Dom.objects.filter(dom_liberado_cierre=False)
        )

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

        # Inicialización previa — evita NameError si doms_activos está vacío
        cumplimiento_almacen = 'SIN_DATOS'
        cumplimiento_produccion = 'SIN_DATOS'
        cumplimiento_tratamiento = 'SIN_DATOS'
        cumplimiento_despacho = 'SIN_DATOS'
        cumplimiento_consolidado = 'SIN_DATOS'

        # count() fuera del loop — un único hit a BD
        total_doms_activos_count = doms_activos.count()
        doms_entregados_ok = doms_activos.filter(dom_entregado_ok=True).count()

        for dom in doms_activos:
            for rp in dom.registro_planeacion.all():
                total_planeaciones_activas += 1
                almacenes = rp.registros_almacen.all()
                producciones = rp.registros_produccion.all()
                tratamientos = rp.registros_tratamiento.all()

                # Evaluación dentro del loop interno — cubre todos los rp del DOM
                if almacenes.exists() and all(a.dom_realizado_planeacion for a in almacenes):
                    almacen_ok_count += 1

                if producciones.exists() and all(p.segun_planeacion for p in producciones):
                    produccion_ok_count += 1

                if tratamientos.exists() and all(t.tratamiento_segun_planeacion for t in tratamientos):
                    tratamiento_ok_count += 1

        # Nivel 2 — fuera de ambos loops, con totales finales
        cumplimiento_almacen     = calcular_ratio_cumplimiento(almacen_ok_count, total_planeaciones_activas)
        cumplimiento_produccion  = calcular_ratio_cumplimiento(produccion_ok_count, total_planeaciones_activas)
        cumplimiento_tratamiento = calcular_ratio_cumplimiento(tratamiento_ok_count, total_planeaciones_activas)
        cumplimiento_despacho    = calcular_ratio_cumplimiento(doms_entregados_ok, total_doms_activos_count)

        # Nivel 3 consolidado global - medición cuatro etapas
        niveles = [c['nivel'] for c in (cumplimiento_almacen, cumplimiento_produccion,
                                        cumplimiento_tratamiento, cumplimiento_despacho)]
        if all(n == 'CUMPLIÓ' for n in niveles):
            nivel_consolidado = 'CUMPLIÓ'
        elif all(n == 'NO_CUMPLIÓ' for n in niveles):
            nivel_consolidado = 'NO_CUMPLIÓ'
        elif all(n == 'SIN_DATOS' for n in niveles):
            nivel_consolidado = 'SIN_DATOS'
        else:
            nivel_consolidado = 'PARCIAL'

        # Ratio consolidado = suma de "ok" ÷ suma de "total" de las 4 etapas.
        # OJO: mezcla planeaciones (almacén/producción/tratamiento) con DOMs (despacho); aceptado por negocio.
        consolidado_ok = almacen_ok_count + produccion_ok_count + tratamiento_ok_count + doms_entregados_ok
        consolidado_total = total_planeaciones_activas * 3 + total_doms_activos_count
        cumplimiento_consolidado = {
            'nivel': nivel_consolidado,
            'ok': consolidado_ok,
            'total': consolidado_total,
            'porcentaje': round(consolidado_ok / consolidado_total * 100, 1) if consolidado_total else None,
        }

        data = {
            'total_doms': total_doms,
            'total_doms_activos': total_doms_activos,
            'total_doms_cerrados': total_doms_cerrados,
            'doms_por_etapa': doms_por_etapa,
            # Consolidado histórico
            'unidades_elaboradas_historico': unidades_elaboradas_historico,
            # Consolidado DOMs activos
            'cantidad_pedida_activos': cantidad_pedida_activos,
            'cantidad_elaborada_activos': cantidad_elaborada_activos,
            'cantidad_pendiente_activos': cantidad_pendiente_activos,
            'doms_proximos_vencer': DomListSerializer(doms_proximos_vencer, many=True).data,
            'doms_vencidos': DomListSerializer(doms_vencidos, many=True).data,
            'productos_pendientes_15_dias': productos_pendientes,
            'productos_pendientes_activos': productos_pendientes_activos,

            # datos de cumplimiento por etapa
            'cumplimiento_almacen': cumplimiento_almacen,
            'cumplimiento_produccion': cumplimiento_produccion,
            'cumplimiento_tratamiento': cumplimiento_tratamiento,
            'cumplimiento_despacho': cumplimiento_despacho,
            'cumplimiento_consolidado': cumplimiento_consolidado,
        }

        return Response(
            {
                'mensaje': 'Dashboard obtenido correctamente',
                'dashboard': data
            },
            status=status.HTTP_200_OK
        )

class InformeCumplimientoPlaneacion(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        fecha_inicio = request.query_params.get('fecha_inicio', None)
        fecha_fin = request.query_params.get('fecha_fin', None)

        if not fecha_inicio or not fecha_fin:
            return Response(
                {'error': 'Debe indicar fecha_inicio y fecha_fin para generar el informe'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if fecha_inicio > fecha_fin:
            return Response(
                {'error': 'fecha_inicio no puede ser mayor que fecha_fin'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Obtiene registro de planeacion en el rango de fechas
        registros = RegistroPlaneacion.objects.filter(
            fecha_planeacion__range=[fecha_inicio, fecha_fin]
        ).select_related(
            # 'dom_producto' y 'turno' no se usan aquí; el primero además ya no existe en el modelo
            'dom__nombre_cliente',
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
        elif all(n == 'SIN_DATOS' for n in niveles):
            cumplimiento_consolidado = 'SIN_DATOS'
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

    permission_classes = [IsAuthenticated]

    def get(self, request):
        fecha_inicio = request.query_params.get('fecha_inicio', None)
        fecha_fin = request.query_params.get('fecha_fin', None)

        if not fecha_inicio or not fecha_fin:
            return Response(
                {'error': 'Debe indicar fecha_inicio y fecha_fin para generar el informe'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if fecha_inicio > fecha_fin:
            return Response(
                {'error': 'fecha_inicio no puede ser mayor que fecha_fin'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # El filtro es la fecha que produce esta misma etapa. Los DOMs que aún no
        # la tienen no están planeados para despacho todavía; se declaran aparte.
        doms = Dom.objects.filter(
            fecha_entrega_pactada__range=[fecha_inicio, fecha_fin]
        ).select_related('nombre_cliente')

        # Un veredicto por DOM: dom_entregado_ok vive en el DOM y no cuelga de
        # ninguna planeación, así que aquí no hay multiplicidad que recorrer.
        registros = []
        veredictos = []

        for dom in doms:
            veredicto = veredicto_despacho(dom)
            veredictos.append(veredicto)
            registros.append({
                'dom_id': dom.dom_id,
                'nombre_cliente': dom.nombre_cliente.nombre_cliente,
                'fecha_entrega_pactada': dom.fecha_entrega_pactada,
                'veredicto_despacho': veredicto,
                'novedad': dom.novedades_cumplimiento,
            })

        total_cumplieron = veredictos.count(CUMPLIO)
        total_no_cumplieron = veredictos.count(NO_CUMPLIO)
        total_pendientes = veredictos.count(PENDIENTE)

        # El pendiente sale del denominador: no haber contestado todavía no es
        # haber incumplido. El bucle anterior partía en dos con un if/else, y ese
        # else recogía el falso y el nulo juntos: de ahí salía que el encabezado
        # dijera 2 y la lista trajera 4 en la misma respuesta.
        total_evaluables = total_cumplieron + total_no_cumplieron
        porcentaje_cumplimiento = round(
            (total_cumplieron / total_evaluables * 100) if total_evaluables > 0 else 0, 2
        )

        # Ningún rango puede contenerlos, así que el conteo es necesariamente
        # global. Se declara para que la exclusión deje de ser invisible.
        total_doms_sin_fecha_pactada = Dom.objects.filter(
            fecha_entrega_pactada__isnull=True
        ).count()

        data = {
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'total_doms_en_rango': len(registros),
            'total_cumplieron': total_cumplieron,
            'total_no_cumplieron': total_no_cumplieron,
            'total_pendientes': total_pendientes,
            'total_evaluables': total_evaluables,
            'porcentaje_cumplimiento': porcentaje_cumplimiento,
            'total_doms_sin_fecha_pactada': total_doms_sin_fecha_pactada,
            'cumplimiento_despacho': consolidar(veredictos),
            'registros': registros,
        }

        serializer = InformeDespachoSerializer(data)
        return Response(
            {
                'mensaje': 'Informe de despacho generado correctamente',
                'informe': serializer.data
            },
            status=status.HTTP_200_OK
        )

# Clases relacionadas con el manejo del reporte PDF
# Retorna toda la información consolidada de un DOM específico para generación de reporte PDF en el frontend.
# Incluye: etapas 0, 1 y 6, productos, registros de planeación con sus etapas hijo anidadas, y métricas de tiempo proyectado vs tiempo real de ejecución.
# Todos los roles autenticados.

class DomReporteView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, dom_id):
        try:
            dom = Dom.objects.select_related(
                'nombre_cliente'
            ).prefetch_related(
                'productos__tipo_producto',
                'registro_planeacion__turno',
                # Antes: 'registro_planeacion__dom_producto__tipo_producto' — ruta previa al
                # refactor N productos. RegistroPlaneacion ya no tiene 'dom_producto' directo;
                # sus productos viven en el hijo 'productos_planeacion' (models.py:512).
                'registro_planeacion__productos_planeacion__dom_producto__tipo_producto',
                'registro_planeacion__registros_almacen',
                'registro_planeacion__registros_produccion__registros_tiempo',
                'registro_planeacion__registros_produccion__registros_tiempo__pausas',
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
        elif all(n == 'SIN_DATOS' for n in niveles):
            cumplimiento_consolidado_dom = 'SIN_DATOS'
        else:
            cumplimiento_consolidado_dom = 'PARCIAL'

        
        # Serializa el DOM con toda su información anidada
        serializer = DomReporteSerializer(dom)

        # Construye respuesta agregando campos calculados
        data = dict(serializer.data)
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

        if fecha_inicio > fecha_fin:
            return Response(
                {'error': 'fecha_inicio no puede ser mayor que fecha_fin'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Filtro base: la consulta para auditoria este es el filtro base
        acciones = AuditoriaDom.objects.filter(
            timestamp__date__range=[fecha_inicio, fecha_fin]
        ).select_related('dom__nombre_cliente', 'usuario', 'usuario__perfil').order_by('-timestamp')

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
            acciones = acciones.filter(dom__nombre_cliente__cliente_id=cliente_id)
        
        # Totales por tipo de acción 
        totales = acciones.aggregate(
            total_acciones=Count('id'),
            total_creaciones=Count('id', filter=Q(accion='CREACION')),
            total_ediciones=Count('id', filter=Q(accion='EDICION')),
            total_bloqueos=Count('id', filter=Q(accion='BLOQUEO_ETAPA')),
            total_eliminaciones=Count('id', filter=Q(accion='ELIMINACION')),
            total_desbloqueos=Count('id', filter=Q(accion='DESBLOQUEO_ETAPA'))
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
            'total_desbloqueos': totales['total_desbloqueos'],
            'acciones': acciones
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

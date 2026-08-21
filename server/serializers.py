from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
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
    RegistroTurnoDia,
    PausaTiempoProduccion,
    RegistroTratamiento,
    PerfilUsuario,
    AuditoriaDom,
)


def validar_password(password, usuario=None, campo='password'):
    """Aplica AUTH_PASSWORD_VALIDATORS (settings.py) y traduce el error de Django al de DRF.

    Punto único de la política de contraseñas por API. Lo llaman desde su
    validate() CrearUsuarioSerializer, CambioPasswordSerializer y
    RestablecerPasswordSerializer. El usuario llega construido sin guardar en el
    alta, de request.user en el cambio —lo que exige context={'request': request}
    en CambioPasswordView— y cargado por user_id en el restablecimiento.
    """
    try:
        validate_password(password, user=usuario)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({campo: list(exc.messages)})


# Uso: mostrar datos básicos del usuario en auditorías y perfiles; no incluye password al ser un serializer de lectura y referencia
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']

# serializer Usuarios
# Uso: autenticación y control de permisos según rol para el frontend
class PerfilUsuarioSerializer(serializers.ModelSerializer):
    # variables para mostrar usuario y rol en front sin consulta adicional
    username = serializers.CharField(source='user.username', read_only=True)
    nombre_completo = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta: 
        model = PerfilUsuario
        fields = ['id', 'username', 'nombre_completo', 'rol']

# Serializer Clientes
# Uso: Dropdown con listado de clientes en etapa. Solo datos esenciales en este aspecto
# Solo muestra campos esenciales
class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['cliente_id', 'nombre_cliente', 'nit', 'activo']

# Serializer familia productos
# Uso: En el modelo de negocio del cliente cada producto está dentro de una familia, se debe mantener esto por integridad de la información
class FamiliaProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamiliaProducto
        fields = ['familia_id', 'nombre_familia', 'activo']

# Serializer Productos
# Uso: Dropdowns listado productos y referencia para calculo de tiempo, se expone tiempo_produccion_unitario para propiedad calculada tiempo_proyectado
class ProductosSerializer(serializers.ModelSerializer):

    # Como cada producto pertenece a una familia, necesita referenciar dicho serializer
    familia_detalle = FamiliaProductoSerializer(source='familia_producto', read_only=True)
    familia_producto = serializers.PrimaryKeyRelatedField(
        queryset=FamiliaProducto.objects.all(),
        required=False, allow_null=True
    )

    class Meta:
        model = Productos
        fields = ['producto_id', 'nombre_producto', 'familia_producto', 'familia_detalle', 'tiempo_produccion_unitario', 'activo']

# Serializer Turno
# Uso: dropdown de turnos de la etapa 2. El catálogo solo aporta identidad; la
# duración de la jornada vive en RegistroTurnoDia, que es de donde sale la capacidad.
class TurnoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Turno
        fields = ['turno_id', 'nombre_turno', 'activo']


class RegistroTurnoDiaSerializer(serializers.ModelSerializer):
    turno_nombre = serializers.CharField(
        source='turno.nombre_turno',
        read_only=True
    )

    class Meta:
        model = RegistroTurnoDia
        fields = ['id', 'turno', 'turno_nombre', 'fecha', 'numero_operarios', 'minutos_totales', 'registrado_por', 'fecha_creacion']
        # turno y fecha identifican una jornada: mover registros afecta las jornadas de
        # trabajo. Operarios y duración son editables según necesidades de la planeación.
        read_only_fields = ['registrado_por', 'fecha_creacion', 'turno', 'fecha']
        # minutos_totales lo valida DRF de forma nativa contra el choices del modelo, jornadas vigentes OPCIONES_MINUTOS y las históricas — fuente única de verdad. Ambas viven en la clase RegistroTurnoDia de models.py: las vigentes en OPCIONES_MINUTOS y las de legislaciones anteriores en OPCIONES_MINUTOS_HISTORICAS. Todo dentro de models
        extra_kwargs = {
            'minutos_totales': {
                'error_messages': {
                    'invalid_choice': 'La duración del turno seleccionada no es válida; recibido: "{input}".'
                }
            }
        }

# Serializer Listas Predefinidas
# Uso: dropdowns de las listas predefinidas, solo se manejan campos necesarios para poblar las vistas de Front

class ListaPredefinidaSerializer(serializers.ModelSerializer):
    class Meta: 
        model = ListaPredefinida
        fields = ['lista_id', 'tipo', 'nombre', 'activo']


# Serializer: ProductosDom
# Uso: dropdown de productos para creación registro DOM, se anida nombre_producto y tiempo_produccion_unitario para vista de front y calculo de tiempo proyectado
class ProductosDomSerializer(serializers.ModelSerializer):
    # variable para devolver a front objeto con nombre y tiempo de produccion unitario del producto
    tipo_producto_detalle = ProductosSerializer(source='tipo_producto', read_only=True)
    # variable para leer datos de tipo de producto con primary key
    tipo_producto = serializers.PrimaryKeyRelatedField(
    queryset=Productos.objects.all()
    )
    # Minutos por unidad ya resueltos para esta fila. Es el valor con el que se calcula
    # 'tiempo_proyectado_total' del DOM, así que es el que debe mostrar la pantalla.
    tiempo_unitario_efectivo = serializers.ReadOnlyField()

    class Meta:
        model = ProductosDom
        fields = [
            'id',
            'tipo_producto',
            'tipo_producto_detalle',
            'cantidad_pedido',
            'tiempo_unitario_efectivo',
        ]

# Serializer : DomListSerializer
# Uso: necesario para manejo de consultad de DOMS especificos, es decir, información que se despliega cuando se hace consulta de DOM especificos
class DomListSerializer(serializers.ModelSerializer):
    # Se obtiene id del nombre del cliente como PK
    nombre_cliente = serializers.PrimaryKeyRelatedField(read_only=True)
    # Detalle del nombre del cliente
    nombre_cliente_detalle = serializers.CharField(
        source='nombre_cliente.nombre_cliente', read_only=True
    )
    # consulta del listado de productos del dom con nombre y cantidad
    productos = ProductosDomSerializer(many=True, read_only=True)

    # propiedades calculadas del modelo, necesario para visualización en fron igualmente
    cantidad_elaborada_total = serializers.ReadOnlyField()
    cantidad_pedida_total = serializers.ReadOnlyField()
    cantidad_pendiente_total = serializers.ReadOnlyField()

    # Fecha de entrega efectiva y nivel de urgencia — criterio ÚNICO de vencimiento.
    # Se calculan en el backend (annotation en la vista) y se exponen aquí para que
    # el frontend MUESTRE y CLASIFIQUE con lo mismo, sin recalcular fechas en JS.
    fecha_criterio = serializers.SerializerMethodField()
    nivel_urgencia = serializers.SerializerMethodField()

    def get_fecha_criterio(self, obj):
        # Respaldo en Python con la misma regla del Coalesce del backend: proyectada,
        # o solicitada si no hay. Si la vista ya anotó 'fecha_criterio', se usa esa.
        return (
            getattr(obj, 'fecha_criterio', None)
            or obj.fecha_entrega_proyectada
            or obj.fecha_solicitada_cliente
        )

    def get_nivel_urgencia(self, obj):
        # Solo lo anota ListaDoms (0 vencido · 1 próximo · 2 activo). En el dashboard
        # las listas ya vienen separadas (vencidos/próximos), así que puede no existir.
        return getattr(obj, 'nivel_urgencia', None)

    class Meta:
        model = Dom
        fields = [
            'dom_id',
            'fecha_asignacion_dom',
            'nombre_cliente',           # ID
            'nombre_cliente_detalle',   # Nombre legible para Front
            'tipo_estado_dom',
            'responsable',
            'fecha_solicitada_cliente',
            'fecha_entrega_pactada',
            'fecha_criterio',           # fecha de entrega efectiva (para mostrar)
            'nivel_urgencia',           # clasificación de vencimiento (para el badge)
            'dom_relacionado_produccion',
            'dom_liberado_cierre',
            'productos',
            'cantidad_pedida_total',
            'cantidad_elaborada_total',
            'cantidad_pendiente_total'
        ]

# Serializer: DomDetalleSerializer
# Uso: Serializer necesario para el manejo del formulario por etapa; lectura o edicion de un DOM especifico

class DomDetalleSerializer(serializers.ModelSerializer):
    nombre_cliente_detalle = serializers.CharField(
        source = 'nombre_cliente.nombre_cliente', read_only = True
    )
    # consulta del cliente con PK como FK 
    nombre_cliente = serializers.PrimaryKeyRelatedField(
        queryset = Cliente.objects.all()
    )
    # Consulta de propiedades calculadas
    productos = ProductosDomSerializer(many=True, read_only=True)
    cantidad_elaborada_total = serializers.ReadOnlyField()
    cantidad_pedida_total = serializers.ReadOnlyField()
    cantidad_pendiente_total = serializers.ReadOnlyField()
    tiempo_proyectado_total = serializers.ReadOnlyField()

    class Meta:
        model = Dom
        fields = [
            #PK
            'dom_id',

            #etapa 0 
            'fecha_asignacion_dom',
            'nombre_cliente',
            'nombre_cliente_detalle',
            'descripcion',
            'tipo_estado_dom',
            'fecha_solicitada_cliente',
            'responsable',

            #etapa 1
            'orden_compra',
            'tiempo_salida_almacen',
            'rentabilidad',
            'campana_venta',
            'numero_cotizacion',
            'numero_factura',
            'dom_relacionado_produccion',    # bloqueo etapa 1

            #etapa 6
            'fecha_entrega_pactada',
            'fecha_entrega_planificada',
            'cantidad_empaques',
            'empaque_servicio',
            'tipo_negociacion',
            'fecha_entrega_proyectada',
            'materiales_externos',
            'vehiculo',
            'orden_entrega',
            'notas',
            'novedades_cumplimiento',
            'dom_entregado_ok',
            'dom_liberado_cierre',   # bloqueo etapa 6

            #Relaciones y calculados
            'productos',
            'cantidad_pedida_total',
            'cantidad_pendiente_total',
            'cantidad_elaborada_total',
            'tiempo_proyectado_total',
        ]
        read_only_fields = ['dom_id', 'fecha_asignacion_dom']
        extra_kwargs = {
            'campana_venta':   {'allow_null': True, 'required': False},
            'dom_entregado_ok': {'allow_null': True, 'required': False},
        }

# Serializer: RegistroAlmacen
# Uso: manejo información etapa 3 - almacen
class RegistroAlmacenSerializer(serializers.ModelSerializer):
    # Propiedad herada para mostrar objetivo establecido en planeacion
    tarea_asignada_planeacion = serializers.ReadOnlyField(source='tarea_planeacion')
    etapa_3_bloqueada = serializers.SerializerMethodField()

    def get_etapa_3_bloqueada(self, obj):
        return obj.etapa_3_bloqueada()
    
    class Meta: 
        model = RegistroAlmacen
        fields = [
            'id',
            'registro_planeacion',
            'numero_registro',
            'materias_primas',
            'novedad_cumplimiento_almacen',
            'dom_realizado_planeacion',
            'materias_liberadas',        # Bloqueo etapa 3
            'tarea_asignada_planeacion', # heredada de planeacion
            'etapa_3_bloqueada',
        ]
        # Se agrega funcionalidad "extra_kwargs de Django" para propagar comportamiento "allow_null al serializer. Si bien el modelo ya lo maneja el comportamiento no siempre se propaga por defecto"
        # registro_planeacion es de solo lectura: lo asigna la vista al crear. Si fuera
        # escribible, un PUT podría mover el registro a otra planeación y a otro DOM.
        read_only_fields = ['numero_registro', 'registro_planeacion']
        extra_kwargs = {
            'novedad_cumplimiento_almacen': {
                'allow_null': True,
                'allow_blank': True,
                'required': False
            },
            'materias_primas': {'allow_null': True, 'required': False},
        }

# Serializer: PausaTiempoProduccion
# Uso: pausas individuales del cronometro

class PausaTiempoProduccionSerializer(serializers.ModelSerializer):
    class Meta: 
        model = PausaTiempoProduccion
        fields = [
            'id',
            'registro_tiempo',
            'inicio_pausa',
            'fin_pausa',
            'segundos_pausados',     #calculado de forma automatica para metodo save()
        ]
        read_only_fields = ['segundos_pausados']

# Serializer: Registro tiempo produccion
# Uso: control del cronometro de produccion, incluye pausas totales (si hay); sus propiedades son necesarias para calcular minutos_hombre y minutos_restantes en tiempo real a nivel Front

class RegistroTiempoProduccionSerializer(serializers.ModelSerializer):
    pausas = PausaTiempoProduccionSerializer(many=True, read_only=True)

    class Meta:
        model = RegistroTiempoProduccion
        fields = [
            'id',
            'registro_produccion',
            'inicio',
            'fin',
            'estado',
            'total_segundos_pausados',
            'minutos_totales',      #Propiedad calculada al seleccional finalizar cronometro
            'pausas',               #Entidad generada para calculo de tiempo en tiempo real
            'usuario',
        ]
        read_only_fields = ['minutos_totales', 'total_segundos_pausados']

# Serializer: ProductoProduccion
# Uso: registro de cantidades parciales elaboradas por producto dentro de un RegistroProduccion

class ProductoProduccionSerializer(serializers.ModelSerializer):
    nombre_producto = serializers.CharField(
        source='producto_planeacion.dom_producto.tipo_producto.nombre_producto',
        read_only=True
    )
    cantidad_proyectada = serializers.IntegerField(
        source='producto_planeacion.cantidad_proyectada',
        read_only=True
    )

    class Meta:
        model = ProductoProduccion
        fields = [
            'id',
            'registro_produccion',
            'producto_planeacion',
            'cantidad_elaborada',
            'nombre_producto',
            'cantidad_proyectada',
            'fecha_registro',
        ]
        # Las dos FK las asigna la vista al crear. Escribibles, un PUT reasignaría la fila
        # y alteraría lo producido de dos planeaciones a la vez.
        read_only_fields = ['fecha_registro', 'registrado_por',
                            'registro_produccion', 'producto_planeacion']


# Serializer: RegistroProduccionSerializer
# Uso: manejo de información de la etapa 4 produccion incluyendo referencias a los serializers de manejo del cronometro, actulizada en tiempo real según JS

class RegistroProduccionSerializer(serializers.ModelSerializer):
    registro_tiempo    = RegistroTiempoProduccionSerializer(source='registros_tiempo', many=True, read_only=True)
    productos_produccion = ProductoProduccionSerializer(many=True, read_only=True)

    cantidad_elaborada            = serializers.ReadOnlyField()
    tiempo_elaboracion_produccion = serializers.ReadOnlyField()
    minutos_hombre_produccion_dom = serializers.ReadOnlyField()
    minutos_restantes_dom         = serializers.ReadOnlyField()
    tarea_asignada_planeacion     = serializers.ReadOnlyField()
    cumplimiento_produccion       = serializers.ReadOnlyField()
    etapa_4_bloqueada             = serializers.SerializerMethodField()

    def get_etapa_4_bloqueada(self, obj):
        return obj.etapa_4_bloqueada()

    class Meta:
        model = RegistroProduccion
        fields = [
            'id',
            'registro_planeacion',
            'numero_registro',
            'minutos_asignados',
            'numero_personas_asignadas',
            'novedad_cumplimiento_produccion',
            'segun_planeacion',
            'produccion_no_completada',
            'cierre_produccion',
            # propiedades calculadas
            'cantidad_elaborada',
            'tarea_asignada_planeacion',
            'tiempo_elaboracion_produccion',
            'minutos_hombre_produccion_dom',
            'minutos_restantes_dom',
            'cumplimiento_produccion',
            'etapa_4_bloqueada',
            # hijos anidados
            'productos_produccion',
            'registro_tiempo',
        ]

        # registro_planeacion es de solo lectura: lo asigna la vista al crear. Si fuera
        # escribible, un PUT podría mover el registro a otra planeación y a otro DOM.
        read_only_fields = ['numero_registro', 'registro_planeacion']
        extra_kwargs = {
            'novedad_cumplimiento_produccion': {
                'allow_null': True,
                'allow_blank': True,
                'required': False
            },
            'produccion_no_completada': {
                'allow_null': True,
                'allow_blank': True,
                'required': False
            },
            'segun_planeacion': {'allow_null': True, 'required': False},
        }

    def validate_numero_personas_asignadas(self, value):
        """Inmutable si ya existe cronómetro: el valor es factor de
        minutos_hombre_produccion_dom, y cambiarlo reescribiría un cálculo ya hecho.
        Comparar contra lo guardado cubre vaciarlo, ponerlo en cero y cambiarlo."""
        inst = self.instance
        if inst and inst.registros_tiempo.exists() and value != inst.numero_personas_asignadas:
            raise serializers.ValidationError(
                'No se puede modificar el número de personas asignadas: este registro '
                'ya tiene un cronómetro.'
            )
        return value

# Serializer: RegistroTratamiento
# Uso: manejo datos etapa 5 - tratamiento fitosanitario

class RegistroTratamientoSerializer(serializers.ModelSerializer):
    tarea_asignada_planeacion = serializers.ReadOnlyField()
    etapa_5_bloqueada = serializers.SerializerMethodField()

    def get_etapa_5_bloqueada(self, obj):
        return obj.etapa_5_bloqueada()
    
    class Meta: 
        model = RegistroTratamiento
        fields = [
            'id', 
            'registro_planeacion',
            'numero_registro',
            'dom_con_tratamiento',
            'numero_tratamiento',
            'novedad_cumplimiento_tratamiento',
            'tratamiento_segun_planeacion',
            'tratamiento_completado', # bloqueo etapa 5
            'tarea_asignada_planeacion',
            'etapa_5_bloqueada',
        ]
        # Se agrega funcionalidad "extra_kwargs de Django" para propagar comportamiento "allow_null al serializer. Si bien el modelo ya lo maneja el comportamiento no siempre se propaga por defecto"
        # registro_planeacion es de solo lectura: lo asigna la vista al crear. Si fuera
        # escribible, un PUT podría mover el registro a otra planeación y a otro DOM.
        read_only_fields = ['numero_registro', 'registro_planeacion']
        extra_kwargs = {
            'novedad_cumplimiento_tratamiento': {
                'allow_null': True,
                'allow_blank': True,
                'required': False
            },
            'dom_con_tratamiento':       {'allow_null': True, 'required': False},
            'tratamiento_segun_planeacion': {'allow_null': True, 'required': False},
            # numero_tratamiento pasó a CharField (código de texto libre): acepta vacío/nulo
            'numero_tratamiento': {'allow_null': True, 'allow_blank': True, 'required': False},
        }

# Serializer: ProductoPlaneacion
# Uso: productos asociados a un registro de planeación, con cantidad proyectada y propiedades calculadas por producto

class ProductoPlaneacionSerializer(serializers.ModelSerializer):
    dom_producto_detalle = ProductosDomSerializer(source='dom_producto', read_only=True)
    dom_producto = serializers.PrimaryKeyRelatedField(queryset=ProductosDom.objects.all())
    cantidad_elaborada = serializers.ReadOnlyField()
    cantidad_pendiente = serializers.ReadOnlyField()
    # Minutos por unidad ya resueltos: fotografía de la fila, o catálogo vigente si es
    # anterior a la migración 0021. Se expone la propiedad y no la columna para que la
    # cascada viva en un solo lugar y el frontend nunca reciba un nulo.
    tiempo_unitario_efectivo = serializers.ReadOnlyField()

    class Meta:
        model = ProductoPlaneacion
        fields = [
            'id',
            'registro_planeacion',
            'dom_producto',
            'dom_producto_detalle',
            'cantidad_proyectada',
            'cantidad_elaborada',
            'cantidad_pendiente',
            'tiempo_unitario_efectivo',
        ]
        read_only_fields = ['registro_planeacion']

    def validate_dom_producto(self, value):
        """Inmutable tras crear, no de solo lectura: al crear la línea el usuario elige el
        producto. tiempo_unitario_aplicado se fotografía sólo al insertar y no se recalcula,
        así que un cambio dejaría la fila calculando con los minutos del producto anterior."""
        if self.instance and value != self.instance.dom_producto:
            raise serializers.ValidationError(
                'No se puede cambiar el producto de una línea de planeación. '
                'Elimine la línea y cree una nueva.'
            )
        return value


# Serializer: RegistroPlaneacion
# Uso: gestion etapa 2 - planeación de la produccion
# Importante: teniendo en cuenta diseño del sistema (nuevo registro planeacion genera nuevos registros produccion, almacen y tratamiento) a demas de la presentacion informes N+1 este serializer anida produccion, almacen y tratamiento.

class RegistroPlaneacionSerializer(serializers.ModelSerializer):
    turno_detalle = TurnoSerializer(source='turno', read_only=True)
    turno = serializers.PrimaryKeyRelatedField(
        queryset=Turno.objects.all(),
        required=False,
        allow_null=True
    )

    # Productos de la planeación — reemplaza dom_producto y cantidad_pedido anteriores
    productos_planeacion = ProductoPlaneacionSerializer(many=True, read_only=True)

    # Registros hijos anidados
    registros_almacen    = RegistroAlmacenSerializer(many=True, read_only=True)
    registros_produccion = RegistroProduccionSerializer(many=True, read_only=True)
    registros_tratamiento = RegistroTratamientoSerializer(many=True, read_only=True)

    # Propiedades calculadas del modelo
    numero_operarios_turno           = serializers.ReadOnlyField()
    tiempo_proyectado                = serializers.ReadOnlyField()
    capacidad_turno_dia              = serializers.ReadOnlyField()
    sumatoria_tiempo_asignado_turnos = serializers.ReadOnlyField()
    tiempo_restante_dia              = serializers.ReadOnlyField()
    cantidad_elaborada               = serializers.ReadOnlyField()
    cantidad_pendiente               = serializers.ReadOnlyField()
    etapa2_bloqueada                 = serializers.SerializerMethodField()

    def get_etapa2_bloqueada(self, obj):
        return obj.etapa2_bloqueada()

    class Meta:
        model = RegistroPlaneacion
        fields = [
            'id',
            'dom',
            'numero_registro',
            'fecha_planeacion',

            # turno
            'turno',
            'turno_detalle',

            # productos de la planeación
            'productos_planeacion',

            # campos de planeación
            'materia_prima_disponible',
            'orden_produccion',
            'lider_produccion',
            'objetivo_planeacion',
            'tablilla_madera',
            'encartonar',
            'grafado_fundas',
            'control_tiempo',
            'orden_tratamiento',
            'lider_almacen',
            'cliente_recoge',
            'mudar_entrega',
            'tratamiento_termico',
            'sello_ica',
            'peso',
            'marcado_cliente',

            # bloqueo
            'planeacion_completa',
            'etapa2_bloqueada',

            # propiedades calculadas
            'tiempo_proyectado',
            'capacidad_turno_dia',
            'sumatoria_tiempo_asignado_turnos',
            'tiempo_restante_dia',
            'cantidad_elaborada',
            'cantidad_pendiente',
            'numero_operarios_turno',

            # hijos anidados
            'registros_almacen',
            'registros_produccion',
            'registros_tratamiento',
        ]

        read_only_fields = ['numero_registro', 'dom']
        extra_kwargs = {
            'materia_prima_disponible': {'allow_null': True, 'required': False},
            'encartonar':               {'allow_null': True, 'required': False},
            'grafado_fundas':           {'allow_null': True, 'required': False},
            'control_tiempo':           {'allow_null': True, 'required': False},
            'cliente_recoge':           {'allow_null': True, 'required': False},
            'mudar_entrega':            {'allow_null': True, 'required': False},
            'tratamiento_termico':      {'allow_null': True, 'required': False},
            'sello_ica':                {'allow_null': True, 'required': False},
            'peso':                     {'allow_null': True, 'required': False},
            'marcado_cliente':          {'allow_null': True, 'required': False},
        }

    def validate(self, data):
        # Regla de negocio (P7): la fecha de planeación no puede ser posterior a la
        # fecha de entrega planificada del DOM. En pantalla "fecha de entrega planificada"
        # corresponde a la columna 'fecha_entrega_pactada' (ver nota de deuda técnica en
        # models.py). Es la ÚNICA restricción de fechas del sistema.
        fecha_planeacion = data.get('fecha_planeacion')
        if fecha_planeacion is None and self.instance is not None:
            fecha_planeacion = self.instance.fecha_planeacion

        # El DOM se asigna del lado del servidor: en edición viene en la instancia,
        # en creación se pasa por contexto desde la vista.
        dom = self.instance.dom if self.instance is not None else self.context.get('dom')

        if fecha_planeacion and dom and dom.fecha_entrega_pactada:
            if fecha_planeacion > dom.fecha_entrega_pactada:
                raise serializers.ValidationError({
                    'fecha_planeacion': 'La fecha de planeación no puede ser posterior a la fecha de entrega planificada.'
                })

        # Regla de negocio (P8): las opciones de entrega son mutuamente excluyentes.
        # Si AMBAS están definidas deben diferir (exactamente una en Sí): no pueden
        # estar ambas en Sí ni ambas en No. Se permite que una o ambas queden en null
        # (no son campos obligatorios), en cuyo caso no hay exclusión que validar.
        # En PUT parcial cada campo se resuelve del payload o, si no vino, de la instancia.
        def _valor_entrega(campo):
            if campo in data:
                return data[campo]
            return getattr(self.instance, campo) if self.instance is not None else None

        cliente_recoge = _valor_entrega('cliente_recoge')
        mudar_entrega = _valor_entrega('mudar_entrega')

        if cliente_recoge is not None and mudar_entrega is not None:
            if cliente_recoge == mudar_entrega:
                raise serializers.ValidationError({
                    'non_field_errors': 'Debe indicar exactamente una opción de entrega: o el cliente recoge los productos o Mudar los entrega.'
                })

        return data

# Serializer: AuditoriaDom
# Uso: trazabilidad y consulta de cambios - solo lectura y EXCLUSIVO ADMINISTRADOR sin embargo, dicha configuracion está en views.py 

class AuditoriaDomSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='usuario.username', read_only = True)
    # Rol del usuario que ejecutó la acción, en su forma legible (get_rol_display).
    # Se resuelve con método porque el usuario pudo ser eliminado (SET_NULL) o
    # no tener PerfilUsuario asignado.
    rol = serializers.SerializerMethodField(read_only = True)

    class Meta:
        model = AuditoriaDom
        fields = [
            'id',
            'dom',
            'usuario',
            'username',
            'rol',
            'accion',
            'etapa',
            'campos_modificados',
            'timestamp',
        ]

        read_only_fields = fields # Auditoria siempre solo lectura

    def get_rol(self, obj):
        usuario = obj.usuario
        if usuario is None:
            return None
        # El descriptor OneToOne inverso de Django hereda de AttributeError,
        # por lo que getattr(..., None) devuelve None si no hay perfil asociado.
        perfil = getattr(usuario, 'perfil', None)
        if perfil is None:
            return None
        return perfil.get_rol_display()

# Serializer: Login 
# Uso: recibir username + password del Front, valide y devuelve token de acceso

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(
        required = True,
        write_only = True,
        style={'input_type': 'password'}
    )

# Serializer: Cambio de contraseña
# Solo ADMIN puede cambiar contraseñas (controlado a través de views.py)

class CambioPasswordSerializer(serializers.Serializer):
    password_actual = serializers.CharField(
        required = True, 
        write_only = True,
        style = {'input_type': 'password'}
    )
    nuevo_password = serializers.CharField(
        required = True,
        write_only = True,
        style={'input_type': 'password'}
    )
    confirmar_password = serializers.CharField(
        required=True,
        write_only=True,
        style = {'input_type' : 'password'}
    )

    def validate(self, data):

        # validacion que nuevo_password y confirmar_password coincidan
        if data ['nuevo_password'] != data['confirmar_password']:
            raise serializers.ValidationError({
                'nuevo_password' : 'Por favor valide que la nueva contraseña y su confirmación coincidan'
            })

        # validacion que la nueva contraseña no sea igua identica a la contraseña acutal
        if data['password_actual'] == data['nuevo_password']:
            raise serializers.ValidationError({
                'nuevo_Password': 'la nueva contraseña debe ser diferente a la contraseña acutal, por favor valide'
            })

        # La fortaleza se comprueba al final: primero lo que el usuario puede
        # corregir de un vistazo. El usuario autenticado llega por el contexto
        # que pasa CambioPasswordView.
        validar_password(data['nuevo_password'],
                         self.context['request'].user,
                         campo='nuevo_password')

        return data

# Serializer: EditarUsuarioSerializer
# Uso: permite a admin modificar datos de usuarios dentro del sistema
class EditarUsuarioSerializer(serializers.Serializer):

    first_name = serializers.CharField(required=False, max_length=150)
    last_name = serializers.CharField(required=False, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    rol = serializers.ChoiceField(
        choices=PerfilUsuario.ROLES_CHOICES,
        required=False
    )

    def validate(self, data):
        # Verifica que se envíe al menos un campo a modificar
        if not data:
            raise serializers.ValidationError(
                'Debe enviar al menos un campo a modificar'
            )
        return data

# Serializer: ReestablecerPasswordSerializer
# Uso: Permite al admin del sistema cambiar la contraseña de cualquier usuario    
class RestablecerPasswordSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=True)
    nuevo_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    confirmar_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, data):
        if data['nuevo_password'] != data['confirmar_password']:
            raise serializers.ValidationError({
                'confirmar_password': 'Las contraseñas no coinciden'
            })

        # El usuario destino llega por id: se carga para poder comparar. Con
        # filter().first() un id inexistente deja usuario en None y sigue siendo
        # la vista quien responde por la identidad.
        usuario = User.objects.filter(pk=data['user_id']).first()
        validar_password(data['nuevo_password'], usuario, campo='nuevo_password')

        return data


class CrearUsuarioSerializer(serializers.Serializer):

    # campos de la entidad User en base de datos
    username = serializers.CharField(required=True, max_length = 150)
    first_name = serializers.CharField(required = True, max_length = 150)
    last_name = serializers.CharField(required = True, max_length = 150)
    email = serializers.EmailField(required=False, allow_blank = True)

    password = serializers.CharField(
        required = True,
        write_only = True,
        style = {'input_type' : 'password'}
    )

    confirmar_password = serializers.CharField(
        required = True, 
        write_only = True,
        style = {'input_type' : 'password'}
    )

    # Campo de rol asignado a nuevo usuario
    rol = serializers.ChoiceField(  
        choices = PerfilUsuario.ROLES_CHOICES,
        required = True
    )

    def validate_username(self, value):
        # Verifica que username no exista ya en el sistema 
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                'Ya existe un usuario con este nombre, por favor cambielo'
            )
        return value
    
    def validate(self, data):
        # validación que las contraseñas coincidan
        if data ['password'] != data['confirmar_password']:
            raise serializers.ValidationError({
                'confirmar_password': 'la contraseña y su confirmación no coinciden'
            })

        # El usuario aún no existe: se construye sin guardar para que
        # UserAttributeSimilarityValidator pueda comparar contra nombre,
        # apellido, usuario y correo.
        tentativo = User(
            username=data.get('username', ''),
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            email=data.get('email', ''),
        )
        validar_password(data['password'], tentativo, campo='password')
        return data
    
    def create(self, validated_data):

        # Extrae campos y los envía al model de Django (estos campos no existen en la estructura del modelo User de dicho framework, fueron añadidos para este sistema)
        rol = validated_data.pop('rol')
        password = validated_data.pop('password')
        validated_data.pop('confirmar_password')

        # Crea user con create_user para que Django hashee contraseña
        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        # Crea el PerfilUsuario vinculado al User recien creado
        PerfilUsuario.objects.create(user=user, rol=rol)
        return user 



# Los serializadores desde esta linea para abajo corresponden al dashboard y al reporte PDF, unicamente para consulta de información

# Serializer: DomReporteSerializer
# Uso: permite la consolidación de toda la información para el reporte PDF

class DomReporteSerializer(serializers.ModelSerializer):
    # Datos del cliente relevantes
    nombre_cliente_detalle = serializers.CharField(
        source='nombre_cliente.nombre_cliente', read_only = True
    )

    # productos del registro DOM - uno o varios - con nombre y cantidad 
    productos = ProductosDomSerializer(many = True, read_only=True)

    # calculo de las cantidades del pedido
    cantidad_pedida_total = serializers.ReadOnlyField()
    cantidad_elaborada_total = serializers.ReadOnlyField()
    cantidad_pendiente_total = serializers.ReadOnlyField()

    # Registro de planeacion con sus respectivos hijos anidados (produccion, tratamiento, almacen)
    registro_planeacion = RegistroPlaneacionSerializer(many = True, read_only = True)

    # Manejo de logica para el reporte de tiempo estimado vs tiempo real ejecutado. logica del calculo en views.py

    tiempo_proyectado_total = serializers.IntegerField(
        read_only = True,
        help_text = 'Tiempo proyectado para la ejecución de este DOM'
    )
    tiempo_real_total = serializers.IntegerField(
        read_only = True, 
        help_text = 'Tiempo total para la ejecución de este DOM'
    )
    diferencia_tiempo = serializers.IntegerField(
        read_only = True,
        help_text = 'Diferencia entre tiempo proyectado vs tiempo real de ejecución de este DOM'
    )
    cumplimiento_tiempo = serializers.ChoiceField(
        choices=['POSITIVO', 'NEUTRO', 'NEGATIVO'],
        read_only = True,
        help_text = 'POSITIVO: tiempo real < tiempo proyectado | NEUTRO: tiempo real = tiempo proyectado | NEGATIVO: tiempo real > tiempo proyectado' 
    )

    cumplimiento_almacen = serializers.CharField(read_only=True)
    cumplimiento_produccion = serializers.CharField(read_only=True)
    cumplimiento_tratamiento = serializers.CharField(read_only=True)
    cumplimiento_despacho = serializers.CharField(read_only=True)
    cumplimiento_consolidado_dom = serializers.CharField(read_only=True)

    class Meta: 
        model = Dom
        fields = [

            #PK
            'dom_id',

            # Etapa 0 
            'fecha_asignacion_dom',
            'nombre_cliente', 
            'nombre_cliente_detalle',
            'descripcion',
            'tipo_estado_dom',
            'fecha_solicitada_cliente',
            'responsable',

            #Etapa 1
            'orden_compra',
            'tiempo_salida_almacen',
            'rentabilidad',
            'campana_venta',
            'numero_cotizacion',
            'numero_factura',
            'dom_relacionado_produccion', 

            #Etapa 6
            'fecha_entrega_pactada',
            'fecha_entrega_planificada',
            'cantidad_empaques',
            'empaque_servicio',
            'tipo_negociacion',
            'fecha_entrega_proyectada',
            'materiales_externos',
            'vehiculo',
            'orden_entrega',
            'notas',
            'novedades_cumplimiento',
            'dom_entregado_ok',
            'dom_liberado_cierre',

            # productos y totales 
            'productos',
            'cantidad_pedida_total',
            'cantidad_elaborada_total',
            'cantidad_pendiente_total',

            # Manejo de lógica tiempo_estimado vs tiempo_real
            "tiempo_proyectado_total",
            "tiempo_real_total",
            "diferencia_tiempo",
            "cumplimiento_tiempo",

            # registros de las etapas 3 a 5 
            'registro_planeacion',
            "cumplimiento_almacen",
            "cumplimiento_produccion",
            "cumplimiento_tratamiento",
            "cumplimiento_despacho",
            "cumplimiento_consolidado_dom",
        ]

        # serializer de PDF solo lectura - objetivo es generación de reporte
        read_only_fields  = fields

# Serializer: ProductoPendienteDashBoardSerializer
# Uso: necesario para la medición de metrica "productos pendiente por categoria" según requerimientos del cliente  

class ProductoPendienteDashBoardSerializer(serializers.Serializer):
    nombre_producto = serializers.CharField(read_only = True)
    cantidad_pendiente = serializers.IntegerField(
        read_only = True,
        help_text='Sumatoria de productos por categoria con fecha entrega <= 15 días'
    )
    doms_involucrados = serializers.IntegerField(
        read_only = True,
        help_text = 'Dom activos con este producto y vencen en <= días'
    )


# Serializer: DashboardSerilizer
# manejo de información relativa al dashboard de la pagína de inicio del aplicativo; nombres de la variables descriptivas (que se está midiendo)

class DashboardSerializer(serializers.Serializer):
    # Resumen global doms
    total_doms = serializers.IntegerField(read_only = True)
    total_doms_activos = serializers.IntegerField(read_only = True)
    total_doms_cerrados = serializers.IntegerField(read_only = True)

    # Doms por etapa - se define de esta manera ára que sea compatible con librerias gráficas de React
    doms_por_etapa = serializers.ListField(
        child = serializers.DictField(),
        read_only = True,
        help_text = 'Lista de objetos por etapa para renderizado de gráfico de métricas'
    )

    # Metricas de producción globales
    cantidad_elaborada_total = serializers.IntegerField(read_only = True)
    cantidad_pendiente_total = serializers.IntegerField(read_only = True)

    # aleta de hecha 
    # Dom's a vencerse en los proximos 7 dias 
    doms_proximos_vencer = DomListSerializer(many = True, read_only = True)
    # Dom's con fecha de entrega ya vencida
    doms_vencidos = DomListSerializer(many = True, read_only = True)

    # Metrica de alto valor para el cliente: sumatoria de productos con pendientes por fabricar en los proximos 15 día según categoría de producto. 
    productos_pendientes_15_dias = ProductoPendienteDashBoardSerializer(
        many = True,
        read_only = True
    )

    # metricas para determinar cumplimiento de planeación, produccion, almacen, tratamiento y 
    cumplimiento_almacen = serializers.CharField(read_only=True)
    cumplimiento_produccion = serializers.CharField(read_only=True)
    cumplimiento_tratamiento = serializers.CharField(read_only=True)
    cumplimiento_despacho = serializers.CharField(read_only=True)
    cumplimiento_consolidado = serializers.CharField(read_only=True)

# InformeCumplimientoPlaneación Serializer
# Uso: informe del porcentaje de DOM's que cumplieron con lo solicitado en planeación; se mide el cumplimiento de las 3 etapas "hijas" en los terminos de configuración de este sistema (produccion, almacen, tratamiento fitosanitario)

class ResumenCumplimientoEtapaSerializer(serializers.Serializer):

    # Serializer auxiliar para mostrar el resumen de cumplimiento por etapas respecto de cada DOM
    dom_id = serializers.IntegerField(read_only = True)
    nombre_cliente = serializers.CharField(read_only = True)

    # Almacen
    almacen_segun_planeacion = serializers.BooleanField(read_only = True)
    novedad_almacen = serializers.CharField(read_only = True,
    allow_null = True)
    
    # Producción
    produccion_segun_planeacion = serializers.BooleanField(read_only = True)
    novedad_produccion =serializers.CharField(read_only = True, allow_null = True)

    # Tratamiento 
    tratamiento_segun_planeacion = serializers.BooleanField(read_only = True)
    novedad_tratamiento = serializers.CharField(read_only = True, allow_null = True)

    # cumplimiento del DOM de la planeación establecida. Solo TRUE si las 3 etapas se cumplieron según planeación
    cumplimiento_global_registro = serializers.BooleanField(read_only = True)

# Serializer: InformeCumplimientoPlaneacionSerializer
# Uso: manejo de información para generación de informes (PDF/EXCEL/INFORME)
class InformeCumplimientoPlaneacionSerializer(serializers.Serializer):
    # Parametros de fecha del informe
    fecha_inicio = serializers.DateField(read_only = True)
    fecha_fin = serializers.DateField(read_only = True)

    # Totales del periodo 
    total_registros_evaluados = serializers.IntegerField(read_only = True)
    total_segun_planeacion = serializers.IntegerField(
        read_only = True,
        help_text = 'registros donde etapas almacen / producción / tratamiento fue cumplido según planeación'
    )
    total_no_segun_planeacion = serializers.IntegerField (read_only = True, help_text = 'Registros donde en al menos una etapa no se cumplio con planeacion')
    porcentaje_cumplimiento = serializers.FloatField(
        read_only = True,
        help_text = 'Porcentaje de DOMs que cumplieron con planeación establecida para produccion, almacen, tratamiento termico'
    )

    cumplimiento_almacen = serializers.CharField(read_only=True)
    cumplimiento_produccion = serializers.CharField(read_only=True)
    cumplimiento_tratamiento = serializers.CharField(read_only=True)
    cumplimiento_despacho = serializers.CharField(read_only=True)
    cumplimiento_consolidado = serializers.CharField(read_only=True)

    # Detalle por registro
    registros_segun_planeacion = ResumenCumplimientoEtapaSerializer(many = True, read_only = True)
    registros_no_segun_planeacion = ResumenCumplimientoEtapaSerializer(many = True, read_only = True)


# Serializer: ResumenDespachoDomSerializer
# Uso: una fila del informe de despacho. Propio y no compartido con el informe de
# cumplimiento porque la unidad es distinta: aquí la fila es un DOM, allá una
# planeación. Por eso no tiene columnas de almacén, producción ni tratamiento.

class ResumenDespachoDomSerializer(serializers.Serializer):
    dom_id = serializers.IntegerField(read_only = True)
    nombre_cliente = serializers.CharField(read_only = True)
    fecha_entrega_pactada = serializers.DateField(read_only = True, allow_null = True)

    # Etiqueta del predicado, no un booleano: CUMPLIÓ, NO_CUMPLIÓ o PENDIENTE.
    veredicto_despacho = serializers.CharField(read_only = True)
    novedad = serializers.CharField(read_only = True, allow_null = True)


# Serializer: InformeDespachoSerializer
# Uso: Informeción respecto de los DOMs que cumplieron con la planeación establecida para despachos vs los que no cumplieron

class InformeDespachoSerializer(serializers.Serializer):
    # Parametros de fecha informe
    fecha_inicio = serializers.DateField(read_only = True)
    fecha_fin = serializers.DateField(read_only = True)

    # Totales del periodo. Evaluable es el DOM donde alguien respondió si se
    # entregó según lo planeado; el pendiente sale del denominador y se muestra
    # al lado, porque no haber contestado todavía no es haber incumplido.
    total_doms_en_rango = serializers.IntegerField(read_only = True)
    total_cumplieron = serializers.IntegerField(read_only = True)
    total_no_cumplieron = serializers.IntegerField(read_only = True)
    total_pendientes = serializers.IntegerField(read_only = True, help_text = 'Doms que aún no tienen fecha de entrega planificada quedan excluidos de este calculo')
    total_evaluables = serializers.IntegerField(read_only = True, help_text = 'Cumplieron + no cumplieron. Es el denominador del porcentaje')
    porcentaje_cumplimiento = serializers.FloatField(read_only = True, help_text = 'Porcentaje de cumplimiento sobre los DOMs evaluables, no sobre el total del rango' )

    # Ningún rango de fechas puede incluirlos: sin fecha de entrega pactada no hay
    # por dónde filtrarlos. Se declara para que la exclusión deje de ser invisible.
    total_doms_sin_fecha_pactada = serializers.IntegerField(read_only = True)

    # Etiqueta de conjunto para todo el periodo.
    cumplimiento_despacho = serializers.CharField(read_only=True)

    # Una sola lista: cada fila lleva su etiqueta y la pantalla decide cómo
    # agrupar. Con cinco etiquetas posibles, repartirlas en cubos obliga a elegir
    # dónde va un pendiente y la pantalla tendría que volver a unirlas.
    registros = ResumenDespachoDomSerializer(many = True, read_only = True)

class InformeAuditoriaSerializer(serializers.Serializer):

    # paramteros del informe 
    fecha_inicio = serializers.DateField(read_only = True)
    fecha_fin = serializers.DateField(read_only = True)
    dom_id = serializers.IntegerField(read_only = True, allow_null = True, help_text = 'Filtrar por DOM')
    usuario_filtro = serializers.CharField(read_only = True, allow_null = True, help_text = 'Filtrar por usuario')

    # Total de acciones realizadas
    total_acciones = serializers.IntegerField(read_only = True)
    total_creaciones = serializers.IntegerField(read_only = True)
    total_ediciones = serializers.IntegerField(read_only = True)
    total_bloqueos = serializers.IntegerField(read_only = True)
    total_eliminaciones = serializers.IntegerField(read_only = True)
    total_desbloqueos = serializers.IntegerField(read_only = True)

    # Detalle cronologico de acciones 
    acciones = AuditoriaDomSerializer(many = True, read_only = True)

# FIN DEL ARCHIVO    

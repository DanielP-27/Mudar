from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.options import Options
from django.db.models import Sum

# Esta consante maneja la logica de +120 minutos si en el campo horas extras en planeación es marcado como TRUE
MINUTOS_HORAS_EXTRAS = 120

# Tabla listado de clientes
class Cliente (models.Model):
    # Listado maestro de los clientes de la organización

    cliente_id = models.AutoField(primary_key=True, verbose_name='Codigo cliente')
    nombre_cliente = models.CharField(max_length=200, verbose_name='Nombre cliente')
    nit = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name='NIT')
    activo = models.BooleanField(default=True, db_index=True, verbose_name='Cliente activo')

    # Auditoria 
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='cliente_creado')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    # las clases meta corresponde a la configuración y conexión con la base de datos
    class Meta:
        db_table = 'clientes'
        verbose_name = 'cliente'
        verbose_name_plural = 'clientes'
        ordering = ['nombre_cliente']

    def __str__(self):
        return self.nombre_cliente


# Tabla Listado familia de productos - necesaria por que cada producto pertenece a una familia, importante para buen diseño Front

class FamiliaProducto(models.Model):
    familia_id = models.AutoField(primary_key=True, verbose_name='Código familia') 
    nombre_familia = models.CharField(max_length=100, verbose_name='Nombre familia')
    activo = models.BooleanField(default=True, db_index=True, verbose_name='Familia activa')

    # Auditoria 
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='familia_creada_por')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'familias_producto'
        verbose_name = 'Familia de Producto'
        verbose_name_plural = 'Familias de Producto'
        ordering = ['nombre_familia']
    
    def __str__(self):
        return self.nombre_familia


# Tabla Listado de productos
class Productos(models.Model):

    # Listado maestro con los productos de la organización

    producto_id = models.AutoField(primary_key=True, verbose_name='Código de producto')
    nombre_producto = models.CharField (max_length=200, verbose_name='Nombre del producto')
    familia_producto = models.ForeignKey(FamiliaProducto, on_delete=models.RESTRICT, related_name='productos', verbose_name='Familia de Producto', null=True, blank=True)
    tiempo_produccion_unitario= models.IntegerField(verbose_name='Tiempo de producción de una unidad en minutos')
    activo=models.BooleanField(default=True, db_index=True, verbose_name='Producto_activo')

    # Auditoria 

    producto_creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='producto_creado')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'productos'
        verbose_name = 'producto'
        verbose_name_plural = 'productos'
        ordering = ['nombre_producto']

    def __str__(self):
        return f'{self.nombre_producto} ({self.tiempo_produccion_unitario})'
    
    def positive(self):
        # función que verifica que el tiempo_produccion_unitario sea positivo siempre

        if self.tiempo_produccion_unitario <= 0:
            raise ValidationError ({'El tiempo de producción unitario debe ser mayor a 0'})


# Tabla para el manejo de turnos (necesario para el manejo y de diferentes datos)
class Turno(models.Model):
    # Esta tabla se crea principalmente ante la necesidad de establecer un tiempo total por turno para la medición de ciertas metricas dentro del sistema.   
    
    turno_id = models.AutoField(primary_key=True, verbose_name = 'código del turno')
    nombre_turno = models.CharField(max_length=100, verbose_name='Nombre del turno')
    minutos_totales = models.IntegerField(verbose_name='Minutos totales del turno', help_text='Incluir tiempo de duración total del turno en minutos')
    activo = models.BooleanField(default=True, db_index=True, verbose_name = 'Turno activo')

    # Auditoria 

    turno_creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='turno_creado')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta: 
        db_table = 'turnos'
        verbose_name = 'Turno'
        verbose_name_plural = 'Turnos'
        ordering = ['turno_id']

    def __str__(self):
        return f'{self.nombre_turno} ({self.minutos_totales} min)'
    
    def positive(self):
        # función que verifica que el tiempo total del turno siempre sea negativo

        if self.minutos_totales <= 0: 
            raise ValidationError ({'los minutos del turno deben ser mayores a 0'})
        
# Clase donde se valida numero de operarios por turno y si se trabajan horas extras (+120 minutos en turno)

class RegistroTurnoDia(models.Model):
    OPCIONES_MINUTOS = [(480, '8 horas (480 min)'), (600, '10 horas (600 min)')]

    turno = models.ForeignKey(Turno, on_delete=models.RESTRICT, related_name='registros_diarios', verbose_name='Turno')
    fecha = models.DateField(verbose_name='Fecha del turno', help_text='Fecha en que se registran los operarios para este turno')
    numero_operarios = models.IntegerField(verbose_name='Número de operarios', help_text='Total de operarios disponibles en este turno para esta fecha')
    minutos_totales = models.IntegerField(choices=OPCIONES_MINUTOS, default=480, verbose_name='Duración del turno', help_text='Duración total del turno en minutos')
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='turnos_dia_registrados')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'registros_turno_dia'
        verbose_name = 'Registro de turno del día'
        verbose_name_plural = 'Registros de turno del día'
        unique_together = ('turno', 'fecha')
        ordering = ['-fecha', 'turno']

    def __str__(self):
        return f'{self.turno.nombre_turno} — {self.fecha} — {self.numero_operarios} operarios — {self.minutos_totales} min'

# Tabla para el manejo de los listados predefinidos que se encuentran dentro del formato. A diferencia de Clientes, productos y turnos, No necesitan una tabla por separado para su manejo.

class ListaPredefinida(models.Model):
     TIPO_CHOICES = [
        ('RESPONSABLE', 'Responsables'),
        ('LIDER_PLANTA', 'Líderes de Planta'),
        ('LIDER_ALMACEN', 'Líderes de Almacén'),
        ('TIPO_ESTADO_DOM', 'Tipos de Estado DOM'),
        ('OBJETIVO_PLANEACION', 'Objetivos de Planeación'),
        ('TIPO_MADERA', 'Tipos de Madera'),
        ('EMPAQUE_SERVICIO', 'Tipos de Empaque/Servicio'),
        ('TIPO_NEGOCIACION', 'Tipos de Negociación'),
    ]
     
     lista_id=models.AutoField(primary_key=True, verbose_name='codigo del listado')
     tipo = models.CharField(max_length=50, choices=TIPO_CHOICES, verbose_name='Tipo de Listado', db_index=True)
     nombre = models.CharField(max_length=200, verbose_name='Nombre',help_text='Texto que ve el usuario')
     activo = models.BooleanField(default=True, verbose_name='Activo', db_index=True)

    # Elementos de auditoria para control de cambios 
     creado_por = models.ForeignKey(User,on_delete=models.RESTRICT, related_name='listas_creadas', verbose_name='Creado Por')
     fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
     
     class Meta:
         db_table='lista_predefinida'
         verbose_name='Lista Predefinida'
         verbose_name_plural='Listas Predefinidas'
         ordering = ['nombre']
         indexes = [
            models.Index(fields=['tipo', 'activo']),
        ]
        
     def __str__(self):
        return f"{self.get_tipo_display()} - {self.nombre}"
    
     @classmethod
     def get_opciones(cls, tipo, activos_solo=True):
        
        #Método helper para obtener opciones de un catálogo
        
        queryset = cls.objects.filter(tipo=tipo)
        if activos_solo:
            queryset = queryset.filter(activo=True)
        return queryset.order_by('nombre')


# Tabla correspondiente a los registros DOM (entidad o tabla principal del sistema) separación del proceso productivo en 6 etapas diferentes.
 
class Dom(models.Model):

    # las etapas 2 a 5 se deben manejar como clases separadas en razón a la necesidad de manejar multiples registros, los cuales se referenciarán a través de FK Dentro de la clase DOM, la clase en la cual nos encontramos tendrá la estructura de creación y etapas 1 y 6.

    # llave primaria 
    dom_id = models.AutoField(primary_key=True, verbose_name='Consecutivo DOM')


    # Etapa 0: creación del DOM 
    fecha_asignacion_dom = models.DateField(auto_now_add=True, verbose_name='Fecha asignación DOM')
    nombre_cliente=models.ForeignKey(Cliente, on_delete=models.RESTRICT, related_name='doms', verbose_name='Cliente')
    descripcion=models.TextField(blank=True, null=True, verbose_name='Descripción')
    tipo_estado_dom = models.CharField(max_length=100, verbose_name='Tipo o Estado del DOM', db_index=True, help_text='Referencia a ListaPredifinida tipo=TIPO:ESTADO:DOM')
    fecha_solicitada_cliente = models.DateField(verbose_name= 'Fecha de entrega solicitada por el cliente')
    responsable = models.CharField(max_length=200, verbose_name='Nombre Responsable', help_text='Referencia a ListaPrededefinida tipo=RESPONSABLE')
    
    # Etapa 1 gestión comercial y diseño
    orden_compra=models.CharField(max_length=50, blank=True, null=True, verbose_name='Número orden de compra')
    tiempo_salida_almacen=models.IntegerField(blank=True, null=True, verbose_name='Tiempo de salida de almacen (minutos)')
    rentabilidad=models.IntegerField(blank=True, null=True, verbose_name='Rentabilidad (%)', help_text='Porcentaje de rentabilidad')
    campana_venta = models.BooleanField(null=True, blank=True, default=None, verbose_name='DOM generado en campaña de venta')
    numero_cotizacion=models.CharField(max_length=50, blank=True, null=True, verbose_name='Numero de Cotización')
    numero_factura=models.IntegerField(blank=True, null=True, verbose_name='Número Factura de venta')
    # Bloqueo etapa
    dom_relacionado_produccion=models.BooleanField(default=False, verbose_name='Validación etapa 1', help_text='Seleccione si unicamente si ya ha finalizado esta etapa, no podrá realizar cambios de forma posterior')

    # Etapa 6 planeación despachos y servicios externos 

    fecha_entrega_pactada = models.DateField(blank=True, null=True, verbose_name='Fecha de entrega pactada')
    fecha_entrega_planificada = models.DateField(blank=True, null=True, verbose_name='Fecha de entrega planificada')
    cantidad_empaques = models.IntegerField(blank=True, null=True, verbose_name='Fecha de entrega proyectada')
    empaque_servicio = models.CharField(max_length=70, blank=True, null=True, verbose_name='Empaque/Servicio', help_text='Elegir el tipo de servicio que se ofrece al cliente')
    tipo_negociacion = models.CharField(max_length=70, blank=True, null=True, verbose_name='Tipo de Negociacion', help_text='Elegir el tipo de negociación pactada con el cliente')
    fecha_entrega_proyectada = models.DateField(blank=True, null=True, verbose_name='Fecha de entrega proyectada')
    materiales_externos = models.BooleanField(default=False, verbose_name='Este DOM requiere materiales externos (SI/NO)')
    vehiculo = models.CharField (max_length=100, blank=True, null=True, verbose_name='Vehiculo en el cual se realziará el despacho')
    orden_entrega = models.CharField(max_length=100, blank=True, null=True, verbose_name='Orden de entrega')
    notas = models.TextField(blank=True, null=True, verbose_name = 'Información relevante para el despacho', help_text='Incluya en este apartado información relevante respescto de este DOM Enchargados de servicios externos, notas o comentarios relevantes para el despacho, etc.')
    novedades_cumplimiento = models.TextField(blank=True, null=True, verbose_name='Novedades en el cumplimiento del despacho', help_text='Incluya en este campo información relevante respecto de cualquier novedad o incidencia que se ha presentando en el despacho de los productos')
    dom_entregado_ok = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿DOM entregado según planeación?')
    # Bloqueo Etapa 
    dom_liberado_cierre = models.BooleanField(default=False, verbose_name='¿DOM liberado para cierre', help_text='Marque esta casilla unicamente si el DOM ya ha sido despacho y entregado. Una vez marcada la opción SI, no se podrán realziar cambios')

    # Auditoria de creación dom 
    
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='doms_creados', verbose_name='Creado Por')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha Creación')
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name='Fecha Modificación')

    class Meta:
        db_table = 'doms'
        verbose_name = 'DOM'
        verbose_name_plural = 'DOMS'
        ordering = ['-dom_id']

    def __str__(self):
        return f"DOM #{self.dom_id} - {self.nombre_cliente}"
    
    # las siguientes propiedades se calculan respecto del global o total de productos del DOM por esta razon se encuentran dentro del scope de la tabla DOM 

    @property
    def cantidad_elaborada_total(self):
        # propiedad para calcular cantidades elaboradas de todos los registros de produccion (ya sea 1 o N)
        from server.models import RegistroProduccion
        return RegistroProduccion.objects.filter(registro_planeacion__dom=self).aggregate(total=Sum('cantidad_elaborada')) ['total'] or 0
    
    @property
    def cantidad_pedida_total(self):
        # Para cuando sea necesario, suma todos los tipos de producto del DOM
        return self.productos.aggregate(total=Sum('cantidad_pedido')) ['total'] or 0
    
    @property
    def cantidad_pendiente_total(self):
        pedido = self.cantidad_pedida_total
        if pedido:
            return pedido - self.cantidad_elaborada_total
        return None
    
    def etapa_1_bloqueada(self):
        return self.dom_relacionado_produccion
    
    def etapa_6_bloqueada(self):
        return self.dom_liberado_cierre


class ProductosDom(models.Model):
    
    # Esta clase permite registrar uno o más productos por DOM, según necesidades de cada registro particular

    productoDom = models.ForeignKey(Dom, on_delete=models.CASCADE, related_name='productos', verbose_name='DOM')
    tipo_producto = models.ForeignKey(Productos, on_delete=models.RESTRICT, related_name='dom_productos', verbose_name='Tipo de Producto')
    cantidad_pedido = models.IntegerField(verbose_name='Cantidad del pedido')

    class Meta: 
        db_table = 'dom_productos'
        verbose_name = 'Producto del DOM'
        verbose_name_plural = 'Productos del DOM'
        unique_together = ('productoDom', 'tipo_producto')
    
    def __str__(self):
        return f"DOM # {self.productoDom.dom_id} - {self.tipo_producto.nombre_producto} x {self.cantidad_pedido}"
    

# clase correspondiente a etapa 2 proceso Mudar, Planeación de la producción

class RegistroPlaneacion(models.Model):

    # está clase permite múltiples registros de planeación, con su correspondientes registros adicionales (producción o almacén según cada registro DOM en particular)

    # Líneas 257 a 262 llave foraneas de otras tablas
    dom = models.ForeignKey(Dom, on_delete=models.CASCADE, related_name='registro_planeacion', verbose_name='No. DOM')
    numero_registro = models.IntegerField(verbose_name='Número de Registro')

    turno = models.ForeignKey(Turno, on_delete=models.RESTRICT, related_name='planeaciones', blank=True, null=True, verbose_name='Turno')

    # campos correspondientes a la etapa 2

    fecha_planeacion = models.DateField(blank=True, null=True, verbose_name='Fecha planeada para esta producción')
    materia_prima_disponible = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Matería Prima Disponible')
    orden_produccion = models.IntegerField(blank=True, null=True, verbose_name='Orden de producción en fecha planeada')
    lider_produccion=models.CharField(max_length=50, blank=True, null=True, verbose_name='Lider de Producción')
    objetivo_planeacion = models.CharField(max_length=50, blank=True, null=True, verbose_name="objetivo de planeación inicial")
    tablilla_madera = models.CharField(max_length=50, blank=True, null=True, verbose_name='¿Producto con madera o tablilla larga?')
    encartonar = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Encartonar?')
    grafado_fundas = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Productos requieren grafado y/o elaboración fundas?')
    control_tiempo = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Producto lleva control de tiempo de corte y ensamble en armadora?')
    orden_tratamiento=models.IntegerField(default=1, verbose_name='Orden Tratamiento')
    lider_almacen = models.CharField(max_length=50, blank=True, null=True, verbose_name='Lider de almacén')
    cliente_recoge = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Cliente recoge productos?')
    mudar_entrega = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Mudar de Colombia entrega productos?')
    tratamiento_termico = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Tratamiento térmico realizado?')
    sello_ica = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Productos cuentan ya con sello ICA?')
    peso = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Productos requieren ser pesados?')
    
    # condicional bloqueo etapa 
    planeacion_completa = models.BooleanField(default=False, verbose_name='¿Planeación completada?', help_text='En el evento en que seleccione si, no se permitirá más modificaciones a esta etapa')

    # auditoria de cambios
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='planeaciones_creadas'
        )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'registros_planeacion'
        verbose_name = 'Registro de Planeación'
        verbose_name_plural = 'Registros de Planeación'
        unique_together = ('dom', 'numero_registro')
        ordering = ['dom', 'numero_registro']

    def __str__(self):
        return f"Planeación #{self.numero_registro} - DOM #{self.dom.dom_id}"
    
    # Propiedades calculadas 

    @property
    def capacidad_turno_dia(self):
        if not self.turno or not self.fecha_planeacion:
            return None
        registro = RegistroTurnoDia.objects.filter(
            turno=self.turno,
            fecha=self.fecha_planeacion
        ).first()
        if not registro:
            return None
        return registro.minutos_totales * registro.numero_operarios

    @property
    def tiempo_proyectado(self):
        total = 0
        for pp in self.productos_planeacion.select_related('dom_producto__tipo_producto').all():
            if pp.cantidad_proyectada and pp.dom_producto:
                total += pp.cantidad_proyectada * pp.dom_producto.tipo_producto.tiempo_produccion_unitario
        return total or None
    
    @property
    def sumatoria_tiempo_asignado_turnos(self):
        if not self.fecha_planeacion or not self.turno:
            return None
        planeaciones = RegistroPlaneacion.objects.filter(
            fecha_planeacion=self.fecha_planeacion,
            turno=self.turno,
        ).prefetch_related('productos_planeacion__dom_producto__tipo_producto')
        total = 0
        for p in planeaciones:
            operarios = p.numero_operarios_turno or 1
            for pp in p.productos_planeacion.all():
                if pp.cantidad_proyectada and pp.dom_producto:
                    total += pp.cantidad_proyectada * pp.dom_producto.tipo_producto.tiempo_produccion_unitario * operarios
        return total
    
    @property
    def tiempo_restante_dia(self):
        capacidad = self.capacidad_turno_dia
        sumatoria = self.sumatoria_tiempo_asignado_turnos
        if capacidad is None or sumatoria is None:
            return None
        return capacidad - sumatoria
    
    @property
    def cantidad_elaborada(self):
        return self.registros_produccion.aggregate(
            total=Sum('cantidad_elaborada')
        )['total'] or 0
    
    @property
    def cantidad_pendiente(self):
        total = sum(
            pp.cantidad_pendiente for pp in self.productos_planeacion.all()
            if pp.cantidad_pendiente is not None
        )
        return total or None
    
    
    def tiempo_disponible_turno(self, tiempo_nuevo, excluir_registro_id=None):
        capacidad = self.capacidad_turno_dia
        if capacidad is None:
            return None, None
        planeaciones = RegistroPlaneacion.objects.filter(
            fecha_planeacion=self.fecha_planeacion,
            turno=self.turno,
        ).prefetch_related('productos_planeacion__dom_producto__tipo_producto')
        if excluir_registro_id:
            planeaciones = planeaciones.exclude(id=excluir_registro_id)
        sumatoria = 0
        for p in planeaciones:
            for pp in p.productos_planeacion.all():
                if pp.cantidad_proyectada and pp.dom_producto:
                    sumatoria += pp.cantidad_proyectada * pp.dom_producto.tipo_producto.tiempo_produccion_unitario
        disponible_actual = capacidad - sumatoria
        return disponible_actual, disponible_actual - tiempo_nuevo

    def cantidad_disponible_produccion(self, producto_planeacion, cantidad_nueva, excluir_registro_id=None):
        registros = RegistroProduccion.objects.filter(
            producto_planeacion=producto_planeacion
        )
        if excluir_registro_id:
            registros = registros.exclude(id=excluir_registro_id)
        elaborada = registros.aggregate(total=Sum('cantidad_elaborada'))['total'] or 0
        return producto_planeacion.dom_producto.cantidad_pedido - elaborada - cantidad_nueva

    @property
    def numero_operarios_turno(self):
        if not self.turno or not self.fecha_planeacion:
            return None
        registro = RegistroTurnoDia.objects.filter(
            turno=self.turno,
            fecha=self.fecha_planeacion
        ).first()
        return registro.numero_operarios if registro else None

    # Bloqueo etapa
    def etapa2_bloqueada(self):
        return self.planeacion_completa


class ProductoPlaneacion(models.Model):

    registro_planeacion = models.ForeignKey(
        RegistroPlaneacion,
        on_delete=models.CASCADE,
        related_name='productos_planeacion',
        verbose_name='Registro de Planeación'
    )
    dom_producto = models.ForeignKey(
        ProductosDom,
        on_delete=models.RESTRICT,
        related_name='productos_planeacion',
        verbose_name='Producto del DOM'
    )
    cantidad_proyectada = models.IntegerField(
        blank=True, null=True,
        verbose_name='Cantidad proyectada a elaborar'
    )

    class Meta:
        db_table = 'productos_planeacion'
        verbose_name = 'Producto de Planeación'
        verbose_name_plural = 'Productos de Planeación'
        unique_together = ('registro_planeacion', 'dom_producto')

    def __str__(self):
        return f"Planeación #{self.registro_planeacion.numero_registro} - {self.dom_producto.tipo_producto.nombre_producto} x {self.cantidad_proyectada}"

    @property
    def cantidad_elaborada(self):
        return self.registros_produccion.aggregate(
            total=Sum('cantidad_elaborada')
        )['total'] or 0

    @property
    def cantidad_pendiente(self):
        if self.cantidad_proyectada:
            return self.cantidad_proyectada - self.cantidad_elaborada
        return None


# Clase correspondiente a la etapa 3 - almacen

class RegistroAlmacen(models.Model):
    
    # configuración para permitir nuevo registro producción ante nuevo registro planeacion

    registro_planeacion = models.ForeignKey(RegistroPlaneacion, on_delete=models.CASCADE, related_name='registros_almacen',verbose_name='Registro Planeacion')
    
    numero_registro = models.IntegerField(verbose_name='Número de Registro')

    # campos de formulario correspondiente a la etapa 3

    materias_primas = models.BooleanField(null=True, blank=True, default=None, verbose_name='Materias Primas Internas Procesadas')

    novedad_cumplimiento_almacen = models.TextField(blank=True, null=True, verbose_name='Novedad cumplimiento almacen', help_text='Registre aquí cualquier novedad relevante respecto de las actividades desarrolladas en dentro de las labores de almacen para este DOM')
    dom_realizado_planeacion = models.BooleanField(default=False, verbose_name= '¿Actividades de almacen realizadas según planeacion de la producción?')

    # Bloquep de etapa 3 
    materias_liberadas = models.BooleanField(default=False, verbose_name='¿Materías primas liberadas en su totalidad para este DOM?', help_text='Marque está esta opcion como SI unicamente en el evento en que la totalidad de materias primas hubieren sido liberadas para producción, no podrá realizar cambios de forma posterior')
    
    # auditoría control de cambios

    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='almacenes_creados'
        )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'registros_almacen'
        verbose_name = 'Registro de Almacén'
        verbose_name_plural = 'Registros de Almacén'
        unique_together = ('registro_planeacion', 'numero_registro')

    def __str__(self):
        return f"Almacén #{self.numero_registro} - Planeación #{self.registro_planeacion.numero_registro}"
    
    @property
    def tarea_planeacion(self):
        # refleja objetivo de planeación inicial
        return self.registro_planeacion.objetivo_planeacion
    
    def etapa_3_bloqueada(self):
        # cambio del atributo materias liberadas bloquea etapa
        return self.materias_liberadas
    
# Clase correspondiente al registro de producción

class RegistroProduccion(models.Model):
    # Configuración para permitir múltiples registros de planeacion, cuando se realicen producciones parciales

    registro_planeacion = models.ForeignKey(
        RegistroPlaneacion,
        on_delete=models.CASCADE,
        related_name='registros_produccion',
        verbose_name='Registro Planeacion'
    )
    producto_planeacion = models.ForeignKey(
        ProductoPlaneacion,
        on_delete=models.RESTRICT,
        related_name='registros_produccion',
        verbose_name='Producto de Planeación',
        blank=True, null=True
    )

    numero_registro = models.IntegerField(verbose_name='Numero de Registro')

    # campos de formulario correspondiente a la etapa de producción 

    cantidad_elaborada = models.IntegerField(blank=True, null=True, verbose_name='Cantidad Elaborada')
    minutos_asignados = models.IntegerField(blank=True, null=True, verbose_name='Minutos asignados DOM', help_text='Este campo se comoleta automaticamente al momento de darle finalizar al cronometro')
    numero_personas_asignadas = models.IntegerField(blank=True, null=True, verbose_name='Número de personas asignadas a la producción de este DOM')
    novedad_cumplimiento_produccion = models.TextField(blank=True, null=True, verbose_name='Novedad Cumplimiento Producción', help_text='Registre aquí cualquier novedad relevante respecto de las actividades desarrolladas en dentro de las labores de produccion para este DOM')
    segun_planeacion = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Actividades de producción realizadas según planeación de este DOM?')
    produccion_no_completada = models.TextField(blank = True, null = True, verbose_name='Razones por la cuales la producción no ha podido ser realizada según planeación', help_text='Incluya en este toda la información relevante respecto del por que la producción no ha podido ser finalizada según planeación realizada, si la producción ha sido realizada según planeación, ignore este campo' )

    # Bloqueo etapa 4 

    cierre_produccion = models.BooleanField(default=False, verbose_name='¿Cerrar producción respecto de está planeación?', help_text='Marque esta opción como SI independimiente de si la producción ha podido ser realizada o no según planeación de la producción')
    
    # Control de auditoria
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='producciones_creadas'
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'registros_produccion'
        verbose_name = 'Registro de Producción'
        verbose_name_plural = 'Registros de Producción'
        unique_together = ('registro_planeacion', 'numero_registro')
        ordering = ['registro_planeacion', 'numero_registro']

    def __str__(self):
        return f"Producción #{self.numero_registro} - Planeación #{self.registro_planeacion.numero_registro}"
    
    # Propiedades calculadas para datos que requieren calculo automatico 

    @property
    def tarea_asignada_planeacion(self):
        # Hereda contenido de atributo objetivo_planeación de la clase RegistroPlaneacion
        return self.registro_planeacion.objetivo_planeacion
    
    @property
    def tiempo_elaboracion_produccion(self):
        if self.cantidad_elaborada and self.producto_planeacion:
            return self.cantidad_elaborada * self.producto_planeacion.dom_producto.tipo_producto.tiempo_produccion_unitario
        return None
    
    @property
    # Calcula tiempo de producción proyectado o esperado según número de unidades a propudcir y cantidad de trabajadores disponible
    def minutos_hombre_produccion_dom(self):
        if self.minutos_asignados and self.numero_personas_asignadas:
            return self.minutos_asignados * self.numero_personas_asignadas
        return None
    
    @property
    def minutos_restantes_dom(self):
        t_elab = self.tiempo_elaboracion_produccion
        m_hombre = self.minutos_hombre_produccion_dom
        if t_elab is not None and m_hombre is not None:
            return t_elab - m_hombre
        return None
    
    def etapa_4_bloqueada(self):
        return self.cierre_produccion
    
# Clase para registro tiempos de produccion ('Cronometro')

class RegistroTiempoProduccion(models.Model):
    # Esta clase permite el funcionamiento a nivel Back del cronometro que mide inicio - pausa - finalización de tiempos de produccion

    ESTADO_CHOICES = [
        ('EN_CURSO', 'En Curso'),
        ('PAUSADO', 'Pausado'),
        ('FINALIZADO', 'Finalizado'), 
    ]

    registro_produccion = models.ForeignKey(
        RegistroProduccion, 
        on_delete=models.CASCADE,
        related_name='registros_tiempo',
        verbose_name='Registro Produccion'
    )

    # Configuracion Timestamps

    inicio = models.DateTimeField(verbose_name='Inicio')
    fin = models.DateTimeField(blank=True, null=True, verbose_name='Fin')

    # Atribiuto de ESTADO_CHOICES

    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='EN_CURSO', verbose_name='Estado')

    # Calculo de minutos en pausa del cronometro y de los minutos totales una vez se selecciona la opción FINALIZADO

    total_segundos_pausados = models.IntegerField(default=0, verbose_name='Total segundos pausados')
    minutos_totales = models.IntegerField(blank=True, null=True, verbose_name='Minutos totales', help_text='calculo se obtiene al darle finalizado a la producción')

    # auditoria 

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Usuario'
    )

    class Meta:
        db_table = 'registros_tiempo_produccion'
        verbose_name = 'Registro Tiempo Producción'
        verbose_name_plural = 'Registros Tiempo Producción'
        ordering = ['-inicio']

    def __str__(self):
        return f"Tiempo {self.estado} - {self.minutos_totales or 0} min"
    
    def calcular_minutos_totales(self):
        # Calculo de minutos excluyendo pausas
        if self.fin:
            delta = self.fin - self.inicio
            return int((delta.total_seconds() - self.total_segundos_pausados) / 60)
        return None
    
    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)
       
        # Cuando se seleccione la opción FINALIZADO, actualiza el atributo minutos_asignados_dom

        if self.estado == 'FINALIZADO' and self.minutos_totales:
            self.registro_produccion.minutos_asignados = self.minutos_totales
            self.registro_produccion.save()
        

# Clase para el manejo de pausas del cronometro

class PausaTiempoProduccion(models.Model):
    # se registra cada pausa individual 

    registro_tiempo = models.ForeignKey(RegistroTiempoProduccion, on_delete=models.CASCADE, related_name='pausas', verbose_name='Registro tiempo de pausas')

    inicio_pausa = models.DateTimeField(verbose_name='Inicio Pausa')

    fin_pausa = models.DateTimeField(blank=True, null=True, verbose_name='Fin pausa', help_text='resultado se obtiene al momento de finalizar la pausa')

    segundos_pausados = models.IntegerField(blank=True, null=True, verbose_name='Segundos de Pausa')

    class Meta:
        db_table = 'pausas_tiempo_produccion'
        verbose_name = 'Pausa Tiempo Producción'
        verbose_name_plural = 'Pausas Tiempo Producción'
        ordering = ['inicio_pausa']

    def __str__(self):
        return f"Pausa: {self.segundos_pausados or '?'} seg"
    
    def save(self, *args, **kwargs):
        # Calculo automatico de minutos en pausa una vez se finaliza la misma

        if self.fin_pausa and self.inicio_pausa:
            delta = self.fin_pausa - self.inicio_pausa
            self.segundos_pausados = int(delta.total_seconds())
        super().save(*args, **kwargs)

# Clase correspondiente al manejo de datos de tratamiento termico

class RegistroTratamiento(models.Model):

    # Configuración para permitir múltiples registros de planeacion,

    registro_planeacion = models.ForeignKey(
        RegistroPlaneacion,
        on_delete=models.CASCADE, 
        related_name='registros_tratamiento', 
        verbose_name='Registro Planeacion'
    )

    numero_registro = models.IntegerField(
        verbose_name='Numero de Registro'
    )

    # atributos correspondientes a los campos de la etapa de tratamiento fitosanitario 

    dom_con_tratamiento = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Tratamiento Fitosanitario realizado respecto de este DOM?')
    numero_tratamiento = models.IntegerField(blank=True, null=True, verbose_name='Número de tratamiento termico fitosanitario asignado a este DOM')
    novedad_cumplimiento_tratamiento = models.TextField(blank=True, null=True, verbose_name='Novedades en la realización o cumplimiento del tratamiento termico', help_text='Incluya en este campo cualquier novedad o hecho relevante relativo al cumplimiento del tratamiento fitosanitario respecto de este DOM')
    tratamiento_segun_planeacion = models.BooleanField(null=True, blank=True, default=None, verbose_name='¿Tratamiento termico realizado según planeación para este DOM?')

    # bloque etapa 5 
    tratamiento_completado = models.BooleanField(default=False, verbose_name='¿Tratamiento termico realizado respecto de todos los productos de este DOM?', help_text='Si selecciona la opción si, este campo ya no podrá realizar ningún cambio respecto de esta etapa')

    # auditoria 

    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tratamientos_creados'
        )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'registros_tratamiento'
        verbose_name = 'Registro de Tratamiento'
        verbose_name_plural = 'Registros de Tratamiento'
        unique_together = ('registro_planeacion', 'numero_registro')

    def __str__(self):
        return f"Tratamiento #{self.numero_registro} - Planeación #{self.registro_planeacion.numero_registro}"

    @property
    def tarea_asignada_planeacion(self):
        # Hereda contenido de atributo objetivo_planeación de la clase RegistroPlaneacion
        return self.registro_planeacion.objetivo_planeacion 
    
    def etapa_5_bloqueada(self):
        return self.tratamiento_completado
    
# clase relacionada a los perfiles de usuarios para el manejo de permisos

class PerfilUsuario(models.Model):
    # definición de roles de permisos según usuario, en views.py se utilizarán estas declaraciones 

    ROLES_CHOICES = [
        ('GERENCIA', 'gerencia'),
        ('ADMIN', 'administrador'),
        ('ANALISTA_1', 'Analista Costos 1'),
        ('ANALISTA_2', 'Analista Costos 2'),
        ('PLANEADOR', 'Planeador'),
        ('LIDER_PLANTA', 'Líder de Planta'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil', verbose_name='Usuario')

    rol = models.CharField(max_length=20, choices=ROLES_CHOICES, verbose_name='Rol')

    class Meta:
        db_table = 'perfiles_usuario'
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_rol_display()}"
    
    # Método en el cual se establece permisos para editar etapas especificas
    def puede_editar_etapas(self, etapa):
        permisos = {
            'GERENCIA': [ ],
            'ADMIN' : ['etapa_0', 'etapa_1', 'etapa_2', 'etapa_3', 'etapa_4', 'etapa_5', 'etapa_6'],
            'ANALISTA_1' : ['etapa_0', 'etapa_1', 'etapa_6'],
            'ANALISTA_2' : ['etapa_0', 'etapa_1', 'etapa_6'],
            'PLANEADOR': ['etapa_2'],
            'LIDER_PLANTA': ['etapa_3', 'etapa_4', 'etapa_5'],
        }
        return etapa in permisos.get(self.rol, [])

class AuditoriaDom(models.Model):
    # Trazabilidad de cambios en registros DOMs

    ACTION_CHOICES = [
        ('CREACION', 'Creación'),
        ('EDICION', 'Edicion'),
        ('BLOQUEO_ETAPA', 'Bloqueo de Etapa'),
        ('DESBLOQUEO_ETAPA','Desbloqueo de Etapa'),
        ('ELIMINACION', 'Eliminación'),
    ]
    
    dom = models.ForeignKey(
        Dom, 
        on_delete=models.CASCADE, 
        related_name='auditoria',
        verbose_name='DOM'
    )

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Usuario'
    )

    accion = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        verbose_name='Acción'
    )

    etapa = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Etapa_afectada'
    )

    campos_modificados = models.JSONField(
        blank=True, 
        null=True,
        verbose_name='Campos Modificados',
        help_text='JSON: {"campo": {"antes": "valor_anterior", "despues": "valor_nuevo"}'
    )

    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Fecha/Hora')

    class Meta:
        db_table = 'auditoria_doms'
        verbose_name = 'Auditoría DOM'
        verbose_name_plural = 'Auditorías DOM'
        ordering = ['-timestamp']

    def __str__(self):
        return f"DOM #{self.dom.dom_id} - {self.accion} - {self.timestamp}"

# FIN ARCHIVO MODELS

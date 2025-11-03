from django.db import models
from django.contrib.auth.models import User

class Dom(models.Model):

    # llave primaria 
    dom_id = models.AutoField(primary_key=True)

    # campos obligatorios al momento de la creación del registro
    nombre_cliente = models.CharField(max_lenght=200)

    # campos no obligatorios, información se genera de forma posterior a la creación (proceso productivo cliente)
    fecha_entrega = models.DateField(blank=True)
    orden_produccion = models.IntergerField(blank=True)
    fecha_produccion = models.DateField(blank=True)
    # Se crea lista con valores desplegables a utilizar en atributo "lider_produccion"
    LIDERES = [
        ('SIN_LIDER', '-- Seleccione un lider --'),
        ('ALEX_AREVALO', 'Alex Arevalo'),
        ('JULIO_MARTINEZ', 'Julio Martinez'),
        ('LUIS_MANRIQUE', 'Luis Manrique'),
        ('JHON_MOTERREY', 'Jhon Monterrey'),
    ]
    lider_produccion = models.CharField(max_lenght=20, blank=True, choices=LIDERES,)
    materia_prima_disponible = models.BoleeanField(default=False, blank=True)
    requiere_prealistamiento = models.BoleeanField(default=False, blank=True)
    cantidad_elaborada = models.IntergerField(blank=True)
    cantidad_pendiente = models.IntergerField(blank=True)
    necesita_carton = models.BooleanField(default=False, blank=True)
    grafado_fundas = models.BoleeanField(default=False, blank=True)
    lider_almacen = models.CharField(max_lenght=20, blank=True, choices=LIDERES)
    fecha_tratamiento = models.DateField(blank=True)
    orden_tratamiento = models.IntergerField(blank=True)
    cliente_recoge = models.BooleanField(default=True, blank=True)
    mudar_entrega = models.BoleeanField(default=False, blank=True)
    tratamiento_realizado = models.BoleeanField(default=False, blank=True)
    sello_ica = models.BoleeanField(default=False, blank=True)
    peso_producto = models.IntergerField(blank=True)
    marcacion_cliente = models.BooleanField(default=False, blank=False)
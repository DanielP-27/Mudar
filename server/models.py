from django.db import models
from django.contrib.auth.models import User

class Dom(models.Model):

    # llave primaria 
    dom_id = models.AutoField(primary_key=True)

    # campos obligatorios al momento de la creación del registro
    nombre_cliente = models.CharField(max_length=200)

    # campos no obligatorios, información se genera de forma posterior a la creación (proceso productivo cliente)
    fecha_entrega = models.DateField(blank=True, null=True)
    orden_produccion = models.IntegerField(blank=True, null=True)
    fecha_produccion = models.DateField(blank=True, null=True)
    # Se crea lista con valores desplegables a utilizar en atributo "lider_produccion"
    LIDERES = [
        ('SIN_LIDER', '-- Seleccione un lider --'),
        ('ALEX_AREVALO', 'Alex Arevalo'),
        ('JULIO_MARTINEZ', 'Julio Martinez'),
        ('LUIS_MANRIQUE', 'Luis Manrique'),
        ('JHON_MOTERREY', 'Jhon Monterrey'),
    ]
    lider_produccion = models.CharField(max_length=200, blank=True, null=True, choices=LIDERES)
    materia_prima_disponible = models.BooleanField(default=False, blank=True)
    requiere_prealistamiento = models.BooleanField(default=False, blank=True)
    cantidad_elaborada = models.IntegerField(blank=True, null=True)
    cantidad_pendiente = models.IntegerField(blank=True, null=True)
    necesita_carton = models.BooleanField(default=False, blank=True)
    grafado_fundas = models.BooleanField(default=False, blank=True)
    lider_almacen = models.CharField(max_length=200, blank=True, null=True, choices=LIDERES)
    fecha_tratamiento = models.DateField(blank=True, null=True)
    orden_tratamiento = models.IntegerField(blank=True, null=True)
    cliente_recoge = models.BooleanField(default=True, blank=True, null=False)
    mudar_entrega = models.BooleanField(default=False, blank=True, null=True)
    tratamiento_realizado = models.BooleanField(default=False, blank=True)
    sello_ica = models.BooleanField(default=False, blank=True)
    peso_producto = models.IntegerField(blank=True, null=True)
    marcacion_cliente = models.BooleanField(default=False, blank=False)

    class Meta:
        db_table = 'server_dom'
        verbose_name = 'Dom'
        verbose_name_plural = 'Doms'
    
    def __str__(self):
        return f"Dom {self.dom_id} - {self.nombre_cliente}"
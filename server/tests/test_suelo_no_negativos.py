"""Ningún campo numérico admite valores por debajo de su suelo.

Dieciséis campos llevan restricción, en dos familias: nueve exigen **mayor que cero**
y siete exigen **no negativo**. La diferencia no es cosmética — el cero es un dato
legítimo en la segunda familia (una corrida de menos de un minuto, una planeación que
todavía no proyecta nada) y es un imposible en la primera (nadie produce con cero
personas, ningún pedido pide cero unidades).

**Por qué se prueba con el valor de la frontera y no con -999.** Un -999 solo demuestra
que existe *alguna* restricción: un suelo puesto por error en 0 donde va 1 lo rechazaría
igual y la prueba pasaría en verde. El único valor que distingue los dos suelos es el
contiguo a la frontera, así que cada familia se prueba con su par:

    suelo 1  ->  se rechaza el 0,   se acepta el 1
    suelo 0  ->  se rechaza el -1,  se acepta el 0

**Por qué unas pruebas usan create() y otras update().** Tres de los campos los
sobrescribe el propio save() del modelo antes de llegar a la base: los dos
tiempo_unitario_aplicado se fotografían desde el catálogo al insertar (models.py:354
y :604) y segundos_pausados se recalcula si la pausa tiene fin (:921). Un create() con
un negativo quedaría reemplazado por un valor válido y la prueba pasaría sin probar
nada. Los demás campos que usan update() son los que en la aplicación real se rellenan
en una etapa posterior, con un PUT sobre una fila que ya existe.

Y eso no es un rodeo del test: queryset.update() emite un UPDATE plano que no pasa por
save() ni por ningún validador de Python. Es exactamente la puerta que justifica que la
restricción viva en la tabla y no solo en el serializer.
"""
from datetime import date

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from server.models import (
    Cliente,
    Dom,
    PausaTiempoProduccion,
    PerfilUsuario,
    ProductoPlaneacion,
    ProductoProduccion,
    Productos,
    ProductosDom,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTiempoProduccion,
    RegistroTurnoDia,
    Turno,
)
from server.serializers import ProductoPlaneacionSerializer, ProductosSerializer


class BaseSuelo(TestCase):
    """Cadena completa de objetos válidos: DOM -> producto del DOM -> planeación ->
    producto de planeación -> producción -> cronómetro -> pausa."""

    def setUp(self):
        self.producto = Productos.objects.create(
            nombre_producto='Tanque A', tiempo_produccion_unitario=30,
        )
        self.otro_producto = Productos.objects.create(
            nombre_producto='Tanque B', tiempo_produccion_unitario=45,
        )
        # Tercer producto sin ProductosDom: reservado para las pruebas que crean uno
        # nuevo. Con self.otro_producto chocarían contra unique_together y levantarían
        # IntegrityError por duplicado, no por el suelo — un falso verde.
        self.producto_libre = Productos.objects.create(
            nombre_producto='Tanque C', tiempo_produccion_unitario=60,
        )
        self.turno = Turno.objects.create(nombre_turno='Turno de prueba')
        self.cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=self.cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=date(2026, 8, 30),
            responsable='Responsable de prueba',
        )
        self.producto_dom = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=self.producto, cantidad_pedido=10,
        )
        self.otro_producto_dom = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=self.otro_producto, cantidad_pedido=10,
        )
        self.planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=1,
        )
        self.producto_planeacion = ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.producto_dom,
            cantidad_proyectada=10,
        )
        self.produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
            numero_personas_asignadas=3,
        )
        self.producto_produccion = ProductoProduccion.objects.create(
            registro_produccion=self.produccion,
            producto_planeacion=self.producto_planeacion,
            cantidad_elaborada=4,
        )
        self.cronometro = RegistroTiempoProduccion.objects.create(
            registro_produccion=self.produccion,
            inicio=timezone.now(),
            estado='EN_CURSO',
        )
        self.pausa = PausaTiempoProduccion.objects.create(
            registro_tiempo=self.cronometro, inicio_pausa=timezone.now(),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Bloque A — la restricción de tabla rechaza lo que está por debajo del suelo
# ══════════════════════════════════════════════════════════════════════════════

class RechazoEnBaseSueloUnoTests(BaseSuelo):
    """Los nueve campos que exigen mayor que cero. Se prueba con el 0, que es el valor
    que delata un suelo puesto una muesca demasiado abajo."""

    def test_producto_con_tiempo_unitario_cero_es_rechazado(self):
        """Un estándar de cero minutos por unidad haría que un DOM entero proyecte
        cero tiempo y no consuma capacidad de ningún turno."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            Productos.objects.create(
                nombre_producto='Sin tiempo', tiempo_produccion_unitario=0,
            )

    def test_turno_dia_con_cero_operarios_es_rechazado(self):
        """numero_operarios multiplica la duración de la jornada: con cero, la
        capacidad del turno es cero y nada cabe en él."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistroTurnoDia.objects.create(
                turno=self.turno, fecha=date(2026, 9, 1),
                numero_operarios=0, minutos_totales=420,
            )

    def test_producto_del_dom_con_cantidad_pedida_cero_es_rechazado(self):
        """producto_libre y no otro_producto: este ya tiene fila en el DOM y el
        choque contra unique_together levantaría IntegrityError sin probar el suelo."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductosDom.objects.create(
                productoDom=self.dom, tipo_producto=self.producto_libre,
                cantidad_pedido=0,
            )

    def test_fotografia_del_producto_del_dom_en_cero_es_rechazada(self):
        """update() y no create(): save() fotografía el catálogo al insertar
        (models.py:354), así que un create() con cero no llegaría con cero."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductosDom.objects.filter(pk=self.producto_dom.pk).update(
                tiempo_unitario_aplicado=0,
            )

    def test_fotografia_del_producto_de_planeacion_en_cero_es_rechazada(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductoPlaneacion.objects.filter(pk=self.producto_planeacion.pk).update(
                tiempo_unitario_aplicado=0,
            )

    def test_dom_con_cero_empaques_es_rechazado(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Dom.objects.filter(pk=self.dom.pk).update(cantidad_empaques=0)

    def test_planeacion_con_orden_de_produccion_cero_es_rechazada(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistroPlaneacion.objects.create(
                dom=self.dom, numero_registro=9, orden_produccion=0,
            )

    def test_planeacion_con_orden_de_tratamiento_cero_es_rechazada(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistroPlaneacion.objects.create(
                dom=self.dom, numero_registro=10, orden_tratamiento=0,
            )

    def test_produccion_con_cero_personas_asignadas_es_rechazada(self):
        """Sin nadie no se produce. Es además el campo que hace que
        `if not personas` de cumplimiento.py:115 devuelva CUMPLIÓ con un negativo."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistroProduccion.objects.create(
                registro_planeacion=self.planeacion, numero_registro=9,
                numero_personas_asignadas=0,
            )


class RechazoEnBaseSueloCeroTests(BaseSuelo):
    """Los siete campos que solo excluyen el negativo. Se prueba con el -1, que es el
    único valor rechazable de esta familia."""

    def test_tiempo_de_salida_de_almacen_negativo_es_rechazado(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Dom.objects.filter(pk=self.dom.pk).update(tiempo_salida_almacen=-1)

    def test_cantidad_proyectada_negativa_es_rechazada(self):
        """El defecto que originó todo esto: una cantidad negativa produce tiempo
        proyectado negativo y libera capacidad del turno (views.py:2444)."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductoPlaneacion.objects.create(
                registro_planeacion=self.planeacion,
                dom_producto=self.otro_producto_dom,
                cantidad_proyectada=-1,
            )

    def test_cantidad_elaborada_negativa_es_rechazada(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductoProduccion.objects.create(
                registro_produccion=self.produccion,
                producto_planeacion=self.producto_planeacion,
                cantidad_elaborada=-1,
            )

    def test_minutos_asignados_negativos_son_rechazados(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistroProduccion.objects.filter(pk=self.produccion.pk).update(
                minutos_asignados=-1,
            )

    def test_minutos_totales_del_cronometro_negativos_son_rechazados(self):
        """minutos_totales es la única magnitud del sistema que sale de una resta
        —transcurrido menos pausas—, y una resta es lo único que produce un negativo
        a partir de dos valores no negativos."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistroTiempoProduccion.objects.create(
                registro_produccion=self.produccion,
                inicio=timezone.now(), estado='EN_CURSO', minutos_totales=-1,
            )

    def test_total_de_segundos_pausados_negativo_es_rechazado(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistroTiempoProduccion.objects.create(
                registro_produccion=self.produccion,
                inicio=timezone.now(), estado='EN_CURSO', total_segundos_pausados=-1,
            )

    def test_segundos_de_una_pausa_negativos_son_rechazados(self):
        """Sin fin_pausa: con fin, save() recalcularía el valor (models.py:921)."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            PausaTiempoProduccion.objects.create(
                registro_tiempo=self.cronometro,
                inicio_pausa=timezone.now(), segundos_pausados=-1,
            )


# ══════════════════════════════════════════════════════════════════════════════
# Bloque B — el cero sigue siendo un dato en los siete campos de suelo 0
# ══════════════════════════════════════════════════════════════════════════════

class ElCeroSigueSiendoValidoTests(BaseSuelo):
    """El riesgo de este cambio no es que no proteja: es poner suelo 1 donde va 0 y
    deshacer por la puerta de atrás el trabajo de 8.1.4, donde el cero pasó a ser un
    dato medido y no una ausencia."""

    def test_tiempo_de_salida_de_almacen_cero(self):
        Dom.objects.filter(pk=self.dom.pk).update(tiempo_salida_almacen=0)
        self.dom.refresh_from_db()
        self.assertEqual(self.dom.tiempo_salida_almacen, 0)

    def test_cantidad_proyectada_cero(self):
        """Una planeación que no proyecta nada es un dato pobre pero legítimo: lo que
        se rechaza es cerrarla así, no guardarla."""
        pp = ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.otro_producto_dom,
            cantidad_proyectada=0,
        )
        self.assertEqual(pp.cantidad_proyectada, 0)

    def test_cantidad_elaborada_cero(self):
        pp = ProductoProduccion.objects.create(
            registro_produccion=self.produccion,
            producto_planeacion=self.producto_planeacion,
            cantidad_elaborada=0,
        )
        self.assertEqual(pp.cantidad_elaborada, 0)

    def test_minutos_asignados_cero(self):
        """8.1.4: una corrida de menos de un minuto escribe 0, y ese 0 debe poder
        guardarse o el registro vuelve a ser indistinguible de uno sin cronometrar."""
        RegistroProduccion.objects.filter(pk=self.produccion.pk).update(minutos_asignados=0)
        self.produccion.refresh_from_db()
        self.assertEqual(self.produccion.minutos_asignados, 0)

    def test_minutos_totales_cero(self):
        c = RegistroTiempoProduccion.objects.create(
            registro_produccion=self.produccion,
            inicio=timezone.now(), estado='EN_CURSO', minutos_totales=0,
        )
        self.assertEqual(c.minutos_totales, 0)

    def test_total_de_segundos_pausados_cero(self):
        """Es además el valor por defecto del campo: un cronómetro sin pausas."""
        c = RegistroTiempoProduccion.objects.create(
            registro_produccion=self.produccion,
            inicio=timezone.now(), estado='EN_CURSO', total_segundos_pausados=0,
        )
        self.assertEqual(c.total_segundos_pausados, 0)

    def test_segundos_de_una_pausa_cero(self):
        p = PausaTiempoProduccion.objects.create(
            registro_tiempo=self.cronometro,
            inicio_pausa=timezone.now(), segundos_pausados=0,
        )
        self.assertEqual(p.segundos_pausados, 0)


# ══════════════════════════════════════════════════════════════════════════════
# Bloque C — el nulo sigue pasando en los once campos nulables
# ══════════════════════════════════════════════════════════════════════════════

class ElNuloSiguePasandoTests(BaseSuelo):
    """El suelo restringe el valor cuando lo hay. La ausencia se sigue admitiendo,
    porque en este sistema nada es obligatorio para guardar: lo obligatorio se exige
    al cerrar la etapa."""

    def test_dom_sin_empaques_ni_tiempo_de_salida(self):
        self.assertIsNone(self.dom.cantidad_empaques)
        self.assertIsNone(self.dom.tiempo_salida_almacen)

    def test_planeacion_sin_ordenes(self):
        p = RegistroPlaneacion.objects.create(dom=self.dom, numero_registro=11)
        self.assertIsNone(p.orden_produccion)
        self.assertIsNone(p.orden_tratamiento)

    def test_producto_de_planeacion_sin_cantidad_ni_fotografia(self):
        """La fotografía se pone a nulo con update() porque save() la rellena al
        insertar: son las filas anteriores a la migración 0021."""
        pp = ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.otro_producto_dom,
            cantidad_proyectada=None,
        )
        ProductoPlaneacion.objects.filter(pk=pp.pk).update(tiempo_unitario_aplicado=None)
        pp.refresh_from_db()
        self.assertIsNone(pp.cantidad_proyectada)
        self.assertIsNone(pp.tiempo_unitario_aplicado)

    def test_producto_del_dom_sin_fotografia(self):
        ProductosDom.objects.filter(pk=self.producto_dom.pk).update(
            tiempo_unitario_aplicado=None,
        )
        self.producto_dom.refresh_from_db()
        self.assertIsNone(self.producto_dom.tiempo_unitario_aplicado)

    def test_produccion_sin_personas_ni_minutos(self):
        p = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=12,
        )
        self.assertIsNone(p.numero_personas_asignadas)
        self.assertIsNone(p.minutos_asignados)

    def test_cronometro_sin_minutos_totales(self):
        """Un cronómetro en curso todavía no tiene minutos: es el estado normal."""
        self.assertIsNone(self.cronometro.minutos_totales)

    def test_pausa_abierta_sin_segundos(self):
        """Una pausa sin cerrar no tiene duración calculada."""
        self.assertIsNone(self.pausa.segundos_pausados)


# ══════════════════════════════════════════════════════════════════════════════
# Bloque D — la otra mitad: el validador, que da un 400 legible y no un 500
# ══════════════════════════════════════════════════════════════════════════════

class NombresDeRestriccionTests(TestCase):
    """Guarda de la fábrica `suelo()`: el nombre de la tabla se le pasa a mano, y
    nada comprueba que coincida con el `db_table` del modelo. Un error de tecleo
    daría un nombre incorrecto sin que fallara nada — este recorrido lo detecta."""

    def test_cada_nombre_empieza_por_el_db_table_de_su_modelo(self):
        from django.apps import apps

        revisados = 0
        for modelo in apps.get_app_config('server').get_models():
            tabla = modelo._meta.db_table
            for c in modelo._meta.constraints:
                if not c.name.endswith(('_mayor_que_cero', '_no_negativo')):
                    continue
                revisados += 1
                self.assertTrue(
                    c.name.startswith(tabla + '_'),
                    f'{modelo.__name__}: la restricción «{c.name}» no empieza por su '
                    f'tabla «{tabla}». Revise el primer argumento de suelo().'
                )
        self.assertEqual(revisados, 16, 'Se esperaban 16 restricciones de suelo.')

    def test_ningun_nombre_supera_el_limite_de_postgres(self):
        """63 bytes es el máximo de un identificador en Postgres, y el nombre más
        largo del conjunto mide exactamente 63."""
        from django.apps import apps

        for modelo in apps.get_app_config('server').get_models():
            for c in modelo._meta.constraints:
                if c.name.endswith(('_mayor_que_cero', '_no_negativo')):
                    self.assertLessEqual(len(c.name), 63, f'Nombre demasiado largo: {c.name}')


class MensajeLegibleTests(APITestCase):
    """La restricción de tabla garantiza; el validador explica. Sin él, un negativo
    llegado por la API reventaría con IntegrityError y el usuario vería un 500."""

    def setUp(self):
        self.admin = User.objects.create_user(username='admin.prueba', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=self.admin, rol='ADMIN')
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        self.producto = Productos.objects.create(
            nombre_producto='Tanque A', tiempo_produccion_unitario=30,
        )
        self.cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=self.cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=date(2026, 8, 30),
            responsable='Responsable de prueba',
        )
        self.producto_dom = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=self.producto, cantidad_pedido=10,
        )
        self.planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=1,
        )

    def test_el_serializer_rechaza_el_cero_en_un_campo_de_suelo_uno(self):
        serializer = ProductosSerializer(data={
            'nombre_producto': 'Sin tiempo', 'tiempo_produccion_unitario': 0,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('tiempo_produccion_unitario', serializer.errors)

    def test_el_serializer_rechaza_el_negativo_en_un_campo_de_suelo_cero(self):
        serializer = ProductoPlaneacionSerializer(data={
            'dom_producto': self.producto_dom.id, 'cantidad_proyectada': -1,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('cantidad_proyectada', serializer.errors)

    def test_por_la_api_sale_un_400_y_no_un_500(self):
        """Prueba de extremo a extremo: es lo que separa un mensaje que el usuario
        puede leer de una traza de error."""
        respuesta = self.client.post(
            '/api/productos/',
            {'nombre_producto': 'Sin tiempo', 'tiempo_produccion_unitario': 0},
            format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        self.assertEqual(
            Productos.objects.filter(nombre_producto='Sin tiempo').count(), 0,
            'El producto se creó pese a tener tiempo unitario cero.',
        )

"""Pruebas de que un cero se registra como cero y no como ausencia de dato.

Una corrida de menos de un minuto da 0 minutos netos. Ese cero significa "se midió y
duró poco", que no es lo mismo que "nunca se cronometró". Antes de este cambio ambos
casos dejaban minutos_asignados en nulo y eran indistinguibles.

Las dos condiciones van juntas: escribir el cero no sirve de nada si la propiedad que
lo consume vuelve a descartarlo.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from server.models import (
    Cliente,
    Dom,
    ProductoPlaneacion,
    Productos,
    ProductosDom,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTiempoProduccion,
)


class CeroNoEsAusenciaTests(TestCase):

    def setUp(self):
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
        self.planeacion = RegistroPlaneacion.objects.create(dom=self.dom, numero_registro=1)
        ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.producto_dom,
            cantidad_proyectada=10,
        )
        self.produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
            numero_personas_asignadas=3,
        )

    def cronometro_finalizado(self, segundos):
        """Cierra un cronómetro de la duración indicada, por el mismo camino que la vista:
        calcular_minutos_totales y save()."""
        inicio = timezone.now() - timedelta(seconds=segundos)
        c = RegistroTiempoProduccion.objects.create(
            registro_produccion=self.produccion, inicio=inicio, estado='EN_CURSO',
        )
        c.fin = timezone.now()
        c.estado = 'FINALIZADO'
        c.minutos_totales = c.calcular_minutos_totales()
        c.save()
        return c

    # ------------------------------------------------------------------
    # El cero se escribe
    # ------------------------------------------------------------------

    def test_cronometro_de_menos_de_un_minuto_escribe_cero(self):
        c = self.cronometro_finalizado(segundos=40)
        self.assertEqual(c.minutos_totales, 0)

        self.produccion.refresh_from_db()
        self.assertEqual(
            self.produccion.minutos_asignados, 0,
            'Una corrida de menos de un minuto no escribió minutos_asignados: el '
            'registro queda indistinguible de uno que nunca se cronometró.'
        )

    def test_cronometro_normal_sigue_escribiendo_sus_minutos(self):
        self.cronometro_finalizado(segundos=23 * 60)
        self.produccion.refresh_from_db()
        self.assertEqual(self.produccion.minutos_asignados, 23)

    def test_cronometro_no_finalizado_no_escribe(self):
        RegistroTiempoProduccion.objects.create(
            registro_produccion=self.produccion, inicio=timezone.now(), estado='EN_CURSO',
        )
        self.produccion.refresh_from_db()
        self.assertIsNone(self.produccion.minutos_asignados)

    # ------------------------------------------------------------------
    # Y el cero se consume
    # ------------------------------------------------------------------

    def test_minutos_hombre_con_cero_minutos_da_cero(self):
        self.produccion.minutos_asignados = 0
        self.assertEqual(
            self.produccion.minutos_hombre_produccion_dom, 0,
            'Cero minutos por tres personas son cero minutos-hombre, no ausencia de dato.'
        )

    def test_minutos_hombre_sin_minutos_sigue_siendo_nulo(self):
        self.produccion.minutos_asignados = None
        self.assertIsNone(self.produccion.minutos_hombre_produccion_dom)

    def test_minutos_hombre_sin_personas_sigue_siendo_nulo(self):
        self.produccion.minutos_asignados = 23
        self.produccion.numero_personas_asignadas = None
        self.assertIsNone(self.produccion.minutos_hombre_produccion_dom)

    def test_cero_personas_tambien_es_un_dato(self):
        """Simétrico del anterior: cero personas es un valor, no una ausencia."""
        self.produccion.minutos_asignados = 23
        self.produccion.numero_personas_asignadas = 0
        self.assertEqual(self.produccion.minutos_hombre_produccion_dom, 0)

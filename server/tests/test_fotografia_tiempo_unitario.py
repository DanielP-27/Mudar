"""Pruebas de la fotografía del tiempo unitario de producción.

La regla que fijan estas pruebas es una sola: EDITAR EL CATÁLOGO NO CAMBIA EL
PASADO. Si alguien corrige 'tiempo_produccion_unitario' de un producto, los
tiempos y veredictos ya calculados sobre registros existentes deben quedar
exactamente donde estaban.

Son pruebas metamórficas: no comparan la salida contra un valor esperado —nadie
sabe de antemano cuál DEBE ser el tiempo proyectado de un DOM cualquiera—, sino
DOS SALIDAS DEL MISMO SISTEMA entre sí, antes y después de una transformación de
la entrada cuyo efecto sí se conoce. La transformación es "editar el catálogo" y
el efecto conocido es "ninguno sobre lo ya registrado".

ESTAS PRUEBAS ESTÁN ESCRITAS PARA FALLAR HOY. Se escriben antes del mecanismo que
las cumple, a propósito: si se escribieran después, no habría forma de saber si
pasan porque el código quedó bien o porque la prueba se acomodó a lo que el
código ya hacía.

TestCase y no SimpleTestCase, a diferencia de test_cumplimiento.py: aquí sí hace
falta base de datos, porque las propiedades bajo prueba recorren relaciones.
"""
from datetime import date

from django.test import TestCase

from server.models import (
    Cliente,
    Dom,
    ProductoPlaneacion,
    Productos,
    ProductosDom,
    RegistroPlaneacion,
    RegistroProduccion,
)

# Minutos por unidad con los que nace el catálogo y con los que se registra todo.
UNITARIO_ORIGINAL = 30
# Corrección al alza del estándar, aplicada DESPUÉS de registrar.
UNITARIO_CORREGIDO_ARRIBA = 40
# Corrección a la baja. Es la dirección que altera el veredicto de producción.
UNITARIO_CORREGIDO_ABAJO = 20

CANTIDAD_PEDIDA = 10
CANTIDAD_PROYECTADA = 10


class FotografiaTiempoUnitarioTests(TestCase):

    def setUp(self):
        # Un solo producto y una sola cantidad, para que la aritmética de cada
        # prueba se pueda seguir de cabeza: 10 unidades x 30 min = 300 min.
        self.producto = Productos.objects.create(
            nombre_producto='Tanque A',
            tiempo_produccion_unitario=UNITARIO_ORIGINAL,
        )
        self.cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=self.cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=date(2026, 8, 30),
            responsable='Responsable de prueba',
        )
        self.producto_dom = ProductosDom.objects.create(
            productoDom=self.dom,
            tipo_producto=self.producto,
            cantidad_pedido=CANTIDAD_PEDIDA,
        )
        self.planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom,
            numero_registro=1,
        )
        self.producto_planeacion = ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.producto_dom,
            cantidad_proyectada=CANTIDAD_PROYECTADA,
        )

    def cambiar_catalogo(self, nuevo_unitario):
        """Simula la edición del catálogo desde PaginaProductos."""
        self.producto.tiempo_produccion_unitario = nuevo_unitario
        self.producto.save()

    # ------------------------------------------------------------------
    # Los tiempos proyectados
    # ------------------------------------------------------------------

    def test_tiempo_proyectado_de_la_planeacion_no_cambia(self):
        antes = self.planeacion.tiempo_proyectado
        self.assertEqual(antes, CANTIDAD_PROYECTADA * UNITARIO_ORIGINAL)

        self.cambiar_catalogo(UNITARIO_CORREGIDO_ARRIBA)

        self.assertEqual(
            self.planeacion.tiempo_proyectado, antes,
            'El tiempo proyectado de una planeación ya registrada cambió al '
            'editar el catálogo. La jornada se planeó con el estándar vigente '
            'ese día y ese es el único que la describe.'
        )

    def test_tiempo_proyectado_total_del_dom_no_cambia(self):
        antes = self.dom.tiempo_proyectado_total
        self.assertEqual(antes, CANTIDAD_PEDIDA * UNITARIO_ORIGINAL)

        self.cambiar_catalogo(UNITARIO_CORREGIDO_ARRIBA)

        self.assertEqual(
            self.dom.tiempo_proyectado_total, antes,
            'El tiempo proyectado total de un DOM ya registrado cambió al '
            'editar el catálogo.'
        )

    # ------------------------------------------------------------------
    # El daño de fondo: un veredicto cerrado que se reescribe solo
    # ------------------------------------------------------------------

    def test_veredicto_de_produccion_no_cambia(self):
        """El caso que motivó todo esto.

        'cumplimiento_produccion' compara minutos medidos —persistidos, no se
        mueven— contra tiempo proyectado —que hoy se recalcula—. Sin fotografía,
        una edición de catálogo meses después reescribe el veredicto de una
        producción que ya está cerrada, sin que nadie toque el registro.

        Aquí el veredicto cae de CUMPLIMIENTO_PARCIAL a NO_CUMPLIÓ. El mecanismo
        es el mismo que degradaría un CUMPLIÓ; se prueba con el parcial para no
        tener que sembrar además los productos elaborados.
        """
        produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion,
            numero_registro=1,
            # 100 min x 3 personas = 300 minutos-hombre, exactamente el tiempo
            # proyectado con el estándar original. Cumple en tiempo.
            minutos_asignados=100,
            numero_personas_asignadas=3,
        )
        antes = produccion.cumplimiento_produccion
        self.assertEqual(antes, 'CUMPLIMIENTO_PARCIAL')

        # El estándar se corrige a la baja: 10 x 20 = 200 min proyectados, y los
        # 300 minutos-hombre medidos pasan a estar por encima.
        self.cambiar_catalogo(UNITARIO_CORREGIDO_ABAJO)

        self.assertEqual(
            produccion.cumplimiento_produccion, antes,
            'El veredicto de cumplimiento de una producción ya registrada '
            'cambió al editar el catálogo. Nadie tocó el registro.'
        )

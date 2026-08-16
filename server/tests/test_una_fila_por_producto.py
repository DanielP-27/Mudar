"""Una fila de ProductoProduccion por producto y por registro de producción.

Lo parcial de la producción —producir menos de lo proyectado— se expresa con un número
más pequeño en una fila, y lo que falta se registra en OTRO RegistroProduccion. Esa es
la razón de que `cantidad_disponible_produccion` acumule a través de los registros de
producción de la misma planeación, y no dentro de uno.

De ahí que el par (registro_produccion, producto_planeacion) sea único, y que repetir el
mismo producto en OTRO registro siga siendo válido. El segundo caso es el que importa:
una restricción mal puesta mataría el mecanismo con el que se registra lo parcial.

El frontend ya trabajaba sobre esta suposición —`productoProduccionActivo` busca una
sola fila por producto— pero nada en la base la garantizaba.
"""
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from server.models import (
    Cliente,
    Dom,
    ProductoPlaneacion,
    ProductoProduccion,
    Productos,
    ProductosDom,
    RegistroPlaneacion,
    RegistroProduccion,
)


class UnaFilaPorProductoTests(TestCase):

    def setUp(self):
        self.producto = Productos.objects.create(
            nombre_producto='Tanque A', tiempo_produccion_unitario=30,
        )
        self.otro_producto = Productos.objects.create(
            nombre_producto='Tanque B', tiempo_produccion_unitario=45,
        )
        self.cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=self.cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=date(2026, 8, 30),
            responsable='Responsable de prueba',
        )
        self.producto_dom = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=self.producto, cantidad_pedido=20,
        )
        self.otro_producto_dom = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=self.otro_producto, cantidad_pedido=20,
        )
        self.planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=1,
        )
        self.pp = ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.producto_dom,
            cantidad_proyectada=20,
        )
        self.otro_pp = ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.otro_producto_dom,
            cantidad_proyectada=20,
        )
        # Dos jornadas de producción sobre la misma planeación: es el molde con el que
        # se produce en partes.
        self.produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
            numero_personas_asignadas=3,
        )
        self.segunda_produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=2,
            numero_personas_asignadas=3,
        )

    # ------------------------------------------------------------------
    # La restricción
    # ------------------------------------------------------------------

    def test_no_se_repite_el_mismo_producto_en_el_mismo_registro(self):
        """Dos filas del mismo producto en la misma jornada inflarían el total elaborado
        —`ProductoPlaneacion.cantidad_elaborada` las suma— mientras la pantalla mostraría
        solo la primera, porque `productoProduccionActivo` devuelve la que encuentra."""
        ProductoProduccion.objects.create(
            registro_produccion=self.produccion,
            producto_planeacion=self.pp,
            cantidad_elaborada=13,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductoProduccion.objects.create(
                registro_produccion=self.produccion,
                producto_planeacion=self.pp,
                cantidad_elaborada=4,
            )

    # ------------------------------------------------------------------
    # Los dos controles: lo que debe seguir siendo válido
    # ------------------------------------------------------------------

    def test_el_mismo_producto_en_otro_registro_sigue_permitido(self):
        """Es el mecanismo de lo parcial: 13 unidades una jornada y 7 la siguiente. Si
        esto se rompiera, no habría forma de terminar una producción incompleta."""
        ProductoProduccion.objects.create(
            registro_produccion=self.produccion,
            producto_planeacion=self.pp,
            cantidad_elaborada=13,
        )
        segunda = ProductoProduccion.objects.create(
            registro_produccion=self.segunda_produccion,
            producto_planeacion=self.pp,
            cantidad_elaborada=7,
        )
        self.assertEqual(segunda.cantidad_elaborada, 7)
        self.assertEqual(
            self.pp.cantidad_elaborada, 20,
            'La cantidad elaborada del producto planeado suma las dos jornadas.'
        )

    def test_otro_producto_en_el_mismo_registro_sigue_permitido(self):
        """Una misma jornada produce varios productos del DOM."""
        ProductoProduccion.objects.create(
            registro_produccion=self.produccion,
            producto_planeacion=self.pp,
            cantidad_elaborada=13,
        )
        otro = ProductoProduccion.objects.create(
            registro_produccion=self.produccion,
            producto_planeacion=self.otro_pp,
            cantidad_elaborada=5,
        )
        self.assertEqual(otro.cantidad_elaborada, 5)

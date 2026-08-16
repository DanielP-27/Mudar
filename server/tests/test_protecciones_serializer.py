"""Pruebas de las protecciones de serializer: la pertenencia de un registro a su padre
la fija el servidor al crear y nadie la cambia después.

Son pruebas de serializer y no de vista: el defecto vive en la lista `fields`, no en el
enrutado. Instanciar el serializer directamente prueba lo que se quiere probar y cubre a
la vez todos los endpoints que lo usan.

Las pruebas de control pesan tanto como las de rechazo: el riesgo real de este cambio no
es que no proteja, sino que rompa la creación o el guardado legítimo.
"""
from datetime import date

from django.test import TestCase
from django.utils import timezone

from server.models import (
    Cliente,
    Dom,
    ProductoPlaneacion,
    ProductoProduccion,
    Productos,
    ProductosDom,
    RegistroAlmacen,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTiempoProduccion,
    RegistroTratamiento,
    RegistroTurnoDia,
    Turno,
)
from server.serializers import (
    ProductoPlaneacionSerializer,
    ProductoProduccionSerializer,
    RegistroAlmacenSerializer,
    RegistroProduccionSerializer,
    RegistroTratamientoSerializer,
    RegistroTurnoDiaSerializer,
)


class ProteccionesSerializerTests(TestCase):

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
            productoDom=self.dom, tipo_producto=self.producto, cantidad_pedido=10,
        )
        self.otro_producto_dom = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=self.otro_producto, cantidad_pedido=10,
        )

        # Dos planeaciones del mismo DOM: la segunda es el destino al que un PUT
        # malicioso intentaría mover los registros hijos.
        self.planeacion = RegistroPlaneacion.objects.create(dom=self.dom, numero_registro=1)
        self.otra_planeacion = RegistroPlaneacion.objects.create(dom=self.dom, numero_registro=2)

        self.producto_planeacion = ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=self.producto_dom,
            cantidad_proyectada=10,
        )
        self.almacen = RegistroAlmacen.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
        )
        self.produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
            numero_personas_asignadas=3,
        )
        self.otra_produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.otra_planeacion, numero_registro=1,
        )
        self.tratamiento = RegistroTratamiento.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
        )
        self.producto_produccion = ProductoProduccion.objects.create(
            registro_produccion=self.produccion,
            producto_planeacion=self.producto_planeacion,
            cantidad_elaborada=4,
        )

    def cronometro(self, registro, estado='FINALIZADO'):
        return RegistroTiempoProduccion.objects.create(
            registro_produccion=registro,
            inicio=timezone.now(),
            estado=estado,
        )

    # ------------------------------------------------------------------
    # Reparentar: la FK del padre se ignora en la entrada
    # ------------------------------------------------------------------

    def test_almacen_no_se_puede_mover_a_otra_planeacion(self):
        s = RegistroAlmacenSerializer(
            self.almacen, data={'registro_planeacion': self.otra_planeacion.id}, partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.almacen.refresh_from_db()
        self.assertEqual(
            self.almacen.registro_planeacion_id, self.planeacion.id,
            'Un PUT movió el registro de almacén a otra planeación.'
        )

    def test_produccion_no_se_puede_mover_a_otra_planeacion(self):
        s = RegistroProduccionSerializer(
            self.produccion, data={'registro_planeacion': self.otra_planeacion.id}, partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.produccion.refresh_from_db()
        self.assertEqual(
            self.produccion.registro_planeacion_id, self.planeacion.id,
            'Un PUT movió el registro de producción a otra planeación.'
        )

    def test_tratamiento_no_se_puede_mover_a_otra_planeacion(self):
        s = RegistroTratamientoSerializer(
            self.tratamiento, data={'registro_planeacion': self.otra_planeacion.id}, partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.tratamiento.refresh_from_db()
        self.assertEqual(
            self.tratamiento.registro_planeacion_id, self.planeacion.id,
            'Un PUT movió el registro de tratamiento a otra planeación.'
        )

    def test_producto_produccion_no_se_puede_reasignar(self):
        """Las dos FK a la vez: mover esta fila alteraría lo producido de dos
        planeaciones, porque cantidad_elaborada se agrega por producto_planeacion."""
        otro_pp = ProductoPlaneacion.objects.create(
            registro_planeacion=self.otra_planeacion,
            dom_producto=self.producto_dom,
            cantidad_proyectada=5,
        )
        s = ProductoProduccionSerializer(
            self.producto_produccion,
            data={'registro_produccion': self.otra_produccion.id,
                  'producto_planeacion': otro_pp.id},
            partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.producto_produccion.refresh_from_db()
        self.assertEqual(self.producto_produccion.registro_produccion_id, self.produccion.id)
        self.assertEqual(
            self.producto_produccion.producto_planeacion_id, self.producto_planeacion.id,
            'Un PUT reasignó la cantidad elaborada a otro producto planeado.'
        )

    # ------------------------------------------------------------------
    # dom_producto: inmutable tras crear
    # ------------------------------------------------------------------

    def test_no_se_puede_cambiar_el_producto_de_una_linea_de_planeacion(self):
        s = ProductoPlaneacionSerializer(
            self.producto_planeacion,
            data={'dom_producto': self.otro_producto_dom.id},
            partial=True,
        )
        self.assertFalse(
            s.is_valid(),
            'Se aceptó cambiar el producto de una línea ya creada: conservaría la '
            'fotografía del tiempo unitario del producto anterior.'
        )
        self.assertIn('dom_producto', s.errors)

    def test_la_cantidad_proyectada_sigue_siendo_editable(self):
        """La restricción es sobre el producto, no sobre la cantidad: la planeación
        necesita ajustarla tantas veces como haga falta."""
        s = ProductoPlaneacionSerializer(
            self.producto_planeacion, data={'cantidad_proyectada': 7}, partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.producto_planeacion.refresh_from_db()
        self.assertEqual(self.producto_planeacion.cantidad_proyectada, 7)

    def test_al_crear_si_se_elige_el_producto(self):
        s = ProductoPlaneacionSerializer(data={
            'dom_producto': self.otro_producto_dom.id,
            'cantidad_proyectada': 3,
        })
        self.assertTrue(s.is_valid(), s.errors)
        creado = s.save(registro_planeacion=self.otra_planeacion)
        self.assertEqual(creado.dom_producto_id, self.otro_producto_dom.id)
        self.assertEqual(creado.registro_planeacion_id, self.otra_planeacion.id)

    # ------------------------------------------------------------------
    # numero_personas_asignadas: inmutable si ya hay cronómetro
    # ------------------------------------------------------------------

    def test_no_se_puede_cambiar_las_personas_con_cronometro(self):
        self.cronometro(self.produccion)
        s = RegistroProduccionSerializer(
            self.produccion, data={'numero_personas_asignadas': 5}, partial=True,
        )
        self.assertFalse(s.is_valid(), 'Se aceptó cambiar las personas tras medir con ellas.')
        self.assertIn('numero_personas_asignadas', s.errors)

    def test_no_se_puede_vaciar_las_personas_con_cronometro(self):
        self.cronometro(self.produccion)
        s = RegistroProduccionSerializer(
            self.produccion, data={'numero_personas_asignadas': None}, partial=True,
        )
        self.assertFalse(s.is_valid(), 'Se aceptó vaciar las personas tras medir con ellas.')

    def test_se_pueden_cambiar_las_personas_sin_cronometro(self):
        s = RegistroProduccionSerializer(
            self.produccion, data={'numero_personas_asignadas': 5}, partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        self.produccion.refresh_from_db()
        self.assertEqual(self.produccion.numero_personas_asignadas, 5)

    def test_reenviar_el_mismo_valor_con_cronometro_no_falla(self):
        """El frontend reenvía el registro completo al guardar producción. Si el mismo
        valor se rechazara, la pantalla dejaría de poder guardar."""
        self.cronometro(self.produccion)
        s = RegistroProduccionSerializer(
            self.produccion,
            data={'numero_personas_asignadas': self.produccion.numero_personas_asignadas,
                  'novedad_cumplimiento_produccion': 'Sin novedad'},
            partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)
        s.save()

    def test_registro_antiguo_sin_personas_se_sigue_guardando(self):
        """Registros anteriores a la guarda del inicio tienen cronómetro y el campo en
        nulo. El frontend reenvía nulo, que es igual a lo guardado: debe pasar."""
        self.cronometro(self.otra_produccion)
        s = RegistroProduccionSerializer(
            self.otra_produccion, data={'numero_personas_asignadas': None}, partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)

    # ------------------------------------------------------------------
    # Turno-día: la jornada que describe es su identidad, no su contenido
    # ------------------------------------------------------------------

    def test_el_turno_dia_no_se_puede_mover_de_fecha_ni_de_turno(self):
        turno = Turno.objects.create(nombre_turno='Mañana')
        otro_turno = Turno.objects.create(nombre_turno='Tarde')
        turno_dia = RegistroTurnoDia.objects.create(
            turno=turno, fecha=date(2026, 8, 20), numero_operarios=6, minutos_totales=420,
        )
        s = RegistroTurnoDiaSerializer(
            turno_dia,
            data={'turno': otro_turno.turno_id, 'fecha': date(2026, 8, 21)},
            partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        turno_dia.refresh_from_db()
        self.assertEqual(turno_dia.turno_id, turno.turno_id)
        self.assertEqual(
            turno_dia.fecha, date(2026, 8, 20),
            'Un PUT movió la capacidad de jornada a otro día: dos fechas quedarían mal.'
        )

    def test_los_operarios_y_la_duracion_siguen_siendo_editables(self):
        """Es regla de negocio: la gente disponible y la duración cambian en la planta."""
        turno = Turno.objects.create(nombre_turno='Mañana')
        turno_dia = RegistroTurnoDia.objects.create(
            turno=turno, fecha=date(2026, 8, 20), numero_operarios=6, minutos_totales=420,
        )
        s = RegistroTurnoDiaSerializer(
            turno_dia, data={'numero_operarios': 8, 'minutos_totales': 540}, partial=True,
        )
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        turno_dia.refresh_from_db()
        self.assertEqual(turno_dia.numero_operarios, 8)
        self.assertEqual(turno_dia.minutos_totales, 540)

    # ------------------------------------------------------------------
    # Control: la creación sigue funcionando con la FK inyectada por la vista
    # ------------------------------------------------------------------

    def test_la_creacion_de_almacen_sigue_funcionando(self):
        s = RegistroAlmacenSerializer(data={'dom_realizado_planeacion': True})
        self.assertTrue(s.is_valid(), s.errors)
        creado = s.save(numero_registro=2, registro_planeacion=self.planeacion)
        self.assertEqual(creado.registro_planeacion_id, self.planeacion.id)

    def test_la_creacion_de_producto_produccion_sigue_funcionando(self):
        s = ProductoProduccionSerializer(data={'cantidad_elaborada': 2})
        self.assertTrue(s.is_valid(), s.errors)
        creado = s.save(
            registro_produccion=self.produccion,
            producto_planeacion=self.producto_planeacion,
        )
        self.assertEqual(creado.registro_produccion_id, self.produccion.id)
        self.assertEqual(creado.producto_planeacion_id, self.producto_planeacion.id)

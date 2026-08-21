"""Una etapa no puede cerrarse sin el veredicto que esa etapa produce.

El valor puede ser verdadero o falso según la realidad del negocio; lo que no se admite
es el nulo, porque el DOM quedaría cerrado para todos y el dato que alimenta los
informes no habría existido nunca. Un registro cerrado no se edita.

DOS NIVELES, y el segundo no es redundante:

  1. La regla — validar_cierre etapa por etapa, con sus casos de borde.
  2. El cableado — que cada una de las cinco vistas la llame de verdad. La etapa 4 fue
     la última en cablearse y antes tenía un bloque propio que sólo exigía el
     cronómetro: una guarda correcta que nadie invoca ya ha ocurrido aquí.

Ninguna prueba toca código de producción. Si alguna falla, hay un defecto real.
"""
from datetime import date

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from server.models import (
    Cliente,
    Dom,
    PerfilUsuario,
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
from server.views import validar_cierre

FECHA = date(2026, 8, 20)


class BaseCierre(APITestCase):
    """Un DOM con una planeación y sus tres registros hijos, sin nada diligenciado."""

    def setUp(self):
        self.usuario = User.objects.create_user(username='admin.mudar', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=self.usuario, rol='ADMIN')
        self.client = APIClient()
        self.client.force_authenticate(user=self.usuario)

        self.producto = Productos.objects.create(
            nombre_producto='Tanque A', tiempo_produccion_unitario=30,
        )
        self.cliente_dom = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=self.cliente_dom,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=date(2026, 8, 30),
            responsable='Responsable de prueba',
        )
        self.producto_dom = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=self.producto, cantidad_pedido=10,
        )
        self.turno = Turno.objects.create(nombre_turno='Mañana')
        self.planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=1, turno=self.turno, fecha_planeacion=FECHA,
        )
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
        )
        self.tratamiento = RegistroTratamiento.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
        )

    def crear_turno_dia(self):
        return RegistroTurnoDia.objects.create(
            turno=self.turno, fecha=FECHA, numero_operarios=6, minutos_totales=420,
        )

    def cronometro_finalizado(self):
        return RegistroTiempoProduccion.objects.create(
            registro_produccion=self.produccion,
            inicio=timezone.now(), fin=timezone.now(),
            estado='FINALIZADO', minutos_totales=23,
        )

    def cantidad_elaborada(self, cantidad=10):
        return ProductoProduccion.objects.create(
            registro_produccion=self.produccion,
            producto_planeacion=self.producto_planeacion,
            cantidad_elaborada=cantidad,
            registrado_por=self.usuario,
        )


# ══════════════════════════════════════════════════════════════════════════════
# NIVEL 1 — la regla
# ══════════════════════════════════════════════════════════════════════════════

class ReglaCierreTests(BaseCierre):

    # ── El nulo rechaza, en las cinco etapas ────────────────────────────────

    def test_etapa_2_sin_turno_dia_no_cierra(self):
        """No tiene campo de veredicto: exige turno, fecha y que el turno-día exista.
        Como un turno-día no puede crearse sin operarios ni duración, su existencia
        acredita los cuatro requisitos de una vez."""
        error = validar_cierre(self.planeacion, {'planeacion_completa': True}, 'etapa_2')
        self.assertIsNotNone(error)
        self.assertIn('operarios', error)

    def test_etapa_3_sin_veredicto_no_cierra(self):
        error = validar_cierre(self.almacen, {'materias_liberadas': True}, 'etapa_3')
        self.assertIsNotNone(error)

    def test_etapa_4_sin_veredicto_no_cierra(self):
        # Los otros dos requisitos se cumplen a propósito: así lo único que puede
        # rechazar es el veredicto, que es lo que esta prueba vigila.
        self.cronometro_finalizado()
        self.cantidad_elaborada()
        self.produccion.numero_personas_asignadas = 3
        error = validar_cierre(self.produccion, {'cierre_produccion': True}, 'etapa_4')
        self.assertIsNotNone(error)

    def test_etapa_5_sin_veredicto_no_cierra(self):
        error = validar_cierre(self.tratamiento, {'tratamiento_completado': True}, 'etapa_5')
        self.assertIsNotNone(error)

    def test_etapa_6_sin_veredicto_no_cierra(self):
        self.dom.fecha_entrega_pactada = FECHA
        error = validar_cierre(self.dom, {'dom_liberado_cierre': True}, 'etapa_6')
        self.assertIsNotNone(error)

    # ── El falso SÍ cierra: es una respuesta, no una ausencia ───────────────

    def test_etapa_3_con_veredicto_falso_si_cierra(self):
        """False significa 'no cumplió'. Rechazarlo sería tratar una respuesta
        legítima como un dato sin diligenciar."""
        error = validar_cierre(
            self.almacen,
            {'materias_liberadas': True, 'dom_realizado_planeacion': False},
            'etapa_3',
        )
        self.assertIsNone(error, error)

    def test_etapa_4_con_veredicto_falso_si_cierra(self):
        self.cronometro_finalizado()
        self.cantidad_elaborada()
        error = validar_cierre(
            self.produccion,
            {'cierre_produccion': True, 'segun_planeacion': False,
             'numero_personas_asignadas': 3},
            'etapa_4',
        )
        self.assertIsNone(error, error)

    def test_etapa_5_con_veredicto_falso_si_cierra(self):
        error = validar_cierre(
            self.tratamiento,
            {'tratamiento_completado': True, 'tratamiento_segun_planeacion': False},
            'etapa_5',
        )
        self.assertIsNone(error, error)

    def test_etapa_6_con_veredicto_falso_si_cierra(self):
        error = validar_cierre(
            self.dom,
            {'dom_liberado_cierre': True, 'dom_entregado_ok': False,
             'fecha_entrega_pactada': FECHA},
            'etapa_6',
        )
        self.assertIsNone(error, error)

    # ── La cadena vacía es una ausencia ─────────────────────────────────────

    def test_la_fecha_borrada_en_el_navegador_es_ausencia(self):
        """Un campo de fecha que el usuario vacía envía cadena vacía, no nulo."""
        error = validar_cierre(
            self.dom,
            {'dom_liberado_cierre': True, 'dom_entregado_ok': True,
             'fecha_entrega_pactada': ''},
            'etapa_6',
        )
        self.assertIsNotNone(error)
        self.assertIn('fecha de entrega pactada', error)

    # ── El valor efectivo: veredicto y candado en el mismo PUT ──────────────

    def test_el_veredicto_del_mismo_put_cuenta(self):
        """Ambos viajan juntos desde la pantalla. Mirar sólo la base diría 'falta el
        dato' justo cuando el usuario acaba de marcarlo."""
        self.assertIsNone(self.almacen.dom_realizado_planeacion)
        error = validar_cierre(
            self.almacen,
            {'materias_liberadas': True, 'dom_realizado_planeacion': True},
            'etapa_3',
        )
        self.assertIsNone(error, error)

    def test_el_veredicto_ya_guardado_tambien_cuenta(self):
        """El caso inverso: el veredicto está en base y el PUT sólo trae el candado."""
        self.almacen.dom_realizado_planeacion = True
        error = validar_cierre(self.almacen, {'materias_liberadas': True}, 'etapa_3')
        self.assertIsNone(error, error)

    # ── Si el PUT no cierra, no se valida nada ──────────────────────────────

    def test_un_put_que_no_cierra_no_exige_nada(self):
        error = validar_cierre(
            self.almacen, {'novedad_cumplimiento_almacen': 'Sin novedad'}, 'etapa_3',
        )
        self.assertIsNone(error, error)

    def test_un_put_que_abre_la_etapa_no_exige_nada(self):
        error = validar_cierre(self.almacen, {'materias_liberadas': False}, 'etapa_3')
        self.assertIsNone(error, error)

    # ── Las dos condiciones que no son campos ───────────────────────────────

    def test_etapa_2_con_turno_dia_si_cierra(self):
        self.crear_turno_dia()
        error = validar_cierre(self.planeacion, {'planeacion_completa': True}, 'etapa_2')
        self.assertIsNone(error, error)

    def test_etapa_2_sin_fecha_no_cierra(self):
        """La fecha nula es el hueco que la mitad A vino a cerrar: sin ella la
        planeación no llega siquiera a la consulta del informe."""
        self.crear_turno_dia()
        self.planeacion.fecha_planeacion = None
        error = validar_cierre(self.planeacion, {'planeacion_completa': True}, 'etapa_2')
        self.assertIsNotNone(error)
        self.assertIn('fecha', error)

    # ── Mitad B: una planeación cerrada tiene que planear algo ──────────────

    def test_etapa_2_sin_ninguna_cantidad_no_cierra(self):
        """Cerrada y sin una sola línea, la planeación no dice nada. Y solo un ADMIN
        puede reabrirla, así que el descuido no lo arregla quien lo comete."""
        self.crear_turno_dia()
        self.planeacion.productos_planeacion.all().delete()

        error = validar_cierre(self.planeacion, {'planeacion_completa': True}, 'etapa_2')

        self.assertIsNotNone(error)
        self.assertIn('cantidad', error)

    def test_etapa_2_con_todas_las_cantidades_en_cero_no_cierra(self):
        """El umbral es mayor que cero y no «diligenciado»: un cero explícito en todos
        los productos es una planeación que no planea nada."""
        self.crear_turno_dia()
        self.planeacion.productos_planeacion.update(cantidad_proyectada=0)

        error = validar_cierre(self.planeacion, {'planeacion_completa': True}, 'etapa_2')

        self.assertIsNotNone(error)
        self.assertIn('cantidad', error)

    def test_etapa_2_basta_una_cantidad_positiva_para_cerrar(self):
        """Es «al menos uno», no «todos»: los productos de un DOM se reparten entre
        varias planeaciones, así que exigirlos todos rompería esa forma de trabajar."""
        self.crear_turno_dia()
        self.planeacion.productos_planeacion.update(cantidad_proyectada=0)
        otro_producto = Productos.objects.create(
            nombre_producto='Tanque B', tiempo_produccion_unitario=30,
        )
        otro_producto_dom = ProductosDom.objects.create(
            productoDom=self.dom, tipo_producto=otro_producto, cantidad_pedido=10,
        )
        ProductoPlaneacion.objects.create(
            registro_planeacion=self.planeacion,
            dom_producto=otro_producto_dom,
            cantidad_proyectada=10,
        )

        error = validar_cierre(self.planeacion, {'planeacion_completa': True}, 'etapa_2')

        self.assertIsNone(error, error)

    def test_las_cantidades_solo_se_exigen_al_cerrar(self):
        """Guardar una planeación sin cantidades sigue siendo legítimo. Lo obligatorio
        se exige en el candado, no en el guardado."""
        self.crear_turno_dia()
        self.planeacion.productos_planeacion.update(cantidad_proyectada=0)

        error = validar_cierre(self.planeacion, {'lider_produccion': 'Ana'}, 'etapa_2')

        self.assertIsNone(error, error)

    def test_etapa_4_sin_cronometro_finalizado_no_cierra(self):
        error = validar_cierre(
            self.produccion,
            {'cierre_produccion': True, 'segun_planeacion': True,
             'numero_personas_asignadas': 3},
            'etapa_4',
        )
        self.assertIsNotNone(error)
        self.assertIn('cronómetro', error)

    def test_etapa_4_con_cronometro_en_curso_no_cierra(self):
        RegistroTiempoProduccion.objects.create(
            registro_produccion=self.produccion, inicio=timezone.now(), estado='EN_CURSO',
        )
        self.cantidad_elaborada()
        error = validar_cierre(
            self.produccion,
            {'cierre_produccion': True, 'segun_planeacion': True,
             'numero_personas_asignadas': 3},
            'etapa_4',
        )
        self.assertIsNotNone(error)

    # ── Una producción cerrada tiene que haber producido algo ───────────────

    def test_etapa_4_sin_ninguna_cantidad_no_cierra(self):
        """Cerrado y sin una sola línea, el registro no dice qué salió. Y solo un ADMIN
        puede reabrirlo, así que el descuido no lo arregla quien lo comete."""
        self.cronometro_finalizado()

        error = validar_cierre(
            self.produccion,
            {'cierre_produccion': True, 'segun_planeacion': True,
             'numero_personas_asignadas': 3},
            'etapa_4',
        )

        self.assertIsNotNone(error)
        self.assertIn('cantidad', error)

    def test_etapa_4_con_todas_las_cantidades_en_cero_no_cierra(self):
        """El umbral es mayor que cero y no «hay fila»: un cero explícito en todos los
        productos es una jornada que no produjo nada."""
        self.cronometro_finalizado()
        self.cantidad_elaborada(cantidad=0)

        error = validar_cierre(
            self.produccion,
            {'cierre_produccion': True, 'segun_planeacion': True,
             'numero_personas_asignadas': 3},
            'etapa_4',
        )

        self.assertIsNotNone(error)
        self.assertIn('cantidad', error)

    def test_etapa_4_basta_una_cantidad_positiva_para_cerrar(self):
        """Es «al menos uno», no «todos»: un registro de producción puede cubrir parte de
        lo planeado, y lo que falte se registra en otra jornada."""
        self.cronometro_finalizado()
        self.cantidad_elaborada(cantidad=4)

        error = validar_cierre(
            self.produccion,
            {'cierre_produccion': True, 'segun_planeacion': True,
             'numero_personas_asignadas': 3},
            'etapa_4',
        )

        self.assertIsNone(error, error)

    def test_el_mensaje_enumera_todo_lo_que_falta(self):
        """Con varios faltantes el usuario debe verlos de una vez, no de uno en uno."""
        error = validar_cierre(self.produccion, {'cierre_produccion': True}, 'etapa_4')
        self.assertIn(' y ', error)


# ══════════════════════════════════════════════════════════════════════════════
# NIVEL 2 — el cableado: cada vista llama de verdad a la guarda
# ══════════════════════════════════════════════════════════════════════════════

class CableadoCierreTests(BaseCierre):

    def assert_rechaza_y_no_cierra(self, respuesta, instancia, campo):
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST, respuesta.data)
        instancia.refresh_from_db()
        self.assertNotEqual(
            getattr(instancia, campo), True,
            'La vista respondió error pero el candado quedó cerrado igualmente.'
        )

    def test_planeacion_rechaza_el_cierre_sin_turno_dia(self):
        respuesta = self.client.put(
            f'/api/planeacion/{self.planeacion.id}/',
            {'planeacion_completa': True}, format='json',
        )
        self.assert_rechaza_y_no_cierra(respuesta, self.planeacion, 'planeacion_completa')

    def test_almacen_rechaza_el_cierre_sin_veredicto(self):
        respuesta = self.client.put(
            f'/api/almacen/{self.almacen.id}/',
            {'materias_liberadas': True}, format='json',
        )
        self.assert_rechaza_y_no_cierra(respuesta, self.almacen, 'materias_liberadas')

    def test_produccion_rechaza_el_cierre_sin_veredicto(self):
        self.cronometro_finalizado()
        self.cantidad_elaborada()
        self.produccion.numero_personas_asignadas = 3
        self.produccion.save()
        respuesta = self.client.put(
            f'/api/produccion/{self.produccion.id}/',
            {'cierre_produccion': True}, format='json',
        )
        self.assert_rechaza_y_no_cierra(respuesta, self.produccion, 'cierre_produccion')

    def test_tratamiento_rechaza_el_cierre_sin_veredicto(self):
        respuesta = self.client.put(
            f'/api/tratamiento/{self.tratamiento.id}/',
            {'tratamiento_completado': True}, format='json',
        )
        self.assert_rechaza_y_no_cierra(respuesta, self.tratamiento, 'tratamiento_completado')

    def test_dom_rechaza_el_cierre_sin_veredicto(self):
        respuesta = self.client.put(
            f'/api/doms/{self.dom.dom_id}/',
            {'etapa': 'etapa_6', 'dom_liberado_cierre': True,
             'fecha_entrega_pactada': FECHA}, format='json',
        )
        self.assert_rechaza_y_no_cierra(respuesta, self.dom, 'dom_liberado_cierre')

    def test_el_cierre_legitimo_si_pasa_por_la_vista(self):
        """Control: la guarda no puede impedir un cierre correcto."""
        respuesta = self.client.put(
            f'/api/almacen/{self.almacen.id}/',
            {'materias_liberadas': True, 'dom_realizado_planeacion': True}, format='json',
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.almacen.refresh_from_db()
        self.assertTrue(self.almacen.materias_liberadas)

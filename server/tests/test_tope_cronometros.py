"""Las tres reglas del tope: depende de la jornada, el tiempo medido descuenta las
pausas —también la abierta— y una pausa recién empezada no es un abandono.

Estas pruebas fijan el cimiento del que van a colgar el endpoint de cronómetros
abiertos, la franja de fin de jornada y el cierre automático.
"""
from datetime import date, datetime, timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from server import tope_cronometros as tope
from server.models import (
    Cliente,
    Dom,
    PausaTiempoProduccion,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTiempoProduccion,
    RegistroTurnoDia,
    Turno,
)

FECHA = date(2026, 9, 1)
INICIO = timezone.make_aware(datetime(2026, 9, 1, 6, 0))


class PausaAbandonadaTests(SimpleTestCase):
    """Sin base de datos a propósito: si alguien mete una consulta en el predicado,
    esta clase falla por haberla tocado."""

    def test_sin_pausa_abierta_no_hay_abandono(self):
        self.assertFalse(tope.pausa_abandonada(None))

    def test_una_pausa_recien_empezada_no_es_abandono(self):
        self.assertFalse(tope.pausa_abandonada(0))

    def test_pasado_el_limite_hay_abandono(self):
        self.assertTrue(tope.pausa_abandonada(tope.PAUSA_ABANDONADA_MINUTOS + 1))


class TopeSinJornadaTests(SimpleTestCase):

    def test_sin_jornada_se_aplica_la_reserva_mas_permisiva(self):
        reserva = tope.tope_minutos(None)
        self.assertEqual(reserva, tope.TOPE_RESERVA_MINUTOS)
        self.assertGreaterEqual(reserva, tope.tope_minutos(540))


class BaseCronometro(TestCase):
    """Un cronómetro en curso, iniciado a las 6:00, sobre una planeación con turno y
    fecha. El turno-día no se crea aquí: cada prueba decide qué jornada tiene."""

    def setUp(self):
        self.turno = Turno.objects.create(nombre_turno='Turno de prueba')
        self.cliente = Cliente.objects.create(nombre_cliente='Cliente de prueba')
        self.dom = Dom.objects.create(
            nombre_cliente=self.cliente,
            tipo_estado_dom='PRODUCCION',
            fecha_solicitada_cliente=date(2026, 9, 30),
            responsable='Responsable de prueba',
        )
        self.planeacion = RegistroPlaneacion.objects.create(
            dom=self.dom, numero_registro=1, turno=self.turno, fecha_planeacion=FECHA,
        )
        self.jornada = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
        )
        self.cronometro = RegistroTiempoProduccion.objects.create(
            registro_produccion=self.jornada, inicio=INICIO, estado='EN_CURSO',
        )

    def turno_dia(self, minutos):
        return RegistroTurnoDia.objects.create(
            turno=self.turno, fecha=FECHA, numero_operarios=6, minutos_totales=minutos,
        )


class DuracionJornadaTests(BaseCronometro):

    def test_sale_del_turno_dia_registrado(self):
        self.turno_dia(540)
        self.assertEqual(tope.duracion_jornada(self.cronometro), 540)

    def test_sin_turno_dia_no_se_puede_determinar(self):
        self.assertIsNone(tope.duracion_jornada(self.cronometro))

    def test_sin_turno_en_la_planeacion_no_se_puede_determinar(self):
        self.turno_dia(540)
        self.planeacion.turno = None
        self.planeacion.save()
        self.assertIsNone(tope.duracion_jornada(self.cronometro))

    def test_sin_fecha_en_la_planeacion_no_se_puede_determinar(self):
        self.turno_dia(540)
        self.planeacion.fecha_planeacion = None
        self.planeacion.save()
        self.assertIsNone(tope.duracion_jornada(self.cronometro))


class MinutosMedidosTests(BaseCronometro):

    def pausa_abierta(self, minuto):
        return PausaTiempoProduccion.objects.create(
            registro_tiempo=self.cronometro, inicio_pausa=INICIO + timedelta(minutes=minuto),
        )

    def pausa_cerrada(self, desde, hasta):
        # El acumulador del cronómetro lo escribe la vista al reanudar, no el modelo.
        PausaTiempoProduccion.objects.create(
            registro_tiempo=self.cronometro,
            inicio_pausa=INICIO + timedelta(minutes=desde),
            fin_pausa=INICIO + timedelta(minutes=hasta),
        )
        self.cronometro.total_segundos_pausados += (hasta - desde) * 60
        self.cronometro.save()

    def test_la_pausa_abierta_tambien_se_descuenta(self):
        self.pausa_abierta(60)
        medidos = tope.minutos_medidos(self.cronometro, INICIO + timedelta(minutes=100))
        self.assertEqual(medidos, 60)

    def test_durante_la_pausa_el_neto_se_congela_y_el_reloj_no(self):
        self.pausa_abierta(60)
        a_los_100 = INICIO + timedelta(minutes=100)
        a_los_160 = INICIO + timedelta(minutes=160)

        self.assertEqual(tope.minutos_medidos(self.cronometro, a_los_100), 60)
        self.assertEqual(tope.minutos_medidos(self.cronometro, a_los_160), 60)
        self.assertEqual(tope.minutos_en_pausa(self.cronometro, a_los_100), 40)
        self.assertEqual(tope.minutos_en_pausa(self.cronometro, a_los_160), 100)

    def test_las_pausas_cerradas_se_descuentan(self):
        self.pausa_cerrada(30, 50)
        medidos = tope.minutos_medidos(self.cronometro, INICIO + timedelta(minutes=100))
        self.assertEqual(medidos, 80)

    def test_se_descuentan_las_cerradas_y_la_abierta_a_la_vez(self):
        self.pausa_cerrada(30, 50)
        self.pausa_abierta(90)
        medidos = tope.minutos_medidos(self.cronometro, INICIO + timedelta(minutes=120))
        self.assertEqual(medidos, 70)

    def test_una_pausa_cerrada_no_cuenta_como_abierta(self):
        self.pausa_cerrada(30, 50)
        self.assertIsNone(tope.minutos_en_pausa(self.cronometro, INICIO + timedelta(minutes=100)))


class TopeSegunJornadaTests(BaseCronometro):
    """Cada jornada queda acotada por arriba y por abajo: 500 minutos exceden la de 7
    horas y no la de 9, y 620 sí exceden la de 9. Falla si alguien confunde el
    minutos_totales del turno-día con el del cronómetro, o si invierte los operandos."""

    def excede_con_jornada(self, minutos_jornada, minutos_corrida=500):
        self.turno_dia(minutos_jornada)
        medidos = tope.minutos_medidos(self.cronometro, INICIO + timedelta(minutes=minutos_corrida))
        return tope.techo_excedido(medidos, tope.tope_minutos(tope.duracion_jornada(self.cronometro)))

    def test_quinientos_minutos_exceden_la_jornada_de_siete_horas(self):
        self.assertTrue(self.excede_con_jornada(420))

    def test_quinientos_minutos_no_exceden_la_jornada_de_nueve_horas(self):
        self.assertFalse(self.excede_con_jornada(540))

    def test_seiscientos_veinte_minutos_exceden_la_jornada_de_nueve_horas(self):
        self.assertTrue(self.excede_con_jornada(540, minutos_corrida=620))

    def test_exactamente_en_el_tope_no_esta_excedido(self):
        self.assertFalse(self.excede_con_jornada(540, minutos_corrida=600))

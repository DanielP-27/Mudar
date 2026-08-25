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
        self.assertEqual(tope.duracion_jornada(tope.turno_dia_de(self.cronometro)), 540)

    def test_sin_turno_dia_no_se_puede_determinar(self):
        self.assertIsNone(tope.duracion_jornada(tope.turno_dia_de(self.cronometro)))

    def test_sin_turno_en_la_planeacion_no_se_puede_determinar(self):
        self.turno_dia(540)
        self.planeacion.turno = None
        self.planeacion.save()
        self.assertIsNone(tope.duracion_jornada(tope.turno_dia_de(self.cronometro)))

    def test_sin_fecha_en_la_planeacion_no_se_puede_determinar(self):
        self.turno_dia(540)
        self.planeacion.fecha_planeacion = None
        self.planeacion.save()
        self.assertIsNone(tope.duracion_jornada(tope.turno_dia_de(self.cronometro)))


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
        medidos = tope.minutos_medidos(self.cronometro, tope.pausa_abierta_de(self.cronometro), INICIO + timedelta(minutes=100))
        self.assertEqual(medidos, 60)

    def test_durante_la_pausa_el_neto_se_congela_y_el_reloj_no(self):
        self.pausa_abierta(60)
        a_los_100 = INICIO + timedelta(minutes=100)
        a_los_160 = INICIO + timedelta(minutes=160)

        self.assertEqual(tope.minutos_medidos(self.cronometro, tope.pausa_abierta_de(self.cronometro), a_los_100), 60)
        self.assertEqual(tope.minutos_medidos(self.cronometro, tope.pausa_abierta_de(self.cronometro), a_los_160), 60)
        self.assertEqual(tope.minutos_en_pausa(tope.pausa_abierta_de(self.cronometro),a_los_100), 40)
        self.assertEqual(tope.minutos_en_pausa(tope.pausa_abierta_de(self.cronometro),a_los_160), 100)

    def test_las_pausas_cerradas_se_descuentan(self):
        self.pausa_cerrada(30, 50)
        medidos = tope.minutos_medidos(self.cronometro, tope.pausa_abierta_de(self.cronometro), INICIO + timedelta(minutes=100))
        self.assertEqual(medidos, 80)

    def test_se_descuentan_las_cerradas_y_la_abierta_a_la_vez(self):
        self.pausa_cerrada(30, 50)
        self.pausa_abierta(90)
        medidos = tope.minutos_medidos(self.cronometro, tope.pausa_abierta_de(self.cronometro), INICIO + timedelta(minutes=120))
        self.assertEqual(medidos, 70)

    def test_una_pausa_cerrada_no_cuenta_como_abierta(self):
        self.pausa_cerrada(30, 50)
        self.assertIsNone(tope.minutos_en_pausa(tope.pausa_abierta_de(self.cronometro),INICIO + timedelta(minutes=100)))


class TopeSegunJornadaTests(BaseCronometro):
    """Cada jornada queda acotada por arriba y por abajo: 500 minutos exceden la de 7
    horas y no la de 9, y 620 sí exceden la de 9. Falla si alguien confunde el
    minutos_totales del turno-día con el del cronómetro, o si invierte los operandos."""

    def excede_con_jornada(self, minutos_jornada, minutos_corrida=500):
        self.turno_dia(minutos_jornada)
        ahora = INICIO + timedelta(minutes=minutos_corrida)
        medidos = tope.minutos_medidos(self.cronometro, tope.pausa_abierta_de(self.cronometro), ahora)
        duracion = tope.duracion_jornada(tope.turno_dia_de(self.cronometro))
        return tope.techo_excedido(medidos, tope.tope_minutos(duracion))

    def test_quinientos_minutos_exceden_la_jornada_de_siete_horas(self):
        self.assertTrue(self.excede_con_jornada(420))

    def test_quinientos_minutos_no_exceden_la_jornada_de_nueve_horas(self):
        self.assertFalse(self.excede_con_jornada(540))

    def test_seiscientos_veinte_minutos_exceden_la_jornada_de_nueve_horas(self):
        self.assertTrue(self.excede_con_jornada(540, minutos_corrida=620))

    def test_exactamente_en_el_tope_no_esta_excedido(self):
        self.assertFalse(self.excede_con_jornada(540, minutos_corrida=600))


class MarcasDeLaFranjaTests(SimpleTestCase):
    """Sin base de datos: los tres predicados de la franja son aritmética sobre
    valores ya resueltos."""

    SALIDA = timezone.make_aware(datetime(2026, 9, 1, 16, 0))

    def test_sin_pausa_no_hay_pausa_larga(self):
        self.assertFalse(tope.pausa_larga(None))

    def test_justo_en_el_umbral_todavia_no_es_larga(self):
        self.assertFalse(tope.pausa_larga(tope.AVISO_PAUSA_MINUTOS))

    def test_pasado_el_umbral_la_pausa_es_larga(self):
        self.assertTrue(tope.pausa_larga(tope.AVISO_PAUSA_MINUTOS + 1))

    def test_sin_salida_no_se_marca_por_terminar(self):
        self.assertFalse(tope.por_terminar(None, self.SALIDA))

    def test_fuera_de_la_ventana_no_se_marca(self):
        ahora = self.SALIDA - timedelta(minutes=tope.AVISO_FIN_JORNADA_MINUTOS + 1)
        self.assertFalse(tope.por_terminar(self.SALIDA, ahora))

    def test_justo_en_la_ventana_se_marca(self):
        ahora = self.SALIDA - timedelta(minutes=tope.AVISO_FIN_JORNADA_MINUTOS)
        self.assertTrue(tope.por_terminar(self.SALIDA, ahora))

    def test_sin_salida_no_se_marca_turno_terminado(self):
        self.assertFalse(tope.turno_terminado(None, self.SALIDA))

    def test_antes_de_la_salida_el_turno_no_ha_terminado(self):
        self.assertFalse(tope.turno_terminado(self.SALIDA, self.SALIDA - timedelta(minutes=1)))

    def test_pasada_la_salida_el_turno_ha_terminado(self):
        self.assertTrue(tope.turno_terminado(self.SALIDA, self.SALIDA + timedelta(minutes=1)))

    def test_por_terminar_y_turno_terminado_se_excluyen(self):
        for desplazamiento in (-60, -45, -1, 0, 1, 60):
            ahora = self.SALIDA + timedelta(minutes=desplazamiento)
            self.assertFalse(
                tope.por_terminar(self.SALIDA, ahora) and tope.turno_terminado(self.SALIDA, ahora),
                f'ambas marcas a {desplazamiento} min de la salida',
            )


class HoraSalidaTests(SimpleTestCase):
    """El turno-día se construye sin guardar: es el modelo real, pero la función solo
    lee tres atributos y no consulta nada."""

    def turno_dia(self, turno_id, minutos):
        return RegistroTurnoDia(turno_id=turno_id, fecha=FECHA, minutos_totales=minutos)

    def a_las(self, hora, minuto=0):
        return timezone.make_aware(datetime(2026, 9, 1, hora, minuto))

    def test_manana_sin_extras_sale_a_las_catorce_treinta(self):
        self.assertEqual(tope.hora_salida(self.turno_dia(1, 510)), self.a_las(14, 30))

    def test_manana_con_extras_sale_a_las_dieciseis(self):
        self.assertEqual(tope.hora_salida(self.turno_dia(1, 540)), self.a_las(16))

    def test_tarde_sin_extras_sale_a_las_diecinueve(self):
        self.assertEqual(tope.hora_salida(self.turno_dia(3, 420)), self.a_las(19))

    def test_tarde_con_extras_sale_a_las_diecinueve(self):
        self.assertEqual(tope.hora_salida(self.turno_dia(3, 540)), self.a_las(19))

    def test_el_sabado_de_la_tarde_sale_a_las_catorce(self):
        self.assertEqual(tope.hora_salida(self.turno_dia(3, 480)), self.a_las(14))

    def test_sin_turno_dia_no_hay_salida(self):
        self.assertIsNone(tope.hora_salida(None))

    def test_una_jornada_historica_no_tiene_salida(self):
        self.assertIsNone(tope.hora_salida(self.turno_dia(3, 600)))

    def test_la_salida_es_comparable_con_el_reloj_del_sistema(self):
        salida = tope.hora_salida(self.turno_dia(1, 540))
        self.assertIsNotNone(salida.tzinfo)
        self.assertFalse(tope.turno_terminado(salida, salida - timedelta(minutes=1)))


class DecidirCierreTests(SimpleTestCase):
    """Recibe el cronómetro, el turno-día y la pausa ya resueltos, así que se
    construyen sin guardar y no hace falta base de datos."""

    def cronometro(self, pausados=0):
        return RegistroTiempoProduccion(inicio=INICIO, total_segundos_pausados=pausados)

    def turno_dia(self, minutos=540):
        return RegistroTurnoDia(turno_id=1, fecha=FECHA, minutos_totales=minutos)

    def test_el_fin_por_techo_no_depende_de_cuando_corra_el_barrido(self):
        cron, dia = self.cronometro(), self.turno_dia()

        esa_tarde = tope.decidir_cierre(cron, dia, None, INICIO + timedelta(minutes=690))
        tres_semanas = tope.decidir_cierre(cron, dia, None, INICIO + timedelta(days=21))

        self.assertEqual(esa_tarde, tres_semanas)
        self.assertEqual(esa_tarde[1], INICIO + timedelta(minutes=600))

    def test_el_fin_por_pausa_tampoco_depende(self):
        cron, dia = self.cronometro(), self.turno_dia()
        pausa = PausaTiempoProduccion(inicio_pausa=INICIO + timedelta(minutes=90))

        pronto = tope.decidir_cierre(cron, dia, pausa, INICIO + timedelta(minutes=235))
        tarde = tope.decidir_cierre(cron, dia, pausa, INICIO + timedelta(days=21))

        self.assertEqual(pronto, tarde)
        self.assertEqual(pronto[1], INICIO + timedelta(minutes=210))

    def test_sin_motivo_devuelve_dos_nulos(self):
        resultado = tope.decidir_cierre(self.cronometro(), self.turno_dia(), None,
                                        INICIO + timedelta(minutes=100))

        self.assertEqual(resultado, (None, None))


class CoberturaDeHorariosTests(SimpleTestCase):
    """Una jornada nueva no se anuncia sola: si se declara vigente y nadie le da hora
    de salida, la franja deja de marcar los turnos que la trabajan."""

    def test_toda_jornada_vigente_tiene_alguna_hora_de_salida(self):
        con_horario = {jornada for _, jornada in tope.HORAS_SALIDA}
        for jornada, etiqueta in RegistroTurnoDia.OPCIONES_MINUTOS:
            self.assertIn(jornada, con_horario, f'{etiqueta} no tiene hora de salida declarada')

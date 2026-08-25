"""Las dos formas de cerrar un cronómetro, y qué las distingue.

El cierre automático escribe el tope y no lo medido: un cronómetro olvidado no vale
lo que marque el reloj cuando alguien pase por ahí, vale lo que la jornada admite.
Y deja una fila de auditoría sin autor, porque no la causó ninguna persona.

El cierre humano escribe la hora real del clic, deja `cerrado_por_sistema` en nulo y
firma la auditoría. Ese nulo es lo único que distingue tiempo medido de tiempo
impuesto, así que se prueba aquí y no en otro archivo: las dos afirmaciones solo
significan algo juntas.
"""
from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from server import cierre_cronometros as cierre
from server.models import (
    AuditoriaDom,
    Cliente,
    Dom,
    PausaTiempoProduccion,
    PerfilUsuario,
    RegistroPlaneacion,
    RegistroProduccion,
    RegistroTiempoProduccion,
    RegistroTurnoDia,
    Turno,
)

URL_FINALIZAR = '/api/cronometro/finalizar/'

FECHA = date(2026, 9, 1)
INICIO = timezone.make_aware(datetime(2026, 9, 1, 6, 0))
TOPE = 600  # jornada de 540 más los 60 de margen


class BaseCierre(TestCase):
    """Cronómetro EN_CURSO iniciado a las 06:00, sobre un turno-día de 540 minutos."""

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
        self.produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=1,
        )
        self.cronometro = RegistroTiempoProduccion.objects.create(
            registro_produccion=self.produccion, inicio=INICIO, estado='EN_CURSO',
        )
        self.turno_dia = RegistroTurnoDia.objects.create(
            turno=self.turno, fecha=FECHA, numero_operarios=6, minutos_totales=540,
        )

    def a_los(self, minutos):
        return INICIO + timedelta(minutes=minutos)

    def pausa_desde(self, minuto):
        return PausaTiempoProduccion.objects.create(
            registro_tiempo=self.cronometro, inicio_pausa=self.a_los(minuto),
        )

    def recargar(self):
        self.cronometro.refresh_from_db()
        return self.cronometro


class CierrePorTechoTests(BaseCierre):

    def test_escribe_el_tope_exacto_y_no_lo_medido(self):
        """A las 17:30 lleva 690 minutos de reloj. Se guardan 600."""
        motivo = cierre.cerrar(self.cronometro, self.turno_dia, None, self.a_los(690))

        cronometro = self.recargar()
        self.assertEqual(motivo, RegistroTiempoProduccion.MOTIVO_TECHO)
        self.assertEqual(cronometro.minutos_totales, TOPE)
        self.assertEqual(cronometro.fin, self.a_los(TOPE))
        self.assertEqual(cronometro.estado, 'FINALIZADO')

    def test_marca_el_motivo_y_el_momento_de_la_intervencion(self):
        """cerrado_por_sistema dice cuándo intervino; fin, cuándo dejó de ser creíble."""
        cierre.cerrar(self.cronometro, self.turno_dia, None, self.a_los(690))

        cronometro = self.recargar()
        self.assertEqual(cronometro.motivo_cierre, RegistroTiempoProduccion.MOTIVO_TECHO)
        self.assertIsNotNone(cronometro.cerrado_por_sistema)
        self.assertNotEqual(cronometro.cerrado_por_sistema, cronometro.fin)

    def test_propaga_los_minutos_al_registro_de_produccion(self):
        cierre.cerrar(self.cronometro, self.turno_dia, None, self.a_los(690))

        self.produccion.refresh_from_db()
        self.assertEqual(self.produccion.minutos_asignados, TOPE)


class CierrePorPausaTests(BaseCierre):

    def test_registra_lo_trabajado_hasta_que_la_pausa_empezo(self):
        """Pausa a los 90 minutos, evaluada a los 235: lleva 145 en pausa."""
        pausa = self.pausa_desde(90)

        motivo = cierre.cerrar(self.cronometro, self.turno_dia, pausa, self.a_los(235))

        cronometro = self.recargar()
        self.assertEqual(motivo, RegistroTiempoProduccion.MOTIVO_PAUSA)
        self.assertEqual(cronometro.minutos_totales, 90)
        self.assertEqual(cronometro.fin, self.a_los(90 + 120))

    def test_la_pausa_queda_cerrada_con_sus_ciento_veinte_minutos(self):
        pausa = self.pausa_desde(90)

        cierre.cerrar(self.cronometro, self.turno_dia, pausa, self.a_los(235))

        pausa.refresh_from_db()
        self.assertEqual(pausa.fin_pausa, self.a_los(210))
        self.assertEqual(pausa.segundos_pausados, 120 * 60)


class PrecedenciaTests(BaseCierre):
    """El cronómetro excedió el tope ANTES de pausarse, y la pausa lleva 145 minutos.
    Los dos motivos aplican; gana el techo."""

    def cerrar_con_ambos(self):
        pausa = self.pausa_desde(610)
        cierre.cerrar(self.cronometro, self.turno_dia, pausa, self.a_los(755))
        return pausa

    def test_con_los_dos_motivos_gana_el_techo(self):
        self.cerrar_con_ambos()

        cronometro = self.recargar()
        self.assertEqual(cronometro.motivo_cierre, RegistroTiempoProduccion.MOTIVO_TECHO)
        self.assertEqual(cronometro.fin, self.a_los(TOPE))

    def test_la_pausa_se_cierra_sin_aportar_tiempo(self):
        """Con su duración real el resultado bajaría a 455. Debe quedarse en el tope."""
        pausa = self.cerrar_con_ambos()

        pausa.refresh_from_db()
        self.assertEqual(pausa.segundos_pausados, 0)
        self.assertEqual(self.recargar().minutos_totales, TOPE)


class NoProcedeTests(BaseCierre):

    def test_un_cronometro_normal_no_se_toca(self):
        motivo = cierre.cerrar(self.cronometro, self.turno_dia, None, self.a_los(100))

        cronometro = self.recargar()
        self.assertIsNone(motivo)
        self.assertEqual(cronometro.estado, 'EN_CURSO')
        self.assertIsNone(cronometro.fin)
        self.assertIsNone(cronometro.cerrado_por_sistema)

    def test_un_cronometro_ya_finalizado_no_se_cierra_dos_veces(self):
        """Idempotencia: dos barridos simultáneos no escriben dos veces."""
        self.cronometro.estado = 'FINALIZADO'
        self.cronometro.save()

        motivo = cierre.cerrar(self.cronometro, self.turno_dia, None, self.a_los(690))

        self.assertIsNone(motivo)
        self.assertIsNone(self.recargar().cerrado_por_sistema)


class AuditoriaDelCierreTests(BaseCierre):

    def test_deja_una_fila_sin_autor(self):
        """La ausencia de usuario es la marca del sistema: nadie causó esta acción."""
        cierre.cerrar(self.cronometro, self.turno_dia, None, self.a_los(690))

        fila = AuditoriaDom.objects.get(accion='CIERRE_AUTOMATICO')
        self.assertEqual(fila.dom, self.dom)
        self.assertIsNone(fila.usuario)
        self.assertIsNone(fila.ip)
        self.assertIsNone(fila.agente)


class BarrerTests(BaseCierre):

    def test_el_fallo_de_uno_no_detiene_a_los_demas(self):
        """El primer candidato no está guardado, así que su bloqueo revienta."""
        roto = RegistroTiempoProduccion(registro_produccion=self.produccion, inicio=INICIO)
        candidatos = [
            (roto, self.turno_dia, None),
            (self.cronometro, self.turno_dia, None),
        ]

        with self.assertLogs('server.cierre_cronometros', level='ERROR'):
            cerrados = cierre.barrer(candidatos, self.a_los(690))

        self.assertEqual(len(cerrados), 1)
        self.assertEqual(cerrados[0][1], RegistroTiempoProduccion.MOTIVO_TECHO)
        self.assertEqual(self.recargar().minutos_totales, TOPE)

    def test_devuelve_solo_los_que_cerro(self):
        candidatos = [(self.cronometro, self.turno_dia, None)]

        cerrados = cierre.barrer(candidatos, self.a_los(100))

        self.assertEqual(cerrados, [])

    def test_un_fallo_posterior_no_revierte_lo_ya_cerrado(self):
        """Verifica la granularidad: una transacción por cronómetro y no una global.
        Con una sola, este fallo se llevaría por delante el cierre anterior."""
        roto = RegistroTiempoProduccion(registro_produccion=self.produccion, inicio=INICIO)
        candidatos = [
            (self.cronometro, self.turno_dia, None),
            (roto, self.turno_dia, None),
        ]

        with self.assertLogs('server.cierre_cronometros', level='ERROR'):
            cerrados = cierre.barrer(candidatos, self.a_los(690))

        self.assertEqual(len(cerrados), 1)
        self.assertEqual(self.recargar().estado, 'FINALIZADO')
        self.assertEqual(self.recargar().minutos_totales, TOPE)

    def test_cierra_varios_en_la_misma_pasada(self):
        """Los dos reciben el mismo instante, así que su fin sale idéntico."""
        otra_produccion = RegistroProduccion.objects.create(
            registro_planeacion=self.planeacion, numero_registro=2,
        )
        segundo = RegistroTiempoProduccion.objects.create(
            registro_produccion=otra_produccion, inicio=INICIO, estado='EN_CURSO',
        )
        candidatos = [
            (self.cronometro, self.turno_dia, None),
            (segundo, self.turno_dia, None),
        ]

        cerrados = cierre.barrer(candidatos, self.a_los(690))

        segundo.refresh_from_db()
        self.assertEqual(len(cerrados), 2)
        self.assertEqual(self.recargar().fin, segundo.fin)
        self.assertEqual(segundo.minutos_totales, TOPE)

    def test_sin_candidatos_devuelve_lista_vacia(self):
        self.assertEqual(cierre.barrer([], self.a_los(690)), [])


class CierrePorUnaPersonaTests(BaseCierre):
    """El contraste. Lo que el sistema deja en nulo, la persona lo llena, y al revés."""

    def setUp(self):
        super().setUp()
        self.usuario = User.objects.create_user(username='lider.planta', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=self.usuario, rol='LIDER_PLANTA')
        self.client = APIClient()
        self.client.force_authenticate(user=self.usuario)

        # El cierre humano se fecha con el reloj real, así que su escenario también.
        self.cronometro.inicio = timezone.now() - timedelta(hours=2)
        self.cronometro.save()

    def finalizar(self):
        # La cabecera va explícita: APIClient no la envía, y un navegador siempre sí.
        return self.client.post(
            URL_FINALIZAR, {'cronometro_id': self.cronometro.id}, format='json',
            HTTP_USER_AGENT='Mozilla/5.0 (prueba)',
        )

    def test_no_marca_el_cronometro_como_cerrado_por_el_sistema(self):
        """Ese nulo es lo único que distingue tiempo medido de tiempo impuesto."""
        self.finalizar()

        cronometro = self.recargar()
        self.assertEqual(cronometro.estado, 'FINALIZADO')
        self.assertIsNone(cronometro.cerrado_por_sistema)
        self.assertIsNone(cronometro.motivo_cierre)

    def test_la_auditoria_lleva_autor_ip_y_agente(self):
        self.finalizar()

        fila = AuditoriaDom.objects.filter(dom=self.dom).latest('timestamp')
        self.assertEqual(fila.usuario, self.usuario)
        self.assertIsNotNone(fila.ip)
        self.assertIsNotNone(fila.agente)
        self.assertNotEqual(fila.accion, 'CIERRE_AUTOMATICO')

    def test_el_fin_es_la_hora_del_clic_y_no_un_valor_calculado(self):
        """La otra diferencia de fondo: aquí el reloj sí decide el dato."""
        antes = timezone.now()

        self.finalizar()

        cronometro = self.recargar()
        self.assertGreaterEqual(cronometro.fin, antes)
        self.assertLessEqual(cronometro.fin, timezone.now())

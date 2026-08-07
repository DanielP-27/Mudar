"""Pruebas del predicado único de cumplimiento (server/cumplimiento.py).

SimpleTestCase y no TestCase a propósito: prohíbe el acceso a base de datos, así
que estas pruebas demuestran además que las funciones no consultan nada. Los
modelos se instancian SIN guardar; leer un campo no dispara ninguna consulta.

veredicto_tiempo, veredictos_planeacion y veredictos_dom no están aquí: recorren
relaciones y necesitan fixtures. Van después del catálogo semilla.

Se importan las CONSTANTES y no sus textos, para que renombrar una etiqueta no
ponga en rojo diez pruebas sin que ninguna regla haya cambiado.
"""
from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from server.cumplimiento import (
    ANOMALO,
    CUMPLIO,
    EN_CURSO,
    NO_CUMPLIO,
    PARCIAL,
    PENDIENTE,
    consolidar,
    cronometro_anomalo,
    veredicto_almacen,
    veredicto_despacho,
    veredicto_produccion,
    veredicto_tratamiento,
)
from server.models import (
    Dom,
    RegistroAlmacen,
    RegistroProduccion,
    RegistroTiempoProduccion,
    RegistroTratamiento,
)


class VeredictoBooleanoTests(SimpleTestCase):
    """Las cuatro etapas cuyo veredicto es un booleano nulable."""

    # (función de veredicto, modelo donde vive el dato, campo que lo guarda)
    ETAPAS = [
        (veredicto_almacen, RegistroAlmacen, 'dom_realizado_planeacion'),
        (veredicto_produccion, RegistroProduccion, 'segun_planeacion'),
        (veredicto_tratamiento, RegistroTratamiento, 'tratamiento_segun_planeacion'),
        (veredicto_despacho, Dom, 'dom_entregado_ok'),
    ]

    def test_registro_ausente_es_pendiente(self):
        for veredicto, modelo, _campo in self.ETAPAS:
            with self.subTest(etapa=modelo.__name__):
                self.assertEqual(veredicto(None), PENDIENTE)

    def test_nulo_es_pendiente_y_falso_es_incumplimiento(self):
        # El defecto de fondo: el all() de las vistas trataba el nulo como falso.
        casos = [(None, PENDIENTE), (True, CUMPLIO), (False, NO_CUMPLIO)]
        for veredicto, modelo, campo in self.ETAPAS:
            for valor, esperado in casos:
                with self.subTest(etapa=modelo.__name__, valor=valor):
                    registro = modelo(**{campo: valor})
                    self.assertEqual(veredicto(registro), esperado)


class CronometroAnomaloTests(SimpleTestCase):
    """ANÓMALO no es PENDIENTE: el tiempo no lo resuelve, exige intervención."""

    def cronometro(self, **campos):
        return RegistroTiempoProduccion(**campos)

    def test_sin_cronometro_no_hay_anomalia(self):
        self.assertFalse(cronometro_anomalo(None))

    def test_en_curso_dentro_del_tope(self):
        c = self.cronometro(estado='EN_CURSO',
                            inicio=timezone.now() - timedelta(minutes=60))
        self.assertFalse(cronometro_anomalo(c))

    def test_en_curso_pasado_el_tope(self):
        c = self.cronometro(estado='EN_CURSO',
                            inicio=timezone.now() - timedelta(minutes=700))
        self.assertTrue(cronometro_anomalo(c))

    def test_pausado_y_olvidado(self):
        # PAUSADO cuenta porque finalizar exige EN_CURSO: si no, se congela.
        c = self.cronometro(estado='PAUSADO',
                            inicio=timezone.now() - timedelta(minutes=700))
        self.assertTrue(cronometro_anomalo(c))

    def test_en_curso_sin_inicio(self):
        c = self.cronometro(estado='EN_CURSO', inicio=None)
        self.assertTrue(cronometro_anomalo(c))

    def test_finalizado_sin_minutos(self):
        # Finalizado sin minutos es dato roto, no dato ausente.
        c = self.cronometro(estado='FINALIZADO', minutos_totales=None)
        self.assertTrue(cronometro_anomalo(c))

    def test_finalizado_plausible(self):
        c = self.cronometro(estado='FINALIZADO', minutos_totales=300)
        self.assertFalse(cronometro_anomalo(c))

    def test_finalizado_por_encima_del_maximo(self):
        c = self.cronometro(estado='FINALIZADO', minutos_totales=601)
        self.assertTrue(cronometro_anomalo(c))

    def test_finalizado_de_cero_minutos(self):
        # Los 18 cronómetros del defecto 8.1.4, invisibles hasta ahora.
        c = self.cronometro(estado='FINALIZADO', minutos_totales=0)
        self.assertTrue(cronometro_anomalo(c))

    def test_limites_exactos_son_validos(self):
        # 600 y 1 son plausibles: el código usa > y <, no >= ni <=.
        for minutos in (600, 1):
            with self.subTest(minutos=minutos):
                c = self.cronometro(estado='FINALIZADO', minutos_totales=minutos)
                self.assertFalse(cronometro_anomalo(c))


class ConsolidarTests(SimpleTestCase):
    """Veredicto de un conjunto: un DOM, una planeación, un rango de fechas."""

    def test_conjunto_vacio(self):
        self.assertEqual(consolidar([]), PENDIENTE)

    def test_anomalo_gana_sobre_cumplimiento(self):
        self.assertEqual(consolidar([ANOMALO, CUMPLIO]), ANOMALO)

    def test_anomalo_gana_sobre_incumplimiento(self):
        # Un solo cronómetro anómalo hace incalculable el total del conjunto.
        self.assertEqual(consolidar([ANOMALO, NO_CUMPLIO]), ANOMALO)

    def test_mezcla_con_cumplimiento_es_parcial(self):
        # PARCIAL se comprueba ANTES que NO_CUMPLIÓ: n_no es cierto en ambos.
        self.assertEqual(consolidar([NO_CUMPLIO, CUMPLIO]), PARCIAL)

    def test_mezcla_con_pendiente_es_parcial(self):
        self.assertEqual(consolidar([NO_CUMPLIO, PENDIENTE]), PARCIAL)

    def test_solo_incumplimientos(self):
        self.assertEqual(consolidar([NO_CUMPLIO]), NO_CUMPLIO)
        self.assertEqual(consolidar([NO_CUMPLIO, NO_CUMPLIO]), NO_CUMPLIO)

    def test_pendientes_sin_incumplimientos_es_en_curso(self):
        # Decisión del 2026-07-30: "va bien pero no ha terminado" es distinto.
        self.assertEqual(consolidar([CUMPLIO, PENDIENTE]), EN_CURSO)

    def test_todo_pendiente(self):
        # Decisión REVISABLE, así marcada en cumplimiento.py: podría ser EN_CURSO.
        self.assertEqual(consolidar([PENDIENTE]), PENDIENTE)

    def test_todo_cumplido(self):
        self.assertEqual(consolidar([CUMPLIO, CUMPLIO]), CUMPLIO)

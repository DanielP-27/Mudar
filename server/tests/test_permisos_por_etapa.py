"""Los seis roles y las etapas que cada uno puede editar.

puede_editar_etapas es la única autorización por etapa del sistema y tiene un solo
consumidor: el PUT de DomDetalleView. Hasta hoy no tenía ninguna prueba.

El defecto que estas pruebas vigilan no se manifiesta como error. Si un nombre de rol
deja de coincidir entre ROLES_CHOICES y las llaves del diccionario 'permisos', el
.get(self.rol, []) devuelve lista vacía y ese rol pierde TODAS sus etapas: la aplicación
responde 403 como si fuera una denegación legítima. Nadie sospecha de un fallo, porque
el mensaje suena correcto.

SimpleTestCase y no TestCase a propósito: el método es lectura pura de un diccionario y
no toca la base. Si alguien mete una consulta dentro, esta clase falla por haberla tocado.
"""
from django.test import SimpleTestCase

from server.models import PerfilUsuario

LAS_SIETE = ['etapa_0', 'etapa_1', 'etapa_2', 'etapa_3', 'etapa_4', 'etapa_5', 'etapa_6']

# El mapeo esperado se escribe aquí entero y a mano. No se deriva del diccionario que
# vigila: una prueba que leyera la misma estructura que comprueba no probaría nada.
ESPERADO = {
    'GERENCIA': set(),
    'ADMIN': {'etapa_0', 'etapa_1', 'etapa_2', 'etapa_3', 'etapa_4', 'etapa_5', 'etapa_6'},
    'ANALISTA_1': {'etapa_0', 'etapa_1', 'etapa_6'},
    'ANALISTA_2': {'etapa_0', 'etapa_1', 'etapa_6'},
    'PLANEADOR': {'etapa_2'},
    'LIDER_PLANTA': {'etapa_3', 'etapa_4', 'etapa_5'},
}


def etapas_de(rol):
    """Las etapas permitidas de un rol, preguntando una por una por las siete.

    El perfil se instancia sin guardarse: puede_editar_etapas solo lee self.rol."""
    perfil = PerfilUsuario(rol=rol)
    return {etapa for etapa in LAS_SIETE if perfil.puede_editar_etapas(etapa)}


class PermisosPorEtapaTests(SimpleTestCase):
    """Un caso por rol. Se comparan CONJUNTOS COMPLETOS y no etapa por etapa, para que
    la prueba detecte las dos direcciones del error: una etapa que falta y una de más."""

    def test_admin_puede_las_siete(self):
        self.assertEqual(etapas_de('ADMIN'), ESPERADO['ADMIN'])

    def test_analista_1_puede_cero_uno_y_seis(self):
        self.assertEqual(etapas_de('ANALISTA_1'), ESPERADO['ANALISTA_1'])

    def test_analista_2_puede_cero_uno_y_seis(self):
        self.assertEqual(etapas_de('ANALISTA_2'), ESPERADO['ANALISTA_2'])

    def test_planeador_solo_puede_la_dos(self):
        self.assertEqual(etapas_de('PLANEADOR'), ESPERADO['PLANEADOR'])

    def test_lider_planta_puede_tres_cuatro_y_cinco(self):
        self.assertEqual(etapas_de('LIDER_PLANTA'), ESPERADO['LIDER_PLANTA'])

    def test_gerencia_no_puede_ninguna(self):
        # Solo lectura: es el único rol cuyo conjunto vacío es intencional y no un síntoma.
        self.assertEqual(etapas_de('GERENCIA'), ESPERADO['GERENCIA'])


class CoberturaDeRolesTests(SimpleTestCase):
    """Los seis casos de arriba solo interrogan a los roles que ya conocen. Un rol nuevo
    en ROLES_CHOICES sin entrada en 'permisos' los dejaría a todos en verde."""

    def test_todo_rol_declarado_tiene_expectativa_escrita(self):
        declarados = {rol for rol, _ in PerfilUsuario.ROLES_CHOICES}
        self.assertEqual(declarados, set(ESPERADO))

    def test_un_rol_inexistente_no_puede_nada(self):
        # Fija por escrito que el sistema deniega por omisión. Es lo que ya hace, pero
        # hasta ahora era una consecuencia del .get() y no una decisión declarada.
        self.assertEqual(etapas_de('ROL_QUE_NO_EXISTE'), set())

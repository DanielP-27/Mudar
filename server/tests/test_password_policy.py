"""La política de AUTH_PASSWORD_VALIDATORS debe aplicarse también por la API.

El panel de Django ya la aplica de fábrica: sus formularios llaman a
validate_password por su cuenta. Los tres serializers de contraseña son el
otro camino —hoy sin pantalla que los consuma— y comprueban a mano sólo dos
de las cuatro reglas declaradas. Estas pruebas se escribieron ANTES del
arreglo, y fallaban.

Necesitan base de datos: CrearUsuarioSerializer consulta la unicidad del
username y RestablecerPasswordSerializer carga el usuario por su id.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from server.serializers import (
    CambioPasswordSerializer,
    CrearUsuarioSerializer,
    RestablecerPasswordSerializer,
)

# Cumple las cuatro reglas: ni común, ni numérica, ni corta, ni parecida al usuario.
PASSWORD_BUENA = 'X7k#pL2mQ9'


class _PeticionFalsa:
    """CambioPasswordSerializer necesita el usuario autenticado para que
    UserAttributeSimilarityValidator tenga con qué comparar."""

    def __init__(self, user):
        self.user = user


class PoliticaPasswordAPITests(TestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(
            username='leidy.becerra',
            first_name='Leidy',
            last_name='Becerra',
            email='leidy@mudar.com',
            password=PASSWORD_BUENA,
        )

    # ── Constructores de los tres serializers ────────────────────────────────

    def _alta(self, password):
        return CrearUsuarioSerializer(data={
            'username': 'nuevo.operario',
            'first_name': 'Nuevo',
            'last_name': 'Operario',
            'email': 'nuevo@mudar.com',
            'password': password,
            'confirmar_password': password,
            'rol': 'PLANEADOR',
        })

    def _cambio(self, password):
        return CambioPasswordSerializer(
            data={
                'password_actual': PASSWORD_BUENA,
                'nuevo_password': password,
                'confirmar_password': password,
            },
            context={'request': _PeticionFalsa(self.usuario)},
        )

    def _restablecer(self, password):
        return RestablecerPasswordSerializer(data={
            'user_id': self.usuario.id,
            'nuevo_password': password,
            'confirmar_password': password,
        })

    # ── Contraseñas comunes: las rechaza CommonPasswordValidator ─────────────

    def test_alta_rechaza_password_comun(self):
        self.assertFalse(self._alta('password').is_valid())

    def test_cambio_rechaza_password_comun(self):
        self.assertFalse(self._cambio('qwerty123').is_valid())

    def test_restablecer_rechaza_password_comun(self):
        self.assertFalse(self._restablecer('Password1').is_valid())

    # ── Parecidas al usuario: las rechaza UserAttributeSimilarityValidator ───
    # Es el validador que obliga a pasar el objeto usuario. Si no llega, no
    # compara nada y estas tres pruebas lo detectan.

    def test_alta_rechaza_password_parecida_al_username(self):
        # El usuario aún no existe: el serializer debe construirlo sin guardar.
        self.assertFalse(self._alta('nuevo.operario1').is_valid())

    def test_cambio_rechaza_password_parecida_al_usuario_autenticado(self):
        self.assertFalse(self._cambio('leidy.becerra1').is_valid())

    def test_restablecer_rechaza_password_parecida_al_usuario_destino(self):
        self.assertFalse(self._restablecer('leidy.becerra1').is_valid())

    # ── Reglas que ya se cumplían: no deben perderse al centralizar ──────────

    def test_alta_rechaza_password_solo_numerica(self):
        self.assertFalse(self._alta('849302175').is_valid())

    def test_alta_rechaza_password_corta(self):
        self.assertFalse(self._alta('X7k#pL').is_valid())

    # ── Control: una contraseña válida debe seguir pasando ───────────────────
    # Sin estos casos, un serializer que lo rechazara todo pasaría la suite.

    def test_alta_acepta_password_fuerte(self):
        serializer = self._alta('T4b!vRz8Wq')
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_cambio_acepta_password_fuerte(self):
        serializer = self._cambio('T4b!vRz8Wq')
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_restablecer_acepta_password_fuerte(self):
        serializer = self._restablecer('T4b!vRz8Wq')
        self.assertTrue(serializer.is_valid(), serializer.errors)

    # ── El error debe ir atado al campo, no al objeto ────────────────────────
    # Si sale como error general, una pantalla futura no puede señalar el campo.

    def test_el_error_se_atribuye_al_campo_password(self):
        serializer = self._alta('password')
        serializer.is_valid()
        self.assertIn('password', serializer.errors)

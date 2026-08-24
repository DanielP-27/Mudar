"""Cerrar sesión invalida el token en el servidor, no solo en el navegador.

El frontend borra su copia de localStorage y navega al ingreso, así que desde la
pantalla un logout roto es indistinguible de uno correcto: el usuario sale igual y
nada delata que su credencial sigue viva. Lo único que lo delata es intentar usarla.

Son guardas de regresión, no TDD: el comportamiento ya funciona. Existen porque el
fallo no tendría síntoma visible.
"""
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from server.models import PerfilUsuario

URL_LOGOUT = '/api/auth/logout/'
URL_PERFIL = '/api/auth/perfil/'


class CierreDeSesionTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username='angel.perez', password='X7k#pL2mQ9')
        PerfilUsuario.objects.create(user=self.usuario, rol='ADMIN')
        self.token = Token.objects.create(user=self.usuario)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

    def test_el_logout_borra_el_token(self):
        respuesta = self.client.post(URL_LOGOUT)

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())

    def test_el_token_ya_no_autentica_despues_del_logout(self):
        """Se consulta PerfilView porque es lo que el frontend llama al arrancar: si la
        credencial sobreviviera, una sesión cerrada volvería sola con solo recargar."""
        self.client.post(URL_LOGOUT)

        respuesta = self.client.get(URL_PERFIL)

        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)

"""Un intento de acceso fallido deja una línea con la IP de origen.

Es el insumo de fail2ban: sin esa línea no hay nada que vigilar y el bloqueo por
reincidencia no puede existir. La respuesta al cliente no cambia — sigue siendo el 401
genérico, que es lo que impide enumerar usuarios.

assertLogs captura el mensaje en memoria, así que estas pruebas no dependen de que haya
manejadores configurados: LOGGING vive dentro de `if not DEBUG` y en desarrollo no se
evalúa.
"""
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from server.models import PerfilUsuario

URL = '/api/auth/login/'
LOGGER = 'server.seguridad'
PASSWORD = 'X7k#pL2mQ9'


class LogLoginFallidoTests(APITestCase):

    def setUp(self):
        self.usuario = User.objects.create_user(username='angel.perez', password=PASSWORD)
        PerfilUsuario.objects.create(user=self.usuario, rol='ADMIN')
        self.client = APIClient()

    def entrar(self, username='angel.perez', password=PASSWORD, ip='190.85.12.34'):
        return self.client.post(
            URL, {'username': username, 'password': password},
            format='json', REMOTE_ADDR=ip,
        )

    def test_el_fallo_deja_linea_con_usuario_e_ip(self):
        with self.assertLogs(LOGGER, level='WARNING') as registro:
            respuesta = self.entrar(password='incorrecta')

        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)
        linea = registro.output[0]
        self.assertIn('Login fallido', linea)
        self.assertIn('usuario=angel.perez', linea)
        self.assertIn('ip=190.85.12.34', linea)

    def test_la_ip_sale_de_la_cabecera_del_proxy_si_existe(self):
        """Con Nginx delante, REMOTE_ADDR es el proxy. La IP real viaja en
        X-Forwarded-For y es la que fail2ban debe bloquear."""
        with self.assertLogs(LOGGER, level='WARNING') as registro:
            self.client.post(
                URL, {'username': 'angel.perez', 'password': 'incorrecta'},
                format='json',
                REMOTE_ADDR='127.0.0.1',
                HTTP_X_FORWARDED_FOR='201.14.55.9, 10.0.0.7',
            )

        self.assertIn('ip=201.14.55.9', registro.output[0])

    def test_la_linea_no_contiene_la_contrasena(self):
        with self.assertLogs(LOGGER, level='WARNING') as registro:
            self.entrar(password='SuperSecreta123')

        self.assertNotIn('SuperSecreta123', registro.output[0])

    def test_el_usuario_no_puede_fabricar_lineas_falsas(self):
        """El nombre lo escribe quien intenta entrar: un salto de línea permitiría
        inyectar entradas propias en el archivo que fail2ban analiza."""
        with self.assertLogs(LOGGER, level='WARNING') as registro:
            self.entrar(username='falso\nLogin fallido usuario=otro ip=1.2.3.4')

        linea = registro.output[0]
        self.assertNotIn('\n', linea)
        self.assertEqual(len(registro.output), 1)

    def test_el_ingreso_correcto_no_registra_nada(self):
        with self.assertNoLogs(LOGGER, level='WARNING'):
            respuesta = self.entrar()

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)

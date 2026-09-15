"""Siembra las siete tablas de configuración sobre una base recién migrada.

Lo que se versiona es este mecanismo, no los datos: semilla.json lleva usuarios,
clientes y productos reales de Mudar y viaja fuera de git, junto a la copia cifrada
de los dos .env. ejemplo.json sí está en el repositorio, con filas inventadas, para
poder levantar una base de juguete.

El comando no vacía nada: exige una base recién migrada y se niega si encuentra
una sola fila.
"""
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from server.models import (Cliente, FamiliaProducto, ListaPredefinida, PerfilUsuario,
                           Productos, Turno)

CARPETA = Path(settings.BASE_DIR) / 'server' / 'semilla'

# Las siete que siembra el archivo. El orden es el que imponen las FK, y el mismo en
# que se genera semilla.json: los usuarios primero, porque ListaPredefinida.creado_por
# es obligatorio y RESTRICT; los productos al final, porque apuntan a una familia.
CONFIGURACION = [User, PerfilUsuario, FamiliaProducto, Turno, Cliente, ListaPredefinida, Productos]


class Command(BaseCommand):
    help = 'Siembra las siete tablas de configuración sobre una base recién migrada.'

    def add_arguments(self, parser):
        parser.add_argument('--ejemplo', action='store_true',
                            help='Siembra ejemplo.json, la base de juguete. Solo con DEBUG=True.')
        parser.add_argument('--simular', action='store_true',
                            help='Comprueba que la base esté vacía y no escribe nada.')

    def handle(self, *args, **opciones):
        archivo = self._archivo(opciones['ejemplo'])
        self._exigir_base_vacia()

        if opciones['simular']:
            self.stdout.write(self.style.WARNING(
                f'Simulación: la base está vacía y {archivo.name} existe. No se escribió nada.'))
            return

        # loaddata abre su propia transacción y al terminar reajusta las secuencias:
        # sin eso, sembrar el turno con pk 3 dejaría la secuencia en 1.
        call_command('loaddata', str(archivo), verbosity=0)

        self._resumen(archivo)

    def _archivo(self, es_ejemplo):
        if es_ejemplo:
            # La base de juguete es pública y su ADMIN no tiene contraseña utilizable.
            if not settings.DEBUG:
                raise CommandError('--ejemplo no se permite con DEBUG=False: es una base '
                                   'de juguete, versionada en un repositorio público.')
            nombre = 'ejemplo.json'
        else:
            nombre = 'semilla.json'

        archivo = CARPETA / nombre
        if not archivo.exists():
            raise CommandError(f'No existe {archivo}. La semilla real no viaja en git: '
                               f'cópiala desde el respaldo cifrado, o usa --ejemplo.')
        return archivo

    def _exigir_base_vacia(self):
        # Se le pregunta a Django qué tablas existen en vez de escribir la lista a mano:
        # así un modelo nuevo entra solo en la guarda y no puede quedarse fuera por olvido.
        modelos = [User] + list(apps.get_app_config('server').get_models())

        conteos = [(modelo._meta.db_table, modelo.objects.count()) for modelo in modelos]
        pobladas = sorted((tabla, filas) for tabla, filas in conteos if filas)

        if pobladas:
            detalle = '\n'.join(f'  {tabla}: {filas} filas' for tabla, filas in pobladas)
            raise CommandError('La base no está vacía y no se sembró nada. Tablas con '
                               f'contenido:\n{detalle}')

    def _resumen(self, archivo):
        self.stdout.write(f'Sembrado desde {archivo.name}:')
        for modelo in CONFIGURACION:
            self.stdout.write(f'  {modelo._meta.db_table:<20} {modelo.objects.count()}')

        self.stdout.write(self.style.SUCCESS('Semilla cargada.'))
        self.stdout.write(self.style.WARNING(
            'Faltan las contraseñas: manage.py changepassword <usuario>, una por usuario.'))

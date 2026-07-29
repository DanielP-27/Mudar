from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from datetime import timedelta

# Minutos de INACTIVIDAD antes de cerrar sesión.
# Única fuente de verdad: la vista de login publica este valor al frontend.
TOKEN_EXPIRY_MINUTES = 60


class ExpiringTokenAuthentication(TokenAuthentication):
    """
    Caducidad deslizante: el token muere tras TOKEN_EXPIRY_MINUTES sin uso.
    Cada petición autenticada reinicia el contador, así que quien trabaja no
    pierde la sesión.

    'created' se usa como marca de último uso — el modelo Token de DRF no
    tiene un campo propio para eso y no compensa definir un modelo aparte.
    """

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)

        # Validar antes de renovar: al revés, un token vencido se resucitaría
        # a sí mismo y la caducidad nunca ocurriría.
        if (timezone.now() - token.created) > timedelta(minutes=TOKEN_EXPIRY_MINUTES):
            token.delete()
            raise AuthenticationFailed(
                'Sesión expirada por inactividad, por favor inicie sesión nuevamente'
            )

        # Esta petición cuenta como actividad.
        token.created = timezone.now()
        token.save(update_fields=['created'])

        return user, token

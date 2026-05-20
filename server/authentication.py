from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from datetime import timedelta

TOKEN_EXPIRY_MINUTES = 25

class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if (timezone.now() - token.created) > timedelta(minutes=TOKEN_EXPIRY_MINUTES):
            token.delete()
            raise AuthenticationFailed(
                'Sesión expirada, por favor inicie sesión nuevamente'
            )
        return user, token

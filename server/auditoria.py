"""Registro de AuditoriaDom y resolución de la IP del cliente.

Fuera de views.py porque no solo lo llaman las vistas: el cierre automático
audita sin petición, y tenerlo aquí evita que ese módulo y views se importen
mutuamente. Solo depende de models.
"""
from .models import AuditoriaDom


# Detrás de un proxy REMOTE_ADDR es el proxy: la IP real viaja en X-Forwarded-For
def obtener_ip(request):
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# Centraliza que  la creación de registros de AuditoriaDom ante accciones relevantes (creacion, edicion, bloqueo o desbloqueo etapa, eliminación)
def registrar_auditoria(dom, usuario, accion, request, etapa=None, campos_modificados=None):

    # objects.create() no valida choices: sin esta guarda entra cualquier cadena
    if accion not in dict(AuditoriaDom.ACTION_CHOICES):
        raise ValueError('Acción de auditoría no declarada: %r' % accion)

    # El cierre automático es la única acción sin autor: atarlo a la ausencia de
    # petición impide atribuírselo al usuario que navegaba cuando corrió el barrido.
    if request is None and accion != 'CIERRE_AUTOMATICO':
        raise ValueError('Solo el cierre automático se audita sin petición: %r' % accion)
    if request is not None and accion == 'CIERRE_AUTOMATICO':
        raise ValueError('El cierre automático no se atribuye a una petición')

    if request is not None:
        ip = obtener_ip(request)
        agente = (request.META.get('HTTP_USER_AGENT') or '')[:255] or None
    else:
        ip = agente = None

    AuditoriaDom.objects.create(
        dom = dom,
        usuario = usuario,
        accion = accion,
        etapa = etapa,
        campos_modificados = campos_modificados,
        ip = ip,
        agente = agente,
    )

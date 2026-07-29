from django.contrib import admin
from rest_framework.authtoken.models import TokenProxy
from .models import(
    FamiliaProducto,
    Turno,
    ListaPredefinida,
    PerfilUsuario,
    AuditoriaDom
)

admin.site.register(FamiliaProducto)
admin.site.register(Turno)
admin.site.register(ListaPredefinida)
admin.site.register(PerfilUsuario)

# DRF muestra la clave del token en texto plano en su listado.
admin.site.unregister(TokenProxy)


@admin.register(AuditoriaDom)
class AuditoriaDomAdmin(admin.ModelAdmin):
    """Solo consulta:"""

    list_display = ('timestamp', 'dom', 'usuario', 'accion', 'etapa')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

from django.contrib import admin
from .models import(
    Cliente,
    FamiliaProducto,
    Productos, 
    Turno, 
    ListaPredefinida,
    Dom,
    ProductosDom,
    RegistroPlaneacion,
    RegistroAlmacen,
    RegistroProduccion,
    RegistroTiempoProduccion,
    PausaTiempoProduccion,
    RegistroTratamiento,
    PerfilUsuario,
    AuditoriaDom
)

admin.site.register(Cliente)
admin.site.register(FamiliaProducto)
admin.site.register(Productos)
admin.site.register(Turno)
admin.site.register(ListaPredefinida)
admin.site.register(Dom)
admin.site.register(ProductosDom)
admin.site.register(RegistroPlaneacion)
admin.site.register(RegistroAlmacen)
admin.site.register(RegistroProduccion)
admin.site.register(RegistroTiempoProduccion)
admin.site.register(PausaTiempoProduccion)
admin.site.register(RegistroTratamiento)
admin.site.register(PerfilUsuario)
admin.site.register(AuditoriaDom)
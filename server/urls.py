"""
URL configuration for server project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from server.views import(

    # Módulo 1 - Autenciación usuarios
    LoginView,
    LogoutView,
    PerfilView,
    RestablecerPasswordView,
    UsuarioListView,
    UsuarioDetalleView,

    # Módulo 2 - Catálogos
    ClienteListView,
    ClienteDetalleView,
    ProductoListView,
    ProductoDetalleView,
    TurnoListView,
    TurnoDetalleView,
    ListaPredefinidaListView,
    ListaPredefinidaDetalleView,

    # Módulo 3 - DOMs
    DomListView,
    DomDetalleView,

    # Módulo 4 - Etapas
    RegistroPlaneacionListView,
    RegistroPlaneacionDetalleView,
    RegistroAlmacenListView,
    RegistroAlmacenDetalleView,
    RegistroProduccionListView,
    RegistroProduccionDetalleView,
    RegistroTratamientoListView,
    RegistroTratamientoDetalleView,

    # Modulo 5 - Cronometro 
    CronometroIniciarView,
    CronometroPausaView,
    CronometroReanudarView,
    CronometroFinalizarView,

    # Módulo 6 - Reportes y Dashboard
    DashboardView,
    InformeCumplimientoPlaneacion,
    InformeDespachoView,
    DomReporteView,
    InformeAuditoriaView,
)

urlpatterns = [
    
    # path admin, necesario para acceso interfaz Django
    path('admin/', admin.site.urls), 

    # Módulo 1 - Autenticación
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/logout/', LogoutView.as_view(), name='logout'),
    path('api/auth/perfil/', PerfilView.as_view(), name='perfil'),
    path('api/auth/usuarios/', UsuarioListView.as_view(), name='usuarios'),
    path('api/auth/usuarios/<int:user_id>/', UsuarioDetalleView.as_view(), name='usuario-detalle'),
    path('api/auth/reestablecer-password/', RestablecerPasswordView.as_view(), name='reestablecer-password'),

    # Módulo 2 - catálogos
    path('api/clientes/', ClienteListView.as_view(), name='clientes'),
    path('api/clientes/<int:cliente_id>/', ClienteDetalleView.as_view(), name='cliente-detalle'),
    path('api/productos/', ProductoListView.as_view(), name='productos'),
    path('api/productos/<int:producto_id>/', ProductoDetalleView.as_view(), name='producto-detalle'),
    path('api/turnos/', TurnoListView.as_view(), name='turnos'),
    path('api/turnos/<int:turno_id>/', TurnoDetalleView.as_view(), name='turno-detalle'),
    path('api/listas/', ListaPredefinidaListView.as_view(), name='listas'),
    path('api/listas/<int:lista_id>/', ListaPredefinidaDetalleView.as_view(), name='lista-detalle'),

    # Módulo 3 - DOMs
    path('api/doms/', DomListView.as_view(), name='doms'),
    path('api/doms/<int:dom_id>/', DomDetalleView.as_view(), name='dom-detalle'),

    # Módulo 4 - Etapas 2, 3, 4, 5 (etapas 1 y 6 traen directamente su información de DOM, no es necesario crear rutas especificas)
    path('api/planeacion/', RegistroPlaneacionListView.as_view(), name='planeacion'),
    path('api/planeacion/<int:registro_id>/', RegistroPlaneacionDetalleView.as_view(), name='planeacion-detalle'),
    path('api/almacen/', RegistroAlmacenListView.as_view(), name='almacen'),
    path('api/almacen/<int:registro_id>/', RegistroAlmacenDetalleView.as_view(), name='almacen-detalle'),
    path('api/produccion/', RegistroProduccionListView.as_view(), name='produccion'),
    path('api/produccion/<int:registro_id>/', RegistroProduccionDetalleView.as_view(), name='produccion-detalle'),
    path('api/tratamiento/', RegistroTratamientoListView.as_view(), name='tratamiento'),
    path('api/tratamiento/<int:registro_id>/', RegistroTratamientoDetalleView.as_view(), name='tratamiento-detalle'),

    # Módulo 5 - cronometro
    path('api/cronometro/iniciar/', CronometroIniciarView.as_view(), name='cronometro-iniciar'),
    path('api/cronometro/pausar/', CronometroPausaView.as_view(), name='cronometro-pausar'),
    path('api/cronometro/reanudar/', CronometroReanudarView.as_view(), name='cronometro-reanudar'),
    path('api/cronometro/finalizar/', CronometroFinalizarView.as_view(), name='cronometro-finalizar'),

    # Módulo 6 - Reportes y dashboard
    path('api/dashboard/', DashboardView.as_view(), name='dashboard'),
    path('api/informes/cumplimiento/', InformeCumplimientoPlaneacion.as_view(), name='informe-cumplimiento'),
    path('api/informes/despacho/', InformeDespachoView.as_view(), name='informe-despacho'),
    path('api/informes/auditoria/', InformeAuditoriaView.as_view(), name='informe-auditoria'),
    path('api/reportes/dom/<int:dom_id>/', DomReporteView.as_view(), name='reporte-dom'),
]
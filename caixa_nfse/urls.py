"""
URL configuration for caixa_nfse project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # Apps
    path("", include("caixa_nfse.core.urls")),
    path("caixa/", include("caixa_nfse.caixa.urls")),
    path("clientes/", include("caixa_nfse.clientes.urls")),
    path("nfse/", include("caixa_nfse.nfse.urls")),
    path("contabil/", include("caixa_nfse.contabil.urls")),
    path("fiscal/", include("caixa_nfse.fiscal.urls")),
    path("auditoria/", include("caixa_nfse.auditoria.urls")),
    path("relatorios/", include("caixa_nfse.relatorios.urls")),
    # API
    path("api/v1/", include("caixa_nfse.api.urls")),
    # Backoffice (Platform Admin)
    path("platform/", include("caixa_nfse.backoffice.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Debug toolbar
    try:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

# Admin customization
admin.site.site_header = "Sistema de Caixa - NFS-e"
admin.site.site_title = "Caixa NFS-e Admin"
admin.site.index_title = "Painel Administrativo"

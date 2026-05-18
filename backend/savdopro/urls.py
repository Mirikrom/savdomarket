"""Top-level URL configuration for the savdopro project.

Auth endpoints all live under ``/api/v1/auth/`` and are defined in
``accounts.urls`` (``auth_urls``). Per-resource viewsets live at
``/api/v1/accounts/`` and other app URLs are mounted directly under
``/api/v1/``.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.urls import auth_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include((auth_urls, "auth"))),
    path("api/v1/accounts/", include("accounts.urls")),
    path("api/v1/", include("shops.urls")),
    path("api/v1/", include("subscriptions.urls")),
    path("api/v1/", include("catalog.urls")),
    path("api/v1/", include("inventory.urls")),
    path("api/v1/", include("sales.urls")),
    path("api/v1/provider/", include("provider.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

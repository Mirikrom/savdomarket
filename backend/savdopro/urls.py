"""Top-level URL configuration for the savdopro project.

Auth endpoints all live under ``/api/v1/auth/`` and are defined in
``accounts.urls`` (``auth_urls``). Per-resource viewsets live at
``/api/v1/accounts/`` and other app URLs are mounted directly under
``/api/v1/``.
"""

import re

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

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
elif getattr(settings, 'SERVE_MEDIA', False):
    # static() DEBUG=False da [] qaytaradi — nginx bo‘lmaguncha serve ishlatamiz
    media_prefix = settings.MEDIA_URL.lstrip('/')
    urlpatterns += [
        re_path(
            rf'^{re.escape(media_prefix)}(?P<path>.*)$',
            serve,
            {'document_root': settings.MEDIA_ROOT},
        ),
    ]

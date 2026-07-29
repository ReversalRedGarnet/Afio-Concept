"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Gives us /login/, /logout/, and the password-change pages for free.
    path("", include("django.contrib.auth.urls")),
    path("", include("records.urls")),
]

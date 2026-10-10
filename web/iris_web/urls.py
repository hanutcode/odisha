from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy

from workspace.login_view import TeamLoginView

urlpatterns = [
    path("login/", TeamLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password/", auth_views.PasswordChangeView.as_view(
        template_name="workspace/password.html", success_url=reverse_lazy("dashboard")), name="password_change"),
    path("admin/", admin.site.urls),
    path("", include("workspace.urls")),
]

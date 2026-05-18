from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import (
    ForgotPasswordRequestView,
    ForgotPasswordVerifyView,
    LoginView,
    LogoutView,
    OrganizationUserViewSet,
    RegisterCompleteView,
    RegisterRequestOtpView,
    RegisterVerifyOtpView,
    ResetPasswordView,
    RevokeSessionView,
    RoleViewSet,
    SetLanguageView,
    UserSessionViewSet,
    UserViewSet,
    me,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="users")
router.register("roles", RoleViewSet, basename="roles")
router.register("organization-users", OrganizationUserViewSet, basename="organization-users")
router.register("sessions", UserSessionViewSet, basename="sessions")

auth_urls = [
    path("register/request-otp/", RegisterRequestOtpView.as_view(), name="register-request-otp"),
    path("register/verify-otp/", RegisterVerifyOtpView.as_view(), name="register-verify-otp"),
    path("register/complete/", RegisterCompleteView.as_view(), name="register-complete"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password/forgot/", ForgotPasswordRequestView.as_view(), name="password-forgot"),
    path("password/verify-code/", ForgotPasswordVerifyView.as_view(), name="password-verify"),
    path("password/reset/", ResetPasswordView.as_view(), name="password-reset"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("set-language/", SetLanguageView.as_view(), name="set-language"),
    path("sessions/<int:pk>/revoke/", RevokeSessionView.as_view(), name="session-revoke"),
]

urlpatterns = [
    path("me/", me, name="me"),
    path("", include(router.urls)),
]

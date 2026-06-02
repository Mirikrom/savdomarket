"""Auth + account management views.

The auth endpoints are intentionally **unauthenticated** (``AllowAny``) and
**throttled** (see ``settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']``) so
the SMS layer above can't be abused.

Each endpoint corresponds to a single step in the documented flows in
``serializers.py``.
"""

from __future__ import annotations

from django.db.models import Q
from django.utils.translation import activate
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import OrganizationUser, Role, User, UserSession
from accounts.serializers import (
    ForgotPasswordRequestSerializer,
    ForgotPasswordVerifySerializer,
    InviteUserSerializer,
    LanguageSerializer,
    LoginSerializer,
    OrganizationUserSerializer,
    RegisterCompleteSerializer,
    RegisterRequestOtpSerializer,
    RegisterVerifyOtpSerializer,
    ResetPasswordSerializer,
    RoleSerializer,
    UserSerializer,
    UserSessionSerializer,
)
from accounts.services.audit import log_event
from accounts.services.sessions import revoke_refresh_token
from accounts.models import AuthAuditLog
from core.permissions import IsOrganizationMember, RolePermissionRequired
from core.tenant import get_membership


class RegisterRequestOtpView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = RegisterRequestOtpSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_200_OK)


class RegisterVerifyOtpView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request):
        serializer = RegisterVerifyOtpSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_200_OK)


class RegisterCompleteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        serializer = RegisterCompleteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.to_representation(serializer.validated_data))


class ForgotPasswordRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = ForgotPasswordRequestSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_200_OK)


class ForgotPasswordVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request):
        serializer = ForgotPasswordVerifySerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"detail": "refresh tokeni talab qilinadi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        session = revoke_refresh_token(refresh)
        log_event(
            request,
            AuthAuditLog.Event.LOGOUT,
            user=request.user,
            destination=request.user.phone or "",
            metadata={"session_id": getattr(session, "id", None)},
        )
        return Response({"detail": "Tizimdan chiqildi."})


class SetLanguageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LanguageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lang = serializer.validated_data["preferred_language"]
        request.user.preferred_language = lang
        request.user.save(update_fields=["preferred_language"])
        activate(lang)
        return Response({"preferred_language": lang})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """Return the current user along with their organization context.

    Resolution order for the "active" membership:
    1. If the client passed ``X-Organization-Id`` (or ``?organization_id=``)
       and the user actually belongs to it, use that.
    2. Otherwise, fall back to the user's first active membership so the
       frontend can bootstrap on a fresh login without already knowing the
       org id.
    """
    from core.tenant import active_organization_memberships

    from core.tenant import get_request_organization_id

    org_header_id = get_request_organization_id(request)
    membership = get_membership(request)
    if not membership and not request.user.is_superuser:
        membership = active_organization_memberships(request.user).order_by("id").first()

    memberships_qs = active_organization_memberships(request.user).order_by("id")
    support_mode = bool(
        request.user.is_superuser and org_header_id and membership is not None
    )

    return Response(
        {
            "user": UserSerializer(request.user).data,
            "is_superuser": bool(request.user.is_superuser),
            "is_provider_admin": bool(request.user.is_superuser),
            "support_mode": support_mode,
            "organization_id": membership.organization_id if membership else None,
            "organization_name": membership.organization.name if membership else None,
            "role": membership.role.code if membership else None,
            "branch_id": membership.branch_id if membership else None,
            "memberships": [
                {
                    "organization_id": m.organization_id,
                    "organization_name": m.organization.name,
                    "role": m.role.code,
                    "branch_id": m.branch_id,
                    "status": m.status,
                }
                for m in memberships_qs
            ],
        }
    )


class UserSessionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class RevokeSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        session = UserSession.objects.filter(pk=pk, user=request.user).first()
        if not session:
            return Response(status=status.HTTP_404_NOT_FOUND)
        session.revoke()
        log_event(
            request,
            AuthAuditLog.Event.SESSION_REVOKED,
            user=request.user,
            metadata={"session_id": session.id},
        )
        return Response({"revoked": True})


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("-id")
    serializer_class = UserSerializer
    permission_classes = [IsOrganizationMember, RolePermissionRequired]
    required_permission = "users.manage"

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return User.objects.none()
        return self.queryset.filter(organizations__organization=membership.organization).distinct()


class RoleViewSet(viewsets.ModelViewSet):
    """Role list available for a given organization.

    Returns:
    - System-wide template roles (``organization IS NULL`` and ``is_system=True``)
      that ship with every fresh SavdoPro install (owner, seller).
    - Plus any custom roles the organization itself has created.
    """

    queryset = Role.objects.select_related("organization").all().order_by("id")
    serializer_class = RoleSerializer
    permission_classes = [IsOrganizationMember]

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return Role.objects.none()
        from accounts.role_policy import ACTIVE_SYSTEM_ROLE_CODES

        return self.queryset.filter(
            Q(organization=membership.organization)
            | Q(
                organization__isnull=True,
                is_system=True,
                code__in=ACTIVE_SYSTEM_ROLE_CODES,
                is_active=True,
            )
        )

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        serializer.save(organization=membership.organization)


class OrganizationUserViewSet(viewsets.ModelViewSet):
    queryset = (
        OrganizationUser.objects.select_related("organization", "role", "user", "branch")
        .all()
        .order_by("-id")
    )
    serializer_class = OrganizationUserSerializer
    permission_classes = [IsOrganizationMember, RolePermissionRequired]
    required_permission = "organization_users.manage"

    def get_queryset(self):
        membership = get_membership(self.request)
        if not membership:
            return OrganizationUser.objects.none()
        return self.queryset.filter(organization=membership.organization)

    def perform_create(self, serializer):
        membership = get_membership(self.request)
        serializer.save(organization=membership.organization)

    @action(detail=False, methods=["post"], url_path="invite")
    def invite(self, request):
        """Create a new employee (user + organization membership) in one step.

        Body:
            {
                "phone": "+998...",
                "full_name": "Ali Valiyev",
                "role_id": <id from /accounts/roles/>,
                "branch_id": <optional>,
            }

        Response:
            {
                "membership": {...},
                "user_created": true|false,
                "temporary_password": "abc123" | null
            }

        The ``temporary_password`` is returned **only once**, when the user is
        newly created. The admin must hand it to the employee verbally.
        """
        membership = get_membership(request)
        if not membership:
            return Response(
                {"detail": "Organization membership is required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = InviteUserSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save(organization=membership.organization)
        return Response(result, status=status.HTTP_201_CREATED)

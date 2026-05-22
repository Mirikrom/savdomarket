import os
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import AuthAuditLog, OrganizationUser, Role, User
from accounts.serializers import InviteUserSerializer
from accounts.services.audit import log_event
from accounts.services.registration import bootstrap_owner
from provider.permissions import IsProviderAdmin
from provider.serializers import (
    ChangePlanSerializer,
    ExtendTrialSerializer,
    OrganizationDetailSerializer,
    OrganizationListSerializer,
    ProviderOrganizationWriteSerializer,
    ProviderPlanSerializer,
    ProviderPlanUpdateSerializer,
    ProviderUserListSerializer,
    ProviderBootstrapClientSerializer,
    ProviderChangePasswordSerializer,
    ProviderMemberRemoveSerializer,
    ProviderMemberRoleSerializer,
    SetRemainingDaysSerializer,
    SetUserActiveSerializer,
    MembershipLiteSerializer,
)
from shops.models import Branch, Organization
from subscriptions.models import Plan, Subscription


class ProviderUserPagination(LimitOffsetPagination):
    default_limit = 30
    max_limit = 100


class ProviderPlanViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Tariflar (Lite/Pro) — ko'rish va tahrirlash. `code` o'zgarmaydi."""

    permission_classes = [IsProviderAdmin]

    def get_queryset(self):
        now = timezone.now()
        return (
            Plan.objects.annotate(
                active_subscriptions=Count(
                    "subscriptions",
                    filter=Q(
                        subscriptions__status__in=[
                            Subscription.Status.ACTIVE,
                            Subscription.Status.GRACE,
                        ],
                        subscriptions__ends_at__gte=now,
                    ),
                )
            )
            .order_by("code")
        )

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return ProviderPlanUpdateSerializer
        return ProviderPlanSerializer


class ProviderUserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Mijoz foydalanuvchilari — platforma superadminlari ro'yxatda ko'rinmaydi."""

    permission_classes = [IsProviderAdmin]
    serializer_class = ProviderUserListSerializer
    pagination_class = ProviderUserPagination

    def get_queryset(self):
        qs = (
            User.objects.filter(is_superuser=False)
            .annotate(
                organizations_count=Count(
                    "organizations",
                    filter=Q(organizations__is_active=True),
                )
            )
            .order_by("-id")
        )
        params = self.request.query_params
        search = (params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(phone__icontains=search)
                | Q(full_name__icontains=search)
                | Q(email__icontains=search)
                | Q(username__icontains=search)
            )
        if params.get("is_active") == "1":
            qs = qs.filter(is_active=True)
        elif params.get("is_active") == "0":
            qs = qs.filter(is_active=False)
        if params.get("locked") == "1":
            qs = qs.filter(locked_until__isnull=False, locked_until__gt=timezone.now())
        return qs

    @action(detail=True, methods=["post"], url_path="unlock")
    def unlock(self, request, pk=None):
        user = self.get_object()
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=["failed_login_attempts", "locked_until"])
        return Response({"ok": True, "id": user.id})

    @action(detail=True, methods=["post"], url_path="set-active")
    def set_active(self, request, pk=None):
        user = self.get_object()
        if user.id == request.user.id:
            return Response(
                {"detail": "O'z akkauntingizni bu yerda o'chirib bo'lmaydi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = SetUserActiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        is_active = serializer.validated_data["is_active"]
        if not is_active and user.is_superuser:
            return Response(
                {"detail": "Superuser akkauntini bloklash mumkin emas."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = is_active
        user.save(update_fields=["is_active"])
        return Response({"id": user.id, "is_active": user.is_active})

    @action(detail=False, methods=["post"], url_path="bootstrap-client")
    def bootstrap_client(self, request):
        """Yangi tashkilot (do'kon) + uning egasi foydalanuvchisi + parol (mijozga berish)."""
        serializer = ProviderBootstrapClientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            user, organization, _membership = bootstrap_owner(
                phone=d["phone"],
                password=d["password"],
                full_name=d["full_name"],
                email=(d.get("email") or "").strip(),
                organization_name=d["organization_name"],
            )
        except IntegrityError:
            return Response(
                {"phone": ["Bu telefon raqami bilan akkaunt allaqachon mavjud."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        log_event(
            request,
            AuthAuditLog.Event.REGISTER_COMPLETED,
            user=user,
            destination=user.phone,
            metadata={
                "source": "provider_bootstrap_client",
                "organization_id": organization.id,
                "created_by_user_id": request.user.id,
            },
        )
        return Response(
            {
                "user": {
                    "id": user.id,
                    "phone": user.phone,
                    "full_name": user.full_name,
                    "email": user.email or "",
                },
                "organization": {
                    "id": organization.id,
                    "name": organization.name,
                    "slug": organization.slug,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class ProviderSettingsView(APIView):
    """Platforma haqida umumiy ma'lumot (sozlamalar sahifasi)."""

    permission_classes = [IsProviderAdmin]

    def get(self, request):
        return Response(
            {
                "platform_name": getattr(
                    settings, "PROVIDER_PLATFORM_NAME", os.getenv("PROVIDER_PLATFORM_NAME", "SavdoPro")
                ),
                "timezone": settings.TIME_ZONE,
                "language_code": settings.LANGUAGE_CODE,
                "debug": settings.DEBUG,
                "support_email": os.getenv("PROVIDER_SUPPORT_EMAIL", ""),
                "support_phone": os.getenv("PROVIDER_SUPPORT_PHONE", ""),
                "sms_backend": getattr(settings, "SMS_BACKEND", ""),
            }
        )


class ProviderChangePasswordView(APIView):
    """Super admin joriy akkaunt parolini almashtiradi."""

    permission_classes = [IsProviderAdmin]

    def post(self, request):
        serializer = ProviderChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.last_password_changed_at = timezone.now()
        user.save(update_fields=["password", "last_password_changed_at"])
        log_event(
            request,
            AuthAuditLog.Event.PASSWORD_CHANGED,
            user=user,
            destination=user.phone or "",
            metadata={"source": "provider_change_password"},
        )
        return Response({"detail": "Parol muvaffaqiyatli yangilandi."})


class ProviderOrganizationViewSet(viewsets.ModelViewSet):
    """Platforma egasi uchun tashkilotlar boshqaruvi."""

    permission_classes = [IsProviderAdmin]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return OrganizationDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return ProviderOrganizationWriteSerializer
        return OrganizationListSerializer

    def get_queryset(self):
        qs = (
            Organization.objects.filter(deleted_at__isnull=True)
            .prefetch_related(
                "subscriptions", "subscriptions__plan", "branches", "members"
            )
            .annotate(
                users_count=Count(
                    "members",
                    distinct=True,
                    filter=Q(members__is_active=True),
                ),
                staff_count=Count(
                    "members",
                    distinct=True,
                    filter=Q(
                        members__is_active=True,
                        members__deleted_at__isnull=True,
                    )
                    & ~Q(members__role__code="owner"),
                ),
                owner_full_name=Subquery(
                    OrganizationUser.objects.filter(
                        organization_id=OuterRef("pk"),
                        role__code="owner",
                        is_active=True,
                        deleted_at__isnull=True,
                    ).values("user__full_name")[:1]
                ),
                owner_phone=Subquery(
                    OrganizationUser.objects.filter(
                        organization_id=OuterRef("pk"),
                        role__code="owner",
                        is_active=True,
                        deleted_at__isnull=True,
                    ).values("user__phone")[:1]
                ),
                owner_last_login=Subquery(
                    OrganizationUser.objects.filter(
                        organization_id=OuterRef("pk"),
                        role__code="owner",
                        is_active=True,
                        deleted_at__isnull=True,
                    ).values("user__last_login")[:1]
                ),
                branches_count=Count("branches", distinct=True, filter=Q(branches__is_active=True)),
                products_count=Count("products", distinct=True, filter=Q(products__is_active=True)),
            )
            .order_by("-created_at")
        )

        params = self.request.query_params
        search = (params.get("search") or "").strip()
        plan_code = params.get("plan")
        active = params.get("active")
        sub_status = params.get("sub_status")

        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(phone__icontains=search)
                | Q(slug__icontains=search)
                | Q(members__user__phone__icontains=search)
                | Q(members__user__full_name__icontains=search)
            ).distinct()
        if plan_code:
            qs = qs.filter(subscriptions__plan__code=plan_code).distinct()
        if active == "1":
            qs = qs.filter(is_active=True)
        elif active == "0":
            qs = qs.filter(is_active=False)
        if sub_status:
            qs = qs.filter(subscriptions__status=sub_status).distinct()

        return qs

    def perform_create(self, serializer):
        from accounts.services.registration import _ensure_trial_subscription

        org = serializer.save()
        if not Branch.objects.filter(organization=org, deleted_at__isnull=True).exists():
            Branch.objects.create(
                organization=org,
                name="Asosiy filial",
                address="",
                is_main=True,
                is_active=True,
            )
        _ensure_trial_subscription(org)

    def perform_destroy(self, instance):
        from shops.services.organization_purge import purge_organization

        purge_organization(instance)

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, pk=None):
        org = self.get_object()
        org.is_active = False
        org.save(update_fields=["is_active"])
        return Response({"id": org.id, "is_active": org.is_active})

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        org = self.get_object()
        org.is_active = True
        org.save(update_fields=["is_active"])
        return Response({"id": org.id, "is_active": org.is_active})

    @action(detail=True, methods=["post"], url_path="extend-trial")
    def extend_trial(self, request, pk=None):
        org = self.get_object()
        serializer = ExtendTrialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data["days"]
        now = timezone.now()
        sub = (
            Subscription.objects.filter(
                organization=org,
                status__in=[Subscription.Status.ACTIVE, Subscription.Status.GRACE],
            )
            .order_by("-ends_at")
            .first()
        )
        if not sub:
            plan = Plan.objects.filter(code=Plan.PlanCode.LITE, is_active=True).first()
            if not plan:
                return Response(
                    {"detail": "Lite tarif topilmadi."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sub = Subscription.objects.create(
                organization=org,
                plan=plan,
                starts_at=now,
                ends_at=now + timedelta(days=days),
                status=Subscription.Status.ACTIVE,
                auto_renew=False,
            )
        else:
            base = sub.ends_at if sub.ends_at and sub.ends_at > now else now
            sub.ends_at = base + timedelta(days=days)
            sub.status = Subscription.Status.ACTIVE
            sub.save(update_fields=["ends_at", "status"])
        return Response({"id": sub.id, "ends_at": sub.ends_at, "status": sub.status})

    @action(detail=True, methods=["post"], url_path="change-plan")
    def change_plan(self, request, pk=None):
        org = self.get_object()
        serializer = ChangePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan_code = serializer.validated_data["plan_code"]
        days = serializer.validated_data["days"]
        plan = Plan.objects.filter(code=plan_code, is_active=True).first()
        if not plan:
            return Response(
                {"detail": f"Plan '{plan_code}' topilmadi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        now = timezone.now()
        # Eski faol subscription'ni bekor qilamiz, yangisini yaratamiz.
        Subscription.objects.filter(
            organization=org,
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.GRACE],
        ).update(status=Subscription.Status.CANCELED)
        sub = Subscription.objects.create(
            organization=org,
            plan=plan,
            starts_at=now,
            ends_at=now + timedelta(days=days),
            status=Subscription.Status.ACTIVE,
            auto_renew=True,
        )
        return Response(
            {
                "id": sub.id,
                "plan_code": plan.code,
                "plan_name": plan.name,
                "ends_at": sub.ends_at,
                "status": sub.status,
            }
        )

    @action(detail=True, methods=["post"], url_path="set-remaining-days")
    def set_remaining_days(self, request, pk=None):
        """Faol obuna uchun qolgan kunni to'g'ridan-to'g'ri o'rnatish."""
        org = self.get_object()
        serializer = SetRemainingDaysSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        days = serializer.validated_data["days"]
        now = timezone.now()
        sub = (
            Subscription.objects.filter(
                organization=org,
                status__in=[Subscription.Status.ACTIVE, Subscription.Status.GRACE],
            )
            .order_by("-ends_at")
            .first()
        )
        if not sub:
            plan = Plan.objects.filter(code=Plan.PlanCode.LITE, is_active=True).first()
            if not plan:
                return Response(
                    {"detail": "Lite tarif topilmadi."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sub = Subscription.objects.create(
                organization=org,
                plan=plan,
                starts_at=now,
                ends_at=now + timedelta(days=days),
                status=Subscription.Status.ACTIVE,
                auto_renew=False,
            )
        else:
            sub.ends_at = now + timedelta(days=days)
            sub.status = Subscription.Status.ACTIVE
            sub.save(update_fields=["ends_at", "status"])
        return Response(
            {
                "id": sub.id,
                "ends_at": sub.ends_at,
                "status": sub.status,
                "remaining_days": days,
            }
        )

    @action(detail=True, methods=["post"], url_path="impersonate")
    def impersonate(self, request, pk=None):
        """Tashkilot owner'i nomidan JWT olish (qo‘llab-quvvatlash uchun).

        Bu xavfli operatsiya — faqat Provider Admin qila oladi.
        """
        org = self.get_object()
        owner_mu = (
            org.members.filter(role__code="owner", is_active=True)
            .select_related("user")
            .first()
        )
        if not owner_mu or not owner_mu.user:
            return Response(
                {"detail": "Owner topilmadi."}, status=status.HTTP_404_NOT_FOUND
            )
        target = owner_mu.user
        refresh = RefreshToken.for_user(target)
        return Response(
            {
                "user_id": target.id,
                "user_phone": target.phone,
                "user_full_name": target.full_name,
                "organization_id": org.id,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
        )

    @action(detail=True, methods=["get"], url_path="staff-roles")
    def staff_roles(self, request, pk=None):
        """Tashkilot uchun tanlash mumkin bo'lgan rollar (owner chiqarilgan)."""
        org = self.get_object()
        from accounts.role_policy import STAFF_ROLE_CODE

        qs = (
            Role.objects.filter(
                Q(organization=org) | Q(organization__isnull=True, is_system=True),
                is_active=True,
                code=STAFF_ROLE_CODE,
            )
            .order_by("id")
        )
        data = [{"id": r.id, "code": r.code, "name": r.name} for r in qs]
        return Response(data)

    @action(detail=True, methods=["post"], url_path="invite-staff")
    def invite_staff(self, request, pk=None):
        """Do'konga xodim (kassir, sotuvchi va h.k.) — mavjud invite mantiq."""
        org = self.get_object()
        serializer = InviteUserSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save(organization=org)
        return Response(result, status=status.HTTP_201_CREATED)

    def _resolve_org_role(self, organization, role_id):
        role = (
            Role.objects.filter(id=role_id)
            .filter(Q(organization=organization) | Q(organization__isnull=True, is_system=True))
            .first()
        )
        if not role:
            return None
        return role

    @action(detail=True, methods=["post"], url_path="members/set-role")
    def set_member_role(self, request, pk=None):
        org = self.get_object()
        serializer = ProviderMemberRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership_id = serializer.validated_data["membership_id"]
        role_id = serializer.validated_data["role_id"]
        branch_id = serializer.validated_data.get("branch_id")

        membership = (
            OrganizationUser.objects.filter(
                organization=org, id=membership_id, deleted_at__isnull=True
            )
            .select_related("role", "user")
            .first()
        )
        if not membership:
            return Response({"detail": "A'zolik topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        role = self._resolve_org_role(org, role_id)
        if not role:
            return Response({"detail": "Rol topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        from accounts.role_policy import is_valid_member_role_code

        if not is_valid_member_role_code(role.code):
            return Response(
                {"detail": "Faqat egasi (owner) yoki sotuvchi (seller) rolini tayinlash mumkin."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if role.code == Role.RoleCode.OWNER:
            if (
                OrganizationUser.objects.filter(
                    organization=org,
                    role__code=Role.RoleCode.OWNER,
                    is_active=True,
                    deleted_at__isnull=True,
                )
                .exclude(pk=membership.pk)
                .exists()
            ):
                return Response(
                    {"detail": "Tashkilotda allaqachon boshqa egasi (owner) bor."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if membership.role.code == Role.RoleCode.OWNER and role.code != Role.RoleCode.OWNER:
            owners_left = (
                OrganizationUser.objects.filter(
                    organization=org,
                    role__code=Role.RoleCode.OWNER,
                    is_active=True,
                    deleted_at__isnull=True,
                )
                .exclude(pk=membership.pk)
                .count()
            )
            if owners_left < 1:
                return Response(
                    {"detail": "Yagona egasini boshqa rolga o'tkazib bo'lmaydi."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        branch = None
        if branch_id is not None:
            branch = Branch.objects.filter(id=branch_id, organization=org, deleted_at__isnull=True).first()
            if not branch:
                return Response({"detail": "Filial topilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        membership.role = role
        membership.branch = branch
        membership.is_active = True
        membership.status = OrganizationUser.MembershipStatus.ACTIVE
        membership.save(update_fields=["role", "branch", "is_active", "status", "updated_at"])
        return Response(MembershipLiteSerializer(membership).data)

    @action(detail=True, methods=["post"], url_path="members/remove")
    def remove_member(self, request, pk=None):
        from uuid import uuid4

        org = self.get_object()
        serializer = ProviderMemberRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership_id = serializer.validated_data["membership_id"]

        membership = OrganizationUser.objects.filter(
            organization=org, id=membership_id, deleted_at__isnull=True
        ).first()
        if not membership:
            return Response({"detail": "A'zolik topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        if membership.role.code == Role.RoleCode.OWNER:
            owners_count = OrganizationUser.objects.filter(
                organization=org,
                role__code=Role.RoleCode.OWNER,
                is_active=True,
                deleted_at__isnull=True,
            ).count()
            if owners_count <= 1:
                return Response(
                    {"detail": "Yagona egasini o'chirib bo'lmaydi. Avval boshqa egasi qo'sing yoki tashkilotni o'chiring."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        membership.is_active = False
        membership.status = OrganizationUser.MembershipStatus.SUSPENDED
        membership.deleted_at = timezone.now()
        membership.save(update_fields=["is_active", "status", "deleted_at", "updated_at"])
        return Response({"ok": True, "membership_id": membership.id})


class ProviderStatsView(APIView):
    """Provider asosiy dashboard uchun statistika."""

    permission_classes = [IsProviderAdmin]

    def get(self, request):
        now = timezone.now()
        today = now.date()
        last_30 = today - timedelta(days=30)

        # Ro'yxat bilan bir xil: soft-delete qilingan tashkilotlar sanalmasin
        org_qs = Organization.objects.filter(deleted_at__isnull=True)
        # Platforma superadminlari mijozlar statistikaga kirmaydi
        users_qs = User.objects.filter(is_superuser=False)

        total_orgs = org_qs.count()
        active_orgs = org_qs.filter(is_active=True).count()
        suspended_orgs = total_orgs - active_orgs
        new_orgs_30d = org_qs.filter(created_at__gte=last_30).count()

        active_subs = Subscription.objects.filter(
            organization__deleted_at__isnull=True,
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.GRACE],
            ends_at__gte=now,
        )
        plan_breakdown = (
            active_subs.values("plan__code", "plan__name")
            .annotate(count=Count("id"))
            .order_by("plan__code")
        )

        expiring_soon = active_subs.filter(ends_at__lte=now + timedelta(days=7)).count()
        expired = Subscription.objects.filter(
            organization__deleted_at__isnull=True,
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.GRACE],
            ends_at__lt=now,
        ).count()

        total_users = users_qs.count()
        active_users_30d = users_qs.filter(last_login__gte=last_30).count()

        return Response(
            {
                "organizations": {
                    "total": total_orgs,
                    "active": active_orgs,
                    "suspended": suspended_orgs,
                    "new_30d": new_orgs_30d,
                },
                "subscriptions": {
                    "active_total": active_subs.count(),
                    "expiring_soon": expiring_soon,
                    "expired": expired,
                    "by_plan": list(plan_breakdown),
                },
                "users": {
                    "total": total_users,
                    "active_30d": active_users_30d,
                },
            }
        )

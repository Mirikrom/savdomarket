"""Serializers for the auth module.

Flow overview:
- Registration is 3-step:
    1) ``RegisterRequestOtpSerializer``  — phone in, SMS out.
    2) ``RegisterVerifyOtpSerializer``   — phone+code in, signed
       ``registration_token`` out.
    3) ``RegisterCompleteSerializer``    — token + profile fields in;
       atomically creates User + Organization + OrganizationUser(owner)
       and returns JWT tokens.

- Password reset is 3-step (symmetric):
    1) ``ForgotPasswordRequestSerializer`` — phone in (always answers "sent",
       even if the user doesn't exist, to prevent user enumeration).
    2) ``ForgotPasswordVerifySerializer``  — phone+code in, ``reset_token`` out.
    3) ``ResetPasswordSerializer``         — token + new_password in; updates
       the user and revokes **all** existing refresh tokens.

- Login is single-step with:
    * brute-force lockout after 5 failed attempts (15 minute window).
    * device/session tracking (``UserSession`` row created per token pair).
"""

from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.utils import timezone
from rest_framework import serializers


def _run_password_validators(password, user=None):
    """Run Django's password validators and re-raise as a DRF ValidationError."""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)})

from accounts.models import (
    AuthAuditLog,
    OrganizationUser,
    OtpCode,
    Role,
    RolePermission,
    User,
    UserSession,
)
from accounts.services import tokens as token_service
from accounts.services.otp import issue_otp, verify_otp
from accounts.services.phone import mask_phone, normalize_phone
from accounts.services.registration import bootstrap_owner
from accounts.services.sessions import issue_tokens_for_user


class UserSerializer(serializers.ModelSerializer):
    is_phone_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "phone",
            "full_name",
            "email",
            "preferred_language",
            "is_phone_verified",
            "is_active",
            "is_superuser",
            "is_staff",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "is_active",
            "is_phone_verified",
            "is_superuser",
            "is_staff",
        ]


class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        fields = ["id", "permission_code"]


class RoleSerializer(serializers.ModelSerializer):
    permissions = RolePermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "organization",
            "code",
            "name",
            "description",
            "is_system",
            "permissions",
        ]


class OrganizationUserSerializer(serializers.ModelSerializer):
    user_detail = UserSerializer(source="user", read_only=True)

    class Meta:
        model = OrganizationUser
        fields = [
            "id",
            "organization",
            "user",
            "user_detail",
            "role",
            "branch",
            "status",
            "is_active",
            "created_at",
        ]


class RegisterRequestOtpSerializer(serializers.Serializer):
    """Step 1: user submits a phone, we send an SMS code."""

    phone = serializers.CharField()

    def validate_phone(self, value):
        normalized = normalize_phone(value)
        if User.objects.filter(phone=normalized).exists():
            raise serializers.ValidationError(
                "Bu telefon raqami bilan akkaunt allaqachon mavjud."
            )
        return normalized

    def save(self, **kwargs):
        from accounts.services.sms import send_sms

        request = self.context.get("request")
        phone = self.validated_data["phone"]
        ip = request.META.get("REMOTE_ADDR") if request else None
        ua = (request.META.get("HTTP_USER_AGENT", "") if request else "")[:1000]
        result = issue_otp(
            destination=phone,
            purpose=OtpCode.Purpose.REGISTRATION,
            ip_address=ip,
            user_agent=ua,
        )
        send_sms(
            phone,
            f"SavdoPro: ro'yxatdan o'tish kodingiz {result.raw_code}. "
            f"Kod {result.expires_in // 60} daqiqa ichida amal qiladi.",
        )
        AuthAuditLog.objects.create(
            event=AuthAuditLog.Event.OTP_REQUESTED,
            destination=phone,
            ip_address=ip,
            user_agent=ua,
            metadata={"purpose": "registration"},
        )
        return {
            "sent": True,
            "phone": mask_phone(phone),
            "expires_in": result.expires_in,
        }


class RegisterVerifyOtpSerializer(serializers.Serializer):
    """Step 2: confirm the code, get a short-lived ``registration_token``."""

    phone = serializers.CharField()
    code = serializers.CharField(min_length=4, max_length=8)

    def validate_phone(self, value):
        return normalize_phone(value)

    def save(self, **kwargs):
        phone = self.validated_data["phone"]
        verify_otp(
            destination=phone,
            purpose=OtpCode.Purpose.REGISTRATION,
            code=self.validated_data["code"],
        )
        request = self.context.get("request")
        AuthAuditLog.objects.create(
            event=AuthAuditLog.Event.OTP_VERIFIED,
            destination=phone,
            ip_address=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:1000],
            metadata={"purpose": "registration"},
        )
        return {
            "registration_token": token_service.issue_registration_token(phone),
            "expires_in": token_service.REGISTRATION_TOKEN_TTL,
        }


class RegisterCompleteSerializer(serializers.Serializer):
    """Step 3: trade the verified token for a real account + JWT pair."""

    registration_token = serializers.CharField()
    full_name = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True)
    preferred_language = serializers.ChoiceField(
        choices=[c.value for c in User.LanguageChoices],
        required=False,
        default=User.LanguageChoices.UZ,
    )
    organization_name = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Parollar mos kelmadi."})
        attrs["phone"] = token_service.read_registration_token(attrs["registration_token"])
        if User.objects.filter(phone=attrs["phone"]).exists():
            raise serializers.ValidationError(
                {"phone": "Bu telefon raqami bilan akkaunt allaqachon mavjud."}
            )
        _run_password_validators(attrs["password"])
        return attrs

    def save(self, **kwargs):
        request = self.context.get("request")
        try:
            user, organization, membership = bootstrap_owner(
                phone=self.validated_data["phone"],
                password=self.validated_data["password"],
                full_name=self.validated_data["full_name"],
                email=self.validated_data.get("email", ""),
                preferred_language=self.validated_data.get(
                    "preferred_language", User.LanguageChoices.UZ
                ),
                organization_name=self.validated_data.get("organization_name", "") or None,
            )
        except IntegrityError:
            raise serializers.ValidationError(
                {"phone": "Bu telefon raqami bilan akkaunt allaqachon mavjud."}
            )

        tokens = issue_tokens_for_user(user, request=request)

        AuthAuditLog.objects.create(
            user=user,
            event=AuthAuditLog.Event.REGISTER_COMPLETED,
            destination=user.phone,
            ip_address=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:1000],
            metadata={"organization_id": organization.id},
        )

        return {
            "access": tokens["access"],
            "refresh": tokens["refresh"],
            "user": UserSerializer(user).data,
            "organization": {
                "id": organization.id,
                "name": organization.name,
                "slug": organization.slug,
            },
            "role": membership.role.code,
        }


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate_phone(self, value):
        return normalize_phone(value)

    def validate(self, attrs):
        request = self.context.get("request")
        phone = attrs["phone"]
        ip = request.META.get("REMOTE_ADDR") if request else None
        ua = (request.META.get("HTTP_USER_AGENT", "") if request else "")[:1000]

        user_obj = User.objects.filter(phone=phone).first()
        if user_obj and user_obj.is_locked:
            raise serializers.ValidationError(
                {"detail": "Hisob vaqtincha bloklangan. 15 daqiqadan keyin urinib ko'ring."}
            )

        user = authenticate(request=request, username=phone, password=attrs["password"])
        if not user:
            if user_obj:
                user_obj.register_failed_login()
                if user_obj.is_locked:
                    AuthAuditLog.objects.create(
                        user=user_obj,
                        event=AuthAuditLog.Event.ACCOUNT_LOCKED,
                        destination=phone,
                        ip_address=ip,
                        user_agent=ua,
                    )
            AuthAuditLog.objects.create(
                user=user_obj,
                event=AuthAuditLog.Event.LOGIN_FAILED,
                destination=phone,
                ip_address=ip,
                user_agent=ua,
            )
            raise serializers.ValidationError(
                {"detail": "Telefon yoki parol noto'g'ri."}
            )

        if not user.is_active:
            raise serializers.ValidationError({"detail": "Hisob faolsizlantirilgan."})

        user.reset_login_attempts()
        attrs["user"] = user
        return attrs

    def to_representation(self, instance):
        request = self.context.get("request")
        user = instance["user"]
        tokens = issue_tokens_for_user(user, request=request)
        AuthAuditLog.objects.create(
            user=user,
            event=AuthAuditLog.Event.LOGIN_SUCCESS,
            destination=user.phone,
            ip_address=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:1000],
        )
        return {
            "access": tokens["access"],
            "refresh": tokens["refresh"],
            "user": UserSerializer(user).data,
        }


class ForgotPasswordRequestSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, value):
        return normalize_phone(value)

    def save(self, **kwargs):
        from accounts.services.sms import send_sms

        request = self.context.get("request")
        phone = self.validated_data["phone"]
        ip = request.META.get("REMOTE_ADDR") if request else None
        ua = (request.META.get("HTTP_USER_AGENT", "") if request else "")[:1000]

        user = User.objects.filter(phone=phone, is_active=True).first()
        if user:
            try:
                result = issue_otp(
                    destination=phone,
                    purpose=OtpCode.Purpose.PASSWORD_RESET,
                    ip_address=ip,
                    user_agent=ua,
                )
                send_sms(
                    phone,
                    f"SavdoPro: parolni tiklash kodingiz {result.raw_code}. "
                    f"Kod {result.expires_in // 60} daqiqa ichida amal qiladi.",
                )
                AuthAuditLog.objects.create(
                    user=user,
                    event=AuthAuditLog.Event.PASSWORD_RESET_REQUESTED,
                    destination=phone,
                    ip_address=ip,
                    user_agent=ua,
                )
            except serializers.ValidationError:
                pass

        return {"sent": True, "phone": mask_phone(phone)}


class ForgotPasswordVerifySerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField(min_length=4, max_length=8)

    def validate_phone(self, value):
        return normalize_phone(value)

    def save(self, **kwargs):
        phone = self.validated_data["phone"]
        user = User.objects.filter(phone=phone, is_active=True).first()
        if not user:
            raise serializers.ValidationError(
                {"code": "Kod noto'g'ri yoki muddati tugagan."}
            )
        verify_otp(
            destination=phone,
            purpose=OtpCode.Purpose.PASSWORD_RESET,
            code=self.validated_data["code"],
        )
        request = self.context.get("request")
        AuthAuditLog.objects.create(
            user=user,
            event=AuthAuditLog.Event.OTP_VERIFIED,
            destination=phone,
            ip_address=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:1000],
            metadata={"purpose": "password_reset"},
        )
        return {
            "reset_token": token_service.issue_reset_token(user.id),
            "expires_in": token_service.RESET_TOKEN_TTL,
        }


class ResetPasswordSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        user_id = token_service.read_reset_token(attrs["reset_token"])
        user = User.objects.filter(id=user_id, is_active=True).first()
        if not user:
            raise serializers.ValidationError({"detail": "Foydalanuvchi topilmadi."})
        _run_password_validators(attrs["new_password"], user=user)
        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        from accounts.services.sessions import revoke_all_sessions

        user: User = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.last_password_changed_at = timezone.now()
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(
            update_fields=[
                "password",
                "last_password_changed_at",
                "failed_login_attempts",
                "locked_until",
            ]
        )

        revoked = revoke_all_sessions(user)

        request = self.context.get("request")
        AuthAuditLog.objects.create(
            user=user,
            event=AuthAuditLog.Event.PASSWORD_CHANGED,
            destination=user.phone,
            ip_address=request.META.get("REMOTE_ADDR") if request else None,
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:1000],
            metadata={"revoked_sessions": revoked},
        )
        return {"changed": True}


class LanguageSerializer(serializers.Serializer):
    preferred_language = serializers.ChoiceField(
        choices=[User.LanguageChoices.UZ, User.LanguageChoices.RU, User.LanguageChoices.EN]
    )


class UserSessionSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserSession
        fields = [
            "id",
            "device_name",
            "ip_address",
            "user_agent",
            "last_used_at",
            "expires_at",
            "revoked_at",
            "created_at",
            "is_active",
        ]
        read_only_fields = fields


class InviteUserSerializer(serializers.Serializer):
    """Owner/Admin invites a new employee to join the organization.

    Yangi telefon uchun: ``password`` berilsa shu parol ishlatiladi; aks holda
    tasodifiy vaqtinchalik parol yaratiladi va javobda qaytariladi.
    """

    phone = serializers.CharField()
    full_name = serializers.CharField(max_length=255)
    role_id = serializers.IntegerField()
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password_confirm = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate_phone(self, value):
        return normalize_phone(value)

    def validate(self, attrs):
        pwd = (attrs.get("password") or "").strip()
        pwd_c = (attrs.get("password_confirm") or "").strip()
        if pwd or pwd_c:
            if pwd != pwd_c:
                raise serializers.ValidationError(
                    {"password_confirm": "Parollar mos emas."}
                )
            if not pwd:
                raise serializers.ValidationError(
                    {"password": "Parolni kiriting."}
                )
            provisional = User(
                phone=attrs.get("phone") or "",
                full_name=attrs.get("full_name") or "",
                email="",
            )
            _run_password_validators(pwd, user=provisional)
            attrs["password"] = pwd
        else:
            attrs["password"] = None
        attrs.pop("password_confirm", None)
        return attrs

    def save(self, organization, **kwargs):
        import secrets

        from django.db import transaction
        from django.db.models import Q

        from accounts.models import OrganizationUser, Role
        from shops.models import Branch

        phone = self.validated_data["phone"]
        full_name = self.validated_data["full_name"]
        role_id = self.validated_data["role_id"]
        branch_id = self.validated_data.get("branch_id")
        explicit_password = self.validated_data.get("password")

        role = (
            Role.objects.filter(id=role_id)
            .filter(Q(organization=organization) | Q(organization__isnull=True, is_system=True))
            .first()
        )
        if not role:
            raise serializers.ValidationError({"role_id": "Rol topilmadi."})

        branch = None
        if branch_id:
            branch = Branch.objects.filter(id=branch_id, organization=organization).first()
            if not branch:
                raise serializers.ValidationError({"branch_id": "Filial topilmadi."})

        temporary_password = None
        used_manual_password = False
        is_new_user = False

        with transaction.atomic():
            user = User.objects.filter(phone=phone).first()
            if user is None:
                is_new_user = True
                user = User(
                    phone=phone,
                    full_name=full_name,
                    is_active=True,
                    last_password_changed_at=timezone.now(),
                )
                if explicit_password:
                    user.set_password(explicit_password)
                    used_manual_password = True
                else:
                    temporary_password = secrets.token_urlsafe(6)
                    user.set_password(temporary_password)
                user.save()
            else:
                if explicit_password:
                    raise serializers.ValidationError(
                        {
                            "password": "Bu telefon allaqachon ro'yxatdan o'tgan. Parolni bu yerda o'zgartirib bo'lmaydi."
                        }
                    )
                if not user.full_name:
                    user.full_name = full_name
                    user.save(update_fields=["full_name"])

            existing = OrganizationUser.objects.filter(
                organization=organization, user=user
            ).first()
            if existing and existing.is_active:
                raise serializers.ValidationError(
                    {"detail": "Bu foydalanuvchi tashkilotda allaqachon bor."}
                )
            if existing:
                existing.role = role
                existing.branch = branch
                existing.status = OrganizationUser.MembershipStatus.ACTIVE
                existing.is_active = True
                existing.save()
                membership = existing
            else:
                membership = OrganizationUser.objects.create(
                    organization=organization,
                    user=user,
                    role=role,
                    branch=branch,
                    status=OrganizationUser.MembershipStatus.ACTIVE,
                )

        return {
            "membership": OrganizationUserSerializer(membership).data,
            "user_created": is_new_user,
            "temporary_password": temporary_password,
            "used_manual_password": used_manual_password,
        }

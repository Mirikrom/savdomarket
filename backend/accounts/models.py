from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.models import SoftDeleteModel, TimeStampedModel


class User(AbstractUser, TimeStampedModel):
    class LanguageChoices(models.TextChoices):
        UZ = "uz", "Uzbek"
        RU = "ru", "Russian"

    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    email = models.EmailField(blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    full_name = models.CharField(max_length=255)
    preferred_language = models.CharField(
        max_length=5, choices=LanguageChoices.choices, default=LanguageChoices.UZ
    )
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_password_changed_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        indexes = [
            models.Index(fields=["phone"], name="accounts_us_phone_idx"),
        ]

    def __str__(self):
        return self.full_name or self.phone or self.username or str(self.pk)

    @property
    def is_phone_verified(self):
        return self.phone_verified_at is not None

    @property
    def is_locked(self):
        return self.locked_until is not None and self.locked_until > timezone.now()

    def register_failed_login(self, max_attempts=5, lock_minutes=15):
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        update_fields = ["failed_login_attempts"]
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=lock_minutes)
            update_fields.append("locked_until")
        self.save(update_fields=update_fields)

    def reset_login_attempts(self):
        if self.failed_login_attempts or self.locked_until:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.save(update_fields=["failed_login_attempts", "locked_until"])


class Role(TimeStampedModel, SoftDeleteModel):
    class RoleCode(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MODERATOR = "moderator", "Moderator"
        CASHIER = "cashier", "Cashier"
        SELLER = "seller", "Seller"

    organization = models.ForeignKey(
        "shops.Organization",
        on_delete=models.CASCADE,
        related_name="roles",
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=32, choices=RoleCode.choices)
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=255, blank=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="uniq_role_per_organization"
            )
        ]

    def __str__(self):
        return self.name


class RolePermission(TimeStampedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    permission_code = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission_code"], name="uniq_permission_per_role"
            )
        ]

    def __str__(self):
        return f"{self.role.code}:{self.permission_code}"


class OrganizationUser(TimeStampedModel, SoftDeleteModel):
    class MembershipStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        INVITED = "invited", "Invited"
        SUSPENDED = "suspended", "Suspended"

    organization = models.ForeignKey(
        "shops.Organization", on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="organizations")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="members")
    branch = models.ForeignKey(
        "shops.Branch",
        on_delete=models.SET_NULL,
        related_name="members",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16, choices=MembershipStatus.choices, default=MembershipStatus.ACTIVE
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="uniq_user_per_organization"
            )
        ]

    def __str__(self):
        return f"{self.user} @ {self.organization}"


class OtpCode(TimeStampedModel):
    """Universal one-time code for SMS/email verification.

    The actual code value is never stored in plaintext — only its hash.
    """

    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Registration"
        LOGIN = "login", "Login"
        PASSWORD_RESET = "password_reset", "Password reset"
        PHONE_CHANGE = "phone_change", "Phone change"

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        TELEGRAM = "telegram", "Telegram"

    destination = models.CharField(max_length=255, db_index=True)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.SMS)
    code_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["destination", "purpose", "expires_at"],
                name="accounts_ot_dest_pp_idx",
            ),
        ]

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_blocked(self):
        return self.attempts >= self.max_attempts

    def set_code(self, raw_code: str) -> None:
        self.code_hash = make_password(raw_code)

    def check_code(self, raw_code: str) -> bool:
        return check_password(raw_code, self.code_hash)

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def register_attempt(self):
        self.attempts = (self.attempts or 0) + 1
        self.save(update_fields=["attempts"])


class UserSession(TimeStampedModel):
    """Tracks every active refresh-token / device. Used for session control."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    refresh_jti = models.CharField(max_length=64, unique=True)
    device_name = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    last_used_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "revoked_at"], name="accounts_us_user_rv_idx"),
            models.Index(fields=["refresh_jti"], name="accounts_us_jti_idx"),
        ]
        ordering = ["-last_used_at"]

    @property
    def is_active(self):
        return self.revoked_at is None and self.expires_at > timezone.now()

    def revoke(self):
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])


class AuthAuditLog(TimeStampedModel):
    class Event(models.TextChoices):
        OTP_REQUESTED = "otp_requested", "OTP requested"
        OTP_VERIFIED = "otp_verified", "OTP verified"
        OTP_FAILED = "otp_failed", "OTP failed"
        REGISTER_COMPLETED = "register_completed", "Registration completed"
        LOGIN_SUCCESS = "login_success", "Login success"
        LOGIN_FAILED = "login_failed", "Login failed"
        ACCOUNT_LOCKED = "account_locked", "Account locked"
        PASSWORD_RESET_REQUESTED = "password_reset_requested", "Password reset requested"
        PASSWORD_CHANGED = "password_changed", "Password changed"
        LOGOUT = "logout", "Logout"
        SESSION_REVOKED = "session_revoked", "Session revoked"

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="auth_audit_logs", null=True, blank=True
    )
    event = models.CharField(max_length=48, choices=Event.choices)
    destination = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "event"], name="accounts_aa_user_ev_idx"),
            models.Index(fields=["event", "created_at"], name="accounts_aa_ev_ct_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        who = self.user_id or self.destination or "anon"
        return f"{self.event} ({who})"

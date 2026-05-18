from django.contrib import admin

from accounts.models import (
    AuthAuditLog,
    OrganizationUser,
    OtpCode,
    Role,
    RolePermission,
    User,
    UserSession,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "phone",
        "full_name",
        "username",
        "is_active",
        "phone_verified_at",
        "is_staff",
        "created_at",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", "preferred_language")
    search_fields = ("phone", "username", "full_name", "email")
    ordering = ("-id",)
    readonly_fields = ("last_login", "created_at", "updated_at")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "organization", "is_system", "is_active")
    list_filter = ("code", "is_system", "is_active")
    search_fields = ("name", "code")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("id", "role", "permission_code")
    list_filter = ("permission_code",)
    search_fields = ("permission_code",)


@admin.register(OrganizationUser)
class OrganizationUserAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "organization", "role", "branch", "status", "is_active")
    list_filter = ("status", "is_active")
    search_fields = ("user__phone", "user__full_name", "organization__name")


@admin.register(OtpCode)
class OtpCodeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "destination",
        "purpose",
        "channel",
        "attempts",
        "max_attempts",
        "used_at",
        "expires_at",
        "created_at",
    )
    list_filter = ("purpose", "channel", "used_at")
    search_fields = ("destination",)
    readonly_fields = ("code_hash",)


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "device_name",
        "ip_address",
        "last_used_at",
        "expires_at",
        "revoked_at",
    )
    list_filter = ("revoked_at",)
    search_fields = ("user__phone", "ip_address", "refresh_jti")


@admin.register(AuthAuditLog)
class AuthAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "user", "destination", "ip_address", "created_at")
    list_filter = ("event",)
    search_fields = ("destination", "ip_address", "user__phone")
    readonly_fields = ("created_at", "updated_at", "metadata")

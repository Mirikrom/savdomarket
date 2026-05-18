from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import OrganizationUser
from shops.models import Branch, Organization
from subscriptions.models import Plan, Subscription


class PlanLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "code", "name", "price_monthly"]


class SubscriptionLiteSerializer(serializers.ModelSerializer):
    plan = PlanLiteSerializer(read_only=True)
    plan_code = serializers.CharField(source="plan.code", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "plan_code",
            "plan_name",
            "starts_at",
            "ends_at",
            "status",
            "auto_renew",
        ]


class OrganizationListSerializer(serializers.ModelSerializer):
    """Tashkilotlar ro‘yxati uchun yengil ko‘rinish."""

    plan_code = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()
    subscription_ends_at = serializers.SerializerMethodField()
    users_count = serializers.IntegerField(read_only=True)
    staff_count = serializers.IntegerField(read_only=True, allow_null=True)
    owner_full_name = serializers.CharField(read_only=True, allow_null=True, allow_blank=True)
    owner_phone = serializers.CharField(read_only=True, allow_null=True, allow_blank=True)
    owner_last_login = serializers.DateTimeField(read_only=True, allow_null=True)
    branches_count = serializers.IntegerField(read_only=True)
    products_count = serializers.IntegerField(read_only=True)
    last_sale_at = serializers.SerializerMethodField()
    last_activity_at = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "phone",
            "address",
            "is_active",
            "created_at",
            "plan_code",
            "plan_name",
            "subscription_status",
            "subscription_ends_at",
            "users_count",
            "staff_count",
            "owner_full_name",
            "owner_phone",
            "owner_last_login",
            "branches_count",
            "products_count",
            "last_sale_at",
            "last_activity_at",
        ]

    def _active_sub(self, obj):
        return next(
            (
                s
                for s in obj.subscriptions.all()
                if s.status in (Subscription.Status.ACTIVE, Subscription.Status.GRACE)
            ),
            None,
        )

    def get_plan_code(self, obj):
        sub = self._active_sub(obj)
        return sub.plan.code if sub and sub.plan else None

    def get_plan_name(self, obj):
        sub = self._active_sub(obj)
        return sub.plan.name if sub and sub.plan else None

    def get_subscription_status(self, obj):
        sub = self._active_sub(obj)
        return sub.status if sub else "none"

    def get_subscription_ends_at(self, obj):
        sub = self._active_sub(obj)
        return sub.ends_at if sub else None

    def get_last_sale_at(self, obj):
        last = obj.sales.order_by("-sold_at").values_list("sold_at", flat=True).first()
        return last

    def get_last_activity_at(self, obj):
        """Oxirgi aktivlik: oxirgi savdo yoki ownerning oxirgi kirishi."""
        last_sale = self.get_last_sale_at(obj)
        last_login = getattr(obj, "owner_last_login", None)
        if last_sale and last_login:
            return max(last_sale, last_login)
        return last_sale or last_login


class BranchLiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "is_main", "is_active"]


class MembershipLiteSerializer(serializers.ModelSerializer):
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    role_code = serializers.CharField(source="role.code", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = OrganizationUser
        fields = [
            "id",
            "user_phone",
            "user_full_name",
            "role_code",
            "role_name",
            "branch",
            "status",
            "is_active",
            "created_at",
        ]


class OrganizationDetailSerializer(OrganizationListSerializer):
    address = serializers.CharField(read_only=True)
    subscriptions = SubscriptionLiteSerializer(many=True, read_only=True)
    branches = BranchLiteSerializer(many=True, read_only=True)
    members = serializers.SerializerMethodField()
    stats = serializers.SerializerMethodField()

    class Meta(OrganizationListSerializer.Meta):
        fields = OrganizationListSerializer.Meta.fields + [
            "address",
            "subscriptions",
            "branches",
            "members",
            "stats",
        ]

    def get_members(self, obj):
        members = obj.members.select_related("user", "role", "branch").all()
        return MembershipLiteSerializer(members, many=True).data

    def get_stats(self, obj):
        from sales.models import Sale

        sales_qs = obj.sales.filter(status=Sale.Status.COMPLETED)
        total_sales = sales_qs.count()
        from django.db.models import Sum

        total_amount = sales_qs.aggregate(s=Sum("total"))["s"] or Decimal("0")
        return {
            "total_sales": total_sales,
            "total_amount": total_amount,
            "products": obj.products.filter(is_active=True).count(),
            "categories": obj.categories.filter(is_active=True).count(),
        }


class ExtendTrialSerializer(serializers.Serializer):
    days = serializers.IntegerField(min_value=1, max_value=365, default=30)


class SetRemainingDaysSerializer(serializers.Serializer):
    """Obuna uchun qolgan kunni bevosita o'rnatish."""

    days = serializers.IntegerField(min_value=0, max_value=730, default=0)


class ChangePlanSerializer(serializers.Serializer):
    plan_code = serializers.ChoiceField(choices=[c[0] for c in Plan.PlanCode.choices])
    days = serializers.IntegerField(min_value=1, max_value=730, default=30)


class ProviderOrganizationWriteSerializer(serializers.ModelSerializer):
    """Provider: tashkilot yaratish / yangilash."""

    slug = serializers.CharField(required=False, allow_blank=True, max_length=80)

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "phone", "address", "is_active"]
        read_only_fields = ["id"]

    def validate_slug(self, value):
        from accounts.services.registration import _slugify

        raw = (value or "").strip()
        if not raw:
            return ""
        v = _slugify(raw)[:80]
        if not v:
            raise serializers.ValidationError("Slug bo'sh bo'lishi mumkin emas.")
        qs = Organization.objects.filter(slug=v)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Bu slug band.")
        return v

    def validate_phone(self, value):
        if value is None:
            return ""
        return str(value).strip()[:20]

    def create(self, validated_data):
        if not (validated_data.get("slug") or "").strip():
            from accounts.services.registration import _unique_slug

            validated_data["slug"] = _unique_slug(validated_data["name"])
        validated_data.setdefault("is_active", True)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "slug" in validated_data and not (validated_data.get("slug") or "").strip():
            validated_data.pop("slug")
        return super().update(instance, validated_data)


User = get_user_model()


class ProviderPlanSerializer(serializers.ModelSerializer):
    """Tariflar ro'yxati (provider). `code` o'zgartirilmaydi."""

    active_subscriptions = serializers.IntegerField(read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id",
            "code",
            "name",
            "price_monthly",
            "max_users",
            "max_products",
            "max_branches",
            "feature_flags",
            "is_active",
            "created_at",
            "updated_at",
            "active_subscriptions",
        ]
        read_only_fields = ["id", "code", "created_at", "updated_at", "active_subscriptions"]


class ProviderPlanUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "name",
            "price_monthly",
            "max_users",
            "max_products",
            "max_branches",
            "feature_flags",
            "is_active",
        ]


class ProviderUserListSerializer(serializers.ModelSerializer):
    organizations_count = serializers.IntegerField(read_only=True)
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "created_at",
            "organizations_count",
            "is_locked",
        ]

    def get_is_locked(self, obj):
        return obj.is_locked


class SetUserActiveSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class ProviderBootstrapClientSerializer(serializers.Serializer):
    """Provayder: yangi do'kon (tashkilot) + owner foydalanuvchi + parol (mijozga berish)."""

    organization_name = serializers.CharField(max_length=255)
    full_name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_phone(self, value):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("Telefon majburiy.")
        return v

    def validate_organization_name(self, value):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("Do'kon / tashkilot nomi majburiy.")
        return v

    def validate_full_name(self, value):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("Ism-familiya majburiy.")
        return v

    def validate(self, attrs):
        pwd = attrs["password"]
        provisional = User(
            phone=attrs["phone"],
            full_name=attrs["full_name"],
            email=(attrs.get("email") or "").strip(),
        )
        try:
            password_validation.validate_password(pwd, user=provisional)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


class ProviderChangePasswordSerializer(serializers.Serializer):
    """Super admin o‘z parolini almashtiradi (joriy parol bilan tasdiqlanadi)."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Joriy parol noto‘g‘ri.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Yangi parollar mos kelmadi."}
            )
        user = self.context["request"].user
        try:
            password_validation.validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs

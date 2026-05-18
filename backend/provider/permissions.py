from rest_framework.permissions import BasePermission


class IsProviderAdmin(BasePermission):
    """Faqat platforma egasi (Django superuser) kira oladi.

    Bu permission tashkilot mansubligini tekshirmaydi (oddiy SaaS mijozdan
    farqli o'laroq). Provider — barcha tashkilotlar ustidan boshqaruv qila
    oladigan shaxs.
    """

    message = "Provider admin access required."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)

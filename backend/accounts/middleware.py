from django.conf import settings
from django.utils import translation


class UserLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.supported_languages = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        lang = settings.LANGUAGE_CODE
        if request.user.is_authenticated and getattr(request.user, "preferred_language", None):
            candidate = request.user.preferred_language
            if candidate in self.supported_languages:
                lang = candidate
        translation.activate(lang)
        request.LANGUAGE_CODE = lang
        response = self.get_response(request)
        translation.deactivate()
        return response

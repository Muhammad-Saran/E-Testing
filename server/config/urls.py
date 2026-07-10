from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, JsonResponse
from django.urls import include, path, re_path
from django.views.static import serve


def health(request):
    """Simple liveness probe used by the frontend and for quick manual checks."""
    return JsonResponse({'status': 'ok', 'service': 'e-testing-api', 'environment': settings.ENVIRONMENT})


def spa(request, *args, **kwargs):
    """
    Serve the built React app's index.html for any non-API route so that
    `python manage.py runserver` shows the actual project UI (like bwell).
    React Router then handles client-side routing (/login, /instructor, …).
    """
    index_file = settings.FRONTEND_DIST / 'index.html'
    if not index_file.exists():
        return JsonResponse(
            {
                'error': 'Frontend not built yet.',
                'fix': 'Run:  cd client  &&  npm install  &&  npm run build',
                'api': '/api/health/',
            },
            status=501,
        )
    return FileResponse(open(index_file, 'rb'))


urlpatterns = [
    # --- API + admin (must come before the SPA catch-all) ---
    path('admin/', admin.site.urls),
    path('api/health/', health, name='health'),
    path('api/auth/', include('src.services.accounts.urls')),
    path('api/courses/', include('src.services.courses.urls')),
    path('api/questions/', include('src.services.questionbank.urls')),
    path('api/exams/', include('src.services.exams.urls')),
    path('api/dashboard/', include('src.services.dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# --- Built React app: static assets + SPA catch-all (keep last) ---
urlpatterns += [
    re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': settings.FRONTEND_DIST / 'assets'}),
    re_path(r'^(?!api/|admin/|media/|static/).*$', spa),
]

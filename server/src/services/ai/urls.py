from rest_framework.routers import DefaultRouter

from .views import GenerationJobViewSet, PracticeViewSet

app_name = 'ai'

router = DefaultRouter()
router.register('jobs', GenerationJobViewSet, basename='generation-job')
router.register('practice', PracticeViewSet, basename='practice')

urlpatterns = router.urls

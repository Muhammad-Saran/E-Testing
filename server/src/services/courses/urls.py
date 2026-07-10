from rest_framework.routers import DefaultRouter

from .views import CourseMaterialViewSet, CourseViewSet, EnrollmentViewSet

router = DefaultRouter()
router.register('materials', CourseMaterialViewSet, basename='material')
router.register('enrollments', EnrollmentViewSet, basename='enrollment')
router.register('', CourseViewSet, basename='course')

urlpatterns = router.urls

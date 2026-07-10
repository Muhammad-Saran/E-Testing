from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AvailableExamsView,
    ExamResultView,
    ExamViewSet,
    StartExamView,
    SubmitExamView,
)

router = DefaultRouter()
router.register('', ExamViewSet, basename='exam')

app_name = 'exams'

# Student endpoints first (distinct paths; exam pks are numeric so no clash).
urlpatterns = [
    path('available/', AvailableExamsView.as_view(), name='available'),
    path('<int:pk>/start/', StartExamView.as_view(), name='start'),
    path('<int:pk>/submit/', SubmitExamView.as_view(), name='submit'),
    path('<int:pk>/result/', ExamResultView.as_view(), name='result'),
]

urlpatterns += router.urls

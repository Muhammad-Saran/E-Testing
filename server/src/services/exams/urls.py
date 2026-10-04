from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AvailableExamsView,
    ExamResultView,
    ExamViewSet,
    MyResultsView,
    ProctorEventView,
    SaveAnswersView,
    StartExamView,
    SubmitExamView,
)

router = DefaultRouter()
router.register('', ExamViewSet, basename='exam')

app_name = 'exams'

# Student endpoints first (distinct paths; exam pks are numeric so no clash).
urlpatterns = [
    path('available/', AvailableExamsView.as_view(), name='available'),
    path('results/', MyResultsView.as_view(), name='my_results'),
    path('<int:pk>/start/', StartExamView.as_view(), name='start'),
    path('<int:pk>/save/', SaveAnswersView.as_view(), name='save'),
    path('<int:pk>/proctor-event/', ProctorEventView.as_view(), name='proctor_event'),
    path('<int:pk>/submit/', SubmitExamView.as_view(), name='submit'),
    path('<int:pk>/result/', ExamResultView.as_view(), name='result'),
]

urlpatterns += router.urls

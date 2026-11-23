from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import QuizzesViewSet

router = DefaultRouter()
router.register(r'quizzes', QuizzesViewSet, basename='quizzes')

urlpatterns = [
    path('', include(router.urls)),
]
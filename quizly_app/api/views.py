from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from quizly_app.models import Quiz

from .permissions import IsQuizOwner
from .serializers import QuizSerializer, QuizUpdateSerializer


class QuizzesViewSet(ModelViewSet):
    """List, retrieve, update (title/description) and delete own quizzes."""

    permission_classes = [IsAuthenticated, IsQuizOwner]
    # POST is added once the generation pipeline (utils.py) exists
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        """Own quizzes for list, all quizzes otherwise so foreign ones
        return 403 instead of 404."""
        queryset = Quiz.objects.prefetch_related("questions").order_by(
            "-created_at"
        )
        if self.action == "list":
            return queryset.filter(user=self.request.user)
        return queryset

    def get_serializer_class(self):
        if self.action == "partial_update":
            return QuizUpdateSerializer
        return QuizSerializer

    def partial_update(self, request, *args, **kwargs):
        """Update title/description and return the full quiz."""
        quiz = self.get_object()
        serializer = self.get_serializer(quiz, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(QuizSerializer(quiz).data)

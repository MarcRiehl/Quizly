from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from quizly_app.models import Quiz

from .permissions import IsQuizOwner
from .serializers import (
    QuizCreateSerializer,
    QuizSerializer,
    QuizUpdateSerializer,
)
from .utils import (
    InvalidVideoError,
    QuizGenerationError,
    create_quiz_from_url,
)


class QuizzesViewSet(ModelViewSet):
    """Create quizzes from YouTube URLs and manage own quizzes."""

    permission_classes = [IsAuthenticated, IsQuizOwner]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

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
        if self.action == "create":
            return QuizCreateSerializer
        if self.action == "partial_update":
            return QuizUpdateSerializer
        return QuizSerializer

    def create(self, request, *args, **kwargs):
        """Generate a quiz from a YouTube URL and return it."""
        serializer = self.get_serializer(data=request.data)
        # Invalid URL or request data -> 400
        serializer.is_valid(raise_exception=True)
        try:
            quiz = create_quiz_from_url(
                request.user, serializer.validated_data["url"]
            )
        except InvalidVideoError as error:
            return Response(
                {"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST
            )
        except QuizGenerationError as error:
            # Pipeline failure (transcription, Gemini, validation) -> 500
            return Response(
                {"detail": str(error)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            QuizSerializer(quiz).data, status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, *args, **kwargs):
        """Update title/description and return the full quiz."""
        quiz = self.get_object()
        serializer = self.get_serializer(quiz, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(QuizSerializer(quiz).data)

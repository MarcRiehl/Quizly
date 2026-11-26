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
        """Return the quizzes available for the current action.

        The list action only returns the user's own quizzes. All other
        actions use all quizzes, so accessing a foreign quiz returns 403
        (via IsQuizOwner) instead of 404.

        Returns:
            QuerySet: Quizzes with prefetched questions, newest first.
        """
        queryset = Quiz.objects.prefetch_related("questions").order_by(
            "-created_at"
        )
        if self.action == "list":
            return queryset.filter(user=self.request.user)
        return queryset

    def get_serializer_class(self):
        """Return the serializer class for the current action.

        Returns:
            type[Serializer]: QuizCreateSerializer for create,
            QuizUpdateSerializer for partial_update, otherwise
            QuizSerializer.
        """
        if self.action == "create":
            return QuizCreateSerializer
        if self.action == "partial_update":
            return QuizUpdateSerializer
        return QuizSerializer

    def create(self, request, *args, **kwargs):
        """Generate a quiz from a YouTube URL and return it.

        Args:
            request: The DRF request containing the YouTube URL.
            *args: Additional positional arguments from the router.
            **kwargs: Additional keyword arguments from the router.

        Returns:
            Response: 201 with the created quiz, 400 if the URL is invalid
            or the video is unavailable, or 500 if the quiz generation
            pipeline fails.
        """
        serializer = self.get_serializer(data=request.data)
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
            return Response(
                {"detail": str(error)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            QuizSerializer(quiz).data, status=status.HTTP_201_CREATED
        )

    def partial_update(self, request, *args, **kwargs):
        """Update title/description and return the full quiz.

        Args:
            request: The DRF request containing title and/or description.
            *args: Additional positional arguments from the router.
            **kwargs: Additional keyword arguments from the router (pk).

        Returns:
            Response: 200 with the full updated quiz, 400 on invalid data,
            403 if the quiz belongs to another user, or 404 if it does
            not exist.
        """
        quiz = self.get_object()
        serializer = self.get_serializer(quiz, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(QuizSerializer(quiz).data)

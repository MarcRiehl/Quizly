from urllib.parse import parse_qs, urlparse
from rest_framework import serializers
from quizly_app.models import Question, Quiz
from django.utils import timezone

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
YOUTU_BE_HOST = "youtu.be"


class QuestionSerializer(serializers.ModelSerializer):
    """Output representation of a single quiz question."""

    class Meta:
        model = Question
        fields = [
            "id",
            "question_title",
            "question_options",
            "answer",
            "created_at",
            "updated_at",
        ]


class QuizSerializer(serializers.ModelSerializer):
    """Full output representation of a quiz including its questions."""

    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "description",
            "created_at",
            "updated_at",
            "video_url",
            "questions",
        ]


class QuizCreateSerializer(serializers.Serializer):
    """Validates the YouTube URL used to generate a new quiz."""

    url = serializers.URLField()

    def validate_url(self, value):
        """Accept only YouTube URLs and normalize them to watch?v=<id>.

        Supports youtube.com links with a "v" query parameter and
        youtu.be short links.

        Args:
            value (str): The URL submitted by the user.

        Returns:
            str: The normalized URL in the form
            https://www.youtube.com/watch?v=<video_id>.

        Raises:
            serializers.ValidationError: If the URL is not a YouTube URL
                or does not contain a video ID.
        """
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()

        if host in YOUTUBE_HOSTS:
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif host == YOUTU_BE_HOST:
            video_id = parsed.path.lstrip("/").split("/")[0]
        else:
            raise serializers.ValidationError(
                "Only YouTube URLs are allowed."
            )

        if not video_id:
            raise serializers.ValidationError(
                "The URL does not contain a YouTube video ID."
            )

        return f"https://www.youtube.com/watch?v={video_id}"


class QuizUpdateSerializer(serializers.ModelSerializer):
    """Allows updating only the title and description of a quiz."""

    class Meta:
        model = Quiz
        fields = ["title", "description"]

    def update(self, instance, validated_data):
        """Update the title and description of a quiz.

        Fields missing from validated_data keep their current value.
        The updated_at timestamp is always refreshed.

        Args:
            instance (Quiz): The quiz to update.
            validated_data (dict): The validated title and/or description.

        Returns:
            Quiz: The updated and saved quiz instance.
        """
        instance.title = validated_data.get("title", instance.title)
        instance.description = validated_data.get(
            "description", instance.description
        )
        instance.updated_at = timezone.now()
        instance.save()

        return instance

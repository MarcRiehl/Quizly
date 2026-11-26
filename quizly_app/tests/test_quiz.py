from unittest.mock import patch

import yt_dlp
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from quizly_app.api.utils import (
    InvalidVideoError,
    QuizGenerationError,
    create_quiz_from_url,
    save_quiz,
    validate_quiz_data,
)
from quizly_app.models import Question, Quiz

VIDEO_ID = "dQw4w9WgXcQ"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
SHORT_URL = f"https://youtu.be/{VIDEO_ID}"


def create_user(username):
    """Create a user with a fixed test password."""
    return get_user_model().objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="test-password-123",
    )


def authenticate(client, user):
    """Set the JWT access token as cookie like the real login does."""
    client.cookies["access_token"] = str(AccessToken.for_user(user))


def build_quiz_data():
    """Return valid quiz data as Gemini would deliver it."""
    questions = []
    for index in range(10):
        options = [f"Option {index}-{letter}" for letter in "ABCD"]
        questions.append({
            "question_title": f"Question {index}?",
            "question_options": options,
            "answer": options[0],
        })
    return {
        "title": "Test Quiz",
        "description": "A quiz for testing.",
        "questions": questions,
    }


class QuizApiTests(APITestCase):
    """Endpoint tests for /api/quizzes/ with a mocked pipeline."""

    def setUp(self):
        self.user = create_user("owner")
        self.other_user = create_user("other")
        self.quiz = save_quiz(self.user, VIDEO_URL, build_quiz_data())
        self.other_quiz = save_quiz(
            self.other_user, VIDEO_URL, build_quiz_data()
        )
        self.list_url = reverse("quizzes-list")
        authenticate(self.client, self.user)

    def detail_url(self, quiz_id):
        return reverse("quizzes-detail", args=[quiz_id])

    @patch("quizly_app.api.views.create_quiz_from_url")
    def test_create_quiz_returns_201(self, mock_create):
        mock_create.return_value = self.quiz
        response = self.client.post(
            self.list_url, {"url": SHORT_URL}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["questions"]), 10)
        # Short link must be normalized before it reaches the pipeline
        mock_create.assert_called_once_with(self.user, VIDEO_URL)

    @patch("quizly_app.api.views.create_quiz_from_url")
    def test_create_quiz_invalid_url_returns_400(self, mock_create):
        for body in ({"url": "https://vimeo.com/123"}, {}):
            response = self.client.post(self.list_url, body, format="json")
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST
            )
        mock_create.assert_not_called()

    @patch("quizly_app.api.views.create_quiz_from_url")
    def test_create_quiz_unavailable_video_returns_400(self, mock_create):
        mock_create.side_effect = InvalidVideoError("Video not found.")
        response = self.client.post(
            self.list_url, {"url": VIDEO_URL}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("quizly_app.api.views.create_quiz_from_url")
    def test_create_quiz_pipeline_error_returns_500(self, mock_create):
        mock_create.side_effect = QuizGenerationError("Gemini failed.")
        response = self.client.post(
            self.list_url, {"url": VIDEO_URL}, format="json"
        )
        self.assertEqual(
            response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        self.assertEqual(response.data["detail"], "Gemini failed.")

    def test_list_returns_only_own_quizzes(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [quiz["id"] for quiz in response.data]
        self.assertEqual(ids, [self.quiz.id])

    def test_retrieve_own_quiz(self):
        response = self.client.get(self.detail_url(self.quiz.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.quiz.id)
        self.assertEqual(len(response.data["questions"]), 10)

    def test_retrieve_foreign_quiz_returns_403(self):
        response = self.client.get(self.detail_url(self.other_quiz.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_missing_quiz_returns_404(self):
        response = self.client.get(self.detail_url(99999))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_updates_only_title_and_description(self):
        response = self.client.patch(
            self.detail_url(self.quiz.id),
            {
                "title": "New title",
                "description": "New description",
                "video_url": "https://www.youtube.com/watch?v=changed",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.title, "New title")
        self.assertEqual(self.quiz.description, "New description")
        self.assertEqual(self.quiz.video_url, VIDEO_URL)
        self.assertEqual(len(response.data["questions"]), 10)

    def test_patch_foreign_quiz_returns_403(self):
        response = self.client.patch(
            self.detail_url(self.other_quiz.id),
            {"title": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.other_quiz.refresh_from_db()
        self.assertEqual(self.other_quiz.title, "Test Quiz")

    def test_put_not_allowed(self):
        response = self.client.put(
            self.detail_url(self.quiz.id),
            {"title": "New title", "description": ""},
            format="json",
        )
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_delete_own_quiz_returns_204(self):
        response = self.client.delete(self.detail_url(self.quiz.id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Quiz.objects.filter(id=self.quiz.id).exists())
        self.assertFalse(
            Question.objects.filter(quiz_id=self.quiz.id).exists()
        )

    def test_delete_foreign_quiz_returns_403(self):
        response = self.client.delete(self.detail_url(self.other_quiz.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Quiz.objects.filter(id=self.other_quiz.id).exists())

    def test_requests_without_cookie_return_401(self):
        self.client.cookies.clear()
        responses = [
            self.client.get(self.list_url),
            self.client.post(self.list_url, {"url": VIDEO_URL}, format="json"),
            self.client.get(self.detail_url(self.quiz.id)),
        ]
        for response in responses:
            self.assertEqual(
                response.status_code, status.HTTP_401_UNAUTHORIZED
            )


class QuizUtilsTests(TestCase):
    """Tests for the validation and pipeline helpers in utils.py."""

    def setUp(self):
        self.user = create_user("owner")

    def test_validate_quiz_data_accepts_valid_data(self):
        validate_quiz_data(build_quiz_data())

    def test_validate_quiz_data_rejects_invalid_data(self):
        wrong_count = build_quiz_data()
        wrong_count["questions"].pop()

        three_options = build_quiz_data()
        three_options["questions"][0]["question_options"].pop()

        duplicate_options = build_quiz_data()
        duplicate_options["questions"][0]["question_options"] = [
            "Same", "Same", "Other", "Another",
        ]
        duplicate_options["questions"][0]["answer"] = "Same"

        wrong_answer = build_quiz_data()
        wrong_answer["questions"][0]["answer"] = "Not an option"

        missing_title = build_quiz_data()
        missing_title["title"] = ""

        cases = {
            "wrong_count": wrong_count,
            "three_options": three_options,
            "duplicate_options": duplicate_options,
            "wrong_answer": wrong_answer,
            "missing_title": missing_title,
        }
        for name, data in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(QuizGenerationError):
                    validate_quiz_data(data)

    @patch("quizly_app.api.utils.download_audio")
    def test_create_quiz_from_url_unavailable_video(self, mock_download):
        mock_download.side_effect = yt_dlp.utils.DownloadError("gone")
        with self.assertRaises(InvalidVideoError):
            create_quiz_from_url(self.user, VIDEO_URL)
        self.assertFalse(Quiz.objects.exists())

    @patch("quizly_app.api.utils.generate_quiz_data")
    @patch("quizly_app.api.utils.transcribe_audio")
    @patch("quizly_app.api.utils.download_audio")
    def test_create_quiz_from_url_saves_quiz(
        self, mock_download, mock_transcribe, mock_generate
    ):
        mock_download.return_value = "audio.webm"
        mock_transcribe.return_value = "Some transcript."
        mock_generate.return_value = build_quiz_data()

        quiz = create_quiz_from_url(self.user, VIDEO_URL)

        self.assertEqual(Quiz.objects.count(), 1)
        self.assertEqual(quiz.user, self.user)
        self.assertEqual(quiz.video_url, VIDEO_URL)
        self.assertEqual(quiz.questions.count(), 10)
        mock_generate.assert_called_once_with("Some transcript.")

    @patch("quizly_app.api.utils.generate_quiz_data")
    @patch("quizly_app.api.utils.transcribe_audio")
    @patch("quizly_app.api.utils.download_audio")
    def test_create_quiz_from_url_empty_transcript(
        self, mock_download, mock_transcribe, mock_generate
    ):
        mock_download.return_value = "audio.webm"
        mock_transcribe.return_value = ""

        with self.assertRaises(QuizGenerationError):
            create_quiz_from_url(self.user, VIDEO_URL)
        mock_generate.assert_not_called()
        self.assertFalse(Quiz.objects.exists())

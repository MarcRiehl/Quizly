import tempfile
import time
from pathlib import Path

import whisper
import yt_dlp
from django.conf import settings
from django.db import transaction
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from quizly_app.models import Question, Quiz

WHISPER_MODEL_NAME = "base"
QUESTION_COUNT = 10
OPTION_COUNT = 4

FALLBACK_CLIENT_ERROR_CODES = {404, 429}
SERVER_ERROR_RETRY_DELAYS = (2, 4, 8)
_whisper_model = None


class QuizGenerationError(Exception):
    """Raised when any step of the quiz generation pipeline fails."""


class InvalidVideoError(QuizGenerationError):
    """Raised when the video behind a valid URL cannot be downloaded."""


class GeneratedQuestion(BaseModel):
    """Response schema for a single question returned by Gemini."""

    question_title: str
    question_options: list[str]
    answer: str


class GeneratedQuiz(BaseModel):
    """Response schema for the whole quiz returned by Gemini."""

    title: str
    description: str
    questions: list[GeneratedQuestion]


QUIZ_PROMPT = (
    "Create a quiz based on the following transcript.\n"
    f"- Exactly {QUESTION_COUNT} questions.\n"
    f"- Each question has exactly {OPTION_COUNT} distinct answer options.\n"
    "- Exactly one option is correct; 'answer' must be identical to that "
    "option.\n"
    "- 'title' is a short quiz title, 'description' a short summary "
    "(max. 150 characters).\n"
    "- Use the language of the transcript.\n\n"
    "Transcript:\n"
)


def download_audio(url, target_dir):
    """Download the best audio stream of a YouTube video into target_dir.

    Args:
        url (str): The YouTube video URL.
        target_dir (str | Path): The directory to store the audio file in.

    Returns:
        Path: The path of the downloaded audio file.

    Raises:
        yt_dlp.utils.DownloadError: If the video cannot be downloaded.
    """
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(Path(target_dir) / "%(id)s.%(ext)s"),
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return Path(ydl.prepare_filename(info))


def get_whisper_model():
    """Return the cached Whisper model, loading it on first use.

    Returns:
        whisper.Whisper: The loaded Whisper model (WHISPER_MODEL_NAME).
    """
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
    return _whisper_model


def transcribe_audio(audio_path):
    """Transcribe an audio file to text with Whisper.

    Args:
        audio_path (str | Path): The path of the audio file.

    Returns:
        str: The transcript without leading or trailing whitespace.
    """
    result = get_whisper_model().transcribe(str(audio_path), fp16=False)
    return result["text"].strip()


def get_gemini_models():
    """Return the primary model followed by fallbacks, without duplicates.

    Returns:
        list[str]: GEMINI_MODEL followed by GEMINI_FALLBACK_MODELS from
        the settings, in order and without duplicates.
    """
    models = [settings.GEMINI_MODEL, *settings.GEMINI_FALLBACK_MODELS]
    return list(dict.fromkeys(models))


def is_fallback_error(error):
    """Check whether trying another Gemini model can help.

    Args:
        error (errors.APIError): The error raised by the Gemini API.

    Returns:
        bool: True for server errors and for client errors listed in
        FALLBACK_CLIENT_ERROR_CODES (404, 429), otherwise False.
    """
    if isinstance(error, errors.ServerError):
        return True
    return (
        isinstance(error, errors.ClientError)
        and error.code in FALLBACK_CLIENT_ERROR_CODES
    )


def request_quiz_from_model(client, model, transcript):
    """Send the quiz prompt to a single Gemini model.

    Requests a JSON response that follows the GeneratedQuiz schema.

    Args:
        client (genai.Client): The Gemini API client.
        model (str): The name of the Gemini model.
        transcript (str): The video transcript to build the quiz from.

    Returns:
        types.GenerateContentResponse: The raw Gemini response.

    Raises:
        errors.APIError: If the Gemini API request fails.
    """
    return client.models.generate_content(
        model=model,
        contents=QUIZ_PROMPT + transcript,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeneratedQuiz,
        ),
    )


def request_quiz_with_retry(client, model, transcript):
    """Request a quiz from one model, retrying on server errors.

    Server errors (e.g. 503 overload) are retried with the increasing
    delays from SERVER_ERROR_RETRY_DELAYS before a final attempt.

    Args:
        client (genai.Client): The Gemini API client.
        model (str): The name of the Gemini model.
        transcript (str): The video transcript to build the quiz from.

    Returns:
        types.GenerateContentResponse: The raw Gemini response.

    Raises:
        errors.APIError: If the final attempt fails or a non-server
            error occurs.
    """
    for delay in SERVER_ERROR_RETRY_DELAYS:
        try:
            return request_quiz_from_model(client, model, transcript)
        except errors.ServerError:
            time.sleep(delay)
    return request_quiz_from_model(client, model, transcript)


def generate_quiz_data(transcript):
    """Let Gemini create quiz data from a transcript.

    Tries the configured models in order and falls back to the next one
    on overload, rate limit or unknown model.

    Args:
        transcript (str): The video transcript to build the quiz from.

    Returns:
        dict: The quiz data with title, description and questions.

    Raises:
        QuizGenerationError: If Gemini returns no parsable data or all
            models are unavailable.
        errors.APIError: If a model fails with a non-fallback error.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    for model in get_gemini_models():
        try:
            response = request_quiz_with_retry(client, model, transcript)
        except errors.APIError as error:
            if is_fallback_error(error):
                continue
            raise
        if response.parsed is None:
            raise QuizGenerationError("Gemini returned no valid quiz data.")
        return response.parsed.model_dump()
    raise QuizGenerationError("All Gemini models unavailable.")


def validate_quiz_data(data):
    """Ensure 10 questions with 4 distinct options and a valid answer.

    Also checks that the quiz has a title.

    Args:
        data (dict): The quiz data returned by generate_quiz_data.

    Returns:
        None

    Raises:
        QuizGenerationError: If the quiz data does not meet the rules.
    """
    questions = data.get("questions") or []
    if len(questions) != QUESTION_COUNT:
        raise QuizGenerationError(
            f"Expected {QUESTION_COUNT} questions, got {len(questions)}."
        )
    for question in questions:
        options = question.get("question_options") or []
        if len(options) != OPTION_COUNT or len(set(options)) != OPTION_COUNT:
            raise QuizGenerationError(
                f"Each question needs {OPTION_COUNT} distinct options."
            )
        if question.get("answer") not in options:
            raise QuizGenerationError("Answer is not one of the options.")
    if not data.get("title"):
        raise QuizGenerationError("Quiz title is missing.")


def save_quiz(user, video_url, data):
    """Store quiz and questions in a single transaction.

    Args:
        user (User): The owner of the new quiz.
        video_url (str): The normalized YouTube URL of the video.
        data (dict): The validated quiz data.

    Returns:
        Quiz: The newly created quiz.
    """
    with transaction.atomic():
        quiz = Quiz.objects.create(
            user=user,
            title=data["title"],
            description=data.get("description", ""),
            video_url=video_url,
        )
        Question.objects.bulk_create([
            Question(
                quiz=quiz,
                question_title=question["question_title"],
                question_options=question["question_options"],
                answer=question["answer"],
            )
            for question in data["questions"]
        ])
    return quiz


def create_quiz_from_url(user, url):
    """Run the full pipeline: download, transcribe, generate, save.

    Args:
        user (User): The owner of the new quiz.
        url (str): The normalized YouTube URL of the video.

    Returns:
        Quiz: The newly created quiz with its questions.

    Raises:
        InvalidVideoError: If the video cannot be downloaded.
        QuizGenerationError: If transcription, generation or validation
            fails.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            audio_path = download_audio(url, temp_dir)
        except yt_dlp.utils.DownloadError as error:
            raise InvalidVideoError(
                "Video not found or not available."
            ) from error

        try:
            transcript = transcribe_audio(audio_path)
        except Exception as error:
            raise QuizGenerationError(
                "Audio could not be transcribed."
            ) from error

    if not transcript:
        raise QuizGenerationError("Transcript is empty.")

    try:
        data = generate_quiz_data(transcript)
    except QuizGenerationError:
        raise
    except Exception as error:
        raise QuizGenerationError("Quiz could not be generated.") from error

    validate_quiz_data(data)
    return save_quiz(user, url, data)

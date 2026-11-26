
from django.contrib import admin

from .models import Quiz, Question


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = (
        "question_title",
        "question_options",
        "answer",
        "created_at",
        "updated_at",
    )


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "user",
        "video_url",
        "created_at",
        "updated_at",
    )

    list_display_links = ("id", "title")

    list_filter = (
        "created_at",
        "updated_at",
    )

    search_fields = (
        "title",
        "description",
        "video_url",
        "user__username",
        "user__email",
    )

    ordering = ("-created_at",)


    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "question_title",
        "quiz",
        "answer",
        "created_at",
        "updated_at",
    )

    list_display_links = ("id", "question_title")

    list_filter = (
        "quiz",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "question_title",
        "answer",
        "quiz__title",
    )

    ordering = ("quiz", "id")

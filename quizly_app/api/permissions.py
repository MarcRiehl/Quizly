from rest_framework.permissions import BasePermission


class IsQuizOwner(BasePermission):

    def has_object_permission(self, request, view, obj):
        """Allow access only to the owner of the quiz.

        Args:
            request: The incoming DRF request.
            view: The view handling the request.
            obj: The quiz instance being accessed.

        Returns:
            bool: True if the user is authenticated and owns the quiz,
            otherwise False.
        """
        return (request.user.is_authenticated and obj.user == request.user)

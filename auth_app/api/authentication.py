
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):

    def authenticate(self, request):
        """Authenticate a request using the JWT stored in an HTTP-only cookie.

        Reads the access token from the "access_token" cookie instead of the
        Authorization header, validates it and resolves the associated user.

        Args:
            request: The incoming DRF request object.

        Returns:
            tuple | None: A tuple of (user, validated_token) if the cookie
            contains a valid token, or None if no access token cookie is
            present.

        Raises:
            InvalidToken: If the token in the cookie is invalid or expired.
            AuthenticationFailed: If the user referenced by the token cannot
                be found or is inactive.
        """
        raw_token = request.COOKIES.get("access_token")

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)

        return self.get_user(validated_token), validated_token

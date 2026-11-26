from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.token_blacklist.models import (BlacklistedToken,
                                                             OutstandingToken)
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.views import (TokenObtainPairView,
                                            TokenRefreshView)

from .serializers import RegistrationSerializer

User = get_user_model()


class RegisterView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        """Register a new user account.

        Args:
            request: The DRF request containing username, email, password
                and confirmed_password.

        Returns:
            Response: 201 with a success message if the user was created,
            otherwise 400 with the serializer validation errors.
        """
        serializer = RegistrationSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            return Response(
                {"detail": "User created successfully!"},
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TokenLoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        """Log in a user and store the JWTs in HTTP-only cookies.

        Obtains an access/refresh token pair via Simple JWT and sets both
        tokens as HTTP-only cookies instead of returning them in the body.

        Args:
            request: The DRF request containing username and password.
            *args: Additional positional arguments passed to the parent view.
            **kwargs: Additional keyword arguments passed to the parent view.

        Returns:
            Response: 200 with a success message and basic user data
            (id, username, email) plus the token cookies, or 401 if the
            credentials are invalid.
        """
        response = super().post(request, *args, **kwargs)

        if response.status_code != status.HTTP_200_OK:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = response.data.get("refresh")
        access = response.data.get("access")

        user = self.get_user_from_token(access)

        response = Response(
            {
                "detail": "Login successfully!",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email
                }
            },
            status=status.HTTP_200_OK
        )

        response.set_cookie(
            key="access_token",
            value=access,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax"
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax"
        )

        return response

    def get_user_from_token(self, access):
        """Resolve the user that an access token belongs to.

        Args:
            access (str): The encoded JWT access token.

        Returns:
            User: The user referenced by the token's user_id claim.
        """
        token = AccessToken(access)
        return User.objects.get(id=token["user_id"])


class BaseTokenRefreshView(TokenRefreshView):

    def post(self, request, *args, **kwargs):
        """Issue a new access token using the refresh token cookie.

        Reads the refresh token from the "refresh_token" cookie, validates
        it and sets the new access token (and a rotated refresh token, if
        one is issued) as HTTP-only cookies.

        Args:
            request: The DRF request carrying the refresh token cookie.
            *args: Additional positional arguments passed to the parent view.
            **kwargs: Additional keyword arguments passed to the parent view.

        Returns:
            Response: 200 with a success message and the updated token
            cookies, or 401 if the refresh token is missing or invalid.
        """
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found!"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = self.get_serializer(data={"refresh": refresh_token})

        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, AuthenticationFailed):
            return Response(
                {"detail": "Refresh token invalid!"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        access_token = serializer.validated_data.get("access")
        new_refresh = serializer.validated_data.get("refresh")

        response = Response(
            {"detail": "Token refreshed"},
            status=status.HTTP_200_OK
        )

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax"
        )

        if new_refresh:
            response.set_cookie(
                key="refresh_token",
                value=new_refresh,
                httponly=True,
                secure=not settings.DEBUG,
                samesite="Lax"
            )

        return response


class TokenLogoutView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Log out the user by blacklisting tokens and deleting cookies.

        Blacklists all outstanding refresh tokens of the authenticated user
        and removes the access and refresh token cookies.

        Args:
            request: The DRF request of the authenticated user.

        Returns:
            Response: 200 with a logout confirmation message and the token
            cookies deleted.
        """
        user = request.user
        outstanding_tokens = OutstandingToken.objects.filter(user=user)

        for token in outstanding_tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        response = Response(
            {
                "detail": (
                    "Log-Out successfully! All Tokens will be deleted. "
                    "Refresh token is now invalid."
                )
            },
            status=status.HTTP_200_OK
        )

        response.delete_cookie(
            key="access_token",
            path="/",
            samesite="Lax"
        )

        response.delete_cookie(
            key="refresh_token",
            path="/",
            samesite="Lax"
        )

        return response

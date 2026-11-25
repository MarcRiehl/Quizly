from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .serializers import RegistrationSerializer
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView
from rest_framework import status

from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken
)

User = get_user_model()

class RegisterView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()

            return Response({"detail": "User created successfully!"},status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TokenLoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code != status.HTTP_200_OK:
            return Response({"detail": "Invalid username or password."}, status=status.HTTP_401_UNAUTHORIZED)

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
            # secure=True,
            secure=not settings.DEBUG,
            samesite="Lax"
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh,
            httponly=True,
            # secure=True, #nur mit HTTPS
            secure=not settings.DEBUG,
            samesite="Lax"
        )

        return response

    def get_user_from_token(self, access):
        token = AccessToken(access)
        return User.objects.get(id=token["user_id"])
    

class BaseTokenRefreshView(TokenRefreshView):

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response({"detail": "Refresh token not found!"},status=status.HTTP_401_UNAUTHORIZED)

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

        if new_refresh: #für Refresh-Token-Rotation
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
        user = request.user
        outstanding_tokens = OutstandingToken.objects.filter(user=user) #setzt die Refresh Tokens auf die Blacklist

        for token in outstanding_tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        response = Response(
            {
                "detail": (
                    "Log-Out successfully! All Tokens will be deleted. Refresh token is now invalid."
                )
            },
            status=status.HTTP_200_OK
        )

        response.delete_cookie( #Cookies löschen
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

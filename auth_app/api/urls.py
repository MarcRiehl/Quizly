from django.urls import path
from .views import RegisterView, TokenLoginView, TokenLogoutView, BaseTokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', TokenLoginView.as_view(), name='login'),
    path('logout/', TokenLogoutView.as_view(), name='logout'),
    path('token/refresh/', BaseTokenRefreshView.as_view(), name='token-refresh'),
]
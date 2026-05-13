from django.urls import path

from .views import OrganizationSignupView, PublicLandingView

app_name = "organizations"

urlpatterns = [
    path("", PublicLandingView.as_view(), name="landing"),
    path("signup/", OrganizationSignupView.as_view(), name="signup"),
]

from django.urls import path

from .views import CompanyCreateView

app_name = "companies"

urlpatterns = [
    path("nueva/", CompanyCreateView.as_view(), name="create"),
]

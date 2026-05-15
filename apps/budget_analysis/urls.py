from django.urls import path

from . import views

app_name = "budget_analysis"

urlpatterns = [
    path("", views.ReportListView.as_view(), name="report_list"),
    path("nuevo/", views.cross_generate, name="generate"),
    path("<int:pk>/", views.report_detail, name="report_detail"),
]

from django.urls import path

from . import views

app_name = "tracking"

urlpatterns = [
    path("obras/<int:pk>/", views.project_tracking, name="project"),

    path("sugerencias/", views.SuggestionListView.as_view(), name="suggestions"),
    path("sugerencias/scan/", views.scan_variances, name="scan_variances"),
    path("sugerencias/<int:pk>/aprobar/", views.suggestion_approve, name="suggestion_approve"),
    path("sugerencias/<int:pk>/rechazar/", views.suggestion_reject, name="suggestion_reject"),
]

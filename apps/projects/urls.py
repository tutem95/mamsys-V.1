from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("nueva/", views.ProjectCreateView.as_view(), name="create"),
    path("<int:pk>/", views.ProjectDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.ProjectUpdateView.as_view(), name="edit"),
]

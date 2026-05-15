from django.urls import path

from . import views

app_name = "imports"

urlpatterns = [
    path("", views.index, name="index"),
    path("logs/", views.LogListView.as_view(), name="log_list"),
    path("logs/<int:pk>/", views.log_detail, name="log_detail"),
    path("<slug:slug>/", views.upload, name="upload"),
    path("<slug:slug>/confirmar/", views.confirm, name="confirm"),
]

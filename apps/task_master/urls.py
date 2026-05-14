from django.urls import path

from . import views

app_name = "task_master"

urlpatterns = [
    path("", views.master_index, name="index"),

    path("tareas/", views.TaskListView.as_view(), name="task_list"),
    path("tareas/nueva/", views.task_create, name="task_create"),
    path("tareas/<int:pk>/", views.task_detail, name="task_detail"),
    path("tareas/<int:pk>/editar/", views.task_edit, name="task_edit"),

    path("mezclas/", views.MixListView.as_view(), name="mix_list"),
    path("mezclas/nueva/", views.mix_create, name="mix_create"),
    path("mezclas/<int:pk>/", views.mix_detail, name="mix_detail"),
    path("mezclas/<int:pk>/editar/", views.mix_edit, name="mix_edit"),
]

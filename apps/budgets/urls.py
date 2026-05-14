from django.urls import path

from . import views

app_name = "budgets"

urlpatterns = [
    path("", views.BudgetListView.as_view(), name="list"),
    path("nuevo/", views.budget_create, name="create"),
    path("<int:pk>/", views.budget_detail, name="detail"),
    path("<int:pk>/editar/", views.budget_edit, name="edit"),
    path("<int:pk>/presentar/", views.budget_submit, name="submit"),
    path("<int:pk>/aprobar/", views.budget_approve, name="approve"),
    path("<int:pk>/rechazar/", views.budget_reject, name="reject"),
    path("<int:pk>/clonar/", views.budget_clone, name="clone"),
]

from django.urls import path

from . import views

app_name = "payroll"

urlpatterns = [
    path("empleados/", views.EmployeeListView.as_view(), name="list"),
    path("empleados/nuevo/", views.employee_create, name="create"),
    path("empleados/<int:pk>/", views.EmployeeDetailView.as_view(), name="detail"),
    path("empleados/<int:pk>/editar/", views.employee_edit, name="edit"),
]

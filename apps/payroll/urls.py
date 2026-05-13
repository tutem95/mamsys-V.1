from django.urls import path

from . import views

app_name = "payroll"

urlpatterns = [
    path("empleados/", views.EmployeeListView.as_view(), name="list"),
    path("empleados/nuevo/", views.employee_create, name="create"),
    path("empleados/<int:pk>/", views.EmployeeDetailView.as_view(), name="detail"),
    path("empleados/<int:pk>/editar/", views.employee_edit, name="edit"),

    # Quincenas
    path("quincenas/", views.PayrollPeriodListView.as_view(), name="period_list"),
    path("quincenas/nueva/", views.period_create, name="period_create"),
    path("quincenas/<int:pk>/", views.period_detail, name="period_detail"),
    path("quincenas/<int:pk>/editar/", views.period_edit, name="period_edit"),
    path("quincenas/<int:pk>/regenerar/", views.period_regenerate_entries, name="period_regenerate"),
    path("quincenas/entradas/<int:pk>/", views.entry_edit, name="entry_edit"),
]

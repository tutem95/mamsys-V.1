from django.urls import path

from . import views

app_name = "treasury"

urlpatterns = [
    path("", views.TreasuryEntryListView.as_view(), name="list"),
    path("saldos/", views.balances, name="balances"),
    path("nuevo/", views.entry_create, name="create"),
    path("<int:pk>/editar/", views.entry_edit, name="edit"),
    path("<int:pk>/conciliar/", views.entry_toggle_reconciled, name="toggle_reconciled"),
]

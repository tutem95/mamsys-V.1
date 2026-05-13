from django.urls import path

from . import views

app_name = "procurement"

urlpatterns = [
    path("", views.PurchaseListView.as_view(), name="list"),
    path("a-pagar/", views.to_pay_tray, name="to_pay"),
    path("cuenta-corriente/", views.supplier_balance, name="supplier_balance"),
    path("nueva/", views.purchase_create, name="create"),
    path("<int:pk>/", views.PurchaseDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.purchase_edit, name="edit"),
    path("<int:pk>/pagos/registrar/", views.payment_create, name="payment_create"),
    path("<int:pk>/pagos/<int:payment_pk>/borrar/", views.payment_delete, name="payment_delete"),
]

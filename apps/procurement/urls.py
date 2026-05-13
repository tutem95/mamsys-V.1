from django.urls import path

from . import views

app_name = "procurement"

urlpatterns = [
    path("", views.PurchaseListView.as_view(), name="list"),
    path("nueva/", views.purchase_create, name="create"),
    path("<int:pk>/", views.PurchaseDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.purchase_edit, name="edit"),
]

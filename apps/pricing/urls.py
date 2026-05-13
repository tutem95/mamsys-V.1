from django.urls import path

from . import views

app_name = "pricing"

urlpatterns = [
    path("", views.ExchangeRateTypeListView.as_view(), name="type_list"),
    path("nueva/", views.ExchangeRateTypeCreateView.as_view(), name="type_create"),
    path("<int:pk>/", views.type_detail, name="type_detail"),
    path("<int:pk>/editar/", views.ExchangeRateTypeUpdateView.as_view(), name="type_edit"),
]

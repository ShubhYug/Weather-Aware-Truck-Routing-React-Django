from django.urls import path

from . import views

urlpatterns = [
    path("plan/", views.plan_trip, name="trucking-plan"),
    path("suggest/", views.suggest, name="trucking-suggest"),
]

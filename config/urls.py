from django.urls import include, path

urlpatterns = [path("api/trucking/", include("trucking.urls"))]

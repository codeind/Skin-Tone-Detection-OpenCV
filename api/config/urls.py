from django.contrib import admin
from django.urls import path

from upload.views import ImageProcessView

urlpatterns = [
    path("image-process", ImageProcessView.as_view(), name="image-process"),
    path("admin/", admin.site.urls),
]

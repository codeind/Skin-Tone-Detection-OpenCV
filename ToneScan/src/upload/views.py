from django.shortcuts import render
from django.http import JsonResponse

# Importing modules for API
from rest_framework.response import Response
from rest_framework.views import APIView
from upload.ml import skintone_model

import base64

#fileURL = 'src/some_image.jpg'

# Create your views here.
class TestView(APIView):
    # Main Request Handler
    def post(self, request, *args, **kwargs):
        # Whatever you want to do with the request
        print("Request Received\n")
        text = request.body
        self.imgEncode(text)

        data = skintone_model.run()
        return JsonResponse(data)

    # Encodes the base64 data received in the request into an image and stores at 'src/some_image.jpg'
    def imgEncode(self, text):
        imgdata = base64.b64decode(text)
        filename = 'uploaded-image.jpg'
        with open(filename, 'wb') as f:
            f.write(imgdata)

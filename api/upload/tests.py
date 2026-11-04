import base64

import cv2
import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase


def png_bytes(rgb=(160, 126, 86), bg=(48, 96, 192)):
    img = np.zeros((120, 160, 3), np.uint8)
    img[:] = bg
    img[20:100, 40:120] = rgb
    ok, buf = cv2.imencode(".png", img[..., ::-1])
    return buf.tobytes()


class ImageProcessTests(SimpleTestCase):
    def test_base64_body_like_the_original_front_end(self):
        body = base64.b64encode(png_bytes())
        r = self.client.post("/image-process?face=0", data=body, content_type="text/plain")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["label"], "Tan")
        self.assertEqual(data["result"], "Tan")            # original front-end keys
        self.assertEqual([data["colorR"], data["colorG"], data["colorB"]], data["rgb"])

    def test_data_url_body(self):
        body = b"data:image/png;base64," + base64.b64encode(png_bytes())
        r = self.client.post("/image-process?face=0", data=body, content_type="text/plain")
        self.assertEqual(r.json()["label"], "Tan")

    def test_multipart_upload(self):
        f = SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png")
        r = self.client.post("/image-process?face=0", {"image": f})
        self.assertEqual(r.status_code, 200)
        self.assertIn("ita", r.json())

    def test_no_skin_returns_label_not_error(self):
        r = self.client.post("/image-process?face=0", data=base64.b64encode(png_bytes(rgb=(48, 96, 192))),
                             content_type="text/plain")
        self.assertEqual(r.json()["label"], "No skin detected")

    def test_bad_input_is_a_400(self):
        r = self.client.post("/image-process", data=b"not an image", content_type="text/plain")
        self.assertEqual(r.status_code, 400)

    def test_cors_header_for_allowed_origin(self):
        r = self.client.options("/image-process", HTTP_ORIGIN="http://localhost:8080")
        self.assertEqual(r["Access-Control-Allow-Origin"], "http://localhost:8080")

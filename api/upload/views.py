"""Image endpoint: POST a photo, get the estimated skin tone back as JSON.

Accepted bodies
- multipart/form-data with the file in the field "image"
- the raw base64 text of a JPEG/PNG, optionally as a data URL (what the original front end sends)

The image is decoded in memory and never written to disk.
"""
import base64
import binascii

from rest_framework.parsers import BaseParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from skintone import analyze_bytes


class RawBodyParser(BaseParser):
    """Accept any non-multipart body as raw bytes (base64 text or a data URL)."""
    media_type = "*/*"

    def parse(self, stream, media_type=None, parser_context=None):
        return stream.read()


def decode_base64(raw: bytes) -> bytes:
    text = raw.strip()
    if text.startswith(b"data:"):
        text = text.split(b",", 1)[-1]
    return base64.b64decode(text, validate=True)


class ImageProcessView(APIView):
    parser_classes = [MultiPartParser, RawBodyParser]
    authentication_classes = []          # public endpoint, no session or CSRF needed
    permission_classes = []

    def post(self, request):
        try:
            if "image" in getattr(request, "FILES", {}):
                data = request.FILES["image"].read()
            else:
                data = decode_base64(request.data if isinstance(request.data, bytes) else b"")
            result = analyze_bytes(data, use_face=request.query_params.get("face", "1") != "0")
        except (ValueError, binascii.Error):
            return Response({"error": "Send a JPEG or PNG image (multipart field 'image' or base64 text)."}, status=400)

        # Keys used by the original front end, kept so it still works unchanged
        r, g, b = result.get("rgb", [None, None, None])
        result.update({"result": result["label"], "colorR": r, "colorG": g, "colorB": b})
        return Response(result)

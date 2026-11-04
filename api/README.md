# ToneScan API (Django)

```bash
pip install -r ../requirements.txt
python manage.py runserver            # http://127.0.0.1:8000/image-process
```

`POST /image-process` takes a photo as multipart (`image` field) or as base64 text, and returns:

```json
{"skin_pixels": 5812, "skin_fraction": 0.1734, "label": "Light", "ita": 50.1,
 "lab": [77.4, 3.0, 22.9], "rgb": [213, 188, 149], "hex": "#d5bc95", "cluster_share": 0.97,
 "face_found": true, "result": "Light", "colorR": 213, "colorG": 188, "colorB": 149}
```

Add `?face=0` to analyse the whole image instead of the detected face. `result` and `colorR/G/B` are the
fields the original front end reads.

Settings come from environment variables: `DJANGO_SECRET_KEY` (a random key is generated when unset),
`DJANGO_DEBUG` (`1` by default), `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`.

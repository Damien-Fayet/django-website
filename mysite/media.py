"""Service des fichiers téléversés (`media/`) avec prise en charge des requêtes `Range`.

`django.views.static.serve` renvoie toujours le fichier entier. Or Safari / iOS refusent de lire une vidéo si le
serveur ne répond pas `206 Partial Content`, et le déplacement dans la vidéo en dépend partout. Ce wrapper ne traite
que le cas `Range: bytes=…` ; tout le reste (404, `If-Modified-Since`, types MIME) reste confié à `serve`.
"""
import mimetypes
import os
import re

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.utils._os import safe_join
from django.views.static import serve

_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")
CHUNK = 64 * 1024


def _read(path, start, length):
    with open(path, "rb") as fh:
        fh.seek(start)
        while length > 0:
            data = fh.read(min(CHUNK, length))
            if not data:
                break
            length -= len(data)
            yield data


def serve_media(request, path):
    header = request.headers.get("Range", "").strip()
    match = _RANGE.match(header) if header else None
    if not match or not (match.group(1) or match.group(2)):
        response = serve(request, path, document_root=settings.MEDIA_ROOT)
        response["Accept-Ranges"] = "bytes"
        return response

    try:
        full = safe_join(settings.MEDIA_ROOT, path)
        if not os.path.isfile(full):
            raise OSError("pas un fichier")
        size = os.path.getsize(full)
    except (ValueError, OSError, SuspiciousFileOperation):  # chemin hors de media/ compris
        raise Http404("Fichier introuvable")

    first, last = match.groups()
    if first:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    else:  # « bytes=-N » : les N derniers octets
        start = max(size - int(last), 0)
        end = size - 1
    if start >= size or start > end:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{size}"
        return response

    length = end - start + 1
    response = StreamingHttpResponse(_read(full, start, length), status=206,
                                     content_type=mimetypes.guess_type(full)[0] or "application/octet-stream")
    response["Content-Length"] = str(length)
    response["Content-Range"] = f"bytes {start}-{end}/{size}"
    response["Accept-Ranges"] = "bytes"
    return response

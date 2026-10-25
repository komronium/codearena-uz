"""Avatars are shown at 24-96 px, so what is stored is a 256 px WebP square (a phone photo is megabytes, and a page of
rows would carry one per person). The picture is cropped to the middle square, which is how every avatar is drawn."""
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

SIZE = 256


def shrink(source, stem: str) -> ContentFile:
    """`source` (a path, a file or bytes' BytesIO) as a SIZE x SIZE WebP file named `stem`.webp."""
    image = ImageOps.exif_transpose(Image.open(source))
    image = ImageOps.fit(image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB"),
                         (SIZE, SIZE), Image.Resampling.LANCZOS)
    out = BytesIO()
    image.save(out, "WEBP", quality=82, method=6)
    return ContentFile(out.getvalue(), name=f"{stem}.webp")


def is_small(name: str, size: int) -> bool:
    """True for a file `shrink` made already (or one as light), so the command leaves it alone."""
    return name.endswith(".webp") and size <= 40 * 1024

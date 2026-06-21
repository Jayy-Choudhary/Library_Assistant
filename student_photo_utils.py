import os
import re
from typing import Tuple


from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def safe_ext(filename: str) -> str:
    _, ext = os.path.splitext(filename or "")
    ext = (ext or "").lower()
    return ext


def validate_image_extension(filepath: str) -> Tuple[bool, str]:
    if not filepath:
        return False, "No file selected."
    ext = safe_ext(filepath)
    if ext not in ALLOWED_EXTS:
        return (
            False,
            "Invalid file type. Please select JPG, JPEG, PNG, or WEBP.",
        )
    return True, ""


def resize_and_save_photo(
    src_path: str,
    dst_full_path: str,
    dst_thumb_path: str,
    full_size: Tuple[int, int] = (260, 260),
    thumb_size: Tuple[int, int] = (64, 64),
) -> None:
    """Resize while keeping aspect ratio and save to disk.

    Saves at dst_full_path and dst_thumb_path.
    Output format is kept based on dst path extension.
    """
    if not src_path or not os.path.exists(src_path):
        raise FileNotFoundError("Selected photo does not exist.")

    full_dir = os.path.dirname(dst_full_path)
    thumb_dir = os.path.dirname(dst_thumb_path)
    ensure_dir(full_dir)
    ensure_dir(thumb_dir)

    # Load + validate decode
    try:
        img = Image.open(src_path)
        img.load()  # force decode
    except Exception as e:
        raise ValueError(
            "The selected image could not be read (corrupted/unsupported)."
        ) from e

    def _resize_keep_aspect(im: Image.Image, target: Tuple[int, int]) -> Image.Image:
        tw, th = target
        im = im.convert("RGBA")
        im.thumbnail((tw, th), Image.Resampling.LANCZOS)

        # Center on a solid background so that images never look stretched.
        bg = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
        x = (tw - im.width) // 2
        y = (th - im.height) // 2
        bg.paste(im, (x, y), im)
        return bg

    full_img = _resize_keep_aspect(img, full_size)
    thumb_img = _resize_keep_aspect(img, thumb_size)

    full_ext = os.path.splitext(dst_full_path)[1].lower()
    thumb_ext = os.path.splitext(dst_thumb_path)[1].lower()

    def _save(im: Image.Image, dst: str, ext: str):
        if ext in (".jpg", ".jpeg"):
            # JPEG has no alpha.
            rgb = im.convert("RGB")
            rgb.save(dst, format="JPEG", quality=90, optimize=True)
        elif ext == ".png":
            im.save(dst, format="PNG", optimize=True)
        elif ext == ".webp":
            im.save(dst, format="WEBP", quality=90, method=6)
        else:
            # Fallback
            im.save(dst)

    _save(full_img, dst_full_path, full_ext)
    _save(thumb_img, dst_thumb_path, thumb_ext)


def _slugish(text: str) -> str:
    # Keep a safe subset for filenames while preserving readable names.
    text = (text or "").strip()
    if not text:
        return "Student"
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_]+", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "Student"


def _format_seat_number(seat_number: str) -> str:
    seat = (seat_number or "").strip()
    match = re.search(r"(\d+)", seat)
    if not match:
        return _slugish(seat) or "00"
    return match.group(1).zfill(2)


def _format_mobile_number(mobile_number: str) -> str:
    digits = re.sub(r"\D+", "", mobile_number or "")
    return digits or "0000000000"


def make_photo_filenames(
    student_name: str,
    seat_number: str,
    mobile_number: str,
    original_filename: str,
    photo_dir: str | None = None,
) -> Tuple[str, str]:
    """Return (full_name, thumb_name) using student details.

    Base stem example: Appy_05_9898989898

    Files are versioned: base_stem.ext, base_stem_02.ext, base_stem_03.ext, ...
    Existing files are matched by stem across all supported image extensions.
    """
    ext = safe_ext(original_filename)
    if ext not in ALLOWED_EXTS:
        ext = ".jpg"

    stem = (
        f"{_slugish(student_name)}_"
        f"{_format_seat_number(seat_number)}_"
        f"{_format_mobile_number(mobile_number)}"
    )

    existing_names = set()
    if photo_dir and os.path.isdir(photo_dir):
        existing_names = {name.lower() for name in os.listdir(photo_dir)}

    def _stem_exists(candidate_stem: str) -> bool:
        if not photo_dir:
            return False
        if existing_names:
            return any(
                f"{candidate_stem}{candidate_ext}".lower() in existing_names
                or f"{candidate_stem}_thumb{candidate_ext}".lower() in existing_names
                for candidate_ext in ALLOWED_EXTS
            )
        return any(
            os.path.exists(os.path.join(photo_dir, f"{candidate_stem}{candidate_ext}"))
            or os.path.exists(
                os.path.join(photo_dir, f"{candidate_stem}_thumb{candidate_ext}")
            )
            for candidate_ext in ALLOWED_EXTS
        )

    version = 1
    while True:
        suffix = "" if version == 1 else f"_{version:02d}"
        versioned_stem = f"{stem}{suffix}"
        full_name = f"{versioned_stem}{ext}"
        thumb_name = f"{versioned_stem}_thumb{ext}"

        if not photo_dir or not _stem_exists(versioned_stem):
            return full_name, thumb_name

        version += 1


def sanitize_relpath(path: str) -> str:
    # prevent weird paths; keep basename
    path = path or ""
    return os.path.basename(path)

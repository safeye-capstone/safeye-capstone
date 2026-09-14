"""로컬 VLM 노드에서 사용하는 이미지 검증 및 축소 유틸리티.

이미지 파일의 존재 여부와 확장자를 검증하고,
업로드 이미지가 너무 큰 경우 VLM의 vision token 및 VRAM 사용량을
줄이기 위해 로컬 노드에서 미리 축소한다.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image


SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


def validate_image(image_path: str | Path) -> Path:
    """이미지 파일 존재 여부와 확장자를 검사한다."""

    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {path}")

    if not path.is_file():
        raise ValueError(f"파일이 아닙니다: {path}")

    if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(f"지원하지 않는 이미지 형식입니다: {path.suffix}")

    return path.resolve()


def clamp(
    raw: bytes,
    max_edge: int,
    quality: int = 88,
) -> tuple[bytes, dict]:
    """이미지의 긴 변이 max_edge를 넘으면 JPEG로 축소한다."""

    img = Image.open(io.BytesIO(raw))
    ow, oh = img.size

    if max(ow, oh) <= max_edge and img.mode == "RGB":
        return raw, {
            "w": ow,
            "h": oh,
            "orig_w": ow,
            "orig_h": oh,
            "resized": False,
            "bytes": len(raw),
        }

    if img.mode != "RGB":
        img = img.convert("RGB")

    if max(ow, oh) > max_edge:
        scale = max_edge / max(ow, oh)
        img = img.resize(
            (
                max(1, int(ow * scale)),
                max(1, int(oh * scale)),
            ),
            Image.LANCZOS,
        )

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    out = buf.getvalue()

    return out, {
        "w": img.size[0],
        "h": img.size[1],
        "orig_w": ow,
        "orig_h": oh,
        "resized": True,
        "bytes": len(out),
    }


def to_edge(
    raw: bytes,
    edge: int,
    quality: int = 88,
) -> bytes:
    """벤치마크용 이미지 리사이즈."""

    img = Image.open(io.BytesIO(raw))

    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    scale = edge / max(w, h)

    if scale < 1:
        img = img.resize(
            (
                max(1, int(w * scale)),
                max(1, int(h * scale)),
            ),
            Image.LANCZOS,
        )

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)

    return buf.getvalue()


def dims(raw: bytes) -> tuple[int, int]:
    """이미지 bytes에서 원본 이미지 크기를 반환한다."""

    with Image.open(io.BytesIO(raw)) as img:
        return img.size
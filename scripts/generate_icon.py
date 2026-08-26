"""
아이콘 생성 스크립트.
Pillow만으로 Rookery 아이콘(.png, .ico)을 생성한다.
사용법: python scripts/generate_icon.py
"""
from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow가 필요합니다: pip install Pillow")
    raise

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
ASSET_DIR.mkdir(exist_ok=True)


def create_icon(size: int = 512) -> Image.Image:
    """Rookery 앱 아이콘을 생성한다."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── 배경: 둥근 사각형 (다크 네이비) ─────────────────────
    radius = size // 8
    bg_color = (18, 24, 56)           # 다크 네이비
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=bg_color)

    # ── 그라데이션 오버레이 (인디고 → 퍼플 느낌) ─────────────
    for i in range(size // 2):
        alpha = int(30 * (1 - i / (size // 2)))
        overlay_color = (99, 102, 241, alpha)  # 인디고
        draw.ellipse(
            [size // 4 - i // 4, -i // 2, size * 3 // 4 + i // 4, size // 2],
            fill=overlay_color,
        )

    # ── 동심원 (녹화 버튼 스타일) ────────────────────────────
    cx, cy = size // 2, size // 2
    # 바깥 원 (반투명 흰색)
    outer_r = int(size * 0.38)
    draw.ellipse(
        [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
        outline=(255, 255, 255, 60),
        width=max(2, size // 80),
    )
    # 중간 원 (인디고)
    mid_r = int(size * 0.28)
    draw.ellipse(
        [cx - mid_r, cy - mid_r, cx + mid_r, cy + mid_r],
        fill=(79, 70, 229),   # 인디고-600
    )
    # REC 빨간 점
    dot_r = int(size * 0.15)
    draw.ellipse(
        [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
        fill=(239, 68, 68),   # 레드-500
    )
    # 중앙 흰 점 (광택)
    shine_r = int(size * 0.05)
    shine_offset = int(size * 0.05)
    draw.ellipse(
        [
            cx - shine_offset - shine_r,
            cy - shine_offset - shine_r,
            cx - shine_offset + shine_r,
            cy - shine_offset + shine_r,
        ],
        fill=(255, 255, 255, 180),
    )

    # ── REC 텍스트 ────────────────────────────────────────────
    text = "REC"
    font_size = max(20, size // 12)
    text_color = (255, 255, 255, 200)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    text_y = cy + int(size * 0.32)
    draw.text((cx - tw // 2, text_y - th // 2), text, font=font, fill=text_color)

    return img


def main() -> None:
    img = create_icon(512)

    # PNG 저장
    png_path = ASSET_DIR / "icon.png"
    img.save(png_path, "PNG")
    print(f"✅ icon.png 생성: {png_path}")

    # ICO 저장 (여러 해상도 포함)
    ico_path = ASSET_DIR / "icon.ico"
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icons = [img.resize(s, Image.LANCZOS) for s in sizes]
    icons[0].save(
        ico_path,
        format="ICO",
        sizes=[(s[0], s[1]) for s in sizes],
        append_images=icons[1:],
    )
    print(f"✅ icon.ico 생성: {ico_path}")


if __name__ == "__main__":
    main()

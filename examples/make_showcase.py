"""Build the README comparison graphic from the shared example assets."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
BACKGROUND = "#14161d"
PANEL = "#1e2030"
BORDER = "#383b49"
TEXT = "#f0f1f5"
MUTED = "#989dab"
ACCENTS = ("#e3cf62", "#df7768", "#8ccfab", "#86b9d7")


def find_font(size, bold=False):
    names = (
        "ComicMono-Bold.ttf" if bold else "ComicMono.ttf",
        "MapleMono-NF-Bold.ttf" if bold else "MapleMono-NF-Regular.ttf",
    )
    for name in names:
        path = Path.home() / "Library/Fonts" / name
        if path.exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def contain(image, size):
    result = Image.new("RGB", size, PANEL)
    fitted = image.convert("RGB")
    fitted.thumbnail(size, Image.Resampling.LANCZOS)
    offset = ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2)
    result.paste(fitted, offset)
    return result


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    sources = (
        ("SOURCE", "shinku02.jpg reference", ASSETS / "shinku02.jpg"),
        ("BLOCK MODE", "Solid Unicode half-block color", DOCS / "example-render.png"),
        ("GLYPH MODE", "Font-matched structural output", DOCS / "example-glyph-render.png"),
        ("BEAD MODE", "Physical fuse-bead preview", DOCS / "example-bead-render.png"),
    )
    canvas = Image.new("RGB", (2100, 650), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    title_font = find_font(27, bold=True)
    label_font = find_font(19, bold=True)
    detail_font = find_font(14)
    draw.text((64, 35), "ONE SOURCE / THREE VISUAL SYSTEMS", fill=TEXT, font=title_font)
    draw.text(
        (64, 76),
        "Terminal blocks, matched glyphs, and physical fuse-bead patterns share one rendering contract.",
        fill=MUTED,
        font=detail_font,
    )

    panel_width = 464
    image_size = (420, 420)
    for index, (label, detail, path) in enumerate(sources):
        x = 64 + index * (panel_width + 38)
        y = 120
        draw.rounded_rectangle(
            (x, y, x + panel_width, y + 500),
            radius=8,
            fill=PANEL,
            outline=BORDER,
            width=2,
        )
        image = contain(Image.open(path), image_size)
        canvas.paste(image, (x + 22, y + 18))
        draw.rectangle((x + 22, y + 450, x + 76, y + 456), fill=ACCENTS[index])
        draw.text((x + 22, y + 466), label, fill=TEXT, font=label_font)
        detail_width = draw.textlength(detail, font=detail_font)
        draw.text(
            (x + panel_width - 22 - detail_width, y + 472),
            detail,
            fill=MUTED,
            font=detail_font,
        )

    canvas.save(ASSETS / "showcase.png", optimize=True)


if __name__ == "__main__":
    main()

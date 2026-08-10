#!/usr/bin/env python3

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser(description="Create the synthetic EdgeGlyph example image")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    image = Image.new("RGB", (512, 512), "white")
    draw = ImageDraw.Draw(image)

    outline = "#6f3545"
    hair = "#f3d36d"
    hair_shadow = "#e99b83"
    skin = "#ffe6c7"
    eye = "#d95d73"

    draw.ellipse((36, 80, 190, 430), fill=hair, outline=outline, width=6)
    draw.ellipse((322, 80, 476, 430), fill=hair, outline=outline, width=6)
    draw.polygon([(95, 120), (152, 70), (256, 35), (360, 70), (417, 120), (380, 350), (132, 350)], fill=hair, outline=outline)
    draw.ellipse((132, 118, 380, 395), fill=skin, outline=outline, width=7)
    draw.polygon([(128, 140), (182, 72), (232, 58), (202, 245), (258, 106), (268, 262), (325, 80), (388, 145), (348, 190), (304, 126), (280, 286), (224, 204), (184, 282)], fill=hair, outline=outline)
    draw.line((104, 132, 120, 354), fill=hair_shadow, width=13)
    draw.line((408, 132, 392, 354), fill=hair_shadow, width=13)

    draw.ellipse((165, 224, 228, 306), fill=eye, outline=outline, width=5)
    draw.ellipse((284, 224, 347, 306), fill=eye, outline=outline, width=5)
    draw.ellipse((178, 234, 198, 258), fill="white")
    draw.ellipse((297, 234, 317, 258), fill="white")
    draw.arc((222, 278, 290, 335), 18, 162, fill=outline, width=5)

    draw.rounded_rectangle((225, 335, 287, 390), radius=18, fill="#e6a853", outline=outline, width=5)
    draw.ellipse((270, 352, 340, 447), fill=skin, outline=outline, width=6)
    draw.line((293, 370, 319, 416), fill=outline, width=5)
    draw.line((309, 367, 332, 398), fill=outline, width=5)

    draw.polygon([(70, 360), (91, 390), (127, 382), (106, 411), (121, 447), (87, 433), (58, 457), (62, 420), (31, 400), (68, 397)], fill="#f6d86e", outline=outline)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)


if __name__ == "__main__":
    main()

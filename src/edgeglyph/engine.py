#!/usr/bin/env python3

import collections
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


BG = (30, 30, 46)
UNICODE_LINES = "─│╱╲╭╮╰╯┌┐└┘├┤┬┴┼"
CHARACTERS = (
    " .,:;~-=+*#%@$&!?/\\|_()[]{}<>0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    + UNICODE_LINES
)
STRUCTURE_CHARACTERS = set(" .,:;-_=+*/\\|()[]{}<>!?LJTYXVC" + UNICODE_LINES)
TONE_RAMP = " .,:;irsXA253hMHGS#9B&@"
TONE_CHARACTERS = set(TONE_RAMP)
TONE_POSITION = {
    character: index / (len(TONE_RAMP) - 1) for index, character in enumerate(TONE_RAMP)
}
BAYER_4 = (
    np.array(
        [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32
    )
    / 16.0
)


@dataclass(frozen=True)
class RenderConfig:
    cols: int = 56
    rows: int = 28
    colors: int = 16
    top_k: int = 8
    minimum_luminance: float = 0.72
    fill_mode: str = "none"
    continuity: float = 0.4
    diversity: float = 1.5
    line_renderer: str = "sprite"
    cell_width: int = 11
    cell_height: int = 22
    font_size: int = 18


@dataclass(frozen=True)
class BlockConfig:
    cols: int = 56
    rows: int = 28
    foreground: str = "#cba6f7"
    subject_threshold: float = 0.34
    ink_threshold: float = 0.46
    detail: float = 1.0
    oversample: int = 6
    fit: str = "cover"
    focus_y: float = 0.36
    cell_width: int = 11
    cell_height: int = 22


@dataclass
class RenderResult:
    glyphs: list
    selected: np.ndarray
    palette: np.ndarray
    color_indices: list
    source: dict
    metrics: dict
    config: Union[RenderConfig, BlockConfig]

    @property
    def lines(self):
        return [
            "".join(
                self.glyphs[int(self.selected[y, x])]["character"]
                for x in range(self.config.cols)
            )
            for y in range(self.config.rows)
        ]


def convolve3(image, kernel):
    padded = np.pad(image, ((1, 1), (1, 1)), mode="edge")
    windows = np.lib.stride_tricks.sliding_window_view(padded, (3, 3))
    return np.einsum("ijkl,kl->ij", windows, kernel, optimize=True)


def gradients(image):
    scharr_x = np.array([[-3, 0, 3], [-10, 0, 10], [-3, 0, 3]], dtype=np.float32) / 16.0
    scharr_y = scharr_x.T
    return convolve3(image, scharr_x), convolve3(image, scharr_y)


def nonmaximum_suppression(magnitude, gx, gy):
    angle = (np.rad2deg(np.arctan2(gy, gx)) + 180.0) % 180.0
    result = np.zeros_like(magnitude)

    left = np.roll(magnitude, 1, axis=1)
    right = np.roll(magnitude, -1, axis=1)
    up = np.roll(magnitude, 1, axis=0)
    down = np.roll(magnitude, -1, axis=0)
    up_left = np.roll(up, 1, axis=1)
    up_right = np.roll(up, -1, axis=1)
    down_left = np.roll(down, 1, axis=1)
    down_right = np.roll(down, -1, axis=1)

    directions = (
        ((angle < 22.5) | (angle >= 157.5), left, right),
        (((angle >= 22.5) & (angle < 67.5)), up_right, down_left),
        (((angle >= 67.5) & (angle < 112.5)), up, down),
        (((angle >= 112.5) & (angle < 157.5)), up_left, down_right),
    )
    for selection, before, after in directions:
        keep = selection & (magnitude >= before) & (magnitude >= after)
        result[keep] = magnitude[keep]

    result[[0, -1], :] = 0
    result[:, [0, -1]] = 0
    return result


def hysteresis(edge, low, high):
    strong = edge >= high
    weak = edge >= low
    connected = strong.copy()
    for _ in range(12):
        neighborhood = np.zeros_like(connected)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx or dy:
                    neighborhood |= np.roll(np.roll(connected, dy, axis=0), dx, axis=1)
        updated = strong | (weak & neighborhood)
        if np.array_equal(updated, connected):
            break
        connected = updated
    return connected


def flood_background(rgb):
    near_white = np.min(rgb, axis=2) > 0.94
    height, width = near_white.shape
    visited = np.zeros_like(near_white)
    queue = collections.deque()

    for x in range(width):
        if near_white[0, x]:
            queue.append((0, x))
        if near_white[-1, x]:
            queue.append((height - 1, x))
    for y in range(height):
        if near_white[y, 0]:
            queue.append((y, 0))
        if near_white[y, -1]:
            queue.append((y, width - 1))

    while queue:
        y, x = queue.popleft()
        if visited[y, x] or not near_white[y, x]:
            continue
        visited[y, x] = True
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width and not visited[ny, nx]:
                queue.append((ny, nx))
    return visited


def parse_hex_color(value):
    value = value.strip().removeprefix("#")
    if len(value) != 6:
        raise ValueError("foreground color must use #RRGGBB format")
    try:
        channels = [int(value[index : index + 2], 16) / 255.0 for index in (0, 2, 4)]
    except ValueError as error:
        raise ValueError("foreground color must use #RRGGBB format") from error
    return np.asarray(channels, dtype=np.float32)


def pool_blocks(values, rows, cols, oversample, reducer="mean"):
    expected = (rows * oversample, cols * oversample)
    if values.shape != expected:
        raise ValueError(f"expected source grid {expected}, got {values.shape}")
    blocks = values.reshape(rows, oversample, cols, oversample).transpose(0, 2, 1, 3)
    if reducer == "mean":
        return blocks.mean(axis=(2, 3))
    if reducer == "max":
        return blocks.max(axis=(2, 3))
    raise ValueError(f"unsupported block reducer: {reducer}")


def cleanup_components(mask, minimum_size=2):
    result = mask.copy()
    seen = np.zeros_like(mask, dtype=bool)
    height, width = mask.shape
    for start_y in range(height):
        for start_x in range(width):
            if seen[start_y, start_x] or not mask[start_y, start_x]:
                continue
            queue = collections.deque([(start_y, start_x)])
            seen[start_y, start_x] = True
            component = []
            while queue:
                y, x = queue.popleft()
                component.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if (
                            (dx or dy)
                            and 0 <= ny < height
                            and 0 <= nx < width
                            and mask[ny, nx]
                            and not seen[ny, nx]
                        ):
                            seen[ny, nx] = True
                            queue.append((ny, nx))
            if len(component) < minimum_size:
                for y, x in component:
                    result[y, x] = False
    return result


def block_glyphs(cell_width=11, cell_height=22):
    top = np.zeros((cell_height, cell_width), dtype=np.float32)
    top[: cell_height // 2] = 1.0
    bottom = np.zeros_like(top)
    bottom[cell_height // 2 :] = 1.0
    masks = (np.zeros_like(top), top, bottom, np.ones_like(top))
    characters = (" ", "▀", "▄", "█")
    return [
        {
            "character": character,
            "font_path": None,
            "sprite": True,
            "mask": mask,
            "ink": mask,
            "skeleton": mask > 0.5,
        }
        for character, mask in zip(characters, masks)
    ]


def prepare_block_source(source_path, config):
    pixel_rows = config.rows * 2
    working_size = (config.cols * config.oversample, pixel_rows * config.oversample)
    original = Image.open(source_path).convert("RGBA")
    if config.fit == "cover":
        fitted = ImageOps.fit(
            original,
            working_size,
            Image.Resampling.LANCZOS,
            centering=(0.5, config.focus_y),
        )
    elif config.fit == "contain":
        fitted = ImageOps.contain(original, working_size, Image.Resampling.LANCZOS)
    else:
        raise ValueError(f"unsupported block fit: {config.fit}")
    canvas = Image.new("RGBA", working_size, (255, 255, 255, 0))
    offset = (
        (working_size[0] - fitted.width) // 2,
        (working_size[1] - fitted.height) // 2,
    )
    canvas.alpha_composite(fitted, offset)

    alpha = np.asarray(canvas, dtype=np.float32)[:, :, 3] / 255.0
    flattened = Image.new("RGB", working_size, "white")
    flattened.paste(canvas.convert("RGB"), mask=canvas.getchannel("A"))
    rgb = np.asarray(flattened, dtype=np.float32) / 255.0
    background = flood_background(rgb) | (alpha < 0.02)
    subject = ~background

    softened = (
        np.asarray(flattened.filter(ImageFilter.GaussianBlur(0.55)), dtype=np.float32)
        / 255.0
    )
    luminance = (
        0.2126 * softened[:, :, 0]
        + 0.7152 * softened[:, :, 1]
        + 0.0722 * softened[:, :, 2]
    )
    local_luminance = (
        np.asarray(
            Image.fromarray(np.uint8(np.clip(luminance, 0, 1) * 255)).filter(
                ImageFilter.GaussianBlur(max(1.0, config.oversample * 0.55))
            ),
            dtype=np.float32,
        )
        / 255.0
    )
    darkness = np.clip(1.0 - luminance, 0, 1)
    local_contrast = np.clip(local_luminance - luminance, 0, 1)
    saturation = softened.max(axis=2) - softened.min(axis=2)
    ink_score = np.clip(
        darkness * 0.74 + local_contrast * (1.35 * config.detail) + saturation * 0.06,
        0,
        1,
    )
    ink_score *= subject

    subject_coverage = pool_blocks(
        subject.astype(np.float32), pixel_rows, config.cols, config.oversample, "mean"
    )
    ink_peak = pool_blocks(ink_score, pixel_rows, config.cols, config.oversample, "max")
    ink_coverage = pool_blocks(
        (ink_score >= config.ink_threshold).astype(np.float32),
        pixel_rows,
        config.cols,
        config.oversample,
        "mean",
    )

    silhouette = subject_coverage >= config.subject_threshold
    interior = subject_coverage >= max(0.56, config.subject_threshold + 0.16)
    carved = interior & (
        (ink_peak >= config.ink_threshold + 0.08)
        | ((ink_peak >= config.ink_threshold) & (ink_coverage >= 0.035))
    )
    pixels = cleanup_components(silhouette & ~carved, minimum_size=2)

    return {
        "image": flattened,
        "rgb": rgb,
        "background": background,
        "subject": subject.astype(np.float32),
        "subject_coverage": subject_coverage,
        "ink_score": ink_score,
        "ink_peak": ink_peak,
        "carved": carved,
        "block_pixels": pixels,
    }


def thin(binary):
    image = binary.astype(np.uint8).copy()
    changed = True
    iterations = 0
    while changed and iterations < 24:
        changed = False
        iterations += 1
        for phase in (0, 1):
            padded = np.pad(image, 1)
            p2 = padded[:-2, 1:-1]
            p3 = padded[:-2, 2:]
            p4 = padded[1:-1, 2:]
            p5 = padded[2:, 2:]
            p6 = padded[2:, 1:-1]
            p7 = padded[2:, :-2]
            p8 = padded[1:-1, :-2]
            p9 = padded[:-2, :-2]
            neighbors = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
            transitions = (
                ((p2 == 0) & (p3 == 1)).astype(np.uint8)
                + ((p3 == 0) & (p4 == 1))
                + ((p4 == 0) & (p5 == 1))
                + ((p5 == 0) & (p6 == 1))
                + ((p6 == 0) & (p7 == 1))
                + ((p7 == 0) & (p8 == 1))
                + ((p8 == 0) & (p9 == 1))
                + ((p9 == 0) & (p2 == 1))
            )
            if phase == 0:
                preserve_a = (p2 * p4 * p6) == 0
                preserve_b = (p4 * p6 * p8) == 0
            else:
                preserve_a = (p2 * p4 * p8) == 0
                preserve_b = (p2 * p6 * p8) == 0
            remove = (
                (image == 1)
                & (neighbors >= 2)
                & (neighbors <= 6)
                & (transitions == 1)
                & preserve_a
                & preserve_b
            )
            if np.any(remove):
                image[remove] = 0
                changed = True
    return image.astype(bool)


def skeleton_orientations(skeleton, bins=8):
    height, width = skeleton.shape
    result = np.zeros((height, width), dtype=np.int8)
    points = np.argwhere(skeleton)
    for y, x in points:
        y0, y1 = max(0, y - 2), min(height, y + 3)
        x0, x1 = max(0, x - 2), min(width, x + 3)
        local = np.argwhere(skeleton[y0:y1, x0:x1])
        if len(local) < 2:
            continue
        local = local.astype(np.float32)
        local[:, 0] += y0 - y
        local[:, 1] += x0 - x
        covariance = local.T @ local
        values, vectors = np.linalg.eigh(covariance)
        direction = vectors[:, np.argmax(values)]
        angle = math.atan2(direction[0], direction[1]) % math.pi
        result[y, x] = int(round(angle / math.pi * bins)) % bins
    return result


def distance_and_nearest_orientation(mask, orientations):
    height, width = mask.shape
    points = np.argwhere(mask)
    if not len(points):
        return np.full(
            (height, width), math.hypot(height, width), dtype=np.float32
        ), np.zeros((height, width), dtype=np.int8)
    yy, xx = np.indices((height, width))
    dy = yy[..., None] - points[:, 0]
    dx = xx[..., None] - points[:, 1]
    distance_squared = dy * dy + dx * dx
    nearest = np.argmin(distance_squared, axis=2)
    distance = np.sqrt(
        np.take_along_axis(distance_squared, nearest[..., None], axis=2)[..., 0]
    )
    nearest_orientation = orientations[points[nearest, 0], points[nearest, 1]]
    return distance.astype(np.float32), nearest_orientation.astype(np.int8)


def chamfer_distance(mask):
    height, width = mask.shape
    diagonal = math.sqrt(2)
    distance = np.full((height, width), height + width, dtype=np.float32)
    distance[mask] = 0
    for y in range(height):
        for x in range(width):
            value = distance[y, x]
            if y > 0:
                value = min(value, distance[y - 1, x] + 1)
                if x > 0:
                    value = min(value, distance[y - 1, x - 1] + diagonal)
                if x + 1 < width:
                    value = min(value, distance[y - 1, x + 1] + diagonal)
            if x > 0:
                value = min(value, distance[y, x - 1] + 1)
            distance[y, x] = value
    for y in range(height - 1, -1, -1):
        for x in range(width - 1, -1, -1):
            value = distance[y, x]
            if y + 1 < height:
                value = min(value, distance[y + 1, x] + 1)
                if x > 0:
                    value = min(value, distance[y + 1, x - 1] + diagonal)
                if x + 1 < width:
                    value = min(value, distance[y + 1, x + 1] + diagonal)
            if x + 1 < width:
                value = min(value, distance[y, x + 1] + 1)
            distance[y, x] = value
    return distance


def circular_bin_distance(left, right, bins=8):
    difference = np.abs(left.astype(np.int16) - right.astype(np.int16))
    return np.minimum(difference, bins - difference).astype(np.float32) / (bins / 2)


def render_line_sprite(character, cell_width, cell_height, scale=4):
    width, height = cell_width * scale, cell_height * scale
    center_x, center_y = width / 2, height / 2
    stroke = max(3, scale)
    canvas = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(canvas)

    endpoints = {
        "N": (center_x, -stroke),
        "E": (width + stroke, center_y),
        "S": (center_x, height + stroke),
        "W": (-stroke, center_y),
    }
    straight = {
        "─": "WE",
        "│": "NS",
        "┌": "ES",
        "┐": "WS",
        "└": "NE",
        "┘": "NW",
        "├": "NES",
        "┤": "NWS",
        "┬": "WES",
        "┴": "WEN",
        "┼": "NWES",
    }
    if character in straight:
        for direction in straight[character]:
            draw.line(
                (center_x, center_y, *endpoints[direction]), fill=255, width=stroke
            )
    elif character == "╱":
        draw.line(
            (-stroke, height + stroke, width + stroke, -stroke), fill=255, width=stroke
        )
    elif character == "╲":
        draw.line(
            (-stroke, -stroke, width + stroke, height + stroke), fill=255, width=stroke
        )
    else:
        curves = {
            "╭": (endpoints["E"], endpoints["S"]),
            "╮": (endpoints["W"], endpoints["S"]),
            "╰": (endpoints["N"], endpoints["E"]),
            "╯": (endpoints["N"], endpoints["W"]),
        }
        start, end = curves[character]
        points = []
        for step in range(25):
            t = step / 24
            x = (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * center_x + t**2 * end[0]
            y = (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * center_y + t**2 * end[1]
            points.append((x, y))
        draw.line(points, fill=255, width=stroke, joint="curve")

    return (
        np.asarray(
            canvas.resize((cell_width, cell_height), Image.Resampling.LANCZOS),
            dtype=np.float32,
        )
        / 255
    )


def render_glyphs(
    font_path,
    fallback_font_path,
    font_size,
    cell_width,
    cell_height,
    line_renderer="sprite",
):
    font = ImageFont.truetype(str(font_path), font_size)
    fallback_font_path = fallback_font_path or font_path
    glyphs = []
    for character in CHARACTERS:
        is_sprite = character in UNICODE_LINES and line_renderer == "sprite"
        glyph_font_path = (
            None
            if is_sprite
            else (fallback_font_path if ord(character) > 127 else font_path)
        )
        if is_sprite:
            mask = render_line_sprite(character, cell_width, cell_height)
        else:
            canvas = Image.new("L", (cell_width * 4, cell_height * 4), 0)
            draw = ImageDraw.Draw(canvas)
            scaled_font = ImageFont.truetype(str(glyph_font_path), font_size * 4)
            bounds = draw.textbbox((0, 0), character, font=scaled_font)
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            x = (canvas.width - width) / 2 - bounds[0]
            y = (canvas.height - height) / 2 - bounds[1]
            draw.text((x, y), character, font=scaled_font, fill=255)
            mask = (
                np.asarray(
                    canvas.resize((cell_width, cell_height), Image.Resampling.LANCZOS),
                    dtype=np.float32,
                )
                / 255
            )
        ink = mask > 0.18
        skeleton = thin(mask > 0.38) if character != " " else np.zeros_like(ink)
        orientation = skeleton_orientations(skeleton)
        distance, nearest_orientation = distance_and_nearest_orientation(
            skeleton, orientation
        )
        glyphs.append(
            {
                "character": character,
                "font_path": glyph_font_path,
                "sprite": is_sprite,
                "mask": mask,
                "ink": ink,
                "skeleton": skeleton,
                "orientation": orientation,
                "distance": distance,
                "nearest_orientation": nearest_orientation,
                "density": float(mask.mean()),
                "left": skeleton[:, : max(2, cell_width // 3)]
                .max(axis=1)
                .astype(np.float32),
                "right": skeleton[:, -max(2, cell_width // 3) :]
                .max(axis=1)
                .astype(np.float32),
                "top": skeleton[: max(3, cell_height // 3), :]
                .max(axis=0)
                .astype(np.float32),
                "bottom": skeleton[-max(3, cell_height // 3) :, :]
                .max(axis=0)
                .astype(np.float32),
            }
        )
    return font, glyphs


def prepare_source(source_path, cols, rows, cell_width, cell_height):
    size = (cols * cell_width, rows * cell_height)
    original = Image.open(source_path).convert("RGBA")
    fitted = ImageOps.contain(original, size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (255, 255, 255, 0))
    offset = ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2)
    canvas.alpha_composite(fitted, offset)
    alpha = np.asarray(canvas, dtype=np.float32)[:, :, 3] / 255.0
    flattened = Image.new("RGB", size, "white")
    flattened.paste(canvas.convert("RGB"), mask=canvas.getchannel("A"))
    image = flattened
    rgb = np.asarray(image, dtype=np.float32) / 255.0
    background = flood_background(rgb) | (alpha < 0.02)
    subject = (~background).astype(np.float32)

    blurred = (
        np.asarray(image.filter(ImageFilter.GaussianBlur(0.85)), dtype=np.float32)
        / 255.0
    )
    luminance = (
        0.2126 * blurred[:, :, 0]
        + 0.7152 * blurred[:, :, 1]
        + 0.0722 * blurred[:, :, 2]
    )
    gx_l, gy_l = gradients(luminance)
    channel_gradients = [gradients(blurred[:, :, channel]) for channel in range(3)]
    channel_magnitudes = [np.hypot(gx, gy) for gx, gy in channel_gradients]
    strongest = np.argmax(np.stack(channel_magnitudes, axis=2), axis=2)
    gx_c = np.choose(strongest, [item[0] for item in channel_gradients])
    gy_c = np.choose(strongest, [item[1] for item in channel_gradients])
    magnitude_l = np.hypot(gx_l, gy_l)
    magnitude_c = np.hypot(gx_c, gy_c)
    use_color = magnitude_c > magnitude_l * 1.15
    gx = np.where(use_color, gx_c, gx_l)
    gy = np.where(use_color, gy_c, gy_l)
    magnitude = np.maximum(magnitude_l, magnitude_c * 0.82)

    nms = nonmaximum_suppression(magnitude, gx, gy)
    positive = nms[nms > 0]
    scale = np.percentile(positive, 96) if len(positive) else 1.0
    strength = np.clip(nms / max(scale, 1e-6), 0, 1)
    nonzero_strength = strength[strength > 0]
    if len(nonzero_strength):
        low = max(0.055, float(np.percentile(nonzero_strength, 35)))
        high = max(0.14, float(np.percentile(nonzero_strength, 68)))
        edges = hysteresis(strength, low, high)
    else:
        edges = np.zeros_like(strength, dtype=bool)
    strength *= edges

    tangent = (np.arctan2(gy, gx) + math.pi / 2) % math.pi
    orientation = (np.rint(tangent / math.pi * 8).astype(np.int8)) % 8
    darkness = np.clip(1.0 - luminance, 0, 1) * subject
    saturation = (blurred.max(axis=2) - blurred.min(axis=2)) * subject
    importance = np.clip(strength * 0.70 + darkness * 0.18 + saturation * 0.12, 0, 1)

    return {
        "image": image,
        "rgb": rgb,
        "background": background,
        "subject": subject,
        "luminance": luminance,
        "darkness": darkness,
        "saturation": saturation,
        "edge": edges,
        "strength": strength,
        "orientation": orientation,
        "importance": importance,
    }


def local_candidates(
    source, glyphs, cols, rows, cell_width, cell_height, top_k, fill_mode
):
    choices = [[None for _ in range(cols)] for _ in range(rows)]
    local_scores = [[None for _ in range(cols)] for _ in range(rows)]

    for row in range(rows):
        for col in range(cols):
            y0, y1 = row * cell_height, (row + 1) * cell_height
            x0, x1 = col * cell_width, (col + 1) * cell_width
            edge_strength = source["strength"][y0:y1, x0:x1]
            edge = source["edge"][y0:y1, x0:x1]
            orientation = source["orientation"][y0:y1, x0:x1]
            background_fraction = float(source["background"][y0:y1, x0:x1].mean())
            subject_fraction = 1.0 - background_fraction
            darkness = float(source["darkness"][y0:y1, x0:x1].mean())
            saturation = float(source["saturation"][y0:y1, x0:x1].mean())
            edge_mass = float(edge_strength.sum())
            edge_pixels = int(edge.sum())
            tone_strength = subject_fraction * np.clip(
                darkness * 1.25 + saturation * 0.72, 0, 1
            )
            dither_threshold = float(BAYER_4[row % 4, col % 4])

            if background_fraction > 0.985 and edge_mass < 0.15:
                choices[row][col] = np.array([0], dtype=np.int16)
                local_scores[row][col] = np.array([0.0], dtype=np.float32)
                continue

            source_distance, source_nearest_orientation = (
                distance_and_nearest_orientation(edge, orientation)
            )
            desired_density = np.clip(
                0.012
                + edge_strength.mean() * 0.78
                + darkness * 0.19
                + saturation * 0.07,
                0,
                0.46,
            )
            structural_cell = edge_pixels >= 2 and edge_mass >= 0.12
            if structural_cell:
                pool = [
                    index
                    for index, glyph in enumerate(glyphs)
                    if glyph["character"] in STRUCTURE_CHARACTERS
                ]
            elif (
                fill_mode == "tone"
                and tone_strength > 0.08
                and dither_threshold < min(0.92, tone_strength * 2.7 + 0.12)
            ) or (
                fill_mode == "salient"
                and ((darkness > 0.20 and saturation > 0.18) or darkness > 0.42)
                and dither_threshold < min(0.58, tone_strength * 0.72)
            ):
                pool = [
                    index
                    for index, glyph in enumerate(glyphs)
                    if glyph["character"] in TONE_CHARACTERS
                ]
            else:
                pool = [0]

            scores = np.full(len(glyphs), np.inf, dtype=np.float32)
            for index in pool:
                glyph = glyphs[index]
                if index == 0:
                    blank_score = edge_mass * 0.48 + tone_strength * 1.25
                    scores[index] = blank_score
                    continue

                if not structural_cell:
                    ramp_target = np.clip(
                        tone_strength * 0.84 + (0.5 - dither_threshold) * 0.22,
                        0,
                        1,
                    )
                    density_target = np.clip(tone_strength * 0.34, 0.008, 0.34)
                    density_score = abs(glyph["density"] - density_target) * 1.9
                    ramp_score = (
                        abs(TONE_POSITION[glyph["character"]] - ramp_target) * 2.8
                    )
                    scores[index] = density_score + ramp_score
                    continue

                glyph_edge = glyph["skeleton"]
                glyph_mass = max(1.0, float(glyph_edge.sum()))
                if edge_mass > 0:
                    orientation_cost = circular_bin_distance(
                        orientation, glyph["nearest_orientation"]
                    )
                    source_to_glyph = float(
                        np.sum(
                            edge_strength
                            * (glyph["distance"] + orientation_cost * 0.85)
                        )
                        / edge_mass
                    )
                else:
                    source_to_glyph = glyph_mass * 0.25

                reverse_orientation_cost = circular_bin_distance(
                    glyph["orientation"], source_nearest_orientation
                )
                glyph_to_source = float(
                    np.sum(
                        glyph_edge * (source_distance + reverse_orientation_cost * 0.85)
                    )
                    / glyph_mass
                )
                tone = abs(glyph["density"] - desired_density)
                occupancy = abs(
                    float(glyph["ink"].mean()) - min(0.55, subject_fraction * 0.45)
                )
                complexity = glyph_mass / (cell_width * cell_height)
                complexity_penalty = max(
                    0.0, complexity - (0.06 + edge_strength.mean() * 0.8)
                )

                score = (
                    source_to_glyph * 0.53
                    + glyph_to_source * 0.34
                    + tone * 2.25
                    + occupancy * 0.18
                    + complexity_penalty * 0.22
                )
                if glyph["character"] not in STRUCTURE_CHARACTERS:
                    score += 0.10
                scores[index] = score

            finite = np.flatnonzero(np.isfinite(scores))
            count = min(top_k, len(finite))
            selected = finite[np.argpartition(scores[finite], count - 1)[:count]]
            selected = selected[np.argsort(scores[selected])]
            choices[row][col] = selected.astype(np.int16)
            local_scores[row][col] = scores[selected]
    return choices, local_scores


def pair_cost(left, right, direction):
    if direction == "horizontal":
        return float(np.mean(np.abs(left["right"] - right["left"])))
    return float(np.mean(np.abs(left["bottom"] - right["top"])))


def optimize_grid(
    source,
    glyphs,
    choices,
    local_scores,
    cols,
    rows,
    cell_width,
    cell_height,
    continuity,
    diversity,
):
    selected = np.array(
        [[int(choices[y][x][0]) for x in range(cols)] for y in range(rows)]
    )

    for iteration in range(5):
        changes = 0
        usage = np.bincount(selected.ravel(), minlength=len(glyphs)).astype(np.float32)
        nonblank = max(1.0, float(usage[1:].sum()))
        traversal = range(rows) if iteration % 2 == 0 else range(rows - 1, -1, -1)
        for row in traversal:
            horizontal = range(cols) if iteration % 2 == 0 else range(cols - 1, -1, -1)
            for col in horizontal:
                candidates = choices[row][col]
                scores = local_scores[row][col].copy()
                for position, candidate in enumerate(candidates):
                    glyph = glyphs[int(candidate)]
                    if candidate != 0:
                        frequency = usage[int(candidate)] / nonblank
                        scores[position] += diversity * max(0.0, frequency - 0.035)
                    neighbor_cost = 0.0
                    neighbor_count = 0
                    for dy, dx, direction in (
                        (0, -1, "horizontal"),
                        (0, 1, "horizontal"),
                        (-1, 0, "vertical"),
                        (1, 0, "vertical"),
                    ):
                        ny, nx = row + dy, col + dx
                        if not (0 <= ny < rows and 0 <= nx < cols):
                            continue
                        neighbor = glyphs[int(selected[ny, nx])]
                        if dx < 0:
                            mismatch = pair_cost(neighbor, glyph, direction)
                        elif dx > 0:
                            mismatch = pair_cost(glyph, neighbor, direction)
                        elif dy < 0:
                            mismatch = pair_cost(neighbor, glyph, direction)
                        else:
                            mismatch = pair_cost(glyph, neighbor, direction)

                        y_boundary = min(row, ny) * cell_height + (
                            cell_height if dy else 0
                        )
                        x_boundary = min(col, nx) * cell_width + (
                            cell_width if dx else 0
                        )
                        if direction == "horizontal":
                            x_index = min(source["strength"].shape[1] - 1, x_boundary)
                            y0 = row * cell_height
                            crossing = float(
                                source["strength"][y0 : y0 + cell_height, x_index].max()
                            )
                        else:
                            y_index = min(source["strength"].shape[0] - 1, y_boundary)
                            x0 = col * cell_width
                            crossing = float(
                                source["strength"][y_index, x0 : x0 + cell_width].max()
                            )
                        neighbor_cost += mismatch * (0.16 + crossing * 0.44)
                        neighbor_count += 1
                    scores[position] += (
                        continuity * neighbor_cost / max(1, neighbor_count)
                    )

                best = int(candidates[int(np.argmin(scores))])
                if best != selected[row, col]:
                    usage[int(selected[row, col])] -= 1
                    usage[best] += 1
                    selected[row, col] = best
                    changes += 1
        if changes == 0:
            break
    return selected


def sample_colors(source, glyphs, selected, cols, rows, cell_width, cell_height):
    colors = []
    cell_colors = [[None for _ in range(cols)] for _ in range(rows)]
    for row in range(rows):
        for col in range(cols):
            glyph = glyphs[int(selected[row, col])]
            if glyph["character"] == " ":
                continue
            y0, y1 = row * cell_height, (row + 1) * cell_height
            x0, x1 = col * cell_width, (col + 1) * cell_width
            rgb = source["rgb"][y0:y1, x0:x1]
            structural = source["importance"][y0:y1, x0:x1]
            subject = source["subject"][y0:y1, x0:x1]
            weights = glyph["mask"] * (0.18 + structural * 0.82) * subject
            if weights.sum() < 0.02:
                weights = glyph["mask"] * (
                    0.15 + source["subject"][y0:y1, x0:x1] * 0.85
                )
            if weights.sum() < 0.02:
                color = np.array([0.92, 0.84, 0.72], dtype=np.float32)
            else:
                color = np.sum(rgb * weights[:, :, None], axis=(0, 1)) / weights.sum()
            cell_colors[row][col] = color
            colors.append(color)
    return cell_colors, np.asarray(colors, dtype=np.float32)


def perceptual_luminance(color):
    return float(0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2])


def grade_colors(colors, minimum_luminance):
    result = colors.copy()
    for index, color in enumerate(result):
        light = perceptual_luminance(color)
        neutral = np.full(3, light, dtype=np.float32)
        color = color * 0.88 + neutral * 0.12
        current = perceptual_luminance(color)
        if current < minimum_luminance:
            blend = (minimum_luminance - current) / max(1e-6, 1.0 - current)
            color = color * (1 - blend) + blend
        result[index] = np.clip(color, 0, 1)
    return result


def kmeans(colors, count, minimum_luminance):
    if len(colors) == 0:
        return np.asarray([[0.9, 0.9, 0.9]], dtype=np.float32)
    colors = grade_colors(colors, minimum_luminance)
    unique = (
        np.unique(np.round(colors * 255).astype(np.uint8), axis=0).astype(np.float32)
        / 255
    )
    if len(unique) <= count:
        centers = unique
    else:
        centers = [unique[np.argmin([perceptual_luminance(item) for item in unique])]]
        while len(centers) < count:
            distances = np.min(
                np.sum(
                    (unique[:, None, :] - np.asarray(centers)[None, :, :]) ** 2, axis=2
                ),
                axis=1,
            )
            centers.append(unique[int(np.argmax(distances))])
        centers = np.asarray(centers)
        for _ in range(30):
            assignments = np.argmin(
                np.sum((colors[:, None, :] - centers[None, :, :]) ** 2, axis=2), axis=1
            )
            updated = centers.copy()
            for index in range(len(centers)):
                cluster = colors[assignments == index]
                if len(cluster):
                    updated[index] = cluster.mean(axis=0)
            if np.allclose(updated, centers, atol=1e-5):
                break
            centers = updated
    order = np.argsort([perceptual_luminance(item) for item in centers])
    return centers[order]


def assign_palette(cell_colors, palette, cols, rows):
    indices = [[None for _ in range(cols)] for _ in range(rows)]
    for row in range(rows):
        for col in range(cols):
            color = cell_colors[row][col]
            if color is None:
                continue
            color = grade_colors(
                np.asarray([color]), min(perceptual_luminance(p) for p in palette)
            )[0]
            indices[row][col] = (
                int(np.argmin(np.sum((palette - color) ** 2, axis=1))) + 1
            )
    return indices


def quote_lua(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_lua(path, glyphs, selected, palette, color_indices, cols, rows):
    lines = [
        "".join(glyphs[int(selected[y, x])]["character"] for x in range(cols))
        for y in range(rows)
    ]
    output = ["-- Generated by EdgeGlyph.", "return {"]
    output.extend((f"  width = {cols},", f"  height = {rows},", "  palette = {"))
    for color in palette:
        rgb = np.clip(np.rint(color * 255), 0, 255).astype(np.uint8)
        output.append(f'    "#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}",')
    output.extend(("  },", "  lines = {"))
    output.extend(f"    {quote_lua(line)}," for line in lines)
    output.extend(("  },", "  chunks = {"))
    for row in range(rows):
        chunks = []
        start = 0
        current = color_indices[row][0]
        for col in range(1, cols + 1):
            following = color_indices[row][col] if col < cols else object()
            if following != current:
                text = lines[row][start:col]
                color = "nil" if current is None else str(current)
                chunks.append(f"{{ {quote_lua(text)}, {color} }}")
                start = col
                current = following
        output.append("    { " + ", ".join(chunks) + " },")
    output.extend(("  },", "}", ""))
    path.write_text("\n".join(output), encoding="utf-8")


def write_text(path, lines):
    content = "\n".join(line.rstrip() for line in lines).rstrip()
    path.write_text(content + "\n", encoding="utf-8")


def draw_preview(
    path,
    font_path,
    fallback_font_path,
    glyphs,
    selected,
    palette,
    color_indices,
    cols,
    rows,
    scale=3,
):
    cell_width, cell_height = 11 * scale, 22 * scale
    fonts = {}
    for glyph in glyphs:
        glyph_font = glyph.get("font_path")
        if (
            not glyph["sprite"]
            and glyph_font is not None
            and str(glyph_font) not in fonts
        ):
            fonts[str(glyph_font)] = ImageFont.truetype(str(glyph_font), 18 * scale)
    margin = 18 * scale
    canvas = Image.new(
        "RGB", (cols * cell_width + margin * 2, rows * cell_height + margin * 2), BG
    )
    draw = ImageDraw.Draw(canvas)
    for row in range(rows):
        for col in range(cols):
            character = glyphs[int(selected[row, col])]["character"]
            glyph = glyphs[int(selected[row, col])]
            color_index = color_indices[row][col]
            if character == " " or color_index is None:
                continue
            rgb = tuple(
                np.clip(np.rint(palette[color_index - 1] * 255), 0, 255).astype(
                    np.uint8
                )
            )
            if glyph["sprite"]:
                alpha = Image.fromarray(
                    np.uint8(np.clip(glyph["mask"], 0, 1) * 255)
                ).resize((cell_width, cell_height), Image.Resampling.LANCZOS)
                block = Image.new("RGB", (cell_width, cell_height), rgb)
                canvas.paste(
                    block,
                    (margin + col * cell_width, margin + row * cell_height),
                    alpha,
                )
                continue
            font = fonts[str(glyph["font_path"])]
            bounds = draw.textbbox((0, 0), character, font=font)
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            x = margin + col * cell_width + (cell_width - width) / 2 - bounds[0]
            y = margin + row * cell_height + (cell_height - height) / 2 - bounds[1]
            draw.text((x, y), character, font=font, fill=rgb)
    canvas.resize(
        (canvas.width // scale, canvas.height // scale), Image.Resampling.LANCZOS
    ).save(path)


def structural_metrics(source, glyphs, selected, cols, rows, cell_width, cell_height):
    reconstruction = np.zeros_like(source["edge"])
    for row in range(rows):
        for col in range(cols):
            y0, y1 = row * cell_height, (row + 1) * cell_height
            x0, x1 = col * cell_width, (col + 1) * cell_width
            reconstruction[y0:y1, x0:x1] = glyphs[int(selected[row, col])]["skeleton"]
    source_distance = chamfer_distance(source["edge"])
    reconstruction_distance = chamfer_distance(reconstruction)
    source_edges = source["edge"]
    generated_edges = reconstruction
    recall = (
        float(np.mean(reconstruction_distance[source_edges] <= 2.0))
        if source_edges.any()
        else 1.0
    )
    precision = (
        float(np.mean(source_distance[generated_edges] <= 2.0))
        if generated_edges.any()
        else 1.0
    )
    f1 = 2 * recall * precision / max(1e-6, recall + precision)
    source_term = (
        float(reconstruction_distance[source_edges].mean())
        if source_edges.any()
        else 0.0
    )
    generated_term = (
        float(source_distance[generated_edges].mean()) if generated_edges.any() else 0.0
    )
    chamfer = 0.5 * (source_term + generated_term)
    return {"recall": recall, "precision": precision, "f1": f1, "chamfer": chamfer}


def write_debug(
    debug_dir, source, glyphs, selected, cols, rows, cell_width, cell_height
):
    debug_dir.mkdir(parents=True, exist_ok=True)
    if "block_pixels" in source:
        Image.fromarray(np.uint8(np.clip(source["subject_coverage"], 0, 1) * 255)).save(
            debug_dir / "subject-coverage.png"
        )
        Image.fromarray(np.uint8(np.clip(source["ink_peak"], 0, 1) * 255)).save(
            debug_dir / "ink-score.png"
        )
        Image.fromarray(np.uint8(source["carved"] * 255)).save(
            debug_dir / "carved-detail.png"
        )
        Image.fromarray(np.uint8(source["block_pixels"] * 255)).save(
            debug_dir / "block-pixels.png"
        )
        return
    Image.fromarray(np.uint8(source["edge"] * 255)).save(debug_dir / "source-edges.png")
    Image.fromarray(np.uint8(source["subject"] * 255)).save(
        debug_dir / "subject-mask.png"
    )
    Image.fromarray(np.uint8(np.clip(source["importance"], 0, 1) * 255)).save(
        debug_dir / "importance.png"
    )
    reconstruction = np.zeros_like(source["edge"])
    for row in range(rows):
        for col in range(cols):
            y0, y1 = row * cell_height, (row + 1) * cell_height
            x0, x1 = col * cell_width, (col + 1) * cell_width
            reconstruction[y0:y1, x0:x1] = glyphs[int(selected[row, col])]["skeleton"]
    Image.fromarray(np.uint8(reconstruction * 255)).save(debug_dir / "glyph-edges.png")


def render_blocks(source_path, config=None):
    config = config or BlockConfig()
    if config.cols < 1 or config.rows < 1:
        raise ValueError("cols and rows must be positive")
    if config.oversample < 2:
        raise ValueError("oversample must be at least 2")
    if config.fit not in {"contain", "cover"}:
        raise ValueError(f"unsupported block fit: {config.fit}")
    if not 0 <= config.focus_y <= 1:
        raise ValueError("focus_y must be between 0 and 1")
    if not 0 <= config.subject_threshold <= 1 or not 0 <= config.ink_threshold <= 1:
        raise ValueError("block thresholds must be between 0 and 1")

    source = prepare_block_source(source_path, config)
    pixels = source["block_pixels"]
    top = pixels[0::2].astype(np.int16)
    bottom = pixels[1::2].astype(np.int16)
    selected = top + bottom * 2
    glyphs = block_glyphs(config.cell_width, config.cell_height)
    palette = np.asarray([parse_hex_color(config.foreground)], dtype=np.float32)
    color_indices = [
        [None if selected[row, col] == 0 else 1 for col in range(config.cols)]
        for row in range(config.rows)
    ]

    silhouette = source["subject_coverage"] >= config.subject_threshold
    retained_subject = np.logical_and(pixels, silhouette).sum()
    subject_area = silhouette.sum()
    carved = source["carved"]
    metrics = {
        "silhouette_coverage": (
            float(retained_subject / subject_area) if subject_area else 1.0
        ),
        "carved_detail_ratio": (
            float(carved.sum() / subject_area) if subject_area else 0.0
        ),
        "foreground_ratio": float(pixels.mean()),
    }
    return RenderResult(
        glyphs=glyphs,
        selected=selected,
        palette=palette,
        color_indices=color_indices,
        source=source,
        metrics=metrics,
        config=config,
    )


def render(source_path, font_path, fallback_font_path=None, config=None):
    config = config or RenderConfig()
    if config.fill_mode not in {"none", "salient", "tone"}:
        raise ValueError(f"unsupported fill mode: {config.fill_mode}")
    if config.line_renderer not in {"sprite", "font"}:
        raise ValueError(f"unsupported line renderer: {config.line_renderer}")
    if config.cols < 1 or config.rows < 1:
        raise ValueError("cols and rows must be positive")

    _, glyphs = render_glyphs(
        font_path,
        fallback_font_path,
        config.font_size,
        config.cell_width,
        config.cell_height,
        config.line_renderer,
    )
    source = prepare_source(
        source_path,
        config.cols,
        config.rows,
        config.cell_width,
        config.cell_height,
    )
    choices, local_scores = local_candidates(
        source,
        glyphs,
        config.cols,
        config.rows,
        config.cell_width,
        config.cell_height,
        config.top_k,
        config.fill_mode,
    )
    selected = optimize_grid(
        source,
        glyphs,
        choices,
        local_scores,
        config.cols,
        config.rows,
        config.cell_width,
        config.cell_height,
        config.continuity,
        config.diversity,
    )
    cell_colors, colors = sample_colors(
        source,
        glyphs,
        selected,
        config.cols,
        config.rows,
        config.cell_width,
        config.cell_height,
    )
    palette = kmeans(colors, config.colors, config.minimum_luminance)
    color_indices = assign_palette(cell_colors, palette, config.cols, config.rows)
    metrics = structural_metrics(
        source,
        glyphs,
        selected,
        config.cols,
        config.rows,
        config.cell_width,
        config.cell_height,
    )
    return RenderResult(
        glyphs=glyphs,
        selected=selected,
        palette=palette,
        color_indices=color_indices,
        source=source,
        metrics=metrics,
        config=config,
    )

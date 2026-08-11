#!/usr/bin/env python3

import collections
import colorsys
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .glyphsets import (
    ASCII_PRINTABLE,
    ASCII_STRUCTURE,
    ASCII_TONE,
    UNICODE_LINES,
    resolve_glyph_set,
)


BG = (30, 30, 46)
CHARACTERS = ASCII_PRINTABLE + UNICODE_LINES
STRUCTURE_CHARACTERS = set(ASCII_STRUCTURE + UNICODE_LINES)
TONE_RAMP = ASCII_TONE
TONE_CHARACTERS = set(TONE_RAMP)
BAYER_4 = (
    np.array(
        [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32
    )
    / 16.0
)
BEAD_CLUSTER_SAMPLE_LIMIT = 65_536
BEAD_CLUSTER_DISTANCE_BUDGET = 1_500_000


@dataclass(frozen=True)
class RenderConfig:
    cols: int = 56
    rows: int = 28
    colors: int = 16
    color_mode: str = "color"
    monochrome_color: str = "#e8e8e8"
    top_k: int = 8
    minimum_luminance: float = 0.72
    profile: str = "hybrid"
    character_preset: str = "portrait"
    symbols: str = ""
    fill_symbols: str = ""
    fill_mode: str = "auto"
    continuity: float = 0.4
    diversity: float = 1.5
    shape_weight: float = 1.0
    tone_weight: float = 1.0
    color_weight: float = 0.75
    texture_weight: float = 0.35
    global_weight: float = 0.6
    line_renderer: str = "sprite"
    cell_width: int = 11
    cell_height: int = 22
    font_size: int = 18


@dataclass(frozen=True)
class BlockConfig:
    cols: int = 56
    rows: int = 28
    colors: int = 4
    foreground: str = "#cba6f7"
    subject_threshold: float = 0.34
    ink_threshold: float = 0.46
    detail: float = 1.0
    oversample: int = 6
    fit: str = "cover"
    focus_y: float = 0.36
    zoom: float = 1.0
    cell_width: int = 11
    cell_height: int = 22


@dataclass(frozen=True)
class BeadConfig:
    cols: int = 48
    rows: int = 48
    colors: int = 12
    subject_threshold: float = 0.20
    oversample: int = 6
    fit: str = "cover"
    focus_y: float = 0.5
    zoom: float = 1.0
    background: str = "auto"
    board_style: str = "light"
    finish: str = "glossy"
    bead_size: int = 16
    chart_title: str = ""
    chart_cell_size: int = 18
    cell_width: int = 1
    cell_height: int = 1


@dataclass
class RenderResult:
    glyphs: list
    selected: np.ndarray
    palette: np.ndarray
    color_indices: list
    source: dict
    metrics: dict
    config: Union[RenderConfig, BlockConfig, BeadConfig]
    background_indices: list = None

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


def pool_block_colors(rgb, weights, rows, cols, oversample):
    expected = (rows * oversample, cols * oversample)
    if rgb.shape[:2] != expected or weights.shape != expected:
        raise ValueError("color and weight grids must match the requested block size")
    color_blocks = rgb.reshape(rows, oversample, cols, oversample, 3).transpose(
        0, 2, 1, 3, 4
    )
    weight_blocks = weights.reshape(rows, oversample, cols, oversample).transpose(
        0, 2, 1, 3
    )
    totals = weight_blocks.sum(axis=(2, 3))
    weighted = (color_blocks * weight_blocks[:, :, :, :, None]).sum(axis=(2, 3))
    return weighted / np.maximum(totals[:, :, None], 1e-6)


def srgb_to_oklab(rgb):
    rgb = np.asarray(rgb, dtype=np.float32)
    linear = np.where(
        rgb <= 0.04045,
        rgb / 12.92,
        ((rgb + 0.055) / 1.055) ** 2.4,
    )
    lms = (
        linear
        @ np.asarray(
            [
                [0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005],
            ],
            dtype=np.float32,
        ).T
    )
    return (
        np.cbrt(np.maximum(lms, 0))
        @ np.asarray(
            [
                [0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660],
            ],
            dtype=np.float32,
        ).T
    )


def oklab_to_srgb(lab):
    lab = np.asarray(lab, dtype=np.float32)
    lms_root = (
        lab
        @ np.asarray(
            [
                [1.0, 0.3963377774, 0.2158037573],
                [1.0, -0.1055613458, -0.0638541728],
                [1.0, -0.0894841775, -1.2914855480],
            ],
            dtype=np.float32,
        ).T
    )
    linear = (lms_root**3) @ np.asarray(
        [
            [4.0767416621, -3.3077115913, 0.2309699292],
            [-1.2684380046, 2.6097574011, -0.3413193965],
            [-0.0041960863, -0.7034186147, 1.7076147010],
        ],
        dtype=np.float32,
    ).T
    srgb = np.where(
        linear <= 0.0031308,
        linear * 12.92,
        1.055 * np.maximum(linear, 0) ** (1 / 2.4) - 0.055,
    )
    return np.clip(srgb, 0, 1)


def fit_oklab_clusters(colors, count):
    points = srgb_to_oklab(colors)
    center_indices = [
        int(np.argmin(np.sum((points - points.mean(axis=0)) ** 2, axis=1)))
    ]
    while len(center_indices) < count:
        centers = points[center_indices]
        distances = np.min(
            np.sum((points[:, None, :] - centers[None, :, :]) ** 2, axis=2), axis=1
        )
        center_indices.append(int(np.argmax(distances)))
    centers = points[center_indices].copy()

    for _ in range(32):
        assignments = np.argmin(
            np.sum((points[:, None, :] - centers[None, :, :]) ** 2, axis=2), axis=1
        )
        updated = centers.copy()
        for index in range(count):
            cluster = points[assignments == index]
            if len(cluster):
                updated[index] = cluster.mean(axis=0)
        if np.allclose(updated, centers, atol=1e-5):
            centers = updated
            break
        centers = updated
    assignments = np.argmin(
        np.sum((points[:, None, :] - centers[None, :, :]) ** 2, axis=2), axis=1
    )
    return centers, assignments


def grade_block_palette(colors):
    hls = np.asarray(
        [colorsys.rgb_to_hls(*color) for color in colors], dtype=np.float32
    )
    lightness = hls[:, 1]
    span = float(np.ptp(lightness))
    relative = (
        (lightness - lightness.min()) / span
        if span > 1e-5
        else np.full_like(lightness, 0.5)
    )
    hls[:, 1] = 0.58 + relative * 0.18
    hls[:, 2] = np.clip(hls[:, 2] * 0.64, 0.20, 0.62)
    return np.asarray([colorsys.hls_to_rgb(*color) for color in hls], dtype=np.float32)


def quantize_block_colors(colors, maximum_colors):
    if maximum_colors < 2:
        raise ValueError(
            "automatic block color quantization requires at least two colors"
        )
    rounded = np.unique(np.rint(np.clip(colors, 0, 1) * 255).astype(np.uint8), axis=0)
    count = min(maximum_colors, len(rounded))
    if count == 0:
        return np.asarray([[0.8, 0.8, 0.8]], dtype=np.float32), np.zeros(
            0, dtype=np.int16
        )

    while count > 1:
        centers, assignments = fit_oklab_clusters(colors, count)
        fractions = np.bincount(assignments, minlength=count) / len(assignments)
        pairwise = np.sqrt(
            np.sum((centers[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        )
        pairwise += np.eye(count, dtype=np.float32) * 10
        if fractions.min() >= 0.02 and pairwise.min() >= 0.065:
            break
        count -= 1

    centers, assignments = fit_oklab_clusters(colors, count)
    source_palette = oklab_to_srgb(centers)
    palette = grade_block_palette(source_palette)
    order = np.argsort([colorsys.rgb_to_hls(*color)[0] for color in palette])
    inverse = np.empty_like(order)
    inverse[order] = np.arange(len(order))
    return palette[order], inverse[assignments].astype(np.int16)


def quantize_bead_colors(colors, maximum_colors):
    """Quantize sampled bead colors without terminal-specific palette grading."""

    if len(colors) == 0:
        return np.asarray([[0.82, 0.78, 0.70]], dtype=np.float32), np.zeros(
            0, dtype=np.int16
        )

    batch_size = min(
        BEAD_CLUSTER_SAMPLE_LIMIT,
        max(8_192, BEAD_CLUSTER_DISTANCE_BUDGET // maximum_colors),
    )
    if len(colors) > batch_size:
        sample_indices = np.linspace(
            0,
            len(colors) - 1,
            batch_size,
            dtype=np.int64,
        )
        training_colors = colors[sample_indices]
    else:
        training_colors = colors

    rounded = np.unique(
        np.rint(np.clip(training_colors, 0, 1) * 255).astype(np.uint8),
        axis=0,
    )
    count = min(maximum_colors, len(rounded))
    centers, _ = fit_oklab_clusters(training_colors, count)
    palette = oklab_to_srgb(centers)
    hls = np.asarray(
        [colorsys.rgb_to_hls(*color) for color in palette], dtype=np.float32
    )
    hls[:, 1] = np.clip(hls[:, 1], 0.16, 0.92)
    hls[:, 2] = np.clip(hls[:, 2] * 0.92, 0.12, 0.92)
    palette = np.asarray(
        [colorsys.hls_to_rgb(*color) for color in hls], dtype=np.float32
    )
    order = np.lexsort((hls[:, 1], hls[:, 0]))
    inverse = np.empty_like(order)
    inverse[order] = np.arange(len(order))
    assignments = np.empty(len(colors), dtype=np.int16)
    for start in range(0, len(colors), batch_size):
        stop = min(start + batch_size, len(colors))
        points = srgb_to_oklab(colors[start:stop])
        assignments[start:stop] = np.argmin(
            np.sum((points[:, None, :] - centers[None, :, :]) ** 2, axis=2),
            axis=1,
        )
    return palette[order], inverse[assignments].astype(np.int16)


def cleanup_components(mask, minimum_size=2):
    if minimum_size == 2:
        padded = np.pad(mask, 1, mode="constant", constant_values=False)
        neighbors = np.zeros_like(mask, dtype=np.uint8)
        for dy in range(3):
            for dx in range(3):
                if dx == 1 and dy == 1:
                    continue
                neighbors += padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
        return mask & (neighbors > 0)

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


def bead_glyphs():
    empty = np.zeros((1, 1), dtype=np.float32)
    filled = np.ones((1, 1), dtype=np.float32)
    return [
        {
            "character": character,
            "font_path": None,
            "sprite": True,
            "mask": mask,
            "ink": mask,
            "skeleton": mask > 0.5,
        }
        for character, mask in ((" ", empty), ("●", filled))
    ]


def prepare_bead_source(source_path, config):
    effective_oversample = min(
        config.oversample,
        max(1, 3072 // max(config.cols, config.rows)),
    )
    working_size = (
        config.cols * effective_oversample,
        config.rows * effective_oversample,
    )
    original = Image.open(source_path).convert("RGBA")
    scale_x = working_size[0] / original.width
    scale_y = working_size[1] / original.height
    scale = (
        max(scale_x, scale_y) if config.fit == "cover" else min(scale_x, scale_y)
    ) * config.zoom
    fitted_size = (
        max(1, round(original.width * scale)),
        max(1, round(original.height * scale)),
    )
    fitted = original.resize(fitted_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", working_size, (255, 255, 255, 0))
    offset = (
        (working_size[0] - fitted.width) // 2,
        round((working_size[1] - fitted.height) * config.focus_y),
    )
    canvas.alpha_composite(fitted, offset)

    alpha = np.asarray(canvas, dtype=np.float32)[:, :, 3] / 255.0
    flattened = Image.new("RGB", working_size, "white")
    flattened.paste(canvas.convert("RGB"), mask=canvas.getchannel("A"))
    softened = flattened.filter(ImageFilter.GaussianBlur(0.42))
    rgb = np.asarray(softened, dtype=np.float32) / 255.0
    if config.background == "auto":
        background = flood_background(rgb) | (alpha < 0.02)
    else:
        background = alpha < 0.02
    subject = ~background
    coverage = pool_blocks(
        subject.astype(np.float32),
        config.rows,
        config.cols,
        effective_oversample,
        "mean",
    )
    cell_rgb = pool_block_colors(
        rgb,
        subject.astype(np.float32),
        config.rows,
        config.cols,
        effective_oversample,
    )
    beads = cleanup_components(
        coverage >= config.subject_threshold,
        minimum_size=2,
    )
    return {
        "subject_coverage": coverage,
        "pixel_rgb": cell_rgb,
        "bead_mask": beads,
        "effective_oversample": effective_oversample,
    }


def prepare_block_source(source_path, config):
    pixel_rows = config.rows * 2
    working_size = (config.cols * config.oversample, pixel_rows * config.oversample)
    original = Image.open(source_path).convert("RGBA")
    scale_x = working_size[0] / original.width
    scale_y = working_size[1] / original.height
    scale = (
        max(scale_x, scale_y) if config.fit == "cover" else min(scale_x, scale_y)
    ) * config.zoom
    fitted_size = (
        max(1, round(original.width * scale)),
        max(1, round(original.height * scale)),
    )
    fitted = original.resize(fitted_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", working_size, (255, 255, 255, 0))
    offset = (
        (working_size[0] - fitted.width) // 2,
        round((working_size[1] - fitted.height) * config.focus_y),
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
    pixel_rgb = pool_block_colors(
        softened,
        subject.astype(np.float32),
        pixel_rows,
        config.cols,
        config.oversample,
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
        "pixel_rgb": pixel_rgb,
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


def spatial_descriptor(mask, divisions=4):
    """Pool a mask into a small layout descriptor without resizing artifacts."""

    return np.asarray(
        [
            float(block.mean())
            for rows in np.array_split(mask, divisions, axis=0)
            for block in np.array_split(rows, divisions, axis=1)
        ],
        dtype=np.float32,
    )


def gradient_descriptor(mask, bins=8):
    gx, gy = gradients(mask)
    magnitude = np.hypot(gx, gy)
    total = float(magnitude.sum())
    if total <= 1e-6:
        return np.zeros(bins, dtype=np.float32)
    angles = (np.arctan2(gy, gx) + math.pi) % math.pi
    indices = np.minimum((angles / math.pi * bins).astype(np.int16), bins - 1)
    histogram = np.bincount(
        indices.ravel(), weights=magnitude.ravel(), minlength=bins
    ).astype(np.float32)
    return histogram / max(float(histogram.sum()), 1e-6)


def render_font_mask(font_path, character, font_size, cell_width, cell_height):
    canvas = Image.new("L", (cell_width * 4, cell_height * 4), 0)
    draw = ImageDraw.Draw(canvas)
    scaled_font = ImageFont.truetype(str(font_path), font_size * 4)
    bounds = draw.textbbox((0, 0), character, font=scaled_font)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    x = (canvas.width - width) / 2 - bounds[0]
    y = (canvas.height - height) / 2 - bounds[1]
    draw.text((x, y), character, font=scaled_font, fill=255)
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
    characters=CHARACTERS,
    structure_characters=None,
    fill_characters=None,
):
    font = ImageFont.truetype(str(font_path), font_size)
    fallback_font_path = fallback_font_path or font_path
    structure_characters = set(structure_characters or STRUCTURE_CHARACTERS)
    fill_characters = set(fill_characters or TONE_CHARACTERS)
    glyphs = []
    missing_masks = {}
    for character in characters:
        is_sprite = character in UNICODE_LINES and line_renderer == "sprite"
        glyph_font_path = (
            None
            if is_sprite
            else (fallback_font_path if ord(character) > 127 else font_path)
        )
        if is_sprite:
            mask = render_line_sprite(character, cell_width, cell_height)
        else:
            mask = render_font_mask(
                glyph_font_path, character, font_size, cell_width, cell_height
            )
            key = str(glyph_font_path)
            if key not in missing_masks:
                missing_masks[key] = render_font_mask(
                    glyph_font_path,
                    "\U0010ffff",
                    font_size,
                    cell_width,
                    cell_height,
                )
            if character != " " and (
                float(mask.max()) < 0.02
                or np.allclose(mask, missing_masks[key], atol=1 / 255)
            ):
                continue
        ink = mask > 0.18
        skeleton = thin(mask > 0.38) if character != " " else np.zeros_like(ink)
        orientation = skeleton_orientations(skeleton)
        distance, nearest_orientation = distance_and_nearest_orientation(
            skeleton, orientation
        )
        mass = float(mask.sum())
        if mass > 1e-6:
            yy, xx = np.indices(mask.shape, dtype=np.float32)
            centroid = np.asarray(
                [float((xx * mask).sum() / mass), float((yy * mask).sum() / mass)],
                dtype=np.float32,
            )
            centroid /= np.asarray(
                [max(1, cell_width - 1), max(1, cell_height - 1)], dtype=np.float32
            )
        else:
            centroid = np.asarray([0.5, 0.5], dtype=np.float32)
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
                "spatial2": spatial_descriptor(mask, 2),
                "spatial4": spatial_descriptor(mask, 4),
                "gradient_histogram": gradient_descriptor(mask),
                "texture": float(np.hypot(*gradients(mask)).mean()),
                "centroid": centroid,
                "structure": character in structure_characters,
                "fill": character in fill_characters,
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

    ranked = sorted(
        (
            (index, glyph["density"])
            for index, glyph in enumerate(glyphs)
            if glyph["fill"]
        ),
        key=lambda item: item[1],
    )
    denominator = max(1, len(ranked) - 1)
    for rank, (index, _) in enumerate(ranked):
        glyphs[index]["tone_position"] = rank / denominator
    for glyph in glyphs:
        glyph.setdefault("tone_position", glyph["density"])
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
    low_frequency = (
        np.asarray(image.filter(ImageFilter.GaussianBlur(2.4)), dtype=np.float32)
        / 255.0
    )
    low_luminance = (
        0.2126 * low_frequency[:, :, 0]
        + 0.7152 * low_frequency[:, :, 1]
        + 0.0722 * low_frequency[:, :, 2]
    )
    local_contrast = np.abs(luminance - low_luminance) * subject
    gradient_scale = np.percentile(magnitude[subject > 0], 94) if subject.any() else 1.0
    gradient_energy = np.clip(magnitude / max(float(gradient_scale), 1e-6), 0, 1)
    texture = np.clip(local_contrast * 3.2 + gradient_energy * 0.45, 0, 1) * subject
    visual_density = subject * np.clip(
        0.045 + darkness * 0.24 + saturation * 0.17 + texture * 0.09 + strength * 0.12,
        0,
        0.48,
    )
    outline_importance = np.clip(
        strength * 0.70 + darkness * 0.18 + saturation * 0.12, 0, 1
    )
    importance = np.clip(
        strength * 0.38 + visual_density * 0.30 + texture * 0.18 + saturation * 0.14,
        0,
        1,
    )

    return {
        "image": image,
        "rgb": rgb,
        "background": background,
        "subject": subject,
        "luminance": luminance,
        "darkness": darkness,
        "saturation": saturation,
        "texture": texture,
        "visual_density": visual_density,
        "edge": edges,
        "strength": strength,
        "orientation": orientation,
        "outline_importance": outline_importance,
        "importance": importance,
    }


def fit_cell_colors(rgb, mask, subject):
    """Fit foreground/background colors for one antialiased glyph mask."""

    weights = np.asarray(subject, dtype=np.float32)
    if float(weights.sum()) < 1e-5:
        neutral = np.asarray(BG, dtype=np.float32) / 255.0
        return neutral, neutral, 0.0

    foreground = np.asarray(mask, dtype=np.float32)
    background = 1.0 - foreground
    a00 = float(np.sum(weights * foreground * foreground)) + 1e-5
    a01 = float(np.sum(weights * foreground * background))
    a11 = float(np.sum(weights * background * background)) + 1e-5
    determinant = a00 * a11 - a01 * a01
    if determinant <= 1e-7:
        average = np.sum(rgb * weights[:, :, None], axis=(0, 1)) / weights.sum()
        return average, average, 0.0

    b0 = np.sum(rgb * (weights * foreground)[:, :, None], axis=(0, 1))
    b1 = np.sum(rgb * (weights * background)[:, :, None], axis=(0, 1))
    foreground_color = np.clip((b0 * a11 - b1 * a01) / determinant, 0, 1)
    background_color = np.clip((b1 * a00 - b0 * a01) / determinant, 0, 1)
    reconstruction = (
        foreground[:, :, None] * foreground_color
        + background[:, :, None] * background_color
    )
    channel_weights = np.asarray([0.30, 0.59, 0.11], dtype=np.float32)
    squared = np.sum((rgb - reconstruction) ** 2 * channel_weights, axis=2)
    error = math.sqrt(float(np.sum(squared * weights) / weights.sum()))
    return foreground_color, background_color, error


def resolve_fill_mode(profile, fill_mode):
    if fill_mode != "auto":
        return fill_mode
    return {"outline": "none", "hybrid": "salient", "tone": "tone"}[profile]


def _orientation_histogram(orientation, strength, bins=8):
    total = float(strength.sum())
    if total <= 1e-6:
        return np.zeros(bins, dtype=np.float32)
    histogram = np.bincount(
        orientation.ravel(), weights=strength.ravel(), minlength=bins
    ).astype(np.float32)
    return histogram / max(float(histogram.sum()), 1e-6)


def _outline_pool_and_scores(
    glyphs,
    row,
    col,
    edge_strength,
    edge,
    orientation,
    subject_fraction,
    darkness,
    saturation,
    top_k,
    fill_mode,
):
    edge_mass = float(edge_strength.sum())
    edge_pixels = int(edge.sum())
    tone_strength = subject_fraction * np.clip(
        darkness * 1.25 + saturation * 0.72, 0, 1
    )
    dither_threshold = float(BAYER_4[row % 4, col % 4])
    source_distance, source_nearest_orientation = distance_and_nearest_orientation(
        edge, orientation
    )
    desired_density = np.clip(
        0.012 + edge_strength.mean() * 0.78 + darkness * 0.19 + saturation * 0.07,
        0,
        0.46,
    )
    structural_cell = edge_pixels >= 2 and edge_mass >= 0.12
    if structural_cell:
        pool = [index for index, glyph in enumerate(glyphs) if glyph["structure"]]
    elif (
        fill_mode == "tone"
        and tone_strength > 0.08
        and dither_threshold < min(0.92, tone_strength * 2.7 + 0.12)
    ) or (
        fill_mode == "salient"
        and ((darkness > 0.20 and saturation > 0.18) or darkness > 0.42)
        and dither_threshold < min(0.58, tone_strength * 0.72)
    ):
        pool = [index for index, glyph in enumerate(glyphs) if glyph["fill"]]
    else:
        pool = [0]

    scores = np.full(len(glyphs), np.inf, dtype=np.float32)
    for index in pool:
        glyph = glyphs[index]
        if index == 0:
            scores[index] = edge_mass * 0.48 + tone_strength * 1.25
            continue
        if not structural_cell:
            ramp_target = np.clip(
                tone_strength * 0.84 + (0.5 - dither_threshold) * 0.22, 0, 1
            )
            density_target = np.clip(tone_strength * 0.34, 0.008, 0.34)
            scores[index] = (
                abs(glyph["density"] - density_target) * 1.9
                + abs(glyph["tone_position"] - ramp_target) * 2.8
            )
            continue

        glyph_edge = glyph["skeleton"]
        glyph_mass = max(1.0, float(glyph_edge.sum()))
        orientation_cost = circular_bin_distance(
            orientation, glyph["nearest_orientation"]
        )
        source_to_glyph = float(
            np.sum(edge_strength * (glyph["distance"] + orientation_cost * 0.85))
            / max(edge_mass, 1e-6)
        )
        reverse_orientation_cost = circular_bin_distance(
            glyph["orientation"], source_nearest_orientation
        )
        glyph_to_source = float(
            np.sum(glyph_edge * (source_distance + reverse_orientation_cost * 0.85))
            / glyph_mass
        )
        tone = abs(glyph["density"] - desired_density)
        occupancy = abs(float(glyph["ink"].mean()) - min(0.55, subject_fraction * 0.45))
        complexity = glyph_mass / glyph_edge.size
        complexity_penalty = max(0.0, complexity - (0.06 + edge_strength.mean() * 0.8))
        scores[index] = (
            source_to_glyph * 0.53
            + glyph_to_source * 0.34
            + tone * 2.25
            + occupancy * 0.18
            + complexity_penalty * 0.22
        )

    finite = np.flatnonzero(np.isfinite(scores))
    count = min(top_k, len(finite))
    selected = finite[np.argpartition(scores[finite], count - 1)[:count]]
    selected = selected[np.argsort(scores[selected])]
    return selected.astype(np.int16), scores[selected]


def local_candidates(source, glyphs, config):
    cols, rows = config.cols, config.rows
    cell_width, cell_height = config.cell_width, config.cell_height
    choices = [[None for _ in range(cols)] for _ in range(rows)]
    local_scores = [[None for _ in range(cols)] for _ in range(rows)]
    cell_density = np.zeros((rows, cols), dtype=np.float32)
    cell_texture = np.zeros((rows, cols), dtype=np.float32)
    structure_pool = [index for index, glyph in enumerate(glyphs) if glyph["structure"]]
    fill_pool = [index for index, glyph in enumerate(glyphs) if glyph["fill"]]
    hybrid_pool = list(dict.fromkeys([0, *structure_pool, *fill_pool]))
    fill_mode = resolve_fill_mode(config.profile, config.fill_mode)

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
            dither_threshold = float(BAYER_4[row % 4, col % 4])
            visual_density = source["visual_density"][y0:y1, x0:x1]
            texture = source["texture"][y0:y1, x0:x1]
            target_density = float(visual_density.mean())
            target_texture = float(texture.mean())
            cell_density[row, col] = target_density
            cell_texture[row, col] = target_texture

            if background_fraction > 0.985 and edge_mass < 0.15:
                choices[row][col] = np.array([0], dtype=np.int16)
                local_scores[row][col] = np.array([0.0], dtype=np.float32)
                continue

            if config.profile == "outline":
                selected, scores = _outline_pool_and_scores(
                    glyphs,
                    row,
                    col,
                    edge_strength,
                    edge,
                    orientation,
                    subject_fraction,
                    darkness,
                    saturation,
                    config.top_k,
                    fill_mode,
                )
                choices[row][col] = selected
                local_scores[row][col] = scores
                continue

            source_distance, source_nearest_orientation = (
                distance_and_nearest_orientation(edge, orientation)
            )
            structural_cell = edge_pixels >= 2 and edge_mass >= 0.12
            if config.profile == "tone":
                pool = list(dict.fromkeys([0, *fill_pool]))
            elif fill_mode == "none" and not structural_cell:
                pool = [0]
            elif (
                fill_mode == "salient"
                and not structural_cell
                and target_density < 0.055
                and dither_threshold > target_density * 5.0
            ):
                pool = [0]
            else:
                pool = hybrid_pool

            scores = np.full(len(glyphs), np.inf, dtype=np.float32)
            target_spatial2 = spatial_descriptor(visual_density, 2)
            target_spatial4 = spatial_descriptor(visual_density, 4)
            target_gradient = _orientation_histogram(orientation, edge_strength)
            rgb = source["rgb"][y0:y1, x0:x1]
            subject = source["subject"][y0:y1, x0:x1]
            for index in pool:
                glyph = glyphs[index]
                if index == 0:
                    scores[index] = (
                        config.shape_weight * edge_mass * 0.45
                        + config.tone_weight * target_density * 7.5
                        + subject_fraction * 0.28
                    )
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
                    reverse_orientation_cost = circular_bin_distance(
                        glyph["orientation"], source_nearest_orientation
                    )
                    glyph_to_source = float(
                        np.sum(
                            glyph_edge
                            * (source_distance + reverse_orientation_cost * 0.85)
                        )
                        / glyph_mass
                    )
                else:
                    source_to_glyph = 0.0
                    glyph_to_source = 0.0
                shape_score = source_to_glyph * 0.48 + glyph_to_source * 0.30
                tone_score = (
                    abs(glyph["density"] - target_density) * 3.8
                    + float(np.mean(np.abs(glyph["spatial2"] - target_spatial2))) * 1.8
                    + float(np.mean(np.abs(glyph["spatial4"] - target_spatial4))) * 2.6
                )
                orientation_score = float(
                    np.mean(np.abs(glyph["gradient_histogram"] - target_gradient))
                )
                texture_score = abs(
                    glyph["texture"] - target_texture
                ) * 3.4 + orientation_score * (1.2 if structural_cell else 0.35)
                if config.color_mode == "color" and config.color_weight > 0:
                    _, _, color_error = fit_cell_colors(rgb, glyph["mask"], subject)
                else:
                    color_error = 0.0
                role_penalty = 0.0
                if structural_cell and not glyph["structure"]:
                    role_penalty += 0.16
                if not structural_cell and not glyph["fill"]:
                    role_penalty += 0.10
                scores[index] = (
                    config.shape_weight
                    * shape_score
                    * min(1.0, edge_mass / 1.2)
                    * (0.35 if config.profile == "tone" else 1.0)
                    + config.tone_weight * tone_score
                    + config.color_weight * color_error * 3.2
                    + config.texture_weight * texture_score
                    + role_penalty
                )

            finite = np.flatnonzero(np.isfinite(scores))
            count = min(config.top_k, len(finite))
            selected = finite[np.argpartition(scores[finite], count - 1)[:count]]
            selected = selected[np.argsort(scores[selected])]
            choices[row][col] = selected.astype(np.int16)
            local_scores[row][col] = scores[selected]
    source["cell_density"] = cell_density
    source["cell_texture"] = cell_texture
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
    global_weight=0.0,
):
    selected = np.array(
        [[int(choices[y][x][0]) for x in range(cols)] for y in range(rows)]
    )
    density_grid = np.asarray(
        [
            [glyphs[int(selected[row, col])]["density"] for col in range(cols)]
            for row in range(rows)
        ],
        dtype=np.float32,
    )
    target_density = source.get(
        "cell_density", np.zeros((rows, cols), dtype=np.float32)
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
                    if global_weight > 0:
                        multiscale_cost = 0.0
                        current_density = density_grid[row, col]
                        for radius, scale_weight in ((1, 0.50), (2, 0.32), (4, 0.18)):
                            y0, y1 = max(0, row - radius), min(rows, row + radius + 1)
                            x0, x1 = max(0, col - radius), min(cols, col + radius + 1)
                            area = (y1 - y0) * (x1 - x0)
                            current_mean = float(density_grid[y0:y1, x0:x1].mean())
                            candidate_mean = (
                                current_mean
                                + (glyph["density"] - current_density) / area
                            )
                            desired_mean = float(target_density[y0:y1, x0:x1].mean())
                            multiscale_cost += scale_weight * abs(
                                candidate_mean - desired_mean
                            )
                        scores[position] += global_weight * multiscale_cost * 5.0

                best = int(candidates[int(np.argmin(scores))])
                if best != selected[row, col]:
                    usage[int(selected[row, col])] -= 1
                    usage[best] += 1
                    selected[row, col] = best
                    density_grid[row, col] = glyphs[best]["density"]
                    changes += 1
        if changes == 0:
            break
    return selected


def fit_foreground_color(rgb, mask, subject):
    terminal_background = np.asarray(BG, dtype=np.float32) / 255.0
    weights = np.asarray(subject, dtype=np.float32)
    denominator = float(np.sum(weights * mask * mask))
    if denominator < 1e-5:
        return np.asarray([0.92, 0.84, 0.72], dtype=np.float32), 1.0
    residual = rgb - (1.0 - mask)[:, :, None] * terminal_background
    color = np.sum(residual * (weights * mask)[:, :, None], axis=(0, 1)) / denominator
    color = np.clip(color, 0, 1)
    reconstruction = (
        mask[:, :, None] * color + (1.0 - mask)[:, :, None] * terminal_background
    )
    channel_weights = np.asarray([0.30, 0.59, 0.11], dtype=np.float32)
    squared = np.sum((rgb - reconstruction) ** 2 * channel_weights, axis=2)
    error = math.sqrt(float(np.sum(squared * weights) / max(weights.sum(), 1e-6)))
    return color, error


def sample_colors(
    source,
    glyphs,
    selected,
    cols,
    rows,
    cell_width,
    cell_height,
    profile="outline",
    fill_mode="none",
):
    colors = []
    cell_colors = [[None for _ in range(cols)] for _ in range(rows)]
    cell_backgrounds = [[None for _ in range(cols)] for _ in range(rows)]
    for row in range(rows):
        for col in range(cols):
            glyph = glyphs[int(selected[row, col])]
            if glyph["character"] == " ":
                continue
            y0, y1 = row * cell_height, (row + 1) * cell_height
            x0, x1 = col * cell_width, (col + 1) * cell_width
            rgb = source["rgb"][y0:y1, x0:x1]
            subject = source["subject"][y0:y1, x0:x1]
            if profile == "outline":
                structural = source["outline_importance"][y0:y1, x0:x1]
                weights = glyph["mask"] * (0.18 + structural * 0.82) * subject
                if weights.sum() < 0.02:
                    weights = glyph["mask"] * (0.15 + subject * 0.85)
                if weights.sum() < 0.02:
                    foreground = np.array([0.92, 0.84, 0.72], dtype=np.float32)
                else:
                    foreground = (
                        np.sum(rgb * weights[:, :, None], axis=(0, 1)) / weights.sum()
                    )
            else:
                fitted_foreground, fitted_background, two_color_error = fit_cell_colors(
                    rgb, glyph["mask"], subject
                )
                foreground, foreground_error = fit_foreground_color(
                    rgb, glyph["mask"], subject
                )
                subject_fraction = float(subject.mean())
                target_density = float(source["visual_density"][y0:y1, x0:x1].mean())
                color_separation = float(
                    np.linalg.norm(fitted_foreground - fitted_background)
                )
                improvement = foreground_error - two_color_error
                adaptive_background = (
                    subject_fraction > 0.88
                    and target_density > 0.12
                    and improvement > 0.045
                    and color_separation > 0.075
                    and (profile == "tone" or fill_mode == "tone")
                )
                if adaptive_background:
                    foreground = fitted_foreground
                    cell_backgrounds[row][col] = fitted_background
                    colors.append(fitted_background)
            cell_colors[row][col] = foreground
            colors.append(foreground)
    return cell_colors, cell_backgrounds, np.asarray(colors, dtype=np.float32)


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


def write_lua(
    path,
    glyphs,
    selected,
    palette,
    color_indices,
    cols,
    rows,
    background_indices=None,
):
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
    background_indices = background_indices or [
        [None for _ in range(cols)] for _ in range(rows)
    ]
    for row in range(rows):
        chunks = []
        start = 0
        current = (color_indices[row][0], background_indices[row][0])
        for col in range(1, cols + 1):
            following = (
                (color_indices[row][col], background_indices[row][col])
                if col < cols
                else object()
            )
            if following != current:
                text = lines[row][start:col]
                foreground = "nil" if current[0] is None else str(current[0])
                background = "nil" if current[1] is None else str(current[1])
                chunks.append(f"{{ {quote_lua(text)}, {foreground}, {background} }}")
                start = col
                current = following
        output.append("    { " + ", ".join(chunks) + " },")
    output.extend(("  },", "}", ""))
    path.write_text("\n".join(output), encoding="utf-8")


def write_text(path, lines):
    content = "\n".join(line.rstrip() for line in lines).rstrip()
    path.write_text(content + "\n", encoding="utf-8")


def _blend_rgb(color, target, amount):
    source = np.asarray(color, dtype=np.float32)
    destination = np.asarray(target, dtype=np.float32)
    return tuple(np.rint(source * (1 - amount) + destination * amount).astype(np.uint8))


def bead_preview_size(config):
    """Return a bounded display size while preserving every logical bead cell."""

    safe_cell = max(1, 4096 // max(config.cols, config.rows))
    return min(config.bead_size, safe_cell)


def draw_bead_preview(path, palette, color_indices, cols, rows, config):
    """Draw a polished top-down pegboard preview with physical bead geometry."""

    display_size = bead_preview_size(config)
    largest_grid_side = max(cols, rows) * display_size
    antialias = (
        3 if largest_grid_side <= 1400 else 2 if largest_grid_side <= 2400 else 1
    )
    cell = display_size * antialias
    outer_margin = max(24, display_size * 2) * antialias
    board_padding = max(8, round(display_size * 0.72)) * antialias
    board_width = cols * cell + board_padding * 2
    board_height = rows * cell + board_padding * 2
    canvas_size = (
        board_width + outer_margin * 2,
        board_height + outer_margin * 2,
    )

    styles = {
        "light": {
            "canvas": (25, 27, 34, 255),
            "board": (232, 231, 225, 255),
            "grid": (183, 183, 178, 80),
            "grid_major": (151, 153, 151, 92),
            "peg": (211, 211, 205, 255),
            "peg_core": (193, 194, 189, 255),
        },
        "dark": {
            "canvas": (15, 16, 21, 255),
            "board": (42, 44, 52, 255),
            "grid": (102, 105, 116, 58),
            "grid_major": (130, 133, 145, 72),
            "peg": (56, 59, 68, 255),
            "peg_core": (30, 32, 38, 255),
        },
        "transparent": {
            "canvas": (0, 0, 0, 0),
            "board": (0, 0, 0, 0),
            "grid": (0, 0, 0, 0),
            "grid_major": (0, 0, 0, 0),
            "peg": (0, 0, 0, 0),
            "peg_core": (0, 0, 0, 0),
        },
    }
    style = styles[config.board_style]
    canvas = Image.new("RGBA", canvas_size, style["canvas"])
    board_box = (
        outer_margin,
        outer_margin,
        outer_margin + board_width,
        outer_margin + board_height,
    )
    corner = max(8, display_size) * antialias

    if config.board_style != "transparent":
        shadow = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_offset = max(3, display_size // 3) * antialias
        shadow_draw.rounded_rectangle(
            (
                board_box[0] + shadow_offset,
                board_box[1] + shadow_offset,
                board_box[2] + shadow_offset,
                board_box[3] + shadow_offset,
            ),
            radius=corner,
            fill=(0, 0, 0, 135),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(7 * antialias))
        canvas.alpha_composite(shadow)
        ImageDraw.Draw(canvas).rounded_rectangle(
            board_box,
            radius=corner,
            fill=style["board"],
            outline=(255, 255, 255, 30),
            width=max(1, antialias),
        )

    draw = ImageDraw.Draw(canvas, "RGBA")
    grid_left = outer_margin + board_padding
    grid_top = outer_margin + board_padding
    grid_right = grid_left + cols * cell
    grid_bottom = grid_top + rows * cell
    if config.board_style != "transparent":
        for col in range(cols + 1):
            x = grid_left + col * cell
            color = style["grid_major"] if col % 5 == 0 else style["grid"]
            draw.line((x, grid_top, x, grid_bottom), fill=color, width=antialias)
        for row in range(rows + 1):
            y = grid_top + row * cell
            color = style["grid_major"] if row % 5 == 0 else style["grid"]
            draw.line((grid_left, y, grid_right, y), fill=color, width=antialias)

    bead_shadow = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    bead_shadow_draw = ImageDraw.Draw(bead_shadow, "RGBA")
    bead_radius = cell * 0.43
    shadow_offset = max(1, round(display_size * 0.10)) * antialias
    peg_radius = cell * 0.095
    for row in range(rows):
        for col in range(cols):
            center_x = grid_left + (col + 0.5) * cell
            center_y = grid_top + (row + 0.5) * cell
            color_index = color_indices[row][col]
            if color_index is None:
                if config.board_style != "transparent":
                    draw.ellipse(
                        (
                            center_x - peg_radius,
                            center_y - peg_radius,
                            center_x + peg_radius,
                            center_y + peg_radius,
                        ),
                        fill=style["peg"],
                        outline=style["peg_core"],
                        width=max(1, antialias),
                    )
                continue
            bead_shadow_draw.ellipse(
                (
                    center_x - bead_radius + shadow_offset,
                    center_y - bead_radius + shadow_offset,
                    center_x + bead_radius + shadow_offset,
                    center_y + bead_radius + shadow_offset,
                ),
                fill=(0, 0, 0, 118),
            )
    bead_shadow = bead_shadow.filter(ImageFilter.GaussianBlur(1.2 * antialias))
    canvas.alpha_composite(bead_shadow)
    draw = ImageDraw.Draw(canvas, "RGBA")

    hole_fill = (
        (*style["board"][:3], 255)
        if config.board_style != "transparent"
        else (0, 0, 0, 0)
    )
    for row in range(rows):
        for col in range(cols):
            color_index = color_indices[row][col]
            if color_index is None:
                continue
            center_x = grid_left + (col + 0.5) * cell
            center_y = grid_top + (row + 0.5) * cell
            rgb = tuple(
                np.clip(np.rint(palette[color_index - 1] * 255), 0, 255).astype(
                    np.uint8
                )
            )
            outer = _blend_rgb(rgb, (0, 0, 0), 0.28)
            inner_ring = _blend_rgb(rgb, (255, 255, 255), 0.15)
            hole_edge = _blend_rgb(rgb, (0, 0, 0), 0.42)
            draw.ellipse(
                (
                    center_x - bead_radius,
                    center_y - bead_radius,
                    center_x + bead_radius,
                    center_y + bead_radius,
                ),
                fill=outer,
            )
            body_radius = bead_radius * 0.90
            draw.ellipse(
                (
                    center_x - body_radius,
                    center_y - body_radius,
                    center_x + body_radius,
                    center_y + body_radius,
                ),
                fill=rgb,
            )
            hole_radius = bead_radius * 0.29
            draw.ellipse(
                (
                    center_x - hole_radius,
                    center_y - hole_radius,
                    center_x + hole_radius,
                    center_y + hole_radius,
                ),
                fill=inner_ring,
            )
            hole_inner = hole_radius * 0.66
            draw.ellipse(
                (
                    center_x - hole_inner,
                    center_y - hole_inner,
                    center_x + hole_inner,
                    center_y + hole_inner,
                ),
                fill=hole_edge,
            )
            hole_core = hole_inner * 0.62
            draw.ellipse(
                (
                    center_x - hole_core,
                    center_y - hole_core,
                    center_x + hole_core,
                    center_y + hole_core,
                ),
                fill=hole_fill,
            )
            if config.finish == "glossy":
                highlight_radius = bead_radius * 0.16
                highlight_x = center_x - bead_radius * 0.42
                highlight_y = center_y - bead_radius * 0.42
                draw.ellipse(
                    (
                        highlight_x - highlight_radius,
                        highlight_y - highlight_radius,
                        highlight_x + highlight_radius,
                        highlight_y + highlight_radius,
                    ),
                    fill=(255, 255, 255, 112),
                )
                draw.arc(
                    (
                        center_x - body_radius * 0.88,
                        center_y - body_radius * 0.88,
                        center_x + body_radius * 0.88,
                        center_y + body_radius * 0.88,
                    ),
                    205,
                    330,
                    fill=(0, 0, 0, 42),
                    width=max(1, antialias),
                )

    output = canvas.resize(
        (canvas.width // antialias, canvas.height // antialias),
        Image.Resampling.LANCZOS,
    )
    output.save(path)


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
    background_indices=None,
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
    background_indices = background_indices or [
        [None for _ in range(cols)] for _ in range(rows)
    ]
    for row in range(rows):
        for col in range(cols):
            character = glyphs[int(selected[row, col])]["character"]
            glyph = glyphs[int(selected[row, col])]
            color_index = color_indices[row][col]
            background_index = background_indices[row][col]
            if background_index is not None:
                background_rgb = tuple(
                    np.clip(
                        np.rint(palette[background_index - 1] * 255), 0, 255
                    ).astype(np.uint8)
                )
                draw.rectangle(
                    (
                        margin + col * cell_width,
                        margin + row * cell_height,
                        margin + (col + 1) * cell_width - 1,
                        margin + (row + 1) * cell_height - 1,
                    ),
                    fill=background_rgb,
                )
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
    target_density = source.get("cell_density")
    generated_density = np.asarray(
        [
            [glyphs[int(selected[row, col])]["density"] for col in range(cols)]
            for row in range(rows)
        ],
        dtype=np.float32,
    )
    if target_density is None:
        tone_rmse = multiscale_error = 0.0
    else:
        kernel = np.full((3, 3), 1 / 9, dtype=np.float32)
        tone_rmse = float(np.sqrt(np.mean((target_density - generated_density) ** 2)))
        errors = [tone_rmse]
        target_level = target_density
        generated_level = generated_density
        for _ in range(2):
            target_level = convolve3(target_level, kernel)
            generated_level = convolve3(generated_level, kernel)
            errors.append(
                float(np.sqrt(np.mean((target_level - generated_level) ** 2)))
            )
        multiscale_error = float(np.average(errors, weights=(0.5, 0.3, 0.2)))
    return {
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "chamfer": chamfer,
        "tone_rmse": tone_rmse,
        "multiscale_error": multiscale_error,
    }


def write_debug(
    debug_dir, source, glyphs, selected, cols, rows, cell_width, cell_height
):
    debug_dir.mkdir(parents=True, exist_ok=True)
    if "bead_mask" in source:
        Image.fromarray(np.uint8(np.clip(source["subject_coverage"], 0, 1) * 255)).save(
            debug_dir / "subject-coverage.png"
        )
        Image.fromarray(np.uint8(source["bead_mask"] * 255)).save(
            debug_dir / "bead-mask.png"
        )
        return
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
    Image.fromarray(
        np.uint8(np.clip(source["visual_density"] / 0.48, 0, 1) * 255)
    ).save(debug_dir / "visual-density.png")
    reconstruction = np.zeros_like(source["edge"])
    for row in range(rows):
        for col in range(cols):
            y0, y1 = row * cell_height, (row + 1) * cell_height
            x0, x1 = col * cell_width, (col + 1) * cell_width
            reconstruction[y0:y1, x0:x1] = glyphs[int(selected[row, col])]["skeleton"]
    Image.fromarray(np.uint8(reconstruction * 255)).save(debug_dir / "glyph-edges.png")
    density_reconstruction = np.zeros_like(source["visual_density"])
    for row in range(rows):
        for col in range(cols):
            y0, y1 = row * cell_height, (row + 1) * cell_height
            x0, x1 = col * cell_width, (col + 1) * cell_width
            density_reconstruction[y0:y1, x0:x1] = glyphs[int(selected[row, col])][
                "mask"
            ]
    Image.fromarray(np.uint8(np.clip(density_reconstruction, 0, 1) * 255)).save(
        debug_dir / "glyph-density.png"
    )


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
    if not 0.1 <= config.zoom <= 4:
        raise ValueError("zoom must be between 0.1 and 4")
    if not 1 <= config.colors <= 8:
        raise ValueError("block colors must be between 1 and 8")
    if not 0 <= config.subject_threshold <= 1 or not 0 <= config.ink_threshold <= 1:
        raise ValueError("block thresholds must be between 0 and 1")

    source = prepare_block_source(source_path, config)
    pixels = source["block_pixels"]
    top = pixels[0::2].astype(np.int16)
    bottom = pixels[1::2].astype(np.int16)
    selected = top + bottom * 2
    glyphs = block_glyphs(config.cell_width, config.cell_height)

    pixel_color_indices = np.zeros_like(pixels, dtype=np.int16)
    if config.colors == 1:
        palette = np.asarray([parse_hex_color(config.foreground)], dtype=np.float32)
        pixel_color_indices[pixels] = 1
    else:
        palette, active_assignments = quantize_block_colors(
            source["pixel_rgb"][pixels], config.colors
        )
        pixel_color_indices[pixels] = active_assignments + 1

    top_colors = pixel_color_indices[0::2]
    bottom_colors = pixel_color_indices[1::2]
    mixed = (top > 0) & (bottom > 0) & (top_colors != bottom_colors)
    selected[mixed] = 1
    foreground = np.where(top > 0, top_colors, bottom_colors)
    background = np.where(mixed, bottom_colors, 0)
    color_indices = [
        [
            None if foreground[row, col] == 0 else int(foreground[row, col])
            for col in range(config.cols)
        ]
        for row in range(config.rows)
    ]
    background_indices = [
        [
            None if background[row, col] == 0 else int(background[row, col])
            for col in range(config.cols)
        ]
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
        background_indices=background_indices,
    )


def render_beads(source_path, config=None):
    config = config or BeadConfig()
    if config.cols < 1 or config.rows < 1:
        raise ValueError("cols and rows must be positive")
    if config.cols > 2048 or config.rows > 2048:
        raise ValueError("bead cols and rows must not exceed 2048")
    if config.oversample < 2:
        raise ValueError("oversample must be at least 2")
    if config.fit not in {"contain", "cover"}:
        raise ValueError(f"unsupported bead fit: {config.fit}")
    if config.background not in {"auto", "keep"}:
        raise ValueError(f"unsupported bead background: {config.background}")
    if config.board_style not in {"light", "dark", "transparent"}:
        raise ValueError(f"unsupported bead board style: {config.board_style}")
    if config.finish not in {"glossy", "matte"}:
        raise ValueError(f"unsupported bead finish: {config.finish}")
    if not 0 <= config.focus_y <= 1:
        raise ValueError("focus_y must be between 0 and 1")
    if not 0.1 <= config.zoom <= 4:
        raise ValueError("zoom must be between 0.1 and 4")
    if not 0 <= config.subject_threshold <= 1:
        raise ValueError("bead subject_threshold must be between 0 and 1")
    if not 2 <= config.colors <= 128:
        raise ValueError("bead colors must be between 2 and 128")
    if not 4 <= config.bead_size <= 24:
        raise ValueError("bead_size must be between 4 and 24")
    if "\n" in config.chart_title or "\r" in config.chart_title:
        raise ValueError("chart title must be one line")
    if len(config.chart_title) > 160:
        raise ValueError("chart title must be at most 160 characters")
    if not 12 <= config.chart_cell_size <= 32:
        raise ValueError("chart_cell_size must be between 12 and 32")

    source = prepare_bead_source(source_path, config)
    beads = source["bead_mask"]
    selected = beads.astype(np.int16)
    glyphs = bead_glyphs()
    palette, assignments = quantize_bead_colors(
        source["pixel_rgb"][beads], config.colors
    )
    indices = np.zeros_like(selected, dtype=np.int16)
    indices[beads] = assignments + 1
    color_indices = [
        [
            None if indices[row, col] == 0 else int(indices[row, col])
            for col in range(config.cols)
        ]
        for row in range(config.rows)
    ]
    bead_count = int(beads.sum())
    metrics = {
        "bead_count": bead_count,
        "empty_cells": int(beads.size - bead_count),
        "occupancy_ratio": float(beads.mean()),
        "preview_bead_size": bead_preview_size(config),
        "effective_oversample": source["effective_oversample"],
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
    if config.profile not in {"outline", "hybrid", "tone"}:
        raise ValueError(f"unsupported glyph profile: {config.profile}")
    if config.fill_mode not in {"auto", "none", "salient", "tone"}:
        raise ValueError(f"unsupported fill mode: {config.fill_mode}")
    if config.color_mode not in {"color", "mono"}:
        raise ValueError(f"unsupported glyph color mode: {config.color_mode}")
    if config.line_renderer not in {"sprite", "font"}:
        raise ValueError(f"unsupported line renderer: {config.line_renderer}")
    if config.cols < 1 or config.rows < 1:
        raise ValueError("cols and rows must be positive")
    if (
        min(
            config.shape_weight,
            config.tone_weight,
            config.color_weight,
            config.texture_weight,
            config.global_weight,
        )
        < 0
    ):
        raise ValueError("glyph feature weights must be non-negative")

    glyph_set = resolve_glyph_set(
        config.character_preset, config.symbols, config.fill_symbols
    )

    _, glyphs = render_glyphs(
        font_path,
        fallback_font_path,
        config.font_size,
        config.cell_width,
        config.cell_height,
        config.line_renderer,
        glyph_set.characters,
        glyph_set.structure,
        glyph_set.fill,
    )
    if len(glyphs) <= 1:
        raise ValueError(
            "the selected fonts contain none of the requested visible glyphs"
        )
    source = prepare_source(
        source_path,
        config.cols,
        config.rows,
        config.cell_width,
        config.cell_height,
    )
    choices, local_scores = local_candidates(source, glyphs, config)
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
        config.global_weight if config.profile != "outline" else 0.0,
    )
    resolved_fill_mode = resolve_fill_mode(config.profile, config.fill_mode)
    if config.color_mode == "mono":
        palette = np.asarray([parse_hex_color(config.monochrome_color)])
        color_indices = [
            [None if selected[row, col] == 0 else 1 for col in range(config.cols)]
            for row in range(config.rows)
        ]
        background_indices = [
            [None for _ in range(config.cols)] for _ in range(config.rows)
        ]
    else:
        cell_colors, cell_backgrounds, colors = sample_colors(
            source,
            glyphs,
            selected,
            config.cols,
            config.rows,
            config.cell_width,
            config.cell_height,
            config.profile,
            resolved_fill_mode,
        )
        palette = kmeans(colors, config.colors, config.minimum_luminance)
        color_indices = assign_palette(cell_colors, palette, config.cols, config.rows)
        background_indices = assign_palette(
            cell_backgrounds, palette, config.cols, config.rows
        )
    metrics = structural_metrics(
        source,
        glyphs,
        selected,
        config.cols,
        config.rows,
        config.cell_width,
        config.cell_height,
    )
    metrics.update(
        {
            "profile": config.profile,
            "color_mode": config.color_mode,
            "character_preset": config.character_preset,
            "fill_mode": resolved_fill_mode,
            "available_glyphs": len(glyphs) - 1,
            "excluded_glyphs": len(glyph_set.excluded)
            + len(glyph_set.characters)
            - len(glyphs),
        }
    )
    return RenderResult(
        glyphs=glyphs,
        selected=selected,
        palette=palette,
        color_indices=color_indices,
        source=source,
        metrics=metrics,
        config=config,
        background_indices=background_indices,
    )

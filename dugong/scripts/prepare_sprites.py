from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import imageio.v3 as iio
import numpy as np
from PIL import Image, ImageSequence


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
ANIM_EXTS = {".gif", ".webp", ".apng"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare stable dugong sprite frames from generated media.")
    parser.add_argument("--input", required=True, help="Input directory (frames) or single file (gif/webp/mp4).")
    parser.add_argument("--output", required=True, help="Output directory for PNG sprites.")
    parser.add_argument("--count", type=int, default=8, help="Target output frame count.")
    parser.add_argument("--canvas", type=int, default=512, help="Output canvas size (square).")
    parser.add_argument("--prefix", default="dugong_swim_right", help="Output filename prefix.")
    parser.add_argument("--bg-key", default="00ff00", help="Background key color hex, e.g. 00ff00 or ff00ff.")
    parser.add_argument("--tol", type=int, default=36, help="Color tolerance for keying (0-255).")
    parser.add_argument("--subject-ratio", type=float, default=0.72, help="Max subject size ratio in canvas.")
    parser.add_argument("--mirror", action="store_true", help="Also export mirrored left-facing frames.")
    return parser.parse_args()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) != 6:
        raise ValueError(f"Invalid hex color: {value}")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def load_frames(input_path: Path) -> list[np.ndarray]:
    if input_path.is_dir():
        files = sorted(p for p in input_path.iterdir() if p.suffix.lower() in IMAGE_EXTS)
        if not files:
            raise RuntimeError(f"No image files found in directory: {input_path}")
        return [np.array(Image.open(p).convert("RGBA")) for p in files]

    ext = input_path.suffix.lower()
    if ext in ANIM_EXTS:
        im = Image.open(input_path)
        return [np.array(frame.convert("RGBA")) for frame in ImageSequence.Iterator(im)]

    if ext in IMAGE_EXTS:
        return [np.array(Image.open(input_path).convert("RGBA"))]

    if ext in VIDEO_EXTS:
        try:
            frames = iio.imread(input_path)
            if frames.ndim == 4:
                out: list[np.ndarray] = []
                for frame in frames:
                    if frame.shape[-1] == 3:
                        alpha = np.full((frame.shape[0], frame.shape[1], 1), 255, dtype=np.uint8)
                        frame = np.concatenate([frame, alpha], axis=2)
                    out.append(frame.astype(np.uint8))
                return out
        except Exception as exc:
            raise RuntimeError(
                f"Cannot decode video file '{input_path}'. Install ffmpeg or export frames/GIF first. Error: {exc}"
            ) from exc

    raise RuntimeError(f"Unsupported input type: {input_path}")


def key_out_background(frame: np.ndarray, key_rgb: tuple[int, int, int], tol: int) -> np.ndarray:
    out = frame.copy()
    rgb = out[:, :, :3].astype(np.int16)
    key = np.array(key_rgb, dtype=np.int16).reshape(1, 1, 3)
    dist = np.sqrt(np.sum((rgb - key) ** 2, axis=2))
    mask = dist <= max(0, int(tol))
    out[mask, 3] = 0
    return out


def alpha_bbox(frame: np.ndarray) -> tuple[int, int, int, int] | None:
    alpha = frame[:, :, 3]
    ys, xs = np.where(alpha > 0)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def crop_to_alpha(frame: np.ndarray) -> np.ndarray:
    box = alpha_bbox(frame)
    if box is None:
        return frame
    x0, y0, x1, y1 = box
    return frame[y0:y1, x0:x1]


def resize_keep_aspect(img: np.ndarray, target_max: int) -> np.ndarray:
    h, w = img.shape[:2]
    scale = min(1.0 if max(h, w) <= target_max else target_max / max(h, w), 10.0)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    pil = Image.fromarray(img, mode="RGBA").resize((new_w, new_h), Image.Resampling.LANCZOS)
    return np.array(pil)


def paste_center(canvas_size: int, fg: np.ndarray, center: tuple[int, int]) -> np.ndarray:
    canvas = np.zeros((canvas_size, canvas_size, 4), dtype=np.uint8)
    cx, cy = center
    h, w = fg.shape[:2]
    x0 = int(round(cx - w / 2))
    y0 = int(round(cy - h / 2))
    x1 = min(canvas_size, x0 + w)
    y1 = min(canvas_size, y0 + h)
    sx0 = max(0, -x0)
    sy0 = max(0, -y0)
    x0 = max(0, x0)
    y0 = max(0, y0)
    if x0 >= x1 or y0 >= y1:
        return canvas
    patch = fg[sy0 : sy0 + (y1 - y0), sx0 : sx0 + (x1 - x0)]
    alpha = patch[:, :, 3:4].astype(np.float32) / 255.0
    base = canvas[y0:y1, x0:x1].astype(np.float32)
    comp = patch.astype(np.float32)
    out = comp * alpha + base * (1 - alpha)
    canvas[y0:y1, x0:x1] = out.astype(np.uint8)
    return canvas


def evenly_sample(frames: list[np.ndarray], count: int) -> list[np.ndarray]:
    if not frames:
        return []
    if count <= 0:
        return frames
    if len(frames) <= count:
        return frames
    idxs = np.linspace(0, len(frames) - 1, count, dtype=int)
    return [frames[i] for i in idxs]


def process_frames(
    frames: list[np.ndarray],
    key_rgb: tuple[int, int, int],
    tol: int,
    canvas: int,
    count: int,
    subject_ratio: float,
) -> list[np.ndarray]:
    keyed = [key_out_background(f, key_rgb=key_rgb, tol=tol) for f in frames]
    sampled = evenly_sample(keyed, count=count)
    cropped = [crop_to_alpha(f) for f in sampled]

    target_max = max(1, int(round(canvas * max(0.1, min(1.0, subject_ratio)))))
    resized = [resize_keep_aspect(f, target_max=target_max) for f in cropped]

    centers_x = []
    centers_y = []
    for f in resized:
        h, w = f.shape[:2]
        centers_x.append(w / 2)
        centers_y.append(h / 2)
    target_center = (canvas // 2, canvas // 2)

    out = [paste_center(canvas_size=canvas, fg=f, center=target_center) for f in resized]
    return out


def save_frames(frames: Iterable[np.ndarray], out_dir: Path, prefix: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for i, frame in enumerate(frames, start=1):
        path = out_dir / f"{prefix}_{i:02d}.png"
        Image.fromarray(frame, mode="RGBA").save(path)
        saved.append(path)
    return saved


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    key_rgb = hex_to_rgb(args.bg_key)

    frames = load_frames(input_path)
    processed = process_frames(
        frames=frames,
        key_rgb=key_rgb,
        tol=args.tol,
        canvas=args.canvas,
        count=args.count,
        subject_ratio=args.subject_ratio,
    )
    saved = save_frames(processed, output_dir, args.prefix)

    if args.mirror:
        mirrored = [np.ascontiguousarray(f[:, ::-1, :]) for f in processed]
        left_prefix = args.prefix.replace("_right", "_left")
        if left_prefix == args.prefix:
            left_prefix = f"{args.prefix}_left"
        save_frames(mirrored, output_dir, left_prefix)

    print(f"saved_frames={len(saved)} output={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

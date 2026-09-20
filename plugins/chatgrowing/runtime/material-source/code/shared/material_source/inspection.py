"""Local media validation only; no file store, identity, or business state."""
from __future__ import annotations
from pathlib import Path
import shutil
import subprocess
import json
import math
from .protocol import MaterialError

class FFmpegVideoInspector:
    def __init__(self, *, ffprobe: str = "ffprobe", ffmpeg: str = "ffmpeg"):
        self.ffprobe = ffprobe
        self.ffmpeg = ffmpeg

    def inspect(self, path: Path) -> tuple[int, int, float]:
        if not shutil.which(self.ffprobe) or not shutil.which(self.ffmpeg):
            raise MaterialError("material_video_inspector_unavailable", 503)
        try:
            result = subprocess.run([
                self.ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format", "-show_streams",
                "-of", "json", str(path),
            ], capture_output=True, timeout=45, check=True)
            parsed = json.loads(result.stdout)
            if "mp4" not in parsed.get("format", {}).get("format_name", "").split(","):
                raise ValueError("format")
            stream = next(s for s in parsed["streams"] if s.get("codec_type") == "video")
            width, height = int(stream["width"]), int(stream["height"])
            duration = float(parsed["format"]["duration"])
            if width <= 0 or height <= 0 or not math.isfinite(duration) or duration <= 0:
                raise ValueError("dimensions")
            # Container metadata alone does not establish that the video can decode.
            subprocess.run([
                self.ffmpeg, "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode",
                "-protocol_whitelist", "file,pipe", "-i", str(path),
                "-map", "0:v:0", "-an", "-f", "null", "-",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300, check=True)
            return width, height, duration
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, StopIteration, TypeError):
            raise MaterialError("material_video_invalid", 422) from None

    def thumbnail(self, path: Path, output: Path) -> None:
        if not shutil.which(self.ffmpeg):
            raise MaterialError("material_thumbnail_processor_unavailable", 503)
        try:
            subprocess.run([
                self.ffmpeg, "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe", "-i", str(path),
                "-frames:v", "1", "-vf", "scale=480:-2", "-y", str(output),
            ], capture_output=True, timeout=45, check=True)
        except (OSError, subprocess.SubprocessError):
            raise MaterialError("material_thumbnail_failed", 422) from None


def inspect_image(path, suffix):
    from PIL import Image
    import warnings
    formats = {'.jpeg': ('JPEG', 'image/jpeg'), '.jpg': ('JPEG', 'image/jpeg'), '.png': ('PNG', 'image/png'), '.webp': ('WEBP', 'image/webp')}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.format != formats[suffix][0] or getattr(image, 'is_animated', False) or image.width * image.height > 40_000_000:
                    raise ValueError()
                image.verify()
            with Image.open(path) as image:
                image.load()
                return image.width, image.height, formats[suffix][1]
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise MaterialError('material_image_invalid', 422) from None

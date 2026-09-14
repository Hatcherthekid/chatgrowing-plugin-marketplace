"""本地私有文件适配器。对象 key 由服务端生成，拒绝路径与覆盖写入。"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from collections import OrderedDict
from threading import Lock
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import BinaryIO, Protocol
from uuid import uuid4

from domains.ads.contracts.material_library import MaterialError


@dataclass(frozen=True)
class FileDescriptor:
    sha256: str
    byte_size: int
    width: int
    height: int
    duration: float | None
    mime: str = "video/mp4"


class VideoInspector(Protocol):
    def inspect(self, path: Path) -> tuple[int, int, float]: ...
    def thumbnail(self, path: Path, output: Path) -> None: ...


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


class LocalMaterialFileStore:
    _key = re.compile(r"^[0-9a-f]{64}/file_[0-9a-f]{32}\.(?:mp4|jpg|jpeg|png|webp)$")

    def __init__(self, root: str | Path, *, inspector: VideoInspector | None = None):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.inspector = inspector or FFmpegVideoInspector()
        self._inspection_cache = OrderedDict()
        self._inspection_cache_lock = Lock()

    def _remember_inspection(self, sha256, metadata):
        with self._inspection_cache_lock:
            self._inspection_cache[sha256] = metadata
            self._inspection_cache.move_to_end(sha256)
            while len(self._inspection_cache) > 64:
                self._inspection_cache.popitem(last=False)

    @staticmethod
    def key(org: str, file_id: str, *, thumbnail: bool = False, extension: str = "mp4") -> str:
        folder = hashlib.sha256(org.encode()).hexdigest()
        return f"{folder}/{file_id}.{'jpg' if thumbnail else extension}"

    def path(self, key: str) -> Path:
        if not self._key.fullmatch(key):
            raise MaterialError("material_object_key_invalid", 422)
        path = self.root / key
        if not path.resolve().is_relative_to(self.root) or path.is_symlink() or path.parent.is_symlink():
            raise MaterialError("material_object_path_invalid", 403)
        return path

    @contextmanager
    def mutation_lock(self, key: str):
        self.path(key)
        root = self.root / ".mutation-locks"
        root.mkdir(mode=0o700, exist_ok=True)
        lock_name = hashlib.sha256(key.rsplit(".", 1)[0].encode()).hexdigest()
        from .material_execution_locks import exclusive
        try:
            with exclusive(root / lock_name):
                self._remove_temporaries(key)
                yield
        except MaterialError as exc:
            if exc.code == 'material_worker_busy':
                raise MaterialError('material_file_busy',409) from None
            raise

    def _remove_temporaries(self, key: str) -> None:
        path = self.path(key)
        stem = path.stem
        pattern = re.compile(r"^\." + re.escape(stem) + r"\.(?:(?:mp4|jpg|jpeg|png|webp)\.[0-9a-f]{32}\.tmp|jpg\.[0-9a-f]{32}\.tmp\.jpg)$")
        if path.parent.exists():
            for candidate in path.parent.iterdir():
                if pattern.fullmatch(candidate.name):
                    candidate.unlink(missing_ok=True)

    def put(self, key: str, source: BinaryIO, *, expected_bytes: int) -> FileDescriptor:
        path = self.path(key)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        hasher, total = hashlib.sha256(), 0
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as output:
                while True:
                    chunk = source.read(min(1024 * 1024, expected_bytes - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > expected_bytes:
                        raise MaterialError("material_file_size_mismatch", 422)
                    hasher.update(chunk)
                    output.write(chunk)
                if total != expected_bytes:
                    raise MaterialError("material_file_size_mismatch", 422)
                output.flush()
                os.fsync(output.fileno())
            if path.suffix in ('.jpg', '.jpeg', '.png', '.webp'):
                width, height, mime = self._inspect_image(temporary, path.suffix)
                duration = None
            else:
                mime = 'video/mp4'
                with temporary.open("rb") as probe:
                    header = probe.read(12)
                    if len(header) < 12 or header[4:8] != b"ftyp":
                        raise MaterialError("material_video_invalid", 422)
                width, height, duration = self.inspector.inspect(temporary)
                self._remember_inspection(hasher.hexdigest(), (width, height, duration))
            try:
                os.link(temporary, path)  # Atomic create only; never replace an audited object.
            except FileExistsError:
                raise MaterialError("material_file_already_stored") from None
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory_fd)
            finally: os.close(directory_fd)
            return FileDescriptor(hasher.hexdigest(), total, width, height, duration, mime)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _inspect_image(path, suffix):
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

    def describe(self, key: str) -> FileDescriptor:
        return self.describe_path(self.path(key))

    def describe_path(self, path: Path) -> FileDescriptor:
        if not path.is_file():
            raise MaterialError("material_file_missing", 404)
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        # Hash every byte on every verification. Only decoder results for that
        # exact content are cached; file path, mtime or size cannot grant a hit.
        content_hash = hasher.hexdigest()
        if path.suffix in ('.jpg', '.jpeg', '.png', '.webp'):
            width, height, mime = self._inspect_image(path, path.suffix)
            return FileDescriptor(content_hash, path.stat().st_size, width, height, None, mime)
        with self._inspection_cache_lock:
            metadata = self._inspection_cache.get(content_hash)
        if metadata is None:
            metadata = self.inspector.inspect(path)
            self._remember_inspection(content_hash, metadata)
        width, height, duration = metadata
        return FileDescriptor(hasher.hexdigest(), path.stat().st_size, width, height, duration)

    def thumbnail(self, source_key: str, target_key: str) -> None:
        target = self.path(target_key)
        if target.exists():
            return
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp.jpg")
        try:
            if self.path(source_key).suffix in ('.jpg', '.jpeg', '.png', '.webp'):
                from PIL import Image, ImageOps
                self._inspect_image(self.path(source_key), self.path(source_key).suffix)
                with Image.open(self.path(source_key)) as image:
                    image = ImageOps.exif_transpose(image).convert('RGB')
                    image.thumbnail((480, 480))
                    image.save(temporary, format='JPEG')
            else:
                self.inspector.thumbnail(self.path(source_key), temporary)
            temporary.chmod(0o600)
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

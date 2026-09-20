# Managed local runtime

The installer downloads, rather than compiles, third-party runtime components into a ChatGrowing-only user directory. Each executable download is pinned by URL and SHA-256 in downloads.tsv; Python package versions and hashes are locked in requirements.lock. No Homebrew, sudo, system Python or global PATH changes are used.

- uv 0.12.17: https://github.com/astral-sh/uv (MIT/Apache-2.0). Its pinned managed Python catalog supplies CPython 3.11.14 via python-build-standalone, including upstream runtime licenses.
- FFmpeg/FFprobe b6.1.1 binaries: https://github.com/eugeneware/ffmpeg-static/releases/tag/b6.1.1 . Per-platform upstream LICENSE and README are downloaded and checksum-verified into the runtime notices directory. Consult those files for the binary build license, build provenance and source information.
- Python package licenses accompany the installed wheels. The helper uses a private environment, not the host's Python site-packages.

macOS arm64 and x86_64 have pinned artifacts. A listed artifact does not establish testing on every macOS release. No Windows/Linux automatic installer is claimed by this manifest.

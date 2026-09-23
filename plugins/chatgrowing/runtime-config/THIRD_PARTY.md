# Managed local runtime

The default local intake helper is distributed as a complete, versioned Python
runtime bundle from `https://chatgrowing.com/downloads/material-runtime/`. The
plugin pins the exact archive SHA-256 in `bundles.tsv`; setup refuses redirects
and checks the digest before extracting. Users do not need GitHub, PyPI,
Homebrew, Xcode, system Python, or local FFmpeg for server intake. The bundle
contains CPython 3.11.14 from python-build-standalone and wheel dependencies
from `requirements.lock` (arm64) or `requirements-x86_64.lock` (Intel; pins
cryptography 45 because version 50 publishes no Intel macOS wheel). Their
license files are kept in the archive. It is
built on the target architecture and has no ChatGrowing server code or secrets.

`downloads.tsv` documents the older, FFmpeg-based direct transfer runtime.
That path is retained only for compatibility; it is not used by the default
local intake setup. The FFmpeg binaries and notices are not in the new bundle.

The installer downloads, rather than compiles, third-party runtime components into a ChatGrowing-only user directory. Each executable download is pinned by URL and SHA-256 in downloads.tsv; Python package versions and hashes are locked in requirements.lock. No Homebrew, sudo, system Python or global PATH changes are used.

- uv 0.12.17: https://github.com/astral-sh/uv (MIT/Apache-2.0). Its pinned managed Python catalog supplies CPython 3.11.14 via python-build-standalone, including upstream runtime licenses.
- FFmpeg/FFprobe b6.1.1 binaries: https://github.com/eugeneware/ffmpeg-static/releases/tag/b6.1.1 . Per-platform upstream LICENSE and README are downloaded and checksum-verified into the runtime notices directory. Consult those files for the binary build license, build provenance and source information.
- Python package licenses accompany the installed wheels. The helper uses a private environment, not the host's Python site-packages.

macOS arm64 and x86_64 have pinned artifacts. A listed artifact does not establish testing on every macOS release. No Windows/Linux automatic installer is claimed by this manifest.

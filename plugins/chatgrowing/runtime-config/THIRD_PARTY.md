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

The installer downloads the pinned complete bundle into a ChatGrowing-only user directory. No Homebrew, sudo, system Python or global PATH changes are used. Python package licenses accompany the installed wheels; the helper uses a private environment, not the host's Python site-packages. Legacy remote-reference support for images does not make FFmpeg part of this runtime.

macOS arm64 and x86_64 have pinned artifacts. A listed artifact does not establish testing on every macOS release. No Windows/Linux automatic installer is claimed by this manifest.

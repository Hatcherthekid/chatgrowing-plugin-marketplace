#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin_root="$(cd "${script_dir}/.." && pwd)"
runtime_root="${plugin_root}/runtime/material-source"
venv_root="${CODEX_HOME:-${HOME}/.codex}/chatgrowing/material-source-venv"
staging="${venv_root}.staging.$$"
[[ -f "${runtime_root}/requirements.txt" ]] || { printf '%s\n' 'Packaged material runtime is missing.' >&2; exit 78; }
trap 'rm -rf "${staging}"' EXIT
python3 -m venv "${staging}"
"${staging}/bin/python" -m pip install --disable-pip-version-check --requirement "${runtime_root}/requirements.txt"
rm -rf "${venv_root}"
mkdir -p "$(dirname "${venv_root}")"
mv "${staging}" "${venv_root}"
trap - EXIT
printf '%s\n' 'ChatGrowing local material runtime installed.'

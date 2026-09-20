#!/bin/bash
# Read-only macOS/Linux install diagnostics. No network, credentials or config writes.
set -u

codex_hint=''
git_hint=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --codex|--git)
      if [ "$#" -lt 2 ] || [ "${2#/}" = "$2" ]; then
        printf '%s\n' 'usage: bash preflight.sh [--codex /absolute/path] [--git /absolute/path]' >&2
        exit 2
      fi
      if [ "$1" = '--codex' ]; then codex_hint="$2"; else git_hint="$2"; fi
      shift 2 ;;
    *) printf '%s\n' 'unknown argument' >&2; exit 2 ;;
  esac
done

platform=$(uname -s)
printf 'platform=%s\n' "$platform"
codex_path=''
cli_failed=0
git_failed=0
apple_git_skipped=0
# Emit only bounded, known error categories; raw stderr may contain secrets.
failure() {
  local kind="$1" candidate="$2" code="$3" output="$4" reason='execution_failed'
  case "$output" in
    *'Permission denied'*|*'Operation not permitted'*) reason='permission_denied' ;;
    *'developer path'*|*'xcrun'*) reason='developer_tools_invalid' ;;
    *'Library not loaded'*|*'shared libraries'*|*'dyld:'*) reason='runtime_dependency_missing' ;;
  esac
  [ "$code" -eq 0 ] && reason='unexpected_version_output'
  printf '%s_candidate=%q\n%s_exit_code=%s\n%s_error=%s\n' "$kind" "$candidate" "$kind" "$code" "$kind" "$reason"
}
# Never choose an unrelated PATH CLI. An explicit path must be verified by the caller.
codex_candidates=("$codex_hint")
if [ -z "$codex_hint" ]; then
  codex_candidates=( \
  '/Applications/ChatGPT.app/Contents/Resources/codex' \
  '/Applications/Codex.app/Contents/Resources/codex' \
  "$HOME/Applications/ChatGPT.app/Contents/Resources/codex" \
  "$HOME/Applications/Codex.app/Contents/Resources/codex" )
fi
for candidate in "${codex_candidates[@]}"; do
  [ -n "$candidate" ] && [ -e "$candidate" ] || continue
  if [ ! -x "$candidate" ]; then
    cli_failed=1
    failure cli "$candidate" 126 'Permission denied'
    continue
  fi
  version=$("$candidate" --version 2>&1)
  code=$?
  if [ "$code" -eq 0 ] && [[ "$version" =~ (^|$'\n')codex-cli[[:space:]]([0-9][0-9A-Za-z.+_-]*)($|[[:space:]]) ]]; then
    codex_path="$candidate"
    # Warnings may precede the version; emit only the bounded version token.
    printf 'codex_path=%q\ncodex_version=%s\n' "$codex_path" "${BASH_REMATCH[2]:0:64}"
    break
  fi
  cli_failed=1
  failure cli "$candidate" "$code" "$version"
done

developer_tools='not_applicable'
if [ "$platform" = 'Darwin' ]; then
  developer_tools='unavailable'
  if xcode-select -p >/dev/null 2>&1; then developer_tools='configured'; fi
fi
printf 'developer_tools=%s\n' "$developer_tools"

git_path=''
try_git() {
  local candidate="$1" version code
  [ -n "$candidate" ] && [ -e "$candidate" ] || return 1
  if [ ! -x "$candidate" ]; then
    git_failed=1
    failure git "$candidate" 126 'Permission denied'
    return 1
  fi
  # Avoid launching Apple's CLT installation dialog during diagnosis.
  if [ "$platform" = 'Darwin' ] && [ "$developer_tools" = 'unavailable' ] \
    && { [ "$candidate" = '/usr/bin/git' ] || [ "$candidate" -ef '/usr/bin/git' ]; }; then
    apple_git_skipped=1
    printf 'git_candidate=%q\ngit_error=apple_clt_unavailable\n' "$candidate"
    return 1
  fi
  version=$("$candidate" --version 2>&1)
  code=$?
  if [ "$code" -eq 0 ] && [[ "$version" =~ (^|$'\n')git[[:space:]]version[[:space:]]([0-9][0-9A-Za-z.+_-]*)($|[[:space:]]) ]]; then
    git_path="$candidate"
    printf 'git_path=%q\ngit_version=%s\n' "$git_path" "${BASH_REMATCH[2]:0:64}"
    return 0
  fi
  git_failed=1
  failure git "$candidate" "$code" "$version"
  return 1
}

if [ -n "$git_hint" ]; then
  try_git "$git_hint" || true
else
  # Test each PATH entry: a broken Apple stub must not hide a working later Git.
  saved_ifs="$IFS"
  IFS=:
  read -r -a search_paths <<< "${PATH:-}"
  IFS="$saved_ifs"
  for directory in "${search_paths[@]}"; do
    # Ignore relative/current-directory executables.
    case "$directory" in /*) ;; *) continue ;; esac
    if try_git "$directory/git"; then break; fi
  done
fi
if [ -z "$git_path" ] && [ -z "$git_hint" ]; then
  for candidate in '/opt/homebrew/bin/git' '/usr/local/bin/git' \
    "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/bin/git"; do
    if try_git "$candidate"; then break; fi
  done
fi

if [ -z "$codex_path" ]; then
  if [ "$cli_failed" -eq 1 ]; then
    printf '%s\n' 'status=cli_execution_failed' 'next=diagnose_existing_cli_environment'
    exit 12
  fi
  printf '%s\n' 'status=cli_missing' 'next=locate_desktop_bundled_cli_then_rerun_with_--codex'
  exit 10
fi
# A version number alone does not prove rotating OAuth credentials are safe.
# Inspect only the named public feature; never load credentials or print config.
refresh_feature=$("$codex_path" features list 2>/dev/null | awk '$1 == "mcp_oauth_refresh_coordination" {print $NF; exit}')
case "$refresh_feature" in
  true) printf '%s\n' 'oauth_refresh_coordination=enabled' ;;
  false) printf '%s\n' 'oauth_refresh_coordination=disabled' 'oauth_next=enable_supported_host_refresh_coordination_before_login' ;;
  *) printf '%s\n' 'oauth_refresh_coordination=unverified' 'oauth_next=check_host_compatibility_not_repeated_login' ;;
esac
if [ -z "$git_path" ]; then
  if [ "$git_failed" -eq 1 ]; then
    printf '%s\n' 'status=git_execution_failed' 'next=diagnose_existing_git_environment'
    exit 13
  fi
  if [ "$apple_git_skipped" -eq 1 ]; then
    printf '%s\n' 'status=apple_clt_unavailable' 'next=use_reviewed_https_snapshot_installer'
    exit 14
  fi
  printf '%s\n' 'status=git_missing' 'next=use_reviewed_https_snapshot_installer'
  exit 11
fi
printf '%s\n' 'status=ready' 'scope=cli_and_git_only_not_network_oauth_or_query'

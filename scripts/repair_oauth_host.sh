#!/bin/bash
# Configure the verified desktop Host through its official CLI. Never touches OAuth credentials.
set -eu

codex=''
apply=false
mode=''
check_running=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --codex)
      [ "$#" -ge 2 ] || exit 2
      codex="$2"; shift 2 ;;
    --check|--apply)
      [ -z "$mode" ] || [ "$mode" = "$1" ] || exit 2
      mode="$1"
      [ "$mode" != --apply ] || apply=true
      shift ;;
    --check-running)
      check_running=true; shift ;;
    *) printf '%s\n' 'usage: repair_oauth_host.sh --codex /verified/desktop/codex [--check | --apply] [--check-running]' >&2; exit 2 ;;
  esac
done
case "$codex" in /*) ;; *) exit 2 ;; esac
[ -x "$codex" ] || { printf '%s\n' 'status=desktop_cli_unavailable'; exit 22; }

printf '%s\n' 'scope=executing_device_host_configuration' 'oauth_credentials=untouched' \
  'running_host_feature=not_verified' 'production_refresh_acceptance=not_verified'
if ! version_output=$("$codex" --version 2>/dev/null); then
  printf '%s\n' 'status=host_inspection_failed'; exit 22
fi
if [[ "$version_output" =~ (^|$'\n')codex-cli[[:space:]]([0-9][0-9A-Za-z.+_-]{0,63})($|[[:space:]]) ]]; then
  version="${BASH_REMATCH[2]}"
  printf 'codex_version=%s\n' "$version"
else
  printf '%s\n' 'status=host_version_unverified'; exit 22
fi

read_feature() {
  local listing
  listing=$("$codex" features list 2>/dev/null) || return 1
  # A failed CLI call must not masquerade as an unsupported option. Never print the full listing.
  printf '%s\n' "$listing" | awk '$1 == "mcp_oauth_refresh_coordination" {value=$NF; count++} END {if (count == 1) print value}'
}
if ! feature=$(read_feature); then
  printf '%s\n' 'status=host_inspection_failed'; exit 22
fi
case "$feature" in
  true|false) ;;
  '')
    printf '%s\n' 'status=host_upgrade_required' 'configuration_changed=false' \
      'next=update_the_desktop_app_then_rerun_this_command' \
      'path_cli_upgrade_does_not_update_the_desktop_host' 'repeated_login_will_not_fix_refresh_coordination'
    exit 21 ;;
  *) printf '%s\n' 'status=host_feature_unverified'; exit 22 ;;
esac

if [ "$feature" = false ]; then
  if [ "$apply" = false ]; then
    printf '%s\n' 'status=refresh_coordination_disabled' 'configuration_changed=false' \
      'next=rerun_with_--apply_to_enable_the_global_host_feature'
    exit 20
  fi
  printf '%s\n' 'change=enabling_global_host_refresh_coordination'
  if ! "$codex" features enable mcp_oauth_refresh_coordination >/dev/null 2>&1; then
    printf '%s\n' 'status=host_feature_enable_failed' 'configuration_changed=unknown'; exit 23
  fi
  if ! feature=$(read_feature) || [ "$feature" != true ]; then
    printf '%s\n' 'status=host_feature_readback_failed' 'configuration_changed=unknown'; exit 24
  fi
  printf '%s\n' 'configuration_changed=true' 'next=restart_the_desktop_app_after_saving_active_work'
else
  printf '%s\n' 'configuration_changed=false' 'next=verify_the_running_host_uses_the_enabled_feature'
fi
if [ "$check_running" = true ]; then
  # This is a conservative activation check, not a credential or feature-state
  # inspection inside the desktop process. A process older than the config write
  # cannot have loaded that write. A newer process still needs real OAuth tests.
  config_file="${CODEX_HOME:-$HOME/.codex}/config.toml"
  if [ "$(uname -s)" != Darwin ] || [ ! -f "$config_file" ] || ! command -v ps >/dev/null 2>&1; then
    printf '%s\n' 'running_host_activation=unverified' 'reason=process_or_config_unavailable'
    exit 25
  fi
  if ! config_epoch=$(stat -f %m "$config_file" 2>/dev/null); then
    printf '%s\n' 'running_host_activation=unverified' 'reason=config_timestamp_unavailable'
    exit 25
  fi
  running=0
  old=0
  unverified=0
  while read -r pid executable; do
    [ "$executable" = "$codex" ] || continue
    running=$((running + 1))
    started=$(ps -p "$pid" -o lstart= 2>/dev/null) || { unverified=$((unverified + 1)); continue; }
    started_epoch=$(date -j -f '%a %b %e %T %Y' "$started" +%s 2>/dev/null) || { unverified=$((unverified + 1)); continue; }
    if [ "$started_epoch" -lt "$config_epoch" ]; then old=$((old + 1)); fi
  done < <(ps -axo pid=,comm= 2>/dev/null)
  printf 'running_host_processes=%s\n' "$running"
  if [ "$old" -gt 0 ]; then
    printf '%s\n' 'running_host_activation=restart_required' \
      'next=save_work_then_fully_quit_and_reopen_desktop'
    exit 26
  fi
  if [ "$running" -eq 0 ] || [ "$unverified" -gt 0 ]; then
    printf '%s\n' 'running_host_activation=unverified' 'reason=no_verified_desktop_process'
    exit 25
  fi
  printf '%s\n' 'running_host_activation=restart_observed_feature_not_proven' \
    'next=verify_real_query_and_natural_refresh'
fi
printf '%s\n' 'status=host_configuration_enabled' \
  'revoked_refresh_credentials=not_restored' \
  'reauthentication=only_if_refresh_credentials_are_explicitly_rejected_after_host_activation'

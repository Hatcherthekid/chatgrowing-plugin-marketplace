#!/bin/bash
# Configure the verified desktop Host through its official CLI. Never touches OAuth credentials.
set -eu

codex=''
apply=false
mode=''
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
    *) printf '%s\n' 'usage: repair_oauth_host.sh --codex /verified/desktop/codex [--check | --apply]' >&2; exit 2 ;;
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
printf '%s\n' 'status=host_configuration_enabled' \
  'revoked_refresh_credentials=not_restored' \
  'reauthentication=only_if_refresh_credentials_are_explicitly_rejected_after_host_activation'

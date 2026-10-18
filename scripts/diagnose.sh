#!/usr/bin/env bash
# Target-device diagnostics. No login, refresh, install, credentials or business calls.
set -euo pipefail
codex=''; task_skill=''; thread=''; status_file=''; host_socket=''; startup_file=''; observe_seconds=5
while [[ $# -gt 0 ]]; do
  case "$1" in
    --codex) codex="${2:-}"; shift 2 ;;
    --task-skill-path) task_skill="${2:-}"; shift 2 ;;
    --thread-id) thread="${2:-}"; shift 2 ;;
    --host-status) status_file="${2:-}"; shift 2 ;;
    --host-socket) host_socket="${2:-}"; shift 2 ;;
    --startup-events) startup_file="${2:-}"; shift 2 ;;
    --observe-seconds) observe_seconds="${2:-}"; shift 2 ;;
    *) printf '%s\n' 'Usage: diagnose.sh --codex /desktop/codex [--task-skill-path /path/SKILL.md] [--host-status /native/status.json] [--thread-id UUID --host-socket /existing/host.sock] [--startup-events /native/events.jsonl]' >&2; exit 2 ;;
  esac
done
[[ "$codex" == /* && -x "$codex" && -x /usr/bin/plutil ]] || exit 2
[[ "$observe_seconds" =~ ^([0-9]|[12][0-9]|30)$ ]] || exit 2
[[ -z "$thread" || "$thread" =~ ^[0-9a-fA-F-]{36}$ ]] || exit 2
[[ -z "$startup_file" || -n "$thread" ]] || exit 2
[[ -z "$host_socket" || ( "$host_socket" == /* && -S "$host_socket" && -n "$thread" && -z "$status_file" ) ]] || exit 2
umask 077
scratch="$(mktemp -d "${TMPDIR:-/tmp}/chatgrowing-diagnose.XXXXXX")"
proxy_pid=''; inspection_pid=''; watchdog_pid=''
cleanup() { for pid in "$watchdog_pid" "$inspection_pid"; do [[ -z "$pid" ]] || { kill -KILL "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; }; done; [[ -z "$proxy_pid" ]] || { kill -KILL "$proxy_pid" 2>/dev/null || true; wait "$proxy_pid" 2>/dev/null || true; }; rm -rf "$scratch"; }
trap cleanup EXIT
value() { /usr/bin/plutil -extract "$2" raw -o - "$1" 2>/dev/null; }
safe_version() { local v="$1"; [[ "$v" =~ ^[0-9][0-9A-Za-z.+_-]{0,63}$ ]] && printf '%s' "$v" || printf unknown; }
printf '%s\n' 'host_proxy_policy=unknown' 'missing_remote_tools_do_not_prove_missing_platform_grant'
printf '%s\n' 'scope=executing_device_only' 'business_query=not_attempted' 'oauth_refresh=not_tested'
"$codex" plugin list --json > "$scratch/plugins.json" 2> "$scratch/error" &
inspection_pid=$!
(sleep 15; kill "$inspection_pid" 2>/dev/null || true; sleep 1; kill -KILL "$inspection_pid" 2>/dev/null || true) >/dev/null 2>&1 &
watchdog_pid=$!
inventory_available=true
if ! wait "$inspection_pid"; then
  inventory_available=false
  printf '%s\n' 'installation=cli_inspection_failed'
fi
kill "$watchdog_pid" 2>/dev/null || true
wait "$watchdog_pid" 2>/dev/null || true
watchdog_pid=''; inspection_pid=''
n=0
if [[ "$inventory_available" == true ]]; then
  n="$(value "$scratch/plugins.json" installed || true)"
  if [[ ! "$n" =~ ^[0-9]+$ ]]; then
    inventory_available=false; n=0
    printf '%s\n' 'installation=invalid_inventory_format'
  fi
fi
version=''; enabled=''
for ((i=0;i<n;i++)); do
  [[ "$(value "$scratch/plugins.json" "installed.$i.pluginId")" == chatgrowing@chatgrowing ]] || continue
  version="$(value "$scratch/plugins.json" "installed.$i.version")"
  enabled="$(value "$scratch/plugins.json" "installed.$i.enabled" || echo unknown)"
  printf 'installed_version=%s\n' "$(safe_version "$version")"
  case "$enabled" in true|false) printf 'enabled=%s\n' "$enabled" ;; *) printf '%s\n' 'enabled=unknown';; esac
  kind="$(value "$scratch/plugins.json" "installed.$i.marketplaceSource.sourceType" || echo unknown)"
  case "$kind" in git|local) printf 'marketplace_source_type=%s\n' "$kind" ;; *) printf '%s\n' 'marketplace_source_type=unknown';; esac
done
if [[ "$inventory_available" == true && -z "$version" ]]; then printf '%s\n' 'installation=not_listed'; fi
# Resolve the installed cache, not the marketplace's available plugin version.
if [[ "$version" =~ ^[0-9][0-9A-Za-z.+_-]{0,63}$ ]]; then
  root="${CODEX_HOME:-${HOME}/.codex}/plugins/cache/chatgrowing/chatgrowing/$version"
  manifest="$root/.codex-plugin/plugin.json"
  if [[ -f "$manifest" && "$(value "$manifest" version)" == "$version" ]]; then
    printf '%s\n' 'installed_files=present'
    for skill in youtube-material-operations ads-configuration; do
      if [[ -f "$root/skills/$skill/SKILL.md" ]]; then printf '%s=present\n' "$skill"; else printf '%s=missing\n' "$skill"; fi
    done
    if [[ "$(value "$root/.mcp.json" mcpServers.chatgrowing_ads_read.url || true)" == https://chatgrowing.com/mcp ]]; then
      printf '%s\n' 'gateway_manifest=canonical'
    else
      printf '%s\n' 'gateway_manifest=missing_or_conflicting'
    fi
    # Older installed versions may still declare the retired local helper.
    # Report its presence without requiring, sourcing or installing its runtime.
    if /usr/bin/plutil -extract mcpServers.chatgrowing_material_local json -o /dev/null "$root/.mcp.json" 2>/dev/null; then
      printf '%s\n' 'local_material_helper=legacy_installed_configuration' 'local_helper_failure_does_not_block_remote_queries'
    else
      printf '%s\n' 'local_material_helper=not_configured' 'material_intake=host_attachment_or_console'
    fi
    if [[ -n "$task_skill" ]]; then
      case "$task_skill" in
        "$root"/skills/*/SKILL.md) printf '%s\n' 'task_skill_reference=current' ;;
        *) printf '%s\n' 'task_skill_reference=stale_or_other_source' 'next_task_snapshot=fully_quit_and_reopen_desktop_once_then_new_task' ;;
      esac
    fi
  else
    printf '%s\n' 'installed_files=unverified_layout_or_missing'
  fi
fi
if [[ -n "$task_skill" ]]; then
  if [[ -f "$task_skill" ]]; then printf '%s\n' 'task_skill_file=present'; else printf '%s\n' 'task_skill_file=missing'; fi
fi
classify_error() {
  local error="$1" reason="${2:-}"
  if [[ "$reason" == reauthenticationRequired ]]; then printf explicit_reauthentication_error; return; fi
  case "$error" in
    ''|null) printf not_reported ;;
    *invalid_grant*|*needs_reauth*) printf explicit_reauthentication_error ;;
    *not*logged*in*|*Not*logged*in*) printf login_required ;;
    *metadata*|*Metadata*|*discovery*) printf discovery_failure ;;
    *timed*out*|*timeout*) printf startup_timeout ;;
    *initialize*) printf initialize_failure ;;
    *tools/list*) printf tools_list_failure ;;
    *request.send*|*request*failed*|*connect*|*TLS*|*DNS*|*HTTP*|*Transport*) printf transport_failure ;;
    *) printf present_unclassified ;;
  esac
}

# Inspect the EXISTING daemon and requested task. Never start another Host or
# refresh credentials as a substitute for the affected task's connection state.
if [[ -n "$thread" && -z "$status_file" && -z "$host_socket" ]]; then
  printf '%s\n' 'host_evidence=explicit_existing_host_socket_required'
fi
if [[ -n "$host_socket" ]]; then
  startup_file="$scratch/startup.jsonl"
  : > "$startup_file"
  mkfifo "$scratch/in" "$scratch/out"
  exec 3<>"$scratch/in" 4<>"$scratch/out"
  "$codex" app-server proxy --sock "$host_socket" < "$scratch/in" > "$scratch/out" 2> "$scratch/proxy-error" &
  proxy_pid=$!
  read_reply() {
    local wanted="$1" line id deadline=$((SECONDS+15))
    while ((SECONDS<deadline)); do
      if IFS= read -r -t 1 line <&4; then
        printf '%s\n' "$line" > "$scratch/message.json"
        if [[ "$(value "$scratch/message.json" method || true)" == mcpServer/startupStatus/updated ]]; then
          printf '%s\n' "$line" >> "$startup_file"
        fi
        id="$(value "$scratch/message.json" id || true)"
        if [[ "$id" == "$wanted" ]]; then
          /usr/bin/plutil -extract result json -o "$scratch/reply.json" "$scratch/message.json" 2>/dev/null
          return $?
        fi
      elif ! kill -0 "$proxy_pid" 2>/dev/null; then return 1
      fi
    done
    return 1
  }
  printf '%s\n' '{"id":1,"method":"initialize","params":{"clientInfo":{"name":"chatgrowing_diagnose","version":"1.0.0"},"capabilities":{"experimentalApi":true}}}' >&3
  if read_reply 1; then
    printf '%s\n' '{"method":"initialized","params":{}}' >&3
    printf '{"id":2,"method":"mcpServerStatus/list","params":{"serverName":"chatgrowing_ads_read","threadId":"%s","detail":"toolsAndAuthOnly"}}\n' "$thread" >&3
    if read_reply 2; then status_file="$scratch/reply.json"; printf '%s\n' 'host_evidence=explicit_existing_socket_target_task' 'desktop_socket_ownership=not_independently_verified'; fi
  fi
  # Newer Hosts may report status before a pending optional client finishes.
  # Observe notifications only; never trigger reload/startup and don't promise replay.
  observe_deadline=$((SECONDS+observe_seconds))
  while ((SECONDS<observe_deadline)); do
    if IFS= read -r -t 1 line <&4; then
      printf '%s\n' "$line" > "$scratch/message.json"
      if [[ "$(value "$scratch/message.json" method || true)" == mcpServer/startupStatus/updated ]]; then
        printf '%s\n' "$line" >> "$startup_file"
      fi
    elif ! kill -0 "$proxy_pid" 2>/dev/null; then break
    fi
  done
  if [[ -z "$status_file" ]]; then printf '%s\n' 'host_evidence=unavailable_or_unsupported_proxy'; fi
fi
# Do not attach another task's (or a daemon-global) startup to this task.
startup_seen=false
if [[ -n "$startup_file" && -f "$startup_file" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    printf '%s\n' "$line" > "$scratch/event.json"
    [[ "$(value "$scratch/event.json" method || true)" == mcpServer/startupStatus/updated ]] || continue
    [[ "$(value "$scratch/event.json" params.threadId || true)" == "$thread" ]] || continue
    name="$(value "$scratch/event.json" params.name || true)"
    [[ "$name" == chatgrowing_ads_read || "$name" == plugin_chatgrowing_chatgrowing_ads_read ]] || continue
    startup_seen=true
    state="$(value "$scratch/event.json" params.status || true)"
    case "$state" in starting|ready|failed|cancelled) printf 'startup_state=%s\n' "$state";; *) printf '%s\n' 'startup_state=unknown';; esac
    error="$(value "$scratch/event.json" params.error || true)"
    reason="$(value "$scratch/event.json" params.failureReason || true)"
    printf 'startup_error=%s\n' "$(classify_error "$error" "$reason")"
  done < "$startup_file"
fi
if [[ "$startup_seen" != true ]]; then printf '%s\n' 'startup_event=not_observed_not_replayed'; fi
if [[ -z "$status_file" ]]; then
  printf '%s\n' 'host_connection=unknown' 'tool_discovery=unknown' 'next=inspect_affected_task_native_mcp_status'
  exit 0
fi
# --host-status accepts the unmodified result of native mcpServerStatus/list.
# It is a supplied observation, never interchangeable with our own device probe.
if [[ -z "$host_socket" ]]; then printf '%s\n' 'host_evidence=supplied_native_status_not_independently_verified'; fi
n="$(value "$status_file" data || true)"; [[ "$n" =~ ^[0-9]+$ ]] || { printf '%s\n' 'host_connection=invalid_status_format'; exit 11; }
found=false
for ((i=0;i<n;i++)); do
  name="$(value "$status_file" "data.$i.name" || true)"
  plugin="$(value "$status_file" "data.$i.pluginId" || true)"
  # Server identity must be exact or tied to this plugin, not arbitrary resources.
  [[ "$name" == chatgrowing_ads_read || ( "$plugin" == chatgrowing@chatgrowing && "$name" == *chatgrowing_ads_read ) ]] || continue
  found=true
  if ! value "$status_file" "data.$i.runtimeStatus" >/dev/null; then
    printf '%s\n' 'host_runtime_field=not_provided_by_host_version'
  fi
  runtime="$(value "$status_file" "data.$i.runtimeStatus" || true)"
  case "$runtime" in notStarted|starting|connected|authenticationRequired|failed|cancelled|disabled) printf 'host_connection=%s\n' "$runtime" ;; *) printf '%s\n' 'host_connection=unknown';; esac
  auth="$(value "$status_file" "data.$i.authStatus" || true)"
  case "$auth" in unknown|unsupported|notLoggedIn|bearerToken|oAuth) printf 'host_auth=%s\n' "$auth" ;; *) printf '%s\n' 'host_auth=unknown';; esac
  for tool in ads_schema ads_sql ads_capability_context material_targets; do
    if value "$status_file" "data.$i.tools.$tool.name" >/dev/null; then printf '%s=host_catalog_present\n' "$tool"; else printf '%s=host_catalog_absent\n' "$tool"; fi
  done
  error="$(value "$status_file" "data.$i.toolsError" || true)"
  printf 'tools_error=%s\n' "$(classify_error "$error")"
  printf '%s\n' 'resource_empty_result_does_not_prove_connection_or_permissions'
done
if [[ "$found" != true ]]; then
  cursor="$(value "$status_file" nextCursor || true)"
  if [[ -n "$cursor" && "$cursor" != null ]]; then
    printf '%s\n' 'host_connection=not_observed_on_partial_page'
  else
    printf '%s\n' 'host_connection=not_reported_for_chatgrowing'
  fi
fi
printf '%s\n' 'task_tool_invocation=not_verified' 'acceptance=not_complete_until_affected_task_queries_succeed'

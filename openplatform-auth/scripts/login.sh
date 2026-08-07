#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "This script must be sourced so it can export ADVOO_OPENPLATFORM_TOKEN." >&2
  echo "Run: source <openplatform-auth-dir>/scripts/login.sh [--load-only]" >&2
  exit 2
fi

_openplatform_auth_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_openplatform_auth_token_file="${ADVOO_OPENPLATFORM_TOKEN_FILE:-${XDG_CONFIG_HOME:-${HOME}/.config}/advoo/openplatform/token}"

if [[ "${1:-}" == "--load-only" ]]; then
  if [[ -n "${ADVOO_OPENPLATFORM_TOKEN:-}" ]]; then
    unset _openplatform_auth_script_dir _openplatform_auth_token_file
    return 0
  fi
  if [[ -r "${_openplatform_auth_token_file}" ]]; then
    IFS= read -r ADVOO_OPENPLATFORM_TOKEN < "${_openplatform_auth_token_file}"
    if [[ -n "${ADVOO_OPENPLATFORM_TOKEN}" ]]; then
      export ADVOO_OPENPLATFORM_TOKEN
      unset _openplatform_auth_script_dir _openplatform_auth_token_file
      return 0
    fi
    unset ADVOO_OPENPLATFORM_TOKEN
  fi
  unset _openplatform_auth_script_dir _openplatform_auth_token_file
  return 1
fi

if [[ -n "${1:-}" ]]; then
  echo "Unknown option: ${1}" >&2
  unset _openplatform_auth_script_dir _openplatform_auth_token_file
  return 2
fi

if python3 "${_openplatform_auth_script_dir}/login.py" \
  --token-file "${_openplatform_auth_token_file}" \
  --app-name "${ADVOO_OPENPLATFORM_APP_NAME:-Local Application}"; then
  IFS= read -r ADVOO_OPENPLATFORM_TOKEN < "${_openplatform_auth_token_file}"
  export ADVOO_OPENPLATFORM_TOKEN
  unset _openplatform_auth_script_dir _openplatform_auth_token_file
  echo "Advoo authorization completed." >&2
else
  unset _openplatform_auth_script_dir _openplatform_auth_token_file
  return 1
fi

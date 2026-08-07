#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "This script must be sourced so it can export ADVOO_OPENPLATFORM_TOKEN." >&2
  echo "Run: source scripts/login.sh [--load-only]" >&2
  exit 2
fi

_social_post_query_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_social_post_query_token_file="${ADVOO_OPENPLATFORM_TOKEN_FILE:-${XDG_CONFIG_HOME:-${HOME}/.config}/advoo/openplatform/token}"

if [[ "${1:-}" == "--load-only" ]]; then
  if [[ -n "${ADVOO_OPENPLATFORM_TOKEN:-}" ]]; then
    unset _social_post_query_script_dir _social_post_query_token_file
    return 0
  fi
  if [[ -r "${_social_post_query_token_file}" ]]; then
    IFS= read -r ADVOO_OPENPLATFORM_TOKEN < "${_social_post_query_token_file}"
    if [[ -n "${ADVOO_OPENPLATFORM_TOKEN}" ]]; then
      export ADVOO_OPENPLATFORM_TOKEN
      unset _social_post_query_script_dir _social_post_query_token_file
      return 0
    fi
    unset ADVOO_OPENPLATFORM_TOKEN
  fi
  unset _social_post_query_script_dir _social_post_query_token_file
  return 1
fi

if [[ -n "${1:-}" ]]; then
  echo "Unknown option: ${1}" >&2
  unset _social_post_query_script_dir _social_post_query_token_file
  return 2
fi

if python3 "${_social_post_query_script_dir}/login.py" --token-file "${_social_post_query_token_file}"; then
  IFS= read -r ADVOO_OPENPLATFORM_TOKEN < "${_social_post_query_token_file}"
  export ADVOO_OPENPLATFORM_TOKEN
  unset _social_post_query_script_dir _social_post_query_token_file
  echo "Advoo authorization completed." >&2
else
  unset _social_post_query_script_dir _social_post_query_token_file
  return 1
fi

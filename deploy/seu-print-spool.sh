#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: seu-print-spool FILE [ORIGINAL] [LANGUAGE] [USERNAME] [TEAMNAME] [TEAMID] [LOCATION]" >&2
  exit 2
fi

source_file=$1
original=${2:-}
language=${3:-}
username=${4:-}
teamname=${5:-}
teamid=${6:-}
location=${7:-}

if [[ ! -r "$source_file" ]]; then
  echo "source file is not readable: $source_file" >&2
  exit 1
fi

spool_root=${SEU_DOMJUDGE_PRINT_SPOOL:-/opt/domjudge/domserver/var/print-spool}
pending_dir="$spool_root/pending"
tmp_dir="$spool_root/.tmp"
mkdir -p "$pending_dir" "$tmp_dir"

safe_original=$(basename "${original:-print.txt}" | tr -c 'A-Za-z0-9._-' '_')
safe_teamid=$(printf '%s' "${teamid:-team}" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-40)
safe_username=$(printf '%s' "${username:-user}" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-40)
safe_teamid=${safe_teamid:-team}
safe_username=${safe_username:-user}
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
job_id="${timestamp}-${safe_teamid}-${safe_username}-$$"
job_dir="$tmp_dir/$job_id"
mkdir "$job_dir"

cp -- "$source_file" "$job_dir/source"

{
  printf 'DOMjudge print job\n'
  printf 'queued_at_utc=%s\n' "$timestamp"
  printf 'original=%s\n' "$original"
  printf 'language=%s\n' "$language"
  printf 'username=%s\n' "$username"
  printf 'teamname=%s\n' "$teamname"
  printf 'teamid=%s\n' "$teamid"
  printf 'location=%s\n' "$location"
} >"$job_dir/metadata.txt"

{
  printf 'DOMjudge print job\n'
  printf 'Team: %s (%s)\n' "${teamname:-unknown}" "${teamid:-unknown}"
  printf 'User: %s\n' "${username:-unknown}"
  printf 'File: %s\n' "${original:-unknown}"
  printf 'Language: %s\n' "${language:-unknown}"
  printf 'Queued: %s UTC\n' "$timestamp"
  printf '%s\n\n' '----------------------------------------'
  cat -- "$source_file"
} >"$job_dir/print.txt"

ln -sfn "$safe_original" "$job_dir/original-name"

mv "$job_dir" "$pending_dir/$job_id"
echo "Queued DOMjudge print job: $job_id"

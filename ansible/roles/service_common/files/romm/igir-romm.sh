#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage: igir-romm.sh [report|copy|move|test]

Modes:
  report  Generate a CSV report only. Does not write to the RomM library.
  copy    Copy verified ROMs from inbox into library/roms. Keeps inbox intact.
  move    Move verified ROMs from inbox into library/roms. Use after copy mode looks good.
  test    Verify input files against DATs without writing library output.

Environment overrides:
  ROMM_ROOT       Root path that contains inbox, dats, reports, library. Default: script directory.
  NODE_IMAGE      Node image used for ephemeral Igir container. Default: node:lts-bookworm-slim
  IGIR_PACKAGE    Igir npm package/version. Default: igir@latest

  INPUT_SUBDIR    Input directory under ROMM_ROOT. Default: inbox
  DAT_SUBDIR      DAT directory under ROMM_ROOT. Default: dats
  OUTPUT_SUBDIR   RomM ROM output under ROMM_ROOT. Default: library/roms
  REPORT_SUBDIR   Report output under ROMM_ROOT. Default: reports
  CACHE_SUBDIR    npm cache directory under ROMM_ROOT. Default: .cache/npm

  PREFER_LANGUAGE Igir preferred language list. Default: EN
  PREFER_REGION   Igir preferred region list. Default: USA,WORLD,EUR,AUS,JPN

  CHECKSUM_MODE   Checksum mode. Default: crc32
                  Supported: default, crc32, quick, full

                  default = Igir defaults, CRC32 to SHA1
                  crc32   = calculate/use CRC32 only
                  quick   = read checksums from archive headers only
                  full    = calculate/use CRC32 through SHA256

  RUN_UID         Container UID. Default: owner UID of ROMM_ROOT
  RUN_GID         Container GID. Default: owner GID of ROMM_ROOT

Examples:
  ./igir-romm.sh report
  ./igir-romm.sh copy
  CHECKSUM_MODE=default ./igir-romm.sh report
  CHECKSUM_MODE=quick ./igir-romm.sh report
  PREFER_REGION=AUS,EUR,USA,WORLD,JPN ./igir-romm.sh copy
USAGE
}

log() {
  printf '[igir-romm] %s\n' "$*"
}

fail() {
  printf '[igir-romm] ERROR: %s\n' "$*" >&2
  exit 1
}

MODE="${1:-report}"

case "${MODE}" in
  -h|--help|help)
    usage
    exit 0
    ;;
  report|copy|move|test)
    ;;
  *)
    usage >&2
    fail "Invalid mode: ${MODE}"
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  fail "docker is not available on PATH"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROMM_ROOT="${ROMM_ROOT:-${SCRIPT_DIR}}"
ROMM_ROOT="$(cd "${ROMM_ROOT}" && pwd)"

NODE_IMAGE="${NODE_IMAGE:-node:lts-bookworm-slim}"
IGIR_PACKAGE="${IGIR_PACKAGE:-igir@latest}"

INPUT_SUBDIR="${INPUT_SUBDIR:-inbox}"
DAT_SUBDIR="${DAT_SUBDIR:-dats}"
OUTPUT_SUBDIR="${OUTPUT_SUBDIR:-library/roms}"
REPORT_SUBDIR="${REPORT_SUBDIR:-reports}"
CACHE_SUBDIR="${CACHE_SUBDIR:-.cache/npm}"

PREFER_LANGUAGE="${PREFER_LANGUAGE:-EN}"
PREFER_REGION="${PREFER_REGION:-USA,WORLD,EUR,AUS,JPN}"
CHECKSUM_MODE="${CHECKSUM_MODE:-crc32}"

INPUT_DIR="${ROMM_ROOT}/${INPUT_SUBDIR}"
DAT_DIR="${ROMM_ROOT}/${DAT_SUBDIR}"
OUTPUT_DIR="${ROMM_ROOT}/${OUTPUT_SUBDIR}"
REPORT_DIR="${ROMM_ROOT}/${REPORT_SUBDIR}"
CACHE_DIR="${ROMM_ROOT}/${CACHE_SUBDIR}"

mkdir -p \
  "${INPUT_DIR}" \
  "${DAT_DIR}" \
  "${OUTPUT_DIR}" \
  "${REPORT_DIR}" \
  "${CACHE_DIR}"

if ! find "${DAT_DIR}" -type f \( -iname '*.dat' -o -iname '*.xml' -o -iname '*.zip' \) -print -quit | grep -q .; then
  fail "No DAT files found in ${DAT_DIR}. Add No-Intro/Redump DAT files first."
fi

if ! find "${INPUT_DIR}" -type f -print -quit | grep -q .; then
  fail "No input files found in ${INPUT_DIR}. Drop files into the inbox first."
fi

RUN_UID="${RUN_UID:-$(stat -c '%u' "${ROMM_ROOT}")}"
RUN_GID="${RUN_GID:-$(stat -c '%g' "${ROMM_ROOT}")}"

# Make sure the ephemeral Node container can write reports, output files, and npm cache.
# This matters on Unraid if Ansible/root created any folders with restrictive ownership.
if [[ "$(id -u)" -eq 0 ]]; then
  chown -R "${RUN_UID}:${RUN_GID}" \
    "${REPORT_DIR}" \
    "${CACHE_DIR}" \
    "${OUTPUT_DIR}" || true
fi

RUN_ID="$(date +%Y%m%d-%H%M%S)"
REPORT_FILE="${REPORT_DIR}/igir-${MODE}-${RUN_ID}.csv"
LOG_FILE="${REPORT_DIR}/igir-${MODE}-${RUN_ID}.log"

CHECKSUM_ARGS=()

case "${CHECKSUM_MODE}" in
  default)
    # Igir default: input-checksum-min CRC32, input-checksum-max SHA1.
    ;;
  crc32)
    # Faster than default. Good first-pass mode for No-Intro/Redump-style matching.
    CHECKSUM_ARGS=(
      --input-checksum-max CRC32
    )
    ;;
  quick)
    # Fastest for archives that expose checksums in their headers.
    # Do not combine this with input-checksum-min/max; Igir treats them as mutually exclusive.
    CHECKSUM_ARGS=(
      --input-checksum-quick
    )
    ;;
  full)
    # Slowest, most exhaustive.
    CHECKSUM_ARGS=(
      --input-checksum-max SHA256
    )
    ;;
  *)
    fail "Invalid CHECKSUM_MODE: ${CHECKSUM_MODE}. Supported: default, crc32, quick, full"
    ;;
esac

COMMON_ARGS=(
  --dat "/data/${DAT_SUBDIR}/"
  --input "/data/${INPUT_SUBDIR}/"
  --report-output "/data/${REPORT_SUBDIR}/igir-${MODE}-${RUN_ID}.csv"

  "${CHECKSUM_ARGS[@]}"

  --only-retail
  --single
  --prefer-language "${PREFER_LANGUAGE}"
  --prefer-region "${PREFER_REGION}"
  --prefer-revision newer
  --prefer-retail
  --verbose
)

case "${MODE}" in
  report)
    # Keep report mode deliberately simple.
    # This is the first sanity check: can Igir read the DATs and inbox and write a CSV?
    IGIR_ARGS=(
      report
      --dat "/data/${DAT_SUBDIR}/"
      --input "/data/${INPUT_SUBDIR}/"
      --report-output "/data/${REPORT_SUBDIR}/igir-${MODE}-${RUN_ID}.csv"
      --input-checksum-max CRC32
      -vvv
    )
    ;;

  test)
    IGIR_ARGS=(
      test
      "${COMMON_ARGS[@]}"
    )
    ;;

  copy)
    IGIR_ARGS=(
      copy
      extract
      report
      test
      "${COMMON_ARGS[@]}"
      --output "/data/${OUTPUT_SUBDIR}/{romm}/"
    )
    ;;

  move)
    IGIR_ARGS=(
      move
      extract
      report
      test
      "${COMMON_ARGS[@]}"
      --output "/data/${OUTPUT_SUBDIR}/{romm}/"
    )
    ;;
esac

printf -v IGIR_COMMAND '%q ' npx --yes "${IGIR_PACKAGE}" "${IGIR_ARGS[@]}"

log "ROMM_ROOT=${ROMM_ROOT}"
log "MODE=${MODE}"
log "NODE_IMAGE=${NODE_IMAGE}"
log "IGIR_PACKAGE=${IGIR_PACKAGE}"
log "CHECKSUM_MODE=${CHECKSUM_MODE}"
log "RUN_UID=${RUN_UID} RUN_GID=${RUN_GID}"
log "Input:  ${INPUT_DIR}"
log "DATs:   ${DAT_DIR}"
log "Output: ${OUTPUT_DIR}"
log "Report: ${REPORT_FILE}"
log "Log:    ${LOG_FILE}"
log "Igir command: ${IGIR_COMMAND}"

if [[ "${MODE}" == "move" ]]; then
  log "Move mode can remove successfully-written source files from inbox. Press Ctrl+C within 10 seconds to abort."
  sleep 10
fi

set +e
docker run \
  --rm \
  --user "${RUN_UID}:${RUN_GID}" \
  --env HOME=/tmp \
  --env NPM_CONFIG_CACHE="/data/${CACHE_SUBDIR}" \
  --env NPM_CONFIG_FOREGROUND_SCRIPTS=true \
  --env NPM_CONFIG_LOGLEVEL=verbose \
  --volume "${ROMM_ROOT}:/data" \
  --workdir /data \
  "${NODE_IMAGE}" \
  npx --yes "${IGIR_PACKAGE}" "${IGIR_ARGS[@]}" 2>&1 | tee "${LOG_FILE}"

status=${PIPESTATUS[0]}
set -e

if [[ "${status}" -ne 0 ]]; then
  fail "Igir exited with status ${status}. Log: ${LOG_FILE}"
fi

case "${MODE}" in
  report|copy|move)
    if [[ -s "${REPORT_FILE}" ]]; then
      log "Report created: ${REPORT_FILE}"
    else
      fail "Igir exited successfully, but no report was created at ${REPORT_FILE}. Log: ${LOG_FILE}"
    fi
    ;;
esac

log "Done."

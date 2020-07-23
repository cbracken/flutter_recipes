#!/bin/bash

set -e

# Writes a line of text to the log prefixed with a timestamp.
function log() {
  local text="$1"
  local now=($(date +%s) $(date +%N))
  local elapsed=$(( (now[0] - START[0]) * 1000 + (10#${now[1]} - 10#${START[1]}) / 1000000 ))
  local sec=$(( elapsed / 1000 ))
  local millis=$(( elapsed - sec * 1000 ))

  printf "[HOST][%04d.%03d] %s\\n" "${sec}" "${millis}" "${text}"
}

function ssh_to_guest() {
  local command="${1}"
  log "Execute "${command}" on target via ssh"

  local result=0
  local attempt=0
  local total_attempts=2

  while [[ ${attempt} -lt ${total_attempts} ]]; do
    attempt=$(($attempt+1))
    ssh localhost -p "${SSH_PORT}" -F "${SSH_CONFIG}" -i "${SSH_KEY}" "${command}" && return
    ssh_result=$?
    if [[ ${ssh_result} == 255 ]]; then
      log "SSH command '$command' failed with exit code ${ssh_result}. Retrying..."
      sleep 2
      continue
    fi
    log "ssh exited with exit code ${ssh_result}."
    return ${ssh_result}
  done

  log "ssh failed to connect after ${total_attempts} retries."
  return 255
}

# Scans ports from and return the first identified unused port.
function find_unused_tcp_port {
  local server_port=$1
  while ss -latn | grep -q :${server_port} && server_port < 59759; do
    server_port=$((${server_port} + 1))
  done
  echo $server_port
}

# Default values of arguments
VDL_LOCATION="device_launcher"
EMULATOR_LOG="raw_emulator.log"
SYSLOG="syslog.log"
SSH_CONFIG="ssh_config"
SSH_KEY="id_ed25519"
RUN_TESTS=""
TEST_ARGS=""
VDL_ARGS=()

for arg in "$@"; do
    if [[ "$#" > 0 ]]; then
      case $1 in
        -v*|--vdl=*)
        VDL_LOCATION="${arg#*=}"
        ;;
        -c=*|--ssh_config=*)
        SSH_CONFIG="${arg#*=}"
        ;;
        -k=*|--ssh_key=*)
        SSH_KEY="${arg#*=}"
        ;;
        -l|--emulator_log)
        EMULATOR_LOG="${2}"
        shift
        ;;
        -s|--syslog)
        SYSLOG="${2}"
        shift
        ;;
        -t=*|--run_test=*)
        RUN_TESTS+="${arg#*=}"
        ;;
        -t=*|--test_args=*)
        TEST_ARGS+="${arg#*=}"
        ;;
        *)
        VDL_ARGS+=("${arg}")
        ;;
      esac
      shift
    fi
done

log "VDL Location: ${VDL_LOCATION}"
echo "VDL Args: ${VDL_ARGS[@]}"
echo "RUN_TESTS: ${RUN_TESTS[@]}"

# Note: This permission is required to SSH
chmod 600 ${SSH_KEY}
SSH_PORT=$(find_unused_tcp_port 32761)
GRPC_PORT=$(find_unused_tcp_port "$(($SSH_PORT + 1))")
log "SSH_PORT: ${SSH_PORT}"
log "GRPC_PORT: ${GRPC_PORT}"
log "EMULATOR_LOG: ${EMULATOR_LOG}"
log "SYSLOG: ${SYSLOG}"

readonly PORT_MAP="hostfwd=tcp::${SSH_PORT}-:22"
readonly VDL_PROTO=$(mktemp -p "${PWD}")

# Make sure --action=kill gets called even if --action=start errored.
set +e

log "Launching virtual device using VDL."
"./${VDL_LOCATION}" "${VDL_ARGS[@]}" \
  --action=start \
  --host_port_map="${PORT_MAP}" \
  --output_launched_device_proto="${VDL_PROTO}" > "${EMULATOR_LOG}" \
  --grpc_port="${GRPC_PORT}"

_EXIT_CODE=$?
_TEST_EXIT_CODE=0

if [[ ${_EXIT_CODE} == 0 ]]; then
  log "Successfully launched virtual device proto ${VDL_PROTO}"
  ssh_to_guest "log_listener" >"${SYSLOG}" 2>&1 &

  # Debug info to makesure fvm resizing worked.
  ssh_to_guest lsblk

  for target in "${RUN_TESTS[@]}"; do
    ssh_to_guest "run fuchsia-pkg://fuchsia.com/${target}#meta/${target}.cmx ${TEST_ARGS}"
    _EXIT_CODE=$?
    if [[ ${_EXIT_CODE} == 0 ]]; then
      log "${target} Passed"
    else
      _TEST_EXIT_CODE=${_EXIT_CODE}
      log "${target} Failed with exit code ${_EXIT_CODE}"
    fi
  done
else
  log "Failed to launch virtual device. Exit code ${_EXIT_CODE}"
fi

# Stop the emulator
log "Stopping virtual device."

"./${VDL_LOCATION}" \
  --action=kill \
  --launched_virtual_device_proto="${VDL_PROTO}"

VDL_STOP_EXIT_CODE=$?

if [[ ${VDL_STOP_EXIT_CODE} == 0 ]]; then
  log "Stopped virtual device."
else
  log "Failed to stop virtual device. Exit code ${VDL_STOP_EXIT_CODE}"
fi

exit ${_TEST_EXIT_CODE}

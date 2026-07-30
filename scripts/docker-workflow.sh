#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

COLIMA_PROFILE="${COLIMA_PROFILE:-default}"
PORT="${PORT:-8000}"
ENV_FILE="${ENV_FILE:-.env}"

LOCAL_IMAGE="homebox-companion:local-test"
CONTAINER_NAME="homebox-companion-local-test"
REGISTRY_IMAGE="ghcr.io/francescocam/homebox-companion"
REGISTRY_REPOSITORY="francescocam/homebox-companion"
DATA_DIR="${REPO_ROOT}/homebox-companion-data"
STATE_DIR="${REPO_ROOT}/.container-workflow"
STATE_FILE="${STATE_DIR}/state"
REVISION_LABEL="org.opencontainers.image.revision"
SOURCE_STATE_LABEL="io.homebox-companion.source-state"
TARGET_PLATFORM="linux/amd64"
HOST_DOCKER_CONFIG_DIR="${DOCKER_CONFIG:-${HOME}/.docker}"
TEMP_DOCKER_CONFIG_DIR=""

info() {
    printf '==> %s\n' "$*"
}

warn() {
    printf 'warning: %s\n' "$*" >&2
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

cleanup_temp_docker_config() {
    if [[ -z "${TEMP_DOCKER_CONFIG_DIR}" || ! -d "${TEMP_DOCKER_CONFIG_DIR}" ]]; then
        return
    fi
    if [[ "$(basename -- "${TEMP_DOCKER_CONFIG_DIR}")" != hbc-docker-anonymous.* ]]; then
        warn "Refusing to remove unexpected temporary Docker config path '${TEMP_DOCKER_CONFIG_DIR}'."
        return
    fi

    find "${TEMP_DOCKER_CONFIG_DIR}" -depth -type f -delete
    find "${TEMP_DOCKER_CONFIG_DIR}" -depth -type l -delete
    find "${TEMP_DOCKER_CONFIG_DIR}" -depth -type d -exec rmdir {} \; 2>/dev/null || true
    TEMP_DOCKER_CONFIG_DIR=""
}

trap cleanup_temp_docker_config EXIT

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command '$1' was not found."
}

validate_inputs() {
    [[ "${COLIMA_PROFILE}" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]] \
        || die "COLIMA_PROFILE must contain only letters, numbers, dots, underscores, and hyphens."
    [[ "${PORT}" =~ ^[0-9]+$ ]] && ((PORT >= 1 && PORT <= 65535)) \
        || die "PORT must be an integer between 1 and 65535."
}

state_value() {
    local key="$1"
    [[ -f "${STATE_FILE}" ]] || return 1
    awk -F= -v wanted="${key}" '$1 == wanted {sub(/^[^=]*=/, ""); print; exit}' "${STATE_FILE}"
}

write_state() {
    local started_by_workflow="$1"
    local existing_profile=""

    if [[ -f "${STATE_FILE}" ]]; then
        existing_profile="$(state_value colima_profile || true)"
        if [[ -n "${existing_profile}" && "${existing_profile}" != "${COLIMA_PROFILE}" ]]; then
            die "Workflow state belongs to Colima profile '${existing_profile}'. Run cleanup with COLIMA_PROFILE=${existing_profile} first."
        fi
    fi

    umask 077
    mkdir -p "${STATE_DIR}"
    {
        printf 'colima_profile=%s\n' "${COLIMA_PROFILE}"
        printf 'colima_started_by_workflow=%s\n' "${started_by_workflow}"
    } >"${STATE_FILE}"
}

colima_is_running() {
    colima status "${COLIMA_PROFILE}" >/dev/null 2>&1
}

connect_colima() {
    local existing_owner="0"
    local started_by_workflow="0"
    local status_output=""
    local docker_socket=""

    require_command colima
    require_command docker

    if [[ -f "${STATE_FILE}" ]]; then
        local state_profile
        state_profile="$(state_value colima_profile || true)"
        if [[ -n "${state_profile}" && "${state_profile}" != "${COLIMA_PROFILE}" ]]; then
            die "Workflow state belongs to Colima profile '${state_profile}'. Use COLIMA_PROFILE=${state_profile}."
        fi
        existing_owner="$(state_value colima_started_by_workflow || true)"
        [[ "${existing_owner}" == "1" ]] || existing_owner="0"
    fi

    if colima_is_running; then
        info "Using running Colima profile '${COLIMA_PROFILE}'."
        started_by_workflow="${existing_owner}"
    else
        info "Starting Colima profile '${COLIMA_PROFILE}'."
        colima start "${COLIMA_PROFILE}"
        started_by_workflow="1"
    fi

    write_state "${started_by_workflow}"

    status_output="$(colima status "${COLIMA_PROFILE}" 2>&1)" \
        || die "Could not read status for Colima profile '${COLIMA_PROFILE}'."
    grep -q 'runtime: docker' <<<"${status_output}" \
        || die "Colima profile '${COLIMA_PROFILE}' is not using the Docker runtime."

    docker_socket="$(
        sed -nE 's/^.*docker socket:[[:space:]]*(unix:\/\/[^"]+)".*$/\1/p' <<<"${status_output}" | head -n 1
    )"
    if [[ -z "${docker_socket}" ]]; then
        docker_socket="$(
            sed -nE 's/^.*socket:[[:space:]]*(unix:\/\/[^"]+)".*$/\1/p' <<<"${status_output}" | head -n 1
        )"
    fi
    [[ "${docker_socket}" == unix://* ]] \
        || die "Could not resolve the Docker socket from 'colima status'."

    export DOCKER_HOST="${docker_socket}"
    docker info >/dev/null 2>&1 \
        || die "Docker is not responding through Colima socket '${docker_socket}'."
    docker buildx version >/dev/null 2>&1 \
        || die "Docker Buildx is required but unavailable."
}

resolve_env_file() {
    local env_path="${ENV_FILE}"
    local env_dir=""
    local env_mode=""

    if [[ "${env_path}" != /* ]]; then
        env_path="${REPO_ROOT}/${env_path}"
    fi
    [[ -f "${env_path}" ]] \
        || die "Environment file '${ENV_FILE}' is missing. Run 'cp .env.example .env', edit it, and 'chmod 600 .env'."
    [[ -r "${env_path}" ]] || die "Environment file '${ENV_FILE}' is not readable."

    env_mode="$(stat -f '%Lp' "${env_path}" 2>/dev/null || stat -c '%a' "${env_path}" 2>/dev/null || true)"
    [[ "${env_mode}" == "600" ]] \
        || die "Environment file '${ENV_FILE}' must have mode 0600. Run 'chmod 600 ${ENV_FILE}'."

    env_dir="$(cd -- "$(dirname -- "${env_path}")" && pwd)"
    printf '%s/%s\n' "${env_dir}" "$(basename -- "${env_path}")"
}

source_state() {
    if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
        printf 'dirty\n'
    else
        printf 'clean\n'
    fi
}

remove_existing_container() {
    if docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
        info "Removing previous test container '${CONTAINER_NAME}'."
        docker container rm --force "${CONTAINER_NAME}" >/dev/null
    fi
}

require_available_port() {
    if command -v lsof >/dev/null 2>&1 \
        && lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
        die "Host port ${PORT} is already in use. Stop its listener or rerun with 'make docker-test PORT=<free-port>'."
    fi
}

wait_for_health() {
    local attempts=60
    local index

    info "Waiting for the application health endpoint."
    for ((index = 1; index <= attempts; index++)); do
        if curl --fail --silent --show-error --max-time 2 \
            "http://127.0.0.1:${PORT}/api/version" >/dev/null 2>&1; then
            return 0
        fi

        if [[ "$(docker container inspect --format '{{.State.Running}}' "${CONTAINER_NAME}" 2>/dev/null || true)" != "true" ]]; then
            break
        fi
        sleep 2
    done

    die "The application did not become healthy. Run 'make docker-logs' to inspect it, then 'make docker-clean'."
}

mac_lan_ip() {
    local network_interface=""
    local lan_ip=""

    network_interface="$(
        route -n get default 2>/dev/null | awk '/interface:/{print $2; exit}'
    )"
    if [[ -n "${network_interface}" ]]; then
        lan_ip="$(ipconfig getifaddr "${network_interface}" 2>/dev/null || true)"
    fi

    if [[ -z "${lan_ip}" ]]; then
        lan_ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
    fi
    if [[ -z "${lan_ip}" ]]; then
        lan_ip="$(ipconfig getifaddr en1 2>/dev/null || true)"
    fi

    printf '%s\n' "${lan_ip}"
}

test_image() {
    local env_path=""
    local revision=""
    local current_source_state=""
    local image_platform=""
    local lan_ip=""

    require_command git
    require_command curl
    require_command route
    require_command ipconfig
    validate_inputs
    cd "${REPO_ROOT}"

    env_path="$(resolve_env_file)"
    connect_colima

    revision="$(git rev-parse --verify HEAD)"
    current_source_state="$(source_state)"

    remove_existing_container
    require_available_port
    mkdir -p "${DATA_DIR}"

    info "Building ${TARGET_PLATFORM} image '${LOCAL_IMAGE}'."
    TEMP_DOCKER_CONFIG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/hbc-docker-anonymous.XXXXXX")"
    if [[ -d "${HOST_DOCKER_CONFIG_DIR}/cli-plugins" ]]; then
        ln -s "${HOST_DOCKER_CONFIG_DIR}/cli-plugins" "${TEMP_DOCKER_CONFIG_DIR}/cli-plugins"
    fi
    docker --config "${TEMP_DOCKER_CONFIG_DIR}" buildx build \
        --platform "${TARGET_PLATFORM}" \
        --load \
        --tag "${LOCAL_IMAGE}" \
        --label "${REVISION_LABEL}=${revision}" \
        --label "${SOURCE_STATE_LABEL}=${current_source_state}" \
        "${REPO_ROOT}"
    cleanup_temp_docker_config

    image_platform="$(
        docker image inspect --format '{{.Os}}/{{.Architecture}}' "${LOCAL_IMAGE}"
    )"
    [[ "${image_platform}" == "${TARGET_PLATFORM}" ]] \
        || die "Built image platform '${image_platform}' does not match '${TARGET_PLATFORM}'."

    info "Running '${CONTAINER_NAME}' on host port ${PORT}."
    docker run \
        --detach \
        --name "${CONTAINER_NAME}" \
        --platform "${TARGET_PLATFORM}" \
        --env-file "${env_path}" \
        --publish "0.0.0.0:${PORT}:8000" \
        --volume "${DATA_DIR}:/app/data" \
        --label "io.homebox-companion.workflow=local-test" \
        "${LOCAL_IMAGE}" >/dev/null

    wait_for_health

    info "Local test is healthy at http://127.0.0.1:${PORT}"
    lan_ip="$(mac_lan_ip)"
    if [[ -n "${lan_ip}" ]]; then
        if curl --fail --silent --show-error --max-time 3 \
            "http://${lan_ip}:${PORT}/api/version" >/dev/null 2>&1; then
            info "Phone URL: http://${lan_ip}:${PORT}"
        else
            warn "The app is healthy locally but the Mac LAN address was not reachable."
            warn "Check Colima port forwarding, the macOS firewall, VPN settings, and that the phone is on the same LAN."
            warn "Expected phone URL: http://${lan_ip}:${PORT}"
        fi
    else
        warn "Could not determine the Mac LAN IP. Find it in System Settings > Network and open port ${PORT}."
    fi

    if [[ "${current_source_state}" == "dirty" ]]; then
        warn "This image was built from a dirty worktree and cannot be published."
        warn "Commit the intended changes, then rerun 'make docker-test'."
    fi
}

show_logs() {
    validate_inputs
    cd "${REPO_ROOT}"
    connect_colima
    docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1 \
        || die "Test container '${CONTAINER_NAME}' does not exist. Run 'make docker-test' first."
    docker container logs --follow "${CONTAINER_NAME}"
}

verify_remote_tag() {
    local tag="${1:-latest}"
    local token_response=""
    local anonymous_token=""
    local manifest_json=""
    local config_digest=""
    local config_json=""

    require_command curl
    require_command jq

    info "Verifying anonymous access to ${REGISTRY_IMAGE}:${tag}."
    token_response="$(
        curl --fail --silent --show-error --get \
            --data-urlencode 'service=ghcr.io' \
            --data-urlencode "scope=repository:${REGISTRY_REPOSITORY}:pull" \
            'https://ghcr.io/token'
    )" || die "GHCR did not issue an anonymous pull token."
    anonymous_token="$(jq -er '.token' <<<"${token_response}")" \
        || die "GHCR anonymous token response was invalid."

    manifest_json="$(
        curl --fail --silent --show-error \
            --header "Authorization: Bearer ${anonymous_token}" \
            --header 'Accept: application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json' \
            "https://ghcr.io/v2/${REGISTRY_REPOSITORY}/manifests/${tag}"
    )" || die "Could not pull the public manifest for ${REGISTRY_IMAGE}:${tag}."

    if jq -e '.manifests | type == "array"' <<<"${manifest_json}" >/dev/null 2>&1; then
        jq -e '.manifests[] | select(.platform.os == "linux" and .platform.architecture == "amd64")' \
            <<<"${manifest_json}" >/dev/null \
            || die "${REGISTRY_IMAGE}:${tag} does not include linux/amd64."
    else
        config_digest="$(jq -er '.config.digest' <<<"${manifest_json}")" \
            || die "Image manifest for ${REGISTRY_IMAGE}:${tag} has no config digest."
        config_json="$(
            curl --fail --silent --show-error \
                --header "Authorization: Bearer ${anonymous_token}" \
                "https://ghcr.io/v2/${REGISTRY_REPOSITORY}/blobs/${config_digest}"
        )" || die "Could not inspect the image configuration for ${REGISTRY_IMAGE}:${tag}."
        jq -e '.os == "linux" and .architecture == "amd64"' <<<"${config_json}" >/dev/null \
            || die "${REGISTRY_IMAGE}:${tag} is not linux/amd64."
    fi

    unset anonymous_token token_response manifest_json config_json
    info "Verified: ${REGISTRY_IMAGE}:${tag} is public and supports linux/amd64."
}

remove_image_tag_if_matching() {
    local candidate="$1"
    local expected_image_id="$2"
    local candidate_image_id=""

    candidate_image_id="$(docker image inspect --format '{{.Id}}' "${candidate}" 2>/dev/null || true)"
    if [[ -n "${candidate_image_id}" && "${candidate_image_id}" == "${expected_image_id}" ]]; then
        docker image rm "${candidate}" >/dev/null
    fi
}

cleanup_runtime() {
    local started_by_workflow="0"
    local image_id=""
    local image_revision=""
    local short_revision=""

    validate_inputs
    cd "${REPO_ROOT}"
    connect_colima
    started_by_workflow="$(state_value colima_started_by_workflow || true)"
    [[ "${started_by_workflow}" == "1" ]] || started_by_workflow="0"

    if docker container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
        info "Removing test container '${CONTAINER_NAME}'."
        docker container rm --force "${CONTAINER_NAME}" >/dev/null
    fi

    image_id="$(docker image inspect --format '{{.Id}}' "${LOCAL_IMAGE}" 2>/dev/null || true)"
    if [[ -n "${image_id}" ]]; then
        image_revision="$(
            docker image inspect --format "{{ index .Config.Labels \"${REVISION_LABEL}\" }}" "${LOCAL_IMAGE}"
        )"
        if [[ "${image_revision}" =~ ^[0-9a-f]{40}$ ]]; then
            short_revision="${image_revision:0:12}"
            remove_image_tag_if_matching "${REGISTRY_IMAGE}:sha-${short_revision}" "${image_id}"
        fi
        remove_image_tag_if_matching "${REGISTRY_IMAGE}:latest" "${image_id}"
        info "Removing local test image '${LOCAL_IMAGE}'."
        docker image rm "${LOCAL_IMAGE}" >/dev/null
    fi

    if [[ "${started_by_workflow}" == "1" ]]; then
        info "Stopping Colima profile '${COLIMA_PROFILE}' because this workflow started it."
        colima stop "${COLIMA_PROFILE}"
    else
        info "Leaving Colima profile '${COLIMA_PROFILE}' running because it predated this workflow."
    fi

    rm -f "${STATE_FILE}"
    rmdir "${STATE_DIR}" 2>/dev/null || true
    info "Cleanup complete. Persisted app data remains in '${DATA_DIR}'."
}

publish_image() {
    local revision=""
    local short_revision=""
    local image_revision=""
    local image_source_state=""
    local image_platform=""
    local immutable_tag=""
    local latest_tag="${REGISTRY_IMAGE}:latest"

    require_command git
    validate_inputs
    cd "${REPO_ROOT}"

    [[ -z "$(git status --porcelain --untracked-files=all)" ]] \
        || die "Publishing requires a clean Git worktree. Commit or remove local changes, then rerun 'make docker-test'."

    connect_colima
    docker image inspect "${LOCAL_IMAGE}" >/dev/null 2>&1 \
        || die "Test image '${LOCAL_IMAGE}' does not exist. Run 'make docker-test' first."

    revision="$(git rev-parse --verify HEAD)"
    short_revision="${revision:0:12}"
    image_revision="$(
        docker image inspect --format "{{ index .Config.Labels \"${REVISION_LABEL}\" }}" "${LOCAL_IMAGE}"
    )"
    image_source_state="$(
        docker image inspect --format "{{ index .Config.Labels \"${SOURCE_STATE_LABEL}\" }}" "${LOCAL_IMAGE}"
    )"
    image_platform="$(
        docker image inspect --format '{{.Os}}/{{.Architecture}}' "${LOCAL_IMAGE}"
    )"

    [[ "${image_revision}" == "${revision}" ]] \
        || die "The tested image revision does not match current HEAD. Rerun 'make docker-test'."
    [[ "${image_source_state}" == "clean" ]] \
        || die "The tested image was built from a dirty worktree. Rerun 'make docker-test' from this clean commit."
    [[ "${image_platform}" == "${TARGET_PLATFORM}" ]] \
        || die "The tested image platform '${image_platform}' does not match '${TARGET_PLATFORM}'."

    immutable_tag="${REGISTRY_IMAGE}:sha-${short_revision}"
    docker image tag "${LOCAL_IMAGE}" "${immutable_tag}"
    docker image tag "${LOCAL_IMAGE}" "${latest_tag}"

    info "Pushing immutable image '${immutable_tag}'."
    docker image push "${immutable_tag}" \
        || die "GHCR push failed. Refresh the saved login with 'docker login ghcr.io --username francescocam' and retry."
    info "Pushing '${latest_tag}'."
    docker image push "${latest_tag}" \
        || die "GHCR push failed. Refresh the saved login with 'docker login ghcr.io --username francescocam' and retry."

    verify_remote_tag "sha-${short_revision}"
    verify_remote_tag latest
    cleanup_runtime
}

usage() {
    printf 'Usage: %s {test|logs|publish|clean|verify}\n' "$(basename -- "$0")"
}

main() {
    local command="${1:-}"

    case "${command}" in
        test)
            test_image
            ;;
        logs)
            show_logs
            ;;
        publish)
            publish_image
            ;;
        clean)
            cleanup_runtime
            ;;
        verify)
            verify_remote_tag latest
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
}

main "$@"

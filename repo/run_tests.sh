#!/usr/bin/env bash
set -e

UNIT_STATUS=0
API_STATUS=0
E2E_STATUS=0
E2E_RESULT="skipped"
RUNNER_MODE=""
TEST_ENV_PREFIX="env -u SECRET_KEY -u HMAC_SECRET -u ENCRYPTION_KEY -u DATABASE_URL -u FLASK_ENV"

has_local_pytest() {
    python3 -c "import pytest" >/dev/null 2>&1
}

has_docker_compose() {
    docker compose version >/dev/null 2>&1
}

web_service_running() {
    [ -n "$(docker compose ps -q web 2>/dev/null)" ]
}

run_in_docker() {
    local cmd="$1"
    if web_service_running; then
        docker compose exec -T web sh -lc "cd /app && ${cmd}"
    else
        docker compose run --rm web sh -lc "cd /app && ${cmd}"
    fi
}

run_python_test_cmd() {
    local cmd="$TEST_ENV_PREFIX $1"
    if [ "${RUN_TESTS_FORCE_LOCAL:-0}" = "1" ]; then
        eval "$cmd"
    elif [ "${RUN_TESTS_FORCE_DOCKER:-0}" = "1" ]; then
        run_in_docker "$cmd"
    elif has_docker_compose; then
        run_in_docker "$cmd"
    elif has_local_pytest; then
        eval "$cmd"
    else
        echo "Neither local pytest nor docker compose is available."
        return 127
    fi
}

if [ "${RUN_TESTS_FORCE_LOCAL:-0}" = "1" ]; then
    RUNNER_MODE="local (forced)"
elif [ "${RUN_TESTS_FORCE_DOCKER:-0}" = "1" ]; then
    RUNNER_MODE="docker (forced)"
elif has_docker_compose; then
    RUNNER_MODE="docker"
elif has_local_pytest; then
    RUNNER_MODE="local"
else
    RUNNER_MODE="unavailable"
fi

echo "========================================"
echo "  Test Runner Mode: ${RUNNER_MODE}"
echo "========================================"
echo ""

echo "========================================"
echo "  Running Unit Tests"
echo "========================================"
UNIT_OUTPUT=$(run_python_test_cmd "python3 -m pytest unit_tests/ -v --tb=short" 2>&1) && UNIT_STATUS=0 || UNIT_STATUS=$?
echo "$UNIT_OUTPUT"
UNIT_RESULT=$(echo "$UNIT_OUTPUT" | grep -E '^\d+ passed|^=.*(passed|failed|error)' | tail -1)

echo ""
echo "========================================"
echo "  Running API Tests"
echo "========================================"
API_OUTPUT=$(run_python_test_cmd "python3 -m pytest API_tests/ -v --tb=short" 2>&1) && API_STATUS=0 || API_STATUS=$?
echo "$API_OUTPUT"
API_RESULT=$(echo "$API_OUTPUT" | grep -E '^\d+ passed|^=.*(passed|failed|error)' | tail -1)

echo ""
echo "========================================"
echo "  Running E2E Tests (Playwright/Chromium)"
echo "========================================"
if run_python_test_cmd "python3 -c \"import playwright\"" >/dev/null 2>&1; then
    if run_python_test_cmd "python3 -c \"from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); b.close(); p.stop()\"" >/dev/null 2>&1; then
        E2E_OUTPUT=$(run_python_test_cmd "python3 -m pytest e2e_tests/ -v --tb=short" 2>&1) && E2E_STATUS=0 || E2E_STATUS=$?
        echo "$E2E_OUTPUT"
        E2E_RESULT=$(echo "$E2E_OUTPUT" | grep -E '^\d+ passed|^=.*(passed|failed|error)' | tail -1)
    else
        echo "Chromium browser not installed — run 'playwright install chromium' first"
        echo "Skipping E2E tests (not a failure)"
        E2E_STATUS=0
        E2E_RESULT="skipped (no browser)"
    fi
else
    echo "playwright not installed — skipping E2E tests"
    E2E_STATUS=0
    E2E_RESULT="skipped (not installed)"
fi

echo ""
echo "========================================"
echo "  Test Summary"
echo "========================================"
echo "Unit tests : $UNIT_RESULT"
echo "API tests  : $API_RESULT"
echo "E2E tests  : $E2E_RESULT"

if [ $UNIT_STATUS -ne 0 ] || [ $API_STATUS -ne 0 ] || [ $E2E_STATUS -ne 0 ]; then
    echo ""
    echo "RESULT: SOME TESTS FAILED"
    exit 1
else
    echo ""
    echo "RESULT: ALL TESTS PASSED"
    exit 0
fi

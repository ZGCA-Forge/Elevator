#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

if [[ "${1:-}" == "--reinstall" ]]; then
  echo "收到 --reinstall 参数，强制重新安装依赖。"
  rm -f "${VENV_DIR}/.deps_installed"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "未检测到 python3，请先安装 Python 3.11 或以上版本。" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "未检测到 curl，请先安装：sudo apt install curl" >&2
  exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
  echo "创建虚拟环境..."
  python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

if [ ! -f "${VENV_DIR}/.deps_installed" ]; then
  echo "升级 pip 并安装项目依赖..."
  python -m pip install --upgrade pip
  python -m pip install -e "${PROJECT_ROOT}"
  touch "${VENV_DIR}/.deps_installed"
else
  echo "发现已安装依赖，跳过安装步骤。"
fi

echo "启动电梯模拟器..."
python -m elevator_saga.server.simulator &
SIMULATOR_PID=$!

cleanup() {
  echo "关闭电梯模拟器 (PID=${SIMULATOR_PID})..."
  kill "${SIMULATOR_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "等待模拟器就绪..."
for i in $(seq 1 10); do
  if curl -sSf "http://127.0.0.1:8000/api/state" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "启动调度算法..."
python -m assignment.main

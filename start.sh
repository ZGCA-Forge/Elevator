#!/usr/bin/env bash

if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env bash "$0" "$@"
fi

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

RUN_DASHBOARD=1
REINSTALL=0

for arg in "$@"; do
  case "$arg" in
    --reinstall)
      REINSTALL=1
      ;;
    --no-dashboard)
      RUN_DASHBOARD=0
      ;;
    *)
      echo "未知参数: ${arg}"
      ;;
  esac
done

if [[ "${REINSTALL}" -eq 1 ]]; then
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
python -m assignment.run_server &
SIMULATOR_PID=$!

cleanup() {
  echo "关闭电梯模拟器 (PID=${SIMULATOR_PID})..."
  kill "${SIMULATOR_PID}" >/dev/null 2>&1 || true
  if [[ "${RUN_DASHBOARD}" -eq 1 && -n "${DASHBOARD_PID:-}" ]]; then
    echo "关闭可视化面板 (PID=${DASHBOARD_PID})..."
    kill "${DASHBOARD_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "等待模拟器就绪..."
for i in $(seq 1 10); do
  if curl -sSf "http://127.0.0.1:8000/api/state" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if [[ "${RUN_DASHBOARD}" -eq 1 ]]; then
  echo "启动可视化面板（http://127.0.0.1:8050）..."
  python -m assignment.web_dashboard &
  DASHBOARD_PID=$!
  sleep 1
  echo "请在浏览器访问 http://127.0.0.1:8050 并点击“启动调度”按钮开始模拟。"
  echo "若需退出，请在本终端按 Ctrl+C。"
  wait "${DASHBOARD_PID}"
else
  echo "已禁用可视化面板，可使用 --no-dashboard 参数控制。"
  echo "直接运行调度算法..."
  python -m assignment.main
  echo "调度算法已完成。"
fi

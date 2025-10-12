const tickEl = document.getElementById("tick");
const elevatorContainer = document.getElementById("elevator-cards");
const floorTableBody = document.querySelector("#floor-table tbody");
const metricsList = document.getElementById("metrics-list");
const statusEl = document.getElementById("controller-status");
const toggleBtn = document.getElementById("toggle-controller");
const lastUpdateEl = document.getElementById("last-update");

let controllerRunning = false;
let pendingAction = false;

async function fetchState() {
  try {
    const resp = await fetch(`/dashboard/state?_=${Date.now()}`, {
      cache: "no-store",
    });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    const data = await resp.json();
    renderState(data);
  } catch (error) {
    console.error("获取状态失败:", error);
  } 
}

function renderState(state) {
  tickEl.textContent = `Tick: ${state.tick}`;
  if (lastUpdateEl) {
    const now = new Date();
    lastUpdateEl.textContent = `上次更新：${now
      .toLocaleTimeString("zh-CN", { hour12: false })
      .padStart(8, "0")}`;
  }
  elevatorContainer.innerHTML = "";
  state.elevators.forEach((elevator) => {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <h3>电梯 #${elevator.id}</h3>
      <span>楼层：${elevator.current.toFixed(1)} → ${elevator.target}</span>
      <span>方向：${translateDirection(elevator.direction)}</span>
      <span>状态：${translateStatus(elevator.status)}</span>
      <span>乘客：${elevator.passenger_count}人，载重比 ${(
        elevator.load_factor * 100
      ).toFixed(0)}%</span>
      <span>车内目标：${
        elevator.pressed_floors.length ? elevator.pressed_floors.join(", ") : "-"
      }</span>
    `;
    elevatorContainer.appendChild(card);
  });

  floorTableBody.innerHTML = "";
  state.floors
    .slice()
    .sort((a, b) => b.floor - a.floor)
    .forEach((floor) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${floor.floor}</td>
        <td>${floor.up_waiting}</td>
        <td>${floor.down_waiting}</td>
        <td>${floor.total}</td>
      `;
      floorTableBody.appendChild(tr);
    });

  metricsList.innerHTML = "";
  Object.entries(state.metrics).forEach(([key, value]) => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${translateMetric(key)}</strong><br />${formatMetricValue(
      key,
      value
    )}`;
    metricsList.appendChild(li);
  });
  controllerRunning = Boolean(state.controller_running);
  updateControls();
}

function updateControls() {
  if (!statusEl || !toggleBtn) {
    return;
  }
  if (controllerRunning) {
    statusEl.textContent = "运行中";
    statusEl.className = "status status-running";
    toggleBtn.textContent = "停止调度";
  } else {
    statusEl.textContent = "未运行";
    statusEl.className = "status status-idle";
    toggleBtn.textContent = "启动调度";
  }
  toggleBtn.disabled = pendingAction;
}

async function toggleController() {
  if (!toggleBtn) {
    return;
  }
  pendingAction = true;
  updateControls();
  toggleBtn.textContent = controllerRunning ? "停止中..." : "启动中...";
  const url = controllerRunning ? "/dashboard/stop" : "/dashboard/start";
  try {
    const resp = await fetch(url, { method: "POST" });
    const payload = await resp.json().catch(() => ({}));
    if (!resp.ok || !payload.success) {
      const message =
        payload.message ||
        (resp.ok ? "操作失败，请稍后重试" : `操作失败 (HTTP ${resp.status})`);
      alert(message);
    }
  } catch (error) {
    console.error("切换调度状态失败:", error);
    alert("操作失败，请检查终端输出。");
  } finally {
    pendingAction = false;
    updateControls();
    fetchState();
  }
}

function translateDirection(direction) {
  switch (direction) {
    case "up":
      return "上行";
    case "down":
      return "下行";
    default:
      return "静止";
  }
}

function translateStatus(status) {
  const map = {
    start_up: "加速",
    start_down: "减速",
    constant_speed: "运行",
    stopped: "停止",
  };
  return map[status] || status;
}

function translateMetric(key) {
  const map = {
    completed_passengers: "已完成",
    total_passengers: "总乘客",
    average_floor_wait_time: "平均楼层等待",
    p95_floor_wait_time: "P95楼层等待",
    average_arrival_wait_time: "平均总等待",
    p95_arrival_wait_time: "P95总等待",
  };
  return map[key] || key;
}

function formatMetricValue(key, value) {
  if (typeof value === "number" && key.includes("wait")) {
    return `${value.toFixed(1)} tick`;
  }
  return value;
}

if (toggleBtn) {
  toggleBtn.addEventListener("click", () => {
    if (pendingAction) {
      return;
    }
    toggleController();
  });
}

setInterval(fetchState, 1000);
fetchState();
updateControls();

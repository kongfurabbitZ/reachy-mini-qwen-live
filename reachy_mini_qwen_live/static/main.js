const $ = id => document.getElementById(id);
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json" } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}
async function loadConfig() {
  const data = await api("/api/config");
  $("region").value = data.region;
  $("workspace").value = data.workspace_id;
  $("voice").value = data.voice;
  $("instructions").value = data.instructions;
  $("motion").checked = data.motion_enabled;
  $("key-state").textContent = data.api_key_configured ? "API Key 已保存在本机" : "尚未设置 API Key";
}
async function refresh() {
  try {
    const data = await api("/api/status");
    $("state").textContent = data.state;
    $("error").hidden = !data.error;
    $("error").textContent = data.error;
    $("start").disabled = !["未连接", "连接失败"].includes(data.state);
    $("stop").disabled = data.state === "未连接";
    const transcript = $("transcript");
    transcript.replaceChildren();
    if (!data.events.length) transcript.textContent = "尚未收到文字记录";
    for (const item of data.events) {
      const p = document.createElement("p");
      const strong = document.createElement("strong");
      strong.textContent = `${item.role}：`;
      p.append(strong, document.createTextNode(item.content));
      transcript.append(p);
    }
  } catch (error) { $("state").textContent = error.message; }
}
$("settings").addEventListener("submit", async event => {
  event.preventDefault();
  const body = { region: $("region").value, workspace_id: $("workspace").value, voice: $("voice").value,
    instructions: $("instructions").value, motion_enabled: $("motion").checked };
  if ($("key").value) body.api_key = $("key").value;
  try {
    await api("/api/config", { method: "POST", body: JSON.stringify(body) });
    $("key").value = "";
    $("save-state").textContent = "已保存到本机";
    await loadConfig();
  } catch (error) { $("save-state").textContent = error.message; }
});
$("clear-key").addEventListener("click", async () => {
  await api("/api/config", { method: "POST", body: JSON.stringify({ clear_api_key: true }) });
  await loadConfig();
});
for (const action of ["start", "stop"]) {
  $(action).addEventListener("click", async () => {
    $("error").hidden = true;
    $("state").textContent = action === "start" ? "连接中" : "结束中";
    try { await api(`/api/${action}`, { method: "POST" }); }
    catch (error) { $("error").textContent = error.message; $("error").hidden = false; }
    await refresh();
  });
}
let configLoaded = false;
async function ensureConfig() {
  if (configLoaded) return;
  try {
    await loadConfig();
    configLoaded = true;
    $("save-state").textContent = "";
  } catch (error) {
    $("save-state").textContent = "等待设置接口准备就绪…";
  }
}
ensureConfig();
refresh();
setInterval(refresh, 1500);
setInterval(ensureConfig, 1500);

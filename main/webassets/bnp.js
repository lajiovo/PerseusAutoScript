document.addEventListener("DOMContentLoaded", () => {
    pollStatus();
    setInterval(pollStatus, 2000);
});

function pollStatus() {
    fetch("/bnp/status")
        .then(res => res.json())
        .then(data => {
            if (data.code === 200) {
                updateUI(data.data);
            }
        })
        .catch(err => console.error("轮询状态失败:", err));
}

function updateUI(info) {
    const isRunning = info.is_running;
    const state = info.state;

    const btnStart = document.getElementById("btnStart");
    const btnStop = document.getElementById("btnStop");
    const lblStatus = document.getElementById("lblStatus");
    const lblGuide = document.getElementById("lblGuide");
    const interactionArea = document.getElementById("interactionArea");

    const panelUrl = document.getElementById("panelUrl");
    const panelVolume = document.getElementById("panelVolume");
    const panelTitle = document.getElementById("panelTitle");

    if (isRunning) {
        btnStart.disabled = true;
        btnStop.disabled = false;
        lblStatus.textContent = `状态: ${state}`;
        lblStatus.className = "status-badge running";
        lblGuide.textContent = `当前程序正在运行中，状态: ${state}`;
        interactionArea.classList.remove("hidden");

        // 隐藏所有子面板，再按状态开启
        panelUrl.classList.add("hidden");
        panelVolume.classList.add("hidden");
        panelTitle.classList.add("hidden");

        if (state === "WAITING_URL") {
            panelUrl.classList.remove("hidden");
        } else if (state === "WAITING_VOLUME") {
            panelVolume.classList.remove("hidden");
            populateVolumes(info.volumes || []);
        } else if (state === "WAITING_TITLE_CONFIG") {
            panelTitle.classList.remove("hidden");
        }
    } else {
        btnStart.disabled = false;
        btnStop.disabled = true;
        lblStatus.textContent = "状态: 未运行";
        lblStatus.className = "status-badge stopped";
        lblGuide.textContent = "当前无活动进程，请点击上方“启动程序”。";
        interactionArea.classList.add("hidden");
    }
}

function populateVolumes(volumes) {
    const select = document.getElementById("selectVolume");
    const currentVal = select.value;
    select.innerHTML = "";
    volumes.forEach(vol => {
        const opt = document.createElement("option");
        opt.value = vol.id;
        opt.textContent = `[${vol.id}] ${vol.name}`;
        select.appendChild(opt);
    });
    if (currentVal) {
        select.value = currentVal;
    }
}

function startProcess() {
    fetch("/bnp/start", { method: "POST" })
        .then(res => res.json())
        .then(data => {
            if (data.code === 200) {
                pollStatus();
            } else {
                alert("启动失败: " + data.message);
            }
        })
        .catch(err => alert("请求异常: " + err));
}

function stopProcess() {
    fetch("/bnp/stop", { method: "POST" })
        .then(res => res.json())
        .then(data => {
            pollStatus();
        })
        .catch(err => alert("请求异常: " + err));
}

function sendDownloadUrl() {
    const url = document.getElementById("inputUrl").value.trim();
    if (!url) {
        alert("请输入有效的小说链接！");
        return;
    }
    fetch("/bnp/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url })
    })
    .then(res => res.json())
    .then(data => {
        if (data.code !== 200) {
            alert(data.message);
        } else {
            document.getElementById("inputUrl").value = "";
        }
        pollStatus();
    })
    .catch(err => alert("发送失败: " + err));
}

function sendVolumeSelection() {
    const select = document.getElementById("selectVolume");
    const volId = select.value;
    if (!volId) {
        alert("请选择分卷！");
        return;
    }
    fetch("/bnp/volume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ volume_id: volId })
    })
    .then(res => res.json())
    .then(data => {
        if (data.code !== 200) {
            alert(data.message);
        }
        pollStatus();
    })
    .catch(err => alert("发送失败: " + err));
}

function sendTitleConfig(includeTitle) {
    fetch("/bnp/title_config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ include_title: includeTitle })
    })
    .then(res => res.json())
    .then(data => {
        if (data.code !== 200) {
            alert(data.message);
        }
        pollStatus();
    })
    .catch(err => alert("发送失败: " + err));
}

function sendFreeInput() {
    const input = document.getElementById("freeInput");
    const text = input.value.trim();
    if (!text) return;

    fetch("/bnp/input", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
    })
    .then(res => res.json())
    .then(data => {
        if (data.code === 200) {
            input.value = "";
        } else {
            alert(data.message);
        }
        pollStatus();
    })
    .catch(err => alert("发送失败: " + err));
}

function handleKeypress(event) {
    if (event.key === "Enter") {
        sendFreeInput();
    }
}

function scanEpubs() {
    fetch("/bnp/epubs")
        .then(res => res.json())
        .then(data => {
            if (data.code === 200) {
                const container = document.getElementById("epubListContainer");
                const files = data.data;
                if (files.length === 0) {
                    container.innerHTML = `<p class="text-muted">未找到任何 EPUB 文件。</p>`;
                    return;
                }
                let html = "";
                files.forEach(f => {
                    html += `<div class="epub-item"><span>${f.name}</span><span class="text-muted">${f.path}</span></div>`;
                });
                container.innerHTML = html;
            }
        })
        .catch(err => alert("扫描失败: " + err));
}

function moveEpubs() {
    fetch("/bnp/move_epubs", { method: "POST" })
        .then(res => res.json())
        .then(data => {
            if (data.code === 200) {
                alert(data.message);
                scanEpubs();
            } else {
                alert(data.message);
            }
        })
        .catch(err => alert("移动失败: " + err));
}

document.addEventListener("DOMContentLoaded", () => {
    fetchStatsData();

    document.getElementById("weightForm").addEventListener("submit", (e) => {
        e.preventDefault();
        saveWeights();
    });

    document.getElementById("clearBtn").addEventListener("click", () => {
        if (confirm("确定要清空所有学习记录吗？此操作不可恢复。")) {
            clearRecords();
        }
    });
});

async function fetchStatsData() {
    try {
        const response = await fetch("/api/watch/stats");
        const result = await response.json();
        
        if (result.status === "success") {
            updateOverview(result);
            updateSubjectTable(result.subjects);
            updateWeightForm(result.weights);
            updateRecordTable(result.records);
        } else {
            alert("获取统计数据失败: " + result.message);
        }
    } catch (error) {
        console.error("网络请求错误:", error);
    }
}

function updateOverview(data) {
    document.getElementById("totalDuration").textContent = `${data.total_duration_hours} 小时`;
    document.getElementById("totalRecords").textContent = `${data.total_records} 条`;
    document.getElementById("totalWeighted").textContent = `${data.total_weighted_score.toFixed(1)}`;
}

function updateSubjectTable(subjects) {
    const tbody = document.getElementById("subjectTableBody");
    if (!subjects || subjects.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="loading">暂无科目学习数据</td></tr>`;
        return;
    }

    tbody.innerHTML = subjects.map(item => `
        <tr>
            <td><strong>${item.subject}</strong></td>
            <td>${item.duration_minutes} 分钟 (${item.duration_hours} 小时)</td>
            <td>${item.weight}</td>
            <td><strong>${item.weighted_score.toFixed(1)}</strong></td>
            <td>${item.count} 次</td>
        </tr>
    `).join("");
}

function updateWeightForm(weights) {
    const container = document.getElementById("weightInputsContainer");
    if (!weights || Object.keys(weights).length === 0) {
        container.innerHTML = "<p>暂无权重配置</p>";
        return;
    }

    container.innerHTML = Object.entries(weights).map(([subject, weight]) => `
        <div class="weight-item">
            <label for="weight_${subject}">${subject} 权重:</label>
            <input type="number" step="0.1" min="0" id="weight_${subject}" name="${subject}" value="${weight}" required>
        </div>
    `).join("");
}

async function saveWeights() {
    const inputs = document.querySelectorAll("#weightInputsContainer input");
    const newWeights = {};
    inputs.forEach(input => {
        newWeights[input.name] = parseFloat(input.value) || 1.0;
    });

    try {
        const response = await fetch("/api/watch/weights", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(newWeights)
        });
        const result = await response.json();
        if (result.status === "success") {
            alert("科目权重保存成功！");
            fetchStatsData();
        } else {
            alert("保存失败: " + result.message);
        }
    } catch (error) {
        console.error("保存权重错误:", error);
    }
}

async function clearRecords() {
    try {
        const response = await fetch("/api/watch/clear", {
            method: "POST"
        });
        const result = await response.json();
        if (result.status === "success") {
            alert("所有记录已清空");
            fetchStatsData();
        } else {
            alert("清空失败: " + result.message);
        }
    } catch (error) {
        console.error("清空错误:", error);
    }
}

function updateRecordTable(records) {
    const tbody = document.getElementById("recordTableBody");
    if (!records || records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="loading">暂无同步记录</td></tr>`;
        return;
    }

    tbody.innerHTML = records.map(r => `
        <tr>
            <td>${r.created_at || r.date || '刚刚'}</td>
            <td><strong>${r.subject}</strong></td>
            <td>${(r.duration / 60).toFixed(1)} 分钟</td>
            <td>${r.note || '-'}</td>
        </tr>
    `).join("");
}

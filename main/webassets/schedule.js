document.addEventListener('DOMContentLoaded', () => {
    let historyChart = null;

    // DOM 元素引用
    const masterStatusBadge = document.getElementById('master-status-badge');
    const masterStatusText = document.getElementById('master-status-text');
    const btnRefresh = document.getElementById('btn-refresh');

    const configForm = document.getElementById('config-form');
    const masterEnabledCheckbox = document.getElementById('master_enabled');
    const defaultEnabledCheckbox = document.getElementById('default_enabled');
    const defaultIntervalsContainer = document.getElementById('default-intervals-container');
    const btnAddInterval = document.getElementById('btn-add-interval');
    const dailyLimitInput = document.getElementById('daily_limit_minutes');

    const todayDateTag = document.getElementById('today-date-tag');
    const todayRuntimeEl = document.getElementById('today-runtime');
    const todayCanRunEl = document.getElementById('today-can-run');
    const statusReasonText = document.getElementById('status-reason-text');

    const reportMinsInput = document.getElementById('report-mins');
    const reportStatusSelect = document.getElementById('report-status');
    const btnReport = document.getElementById('btn-report');

    const specDateInput = document.getElementById('spec-date');
    const specEnabledSelect = document.getElementById('spec-enabled');
    const specLimitInput = document.getElementById('spec-limit');
    const btnSaveSpec = document.getElementById('btn-save-spec');
    const specTableBody = document.querySelector('#spec-table tbody');
    const historyTableBody = document.querySelector('#history-table tbody');

    // 初始化日期输入框为今天
    const todayStr = new Date().toISOString().split('T')[0];
    specDateInput.value = todayStr;
    todayDateTag.textContent = todayStr;

    // 修复请求地址为绝对路径或带 /schedule 前缀的相对路径
    function apiFetch(endpoint, options = {}) {
        const url = './' + endpoint.replace(/^\/+/, '');
        return fetch(url, options);
    }

    // 渲染时段输入行
    function renderDefaultIntervals(intervals) {
        defaultIntervalsContainer.innerHTML = '';
        if (!intervals || intervals.length === 0) {
            intervals = [{ start: '08:00', end: '23:30' }];
        }
        intervals.forEach((interval, index) => {
            const row = document.createElement('div');
            row.className = 'form-row';
            row.style.marginBottom = '8px';
            row.innerHTML = `
                <input type="time" class="form-control def-start" value="${interval.start || '08:00'}" style="width: 130px;">
                <span>~</span>
                <input type="time" class="form-control def-end" value="${interval.end || '23:30'}" style="width: 130px;">
                <button type="button" class="btn btn-danger" style="padding: 6px 10px; font-size: 12px;" data-index="${index}">删除</button>
            `;
            row.querySelector('button').addEventListener('click', () => {
                intervals.splice(index, 1);
                renderDefaultIntervals(intervals);
            });
            defaultIntervalsContainer.appendChild(row);
        });
    }

    let currentIntervals = [];

    btnAddInterval.addEventListener('click', () => {
        currentIntervals.push({ start: '14:00', end: '18:00' });
        renderDefaultIntervals(currentIntervals);
    });

    // 加载数据
    function loadData() {
        apiFetch('status')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    updateUI(data);
                } else {
                    console.error('加载状态失败', data);
                }
            })
            .catch(err => {
                console.error('网络请求失败:', err);
            });
    }

    function updateUI(data) {
        const canRun = data.can_run;
        const reason = data.reason;
        const cfg = data.config;
        const todayLog = data.today_log;
        const recentLogs = data.recent_logs || [];

        // 顶栏状态
        if (canRun) {
            masterStatusBadge.className = 'badge-running';
            masterStatusText.textContent = '运行正常（允许执行）';
        } else {
            masterStatusBadge.className = 'badge-stopped';
            masterStatusText.textContent = '已暂停 / 拦截（' + reason + '）';
        }

        // 配置表单填充
        masterEnabledCheckbox.checked = !!cfg.master_enabled;
        defaultEnabledCheckbox.checked = !!cfg.default_enabled;
        currentIntervals = cfg.default_intervals || [{ start: '08:00', end: '23:30' }];
        renderDefaultIntervals(currentIntervals);
        dailyLimitInput.value = cfg.daily_limit_minutes || 300;

        // 今日状态展示
        todayRuntimeEl.textContent = (todayLog.runtime_minutes || 0) + ' 分钟';
        todayCanRunEl.textContent = canRun ? '允许运行' : '禁止运行';
        todayCanRunEl.style.color = canRun ? 'var(--accent-green)' : 'var(--accent-red)';
        statusReasonText.textContent = reason;

        // 特殊日期表格渲染
        renderSpecTable(cfg.specific_dates || {});

        // 历史趋势与表格
        renderHistory(recentLogs);
    }

    function renderSpecTable(specificDates) {
        specTableBody.innerHTML = '';
        const dates = Object.keys(specificDates).sort().reverse();
        if (dates.length === 0) {
            specTableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">暂无特殊日期设置</td></tr>`;
            return;
        }

        dates.forEach(date => {
            const item = specificDates[date];
            const intervalsStr = (item.intervals || []).map(i => `${i.start}~${i.end}`).join(', ') || '-';
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${date}</strong></td>
                <td><span class="tag" style="background: ${item.enabled ? 'rgba(74, 222, 128, 0.1); color: var(--accent-green)' : 'rgba(248, 113, 113, 0.1); color: var(--accent-red)'}">${item.enabled ? '允许运行' : '禁止运行'}</span></td>
                <td>${intervalsStr}</td>
                <td>${item.daily_limit_minutes || '-'} 分钟</td>
                <td><button class="btn btn-danger" style="padding: 4px 10px; font-size: 12px;" data-date="${date}">删除</button></td>
            `;
            tr.querySelector('button').addEventListener('click', () => {
                deleteSpecificDate(date, specificDates);
            });
            specTableBody.appendChild(tr);
        });
    }

    function deleteSpecificDate(dateKey, specificDates) {
        if (!confirm(`确定删除日期 ${dateKey} 的特殊设置吗？`)) return;
        delete specificDates[dateKey];
        saveConfigAndReload({ specific_dates: specificDates });
    }

    function saveConfigAndReload(partialConfig) {
        // 从DOM收集最新的 default_intervals
        const intervals = [];
        defaultIntervalsContainer.querySelectorAll('.form-row').forEach(row => {
            const st = row.querySelector('.def-start').value;
            const et = row.querySelector('.def-end').value;
            if (st && et) {
                intervals.push({ start: st, end: et });
            }
        });

        const payload = {
            master_enabled: masterEnabledCheckbox.checked,
            default_enabled: defaultEnabledCheckbox.checked,
            default_intervals: intervals,
            daily_limit_minutes: parseInt(dailyLimitInput.value) || 300,
            ...partialConfig
        };

        apiFetch('config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                alert('配置保存成功！');
                loadData();
            } else {
                alert('保存失败: ' + data.message);
            }
        })
        .catch(err => {
            console.error('保存配置异常:', err);
            alert('网络请求异常');
        });
    }

    // 监听表单提交
    configForm.addEventListener('submit', (e) => {
        e.preventDefault();
        saveConfigAndReload({});
    });

    // 监听特例添加
    btnSaveSpec.addEventListener('click', () => {
        const dateVal = specDateInput.value;
        if (!dateVal) {
            alert('请选择有效日期');
            return;
        }
        apiFetch('config')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    const cfg = data.config;
                    if (!cfg.specific_dates) cfg.specific_dates = {};
                    
                    cfg.specific_dates[dateVal] = {
                        enabled: specEnabledSelect.value === 'true',
                        intervals: [{ start: '08:00', end: '23:30' }], // 默认简化为一个特例时段
                        daily_limit_minutes: parseInt(specLimitInput.value) || 300
                    };
                    saveConfigAndReload({ specific_dates: cfg.specific_dates });
                }
            });
    });

    // 手动上报状态
    btnReport.addEventListener('click', () => {
        const mins = parseFloat(reportMinsInput.value) || 0;
        const statusVal = reportStatusSelect.value;
        
        apiFetch('report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                runtime_minutes: mins,
                add_minutes: true,
                status: statusVal,
                message: '前端看板手动上报测试'
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                alert('状态上报成功！');
                loadData();
            } else {
                alert('上报失败: ' + data.message);
            }
        });
    });

    btnRefresh.addEventListener('click', loadData);

    // 渲染历史图表与表格
    function renderHistory(logs) {
        historyTableBody.innerHTML = '';
        if (logs.length === 0) {
            historyTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">暂无往期运行记录</td></tr>`;
        }

        logs.forEach(item => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${item.date || '-'}</td>
                <td><strong>${item.runtime_minutes || 0}</strong> 分钟</td>
                <td><span class="tag">${item.status || 'unknown'}</span></td>
                <td>${item.message || '-'} (${item.update_time || ''})</td>
            `;
            historyTableBody.appendChild(tr);
        });

        const chartData = [...logs].reverse().slice(-15);
        const dates = chartData.map(i => i.date);
        const runtimes = chartData.map(i => i.runtime_minutes || 0);

        if (!historyChart) {
            historyChart = echarts.init(document.getElementById('history-chart'));
        }

        const option = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: '#334155',
                textStyle: { color: '#f8fafc' }
            },
            grid: { top: 40, bottom: 30, left: 50, right: 20 },
            xAxis: {
                type: 'category',
                data: dates,
                axisLine: { lineStyle: { color: '#334155' } },
                axisLabel: { color: '#94a3b8' }
            },
            yAxis: {
                type: 'value',
                name: '运行分钟',
                nameTextStyle: { color: '#94a3b8' },
                axisLine: { lineStyle: { color: '#334155' } },
                splitLine: { lineStyle: { color: 'rgba(51, 65, 85, 0.3)' } },
                axisLabel: { color: '#94a3b8' }
            },
            series: [{
                data: runtimes,
                type: 'bar',
                barWidth: '45%',
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: '#38bdf8' },
                        { offset: 1, color: '#0284c7' }
                    ]),
                    borderRadius: [6, 6, 0, 0]
                }
            }]
        };

        historyChart.setOption(option);
    }

    loadData();
    setInterval(loadData, 15000);
});

function updateElementText(id, text) {
    const el = document.getElementById(id) || document.querySelector(`#section-status #${id}`);
    if (el) el.textContent = text;
}

async function loadAllStatusData() {
    try {
        const statRes = await fetch('/main/stats/get');
        if (statRes.ok) {
            const data = await statRes.json();
            const zs = data.zOnepush || {};
            const bs = data.qbot || {};

            updateElementText('statAutoCheck', (zs.auto_check_count || 0) + ' 次');
            updateElementText('statPushCount', (zs.push_handle_count || 0) + ' 次');
            updateElementText('statRuntime', (zs.total_runtime_hours || 0) + ' 小时');
            updateElementText('statsUpdatedTime', '更新于 ' + new Date().toLocaleTimeString());

            if (bs && (bs.status === 'success' || bs.total_messages !== undefined)) {
                updateElementText('statBotTotalMsg', (bs.total_messages || 0) + ' 条');
                updateElementText('statBotReply', (bs.reply_count || 0) + ' 条');
                updateElementText('statBotHandle', (bs.processed_count || 0) + ' 次');
                updateElementText('statBotGroups', (bs.active_groups_count || 0) + ' 个');
            }
        }
    } catch (e) {
        console.error('加载统计失败:', e);
    }

    try {
        const pingRes = await fetch('/ping');
        if (pingRes.ok) {
            const pingData = await pingRes.json();
            const hpEl = document.getElementById('svHandlepush') || document.querySelector('#section-status #svHandlepush');
            const mumuEl = document.getElementById('svMumu') || document.querySelector('#section-status #svMumu');
            const alasEl = document.getElementById('svAlas') || document.querySelector('#section-status #svAlas');
            if (hpEl) {
                const active = pingData.handlepush !== undefined ? pingData.handlepush : true;
                hpEl.textContent = active ? '🟢 运行中' : '🔴 已暂停';
                hpEl.className = active ? 'text-xs font-bold px-2.5 py-1 rounded bg-emerald-950/60 text-emerald-300' : 'text-xs font-bold px-2.5 py-1 rounded bg-rose-950/60 text-rose-300';
            }
            if (mumuEl) { mumuEl.textContent = '🟢 运行中'; mumuEl.className = 'text-xs font-bold px-2.5 py-1 rounded bg-emerald-950/60 text-emerald-300'; }
            if (alasEl) { alasEl.textContent = '🟢 运行中'; alasEl.className = 'text-xs font-bold px-2.5 py-1 rounded bg-emerald-950/60 text-emerald-300'; }
        }
    } catch (e) {
        const hpEl = document.getElementById('svHandlepush') || document.querySelector('#section-status #svHandlepush');
        const mumuEl = document.getElementById('svMumu') || document.querySelector('#section-status #svMumu');
        const alasEl = document.getElementById('svAlas') || document.querySelector('#section-status #svAlas');
        if (hpEl) { hpEl.textContent = '🟢 运行中'; hpEl.className = 'text-xs font-bold px-2.5 py-1 rounded bg-emerald-950/60 text-emerald-300'; }
        if (mumuEl) { mumuEl.textContent = '🟢 运行中'; mumuEl.className = 'text-xs font-bold px-2.5 py-1 rounded bg-emerald-950/60 text-emerald-300'; }
        if (alasEl) { alasEl.textContent = '🟢 运行中'; alasEl.className = 'text-xs font-bold px-2.5 py-1 rounded bg-emerald-950/60 text-emerald-300'; }
    }

    try {
        const resRes = await fetch('/main/ap/get');
        if (resRes.ok) {
            const jsonFull = await resRes.json();
            const apData = jsonFull.data || jsonFull;
            const resources = apData.resources || [];
            const container = document.getElementById('resourceMonitorContainer') || document.querySelector('#section-status #resourceMonitorContainer');
            const timeEl = document.getElementById('resourceUpdatedTime') || document.querySelector('#section-status #resourceUpdatedTime');
            if (timeEl && apData.updated_at) timeEl.textContent = '更新时间: ' + apData.updated_at;

            if (container) {
                if (resources.length > 0) {
                    container.innerHTML = resources.map(item => {
                        const timeDisplay = item.formatted_time || item.time_text || '刚刚';
                        const iconHtml = item.icon ? `<img src="${item.icon}" class="w-6 h-6 object-contain inline-block mr-2" alt="">` : '';
                        const limitText = item.limit ? `<small class="text-slate-400 ml-1">${item.limit}</small>` : '';
                        return `
                            <div class="bg-slate-900/60 p-3 rounded-xl border border-slate-800 flex items-center justify-between text-xs">
                                <div class="flex items-center">
                                    ${iconHtml}
                                    <span class="font-bold text-slate-200">${item.name || '资源'}</span>
                                    <span class="ml-3 px-2 py-0.5 rounded text-xs bg-indigo-950/60 text-indigo-300 font-mono">${item.amount || '0'}${limitText}</span>
                                </div>
                                <div class="text-[11px] font-mono text-slate-400">
                                    <i class="fa-regular fa-clock mr-1"></i>${timeDisplay}
                                </div>
                            </div>
                        `;
                    }).join('');
                } else {
                    container.innerHTML = '<p class="text-xs text-slate-500 text-center py-6">暂无资源监控数据</p>';
                }
            }
        }
    } catch (e) {
        console.error('加载资源失败:', e);
    }

    try {
        const tasksRes = await fetch('/main/ap/get2');
        if (tasksRes.ok) {
            const jsonFull = await tasksRes.json();
            const tData = jsonFull.data || jsonFull;
            const running = tData.running || [];
            const queued = tData.queued || [];
            const waiting = tData.waiting || [];
            const timeEl = document.getElementById('tasksUpdatedTime') || document.querySelector('#section-status #tasksUpdatedTime');
            if (timeEl && tData.updated_at) timeEl.textContent = '更新时间: ' + tData.updated_at;

            const container = document.getElementById('tasksMonitorContainer') || document.querySelector('#section-status #tasksMonitorContainer');
            if (container) {
                let htmlBuf = '';
                if (running.length > 0) {
                    htmlBuf += `<div class="mb-3"><span class="text-[10px] font-bold text-emerald-400 uppercase">🟢 运行中 (${running.length})</span><div class="space-y-1.5 mt-1.5">`;
                    running.forEach(t => {
                        htmlBuf += `<div class="bg-emerald-950/30 p-2.5 rounded-lg border border-emerald-800/50 flex items-center justify-between text-xs">
                            <span class="font-medium text-emerald-200">${t.title}</span>
                            <span class="text-[10px] font-mono text-emerald-400">${t.formatted_time || t.time_text}</span>
                        </div>`;
                    });
                    htmlBuf += `</div></div>`;
                }
                if (queued.length > 0) {
                    htmlBuf += `<div class="mb-3"><span class="text-[10px] font-bold text-amber-400 uppercase">🟡 队列中 (${queued.length})</span><div class="space-y-1.5 mt-1.5">`;
                    queued.forEach(t => {
                        htmlBuf += `<div class="bg-amber-950/30 p-2.5 rounded-lg border border-amber-800/50 flex items-center justify-between text-xs">
                            <span class="font-medium text-amber-200">${t.title}</span>
                            <span class="text-[10px] font-mono text-amber-400">${t.formatted_time || t.time_text}</span>
                        </div>`;
                    });
                    htmlBuf += `</div></div>`;
                }
                if (waiting.length > 0) {
                    htmlBuf += `<div><span class="text-[10px] font-bold text-slate-400 uppercase">⚪ 等待中 (${waiting.length})</span><div class="space-y-1.5 mt-1.5">`;
                    waiting.forEach(t => {
                        htmlBuf += `<div class="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between text-xs">
                            <span class="font-medium text-slate-300">${t.title}</span>
                            <span class="text-[10px] font-mono text-slate-400">${t.formatted_time || t.time_text}</span>
                        </div>`;
                    });
                    htmlBuf += `</div></div>`;
                }
                if (running.length === 0 && queued.length === 0 && waiting.length === 0) {
                    container.innerHTML = '<p class="text-xs text-slate-500 text-center py-6">当前无活跃任务</p>';
                } else {
                    container.innerHTML = htmlBuf;
                }
            }
        }
    } catch (e) {
        console.error('加载任务失败:', e);
    }

    try {
        const shotRes = await fetch('/main/ap/get3');
        if (shotRes.ok) {
            const shotData = await shotRes.json();
            const container = document.getElementById('screenshotContainer') || document.querySelector('#section-status #screenshotContainer');
            const timeEl = document.getElementById('screenshotUpdatedTime') || document.querySelector('#section-status #screenshotUpdatedTime');
            if (timeEl && shotData.updated_at) timeEl.textContent = '更新时间: ' + shotData.updated_at;

            if (container) {
                if (shotData.exists && shotData.screenshot_url) {
                    container.innerHTML = `<img src="${shotData.screenshot_url}?t=${Date.now()}" class="max-w-full max-h-[600px] rounded-lg shadow-lg object-contain border border-slate-800" alt="实时截图">`;
                } else {
                    container.innerHTML = '<p class="text-xs text-slate-500 py-12">暂无实时截图缓存</p>';
                }
            }
        }
    } catch (e) {
        console.error('加载截图失败:', e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadAllStatusData();
    setInterval(loadAllStatusData, 10000);
});

// --- 1. Theme Switcher Logic ---
const themeToggleBtn = document.getElementById('themeToggle');
const themeIcon = document.getElementById('themeIcon');
const htmlElem = document.documentElement;

function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        htmlElem.classList.add('dark');
        if (themeIcon) themeIcon.className = 'fa-solid fa-sun text-amber-400 text-sm';
    } else {
        htmlElem.classList.remove('dark');
        if (themeIcon) themeIcon.className = 'fa-solid fa-moon text-slate-700 text-sm';
    }
}

if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
        if (htmlElem.classList.contains('dark')) {
            htmlElem.classList.remove('dark');
            localStorage.setItem('theme', 'light');
            if (themeIcon) themeIcon.className = 'fa-solid fa-moon text-slate-700 text-sm';
        } else {
            htmlElem.classList.add('dark');
            localStorage.setItem('theme', 'dark');
            if (themeIcon) themeIcon.className = 'fa-solid fa-sun text-amber-400 text-sm';
        }
    });
}

// --- 2. Open Mode Switcher (Current Tab vs New Tab) ---
let openInNewTab = localStorage.getItem('openInNewTab') === 'true';

function applyTargetMode() {
    const links = document.querySelectorAll('.service-link');
    const toggleIcon = document.getElementById('targetToggleIcon');
    const toggleText = document.getElementById('targetToggleText');

    links.forEach(link => {
        link.setAttribute('target', openInNewTab ? '_blank' : '_self');
    });

    if (toggleIcon && toggleText) {
        if (openInNewTab) {
            toggleIcon.className = 'fa-solid fa-arrow-up-right-from-square text-indigo-500';
            toggleText.textContent = '新标签页打开';
        } else {
            toggleIcon.className = 'fa-solid fa-arrow-right-to-bracket text-slate-400';
            toggleText.textContent = '当前页打开';
        }
    }
}

function toggleNewTabMode() {
    openInNewTab = !openInNewTab;
    localStorage.setItem('openInNewTab', openInNewTab);
    applyTargetMode();
    showToast(openInNewTab ? '已开启：在新标签页中打开访问' : '已恢复：在当前页直接跳转');
}

// --- 3. Live Clock Widget ---
function updateClock() {
    const clockText = document.getElementById('clockText');
    if (clockText) {
        const now = new Date();
        clockText.textContent = now.toLocaleTimeString('zh-CN', { hour12: false });
    }
}
setInterval(updateClock, 1000);
updateClock();

// --- 4. Copy to Clipboard & Toast ---
function copyToClipboard(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    
    try {
        document.execCommand('copy');
        showToast('已复制地址: ' + text);
    } catch (err) {
        showToast('复制失败，请手动选择复制');
    } finally {
        document.body.removeChild(textarea);
    }
}

function showToast(message) {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toastMsg');
    if (toast && toastMsg) {
        toastMsg.textContent = message;
        toast.classList.remove('translate-y-20', 'opacity-0');
        
        setTimeout(() => {
            toast.classList.add('translate-y-20', 'opacity-0');
        }, 2300);
    }
}

// --- 5. Category Tab Switcher & Partial Loading for Status ---
const tabBtns = document.querySelectorAll('.tab-btn[data-target]');
const sectionProxy = document.getElementById('section-proxy');
const sectionLocal = document.getElementById('section-local');
const sectionStatus = document.getElementById('section-status');

let statusLoaded = false;

async function loadStatusSectionContent() {
    if (statusLoaded) return;
    try {
        const res = await fetch('status.html');
        if (res.ok) {
            const htmlText = await res.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(htmlText, 'text/html');
            // 获取 status.html 中真正的 main 标签内部所有子元素或 HTML
            const mainElem = doc.querySelector('main');
            
            if (sectionStatus) {
                if (mainElem) {
                    sectionStatus.innerHTML = mainElem.innerHTML;
                } else {
                    sectionStatus.innerHTML = doc.body.innerHTML;
                }
            }
            statusLoaded = true;

            if (typeof loadAllStatusData === 'function') {
                loadAllStatusData();
            }
        }
    } catch (e) {
        console.error('加载 status.html 失败:', e);
        if (sectionStatus) {
            sectionStatus.innerHTML = '<p class="text-xs text-rose-500 text-center py-6">加载状态页内容失败，请检查文件权限或网络。</p>';
        }
    }
}

tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        tabBtns.forEach(b => {
            b.classList.remove('active', 'text-indigo-600', 'dark:text-indigo-400', 'font-semibold', 'border-b-2', 'border-indigo-600', 'dark:border-indigo-400');
            b.classList.add('text-slate-500', 'dark:text-slate-400', 'font-medium');
        });
        btn.classList.add('active', 'text-indigo-600', 'dark:text-indigo-400', 'font-semibold', 'border-b-2', 'border-indigo-600', 'dark:border-indigo-400');
        btn.classList.remove('text-slate-500', 'dark:text-slate-400', 'font-medium');

        const target = btn.dataset.target;
        if (target === 'all') {
            if (sectionProxy) sectionProxy.classList.remove('hidden');
            if (sectionLocal) sectionLocal.classList.remove('hidden');
            if (sectionStatus) sectionStatus.classList.add('hidden');
        } else if (target === 'proxy') {
            if (sectionProxy) sectionProxy.classList.remove('hidden');
            if (sectionLocal) sectionLocal.classList.add('hidden');
            if (sectionStatus) sectionStatus.classList.add('hidden');
        } else if (target === 'local') {
            if (sectionProxy) sectionProxy.classList.add('hidden');
            if (sectionLocal) sectionLocal.classList.remove('hidden');
            if (sectionStatus) sectionStatus.classList.add('hidden');
        } else if (target === 'status') {
            if (sectionProxy) sectionProxy.classList.add('hidden');
            if (sectionLocal) sectionLocal.classList.add('hidden');
            if (sectionStatus) {
                sectionStatus.classList.remove('hidden');
                loadStatusSectionContent().then(() => {
                    if (typeof loadAllStatusData === 'function') {
                        loadAllStatusData();
                    }
                });
            }
        }
    });
});

// Initialize theme and target mode on page load
initTheme();
applyTargetMode();

// --- 6. Load System Status and Dashboard on Index ---
async function loadIndexSystemStatusAndDashboard() {
    try {
        try {
            const statsRes = await fetch('/main/stats/get');
            if (statsRes.ok) {
                const statsJson = await statsRes.json();
                const sData = statsJson.data || statsJson;
                const zStats = sData.zOnepush || {};
                const bStats = sData.qbot || {};

                const autoCheckEl = document.getElementById('statAutoCheck') || document.querySelector('#section-status #statAutoCheck');
                const pushCountEl = document.getElementById('statPushCount') || document.querySelector('#section-status #statPushCount');
                const runtimeEl = document.getElementById('statRuntime') || document.querySelector('#section-status #statRuntime');
                const botTotalMsgEl = document.getElementById('statBotTotalMsg') || document.querySelector('#section-status #statBotTotalMsg');
                const botReplyEl = document.getElementById('statBotReply') || document.querySelector('#section-status #statBotReply');
                const botHandleEl = document.getElementById('statBotHandle') || document.querySelector('#section-status #statBotHandle');
                const botGroupsEl = document.getElementById('statBotGroups') || document.querySelector('#section-status #statBotGroups');

                if (autoCheckEl) autoCheckEl.textContent = (zStats.auto_check_count || 0) + ' 次';
                if (pushCountEl) pushCountEl.textContent = (zStats.push_handle_count || 0) + ' 次';
                
                if (runtimeEl) {
                    const hours = zStats.total_runtime_hours || 0;
                    runtimeEl.textContent = hours >= 1 ? hours + ' 小时' : Math.round((zStats.total_runtime_seconds || 0) / 60) + ' 分钟';
                }

                if (bStats.status === 'success' || bStats.total_messages !== undefined) {
                    if (botTotalMsgEl) botTotalMsgEl.textContent = (bStats.total_messages || 0) + ' 条';
                    if (botReplyEl) botReplyEl.textContent = (bStats.reply_count || 0) + ' 条';
                    if (botHandleEl) botHandleEl.textContent = (bStats.processed_count || 0) + ' 次';
                    if (botGroupsEl) botGroupsEl.textContent = (bStats.active_groups_count || 0) + ' 个';
                } else {
                    if (botTotalMsgEl) botTotalMsgEl.textContent = '离线';
                    if (botReplyEl) botReplyEl.textContent = '离线';
                    if (botHandleEl) botHandleEl.textContent = '离线';
                    if (botGroupsEl) botGroupsEl.textContent = '离线';
                }
            }
        } catch (eStats) {
            console.error('加载综合统计数据失败:', eStats);
        }

        try {
            const svRes = await fetch('/ping');
            if (svRes.ok) {
                const svData = await svRes.json();
                const hpEl = document.getElementById('indexSvHandlepush');
                const mumuEl = document.getElementById('indexSvMumu');
                const alasEl = document.getElementById('indexSvAlas');

                if (hpEl) {
                    const active = svData.handlepush !== undefined ? svData.handlepush : true;
                    hpEl.textContent = active ? '🟢 运行中' : '🔴 已暂停';
                    hpEl.className = active ? 'text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300' : 'text-xs font-bold px-2 py-0.5 rounded bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300';
                }
                if (mumuEl) {
                    mumuEl.textContent = '🟢 运行中';
                    mumuEl.className = 'text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300';
                }
                if (alasEl) {
                    alasEl.textContent = '🟢 运行中';
                    alasEl.className = 'text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300';
                }
            }
        } catch (eSv) {
            console.error('加载系统状态失败:', eSv);
        }
    } catch (e) {
        console.error('加载首页系统状态失败:', e);
    }
}

loadIndexSystemStatusAndDashboard();
setInterval(loadIndexSystemStatusAndDashboard, 10000);

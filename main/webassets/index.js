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

// --- 5. Fetch and Render Navigation from index.json with Fixed Color Cycle ---
const CARD_COLOR_THEMES = [
    {
        name: 'indigo',
        bg: 'bg-indigo-500/10 dark:bg-indigo-500/20',
        text: 'text-indigo-600 dark:text-indigo-400',
        badgeBg: 'bg-indigo-100 dark:bg-indigo-900/50',
        badgeText: 'text-indigo-600 dark:text-indigo-400',
        btnBg: 'bg-indigo-600 hover:bg-indigo-700 text-white',
        borderClass: 'border-l-2 border-l-indigo-500'
    },
    {
        name: 'purple',
        bg: 'bg-purple-500/10 dark:bg-purple-500/20',
        text: 'text-purple-600 dark:text-purple-400',
        badgeBg: 'bg-purple-100 dark:bg-purple-900/50',
        badgeText: 'text-purple-600 dark:text-purple-400',
        btnBg: 'bg-purple-600 hover:bg-purple-700 text-white',
        borderClass: 'border-l-2 border-l-purple-500'
    },
    {
        name: 'cyan',
        bg: 'bg-cyan-500/10 dark:bg-cyan-500/20',
        text: 'text-cyan-600 dark:text-cyan-400',
        badgeBg: 'bg-cyan-100 dark:bg-cyan-900/50',
        badgeText: 'text-cyan-600 dark:text-cyan-400',
        btnBg: 'bg-cyan-600 hover:bg-cyan-700 text-white',
        borderClass: 'border-l-2 border-l-cyan-500'
    },
    {
        name: 'emerald',
        bg: 'bg-emerald-500/10 dark:bg-emerald-500/20',
        text: 'text-emerald-600 dark:text-emerald-400',
        badgeBg: 'bg-emerald-100 dark:bg-emerald-900/50',
        badgeText: 'text-emerald-600 dark:text-emerald-400',
        btnBg: 'bg-emerald-600 hover:bg-emerald-700 text-white',
        borderClass: 'border-l-2 border-l-emerald-500'
    },
    {
        name: 'amber',
        bg: 'bg-amber-500/10 dark:bg-amber-500/20',
        text: 'text-amber-600 dark:text-amber-400',
        badgeBg: 'bg-amber-100 dark:bg-amber-900/50',
        badgeText: 'text-amber-600 dark:text-amber-400',
        btnBg: 'bg-amber-600 hover:bg-amber-700 text-white',
        borderClass: 'border-l-2 border-l-amber-500'
    },
    {
        name: 'rose',
        bg: 'bg-rose-500/10 dark:bg-rose-500/20',
        text: 'text-rose-600 dark:text-rose-400',
        badgeBg: 'bg-rose-100 dark:bg-rose-900/50',
        badgeText: 'text-rose-600 dark:text-rose-400',
        btnBg: 'bg-rose-600 hover:bg-rose-700 text-white',
        borderClass: 'border-l-2 border-l-rose-500'
    }
];

let serverIpCache = null;

async function fetchServerIp() {
    if (serverIpCache) return serverIpCache;
    try {
        const res = await fetch('/getip');
        if (res.ok) {
            const data = await res.json();
            if (data.ip) {
                serverIpCache = data.ip;
                return serverIpCache;
            }
        }
    } catch (e) {
        try {
            const res2 = await fetch('/main/getip');
            if (res2.ok) {
                const data2 = await res2.json();
                if (data2.ip) {
                    serverIpCache = data2.ip;
                    return serverIpCache;
                }
            }
        } catch (e2) {
            console.error('获取服务端 IP 失败:', e2);
        }
    }
    return null;
}

let statusLoaded = false;

async function loadStatusSectionContent() {
    if (statusLoaded) return;
    const sectionStatus = document.getElementById('section-status');
    try {
        const res = await fetch('status.html');
        if (res.ok) {
            const htmlText = await res.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(htmlText, 'text/html');
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

async function initNavigation() {
    const categoryNav = document.getElementById('categoryNav');
    const dynamicContainer = document.getElementById('dynamicSectionsContainer');

    try {
        const [response, serverIp] = await Promise.all([
            fetch('./index.json'),
            fetchServerIp()
        ]);
        if (!response.ok) throw new Error('Failed to load index.json');
        const sections = await response.json();

        // 1. 构建选项卡按钮
        let navHtml = `<button class="tab-btn active text-indigo-600 dark:text-indigo-400 font-semibold border-b-2 border-indigo-600 dark:border-indigo-400 pb-2 text-xs sm:text-sm px-2" data-target="all">全部区域</button>`;
        
        sections.forEach(sec => {
            const iconHtml = sec.icon ? `<i class="${sec.icon}"></i>` : '';
            navHtml += `<button class="tab-btn text-slate-500 dark:text-slate-400 font-medium hover:text-slate-700 dark:hover:text-slate-200 pb-2 text-xs sm:text-sm px-2 flex items-center gap-1.5" data-target="${sec.id}">${iconHtml}${sec.name}</button>`;
        });
        categoryNav.innerHTML = navHtml;

        // 2. 构建各板块内容
        let sectionsHtml = '';
        
        sections.forEach(sec => {
            if (sec.type === 'status') {
                sectionsHtml += `
                    <section id="section-status" class="region-section space-y-6 hidden">
                        <div class="flex justify-center items-center py-20">
                            <div class="flex items-center gap-2 text-slate-400 text-sm">
                                <i class="fa-solid fa-circle-notch fa-spin text-indigo-500"></i> 正在加载状态区内容...
                            </div>
                        </div>
                    </section>
                `;
            } else if (sec.type === 'grid-local') {
                sectionsHtml += `
                    <section id="section-${sec.id}" class="region-section space-y-3 pt-2">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
                                <h2 class="text-base font-bold text-slate-800 dark:text-slate-100">${sec.name}</h2>
                                <span class="text-[10px] font-normal text-slate-500 dark:text-slate-400 bg-slate-200/60 dark:bg-slate-800 px-2 py-0.5 rounded-full">IP:Port</span>
                            </div>
                        </div>
                        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                `;
                if (sec.cards && sec.cards.length > 0) {
                    sec.cards.forEach((card, index) => {
                        const theme = CARD_COLOR_THEMES[index % CARD_COLOR_THEMES.length];
                        
                        let displayIp = card.ip;
                        let displayUrl = card.url;
                        let displayCopyUrl = card.copyUrl || card.url;

                        if (serverIp) {
                            let targetPort = card.port ? card.port.replace(':', '') : '';
                            if (!targetPort && displayUrl) {
                                try {
                                    const parsed = new URL(displayUrl, window.location.origin);
                                    if (parsed.port) {
                                        targetPort = parsed.port;
                                    }
                                } catch (e) {}
                            }
                            if (!targetPort) {
                                targetPort = window.location.port || '80';
                            }

                            let pathPart = '/';
                            if (displayUrl) {
                                try {
                                    const parsed = new URL(displayUrl, window.location.origin);
                                    pathPart = parsed.pathname + parsed.search + parsed.hash;
                                } catch (e) {
                                    pathPart = displayUrl;
                                    if (!pathPart.startsWith('/')) {
                                        pathPart = '/' + pathPart;
                                    }
                                }
                            }
                            displayUrl = `http://${serverIp}:${targetPort}${pathPart}`;

                            let copyPathPart = pathPart;
                            if (displayCopyUrl) {
                                try {
                                    const parsedCopy = new URL(displayCopyUrl, window.location.origin);
                                    copyPathPart = parsedCopy.pathname + parsedCopy.search + parsedCopy.hash;
                                } catch (e) {
                                    copyPathPart = displayCopyUrl;
                                    if (!copyPathPart.startsWith('/')) {
                                        copyPathPart = '/' + copyPathPart;
                                    }
                                }
                            }
                            displayCopyUrl = `http://${serverIp}:${targetPort}${copyPathPart}`;

                            displayIp = `${serverIp}:${targetPort}`;
                        }

                        const borderClass = card.borderColor ? `border-l-2 border-l-${card.borderColor}-500` : theme.borderClass;
                        sectionsHtml += `
                            <div class="service-card glass-panel rounded-xl p-4 card-hover relative group flex flex-col justify-between ${borderClass}">
                                <div>
                                    <div class="flex items-center justify-between mb-2">
                                        <div class="w-8 h-8 rounded-lg ${theme.bg} ${theme.text} flex items-center justify-center text-sm">
                                            <i class="${card.icon || 'fa-solid fa-link'}"></i>
                                        </div>
                                        <span class="text-xs font-mono font-bold text-slate-500 dark:text-slate-400">${card.port}</span>
                                    </div>
                                    <h3 class="font-bold text-slate-900 dark:text-white text-sm mb-0.5">${card.title}</h3>
                                    <p class="text-[11px] text-slate-500 dark:text-slate-400 mb-2">${displayIp || card.ip}</p>
                                </div>
                                <div class="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between">
                                    <button onclick="copyToClipboard('${displayCopyUrl}')" class="text-[10px] text-slate-400 hover:text-indigo-500 transition-colors flex items-center gap-1">
                                        <i class="fa-regular fa-copy"></i> 复制
                                    </button>
                                    <a href="${displayUrl}" target="_self" class="service-link inline-flex items-center gap-1 text-[11px] font-medium ${theme.text} bg-slate-100 dark:bg-slate-900 hover:bg-slate-200 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700/50 px-2 py-0.5 rounded-md transition-colors">
                                        直连 <i class="fa-solid fa-chevron-right text-[8px]"></i>
                                    </a>
                                </div>
                            </div>
                        `;
                    });
                }
                sectionsHtml += `</div></section>`;
            } else {
                // 标准反向代理区域 (包含内置或自定的系统服务总监控)
                sectionsHtml += `
                    <section id="section-${sec.id}" class="region-section space-y-3">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                                <h2 class="text-base font-bold text-slate-800 dark:text-slate-100">${sec.name}访问区域</h2>
                                <span class="text-[10px] font-normal text-slate-500 dark:text-slate-400 bg-slate-200/60 dark:bg-slate-800 px-2 py-0.5 rounded-full">反向代理</span>
                            </div>
                        </div>

                        <!-- 实时服务与仪表盘数据展示区块 (仅在 proxy 区域展示) -->
                        ${sec.id === 'proxy' ? `
                        <div class="glass-panel rounded-2xl p-5 mb-4 shadow-lg border border-indigo-500/20">
                            <div class="flex items-center justify-between mb-3 pb-2 border-b border-slate-200/60 dark:border-slate-800/80">
                                <div class="flex items-center gap-2">
                                    <div class="w-7 h-7 rounded-lg bg-indigo-500/10 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 flex items-center justify-center text-sm">
                                        <i class="fa-solid fa-chart-pie"></i>
                                    </div>
                                    <h3 class="font-bold text-slate-900 dark:text-white text-sm sm:text-base">系统服务与仪表盘状态实时监控</h3>
                                </div>
                                <button onclick="loadIndexSystemStatusAndDashboard()" class="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 dark:hover:bg-indigo-900/80 px-2.5 py-1 rounded-md transition-colors shadow-sm">
                                    <i class="fa-solid fa-rotate"></i> 刷新数据
                                </button>
                            </div>

                            <!-- 状态指示网格 -->
                            <div id="indexServiceStatus" class="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                                <div class="bg-slate-100/60 dark:bg-slate-900/60 p-3 rounded-xl border border-slate-200/60 dark:border-slate-800 flex items-center justify-between">
                                    <span class="text-xs text-slate-500 dark:text-slate-400 font-medium">HandlePush 状态</span>
                                    <span id="indexSvHandlepush" class="text-xs font-bold px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300">检查中...</span>
                                </div>
                                <div class="bg-slate-100/60 dark:bg-slate-900/60 p-3 rounded-xl border border-slate-200/60 dark:border-slate-800 flex items-center justify-between">
                                    <span class="text-xs text-slate-500 dark:text-slate-400 font-medium">MuMu 进程状态</span>
                                    <span id="indexSvMumu" class="text-xs font-bold px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300">检查中...</span>
                                </div>
                                <div class="bg-slate-100/60 dark:bg-slate-900/60 p-3 rounded-xl border border-slate-200/60 dark:border-slate-800 flex items-center justify-between">
                                    <span class="text-xs text-slate-500 dark:text-slate-400 font-medium">Alas 进程状态</span>
                                    <span id="indexSvAlas" class="text-xs font-bold px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300">检查中...</span>
                                </div>
                            </div>

                            <!-- 综合统计面板（zOnepush 与 QBot） -->
                            <div class="bg-slate-100/50 dark:bg-slate-900/50 p-4 rounded-xl border border-indigo-500/20 mb-4">
                                <div class="flex items-center justify-between mb-3 pb-2 border-b border-slate-200/60 dark:border-slate-800/80">
                                    <h4 class="font-bold text-xs uppercase tracking-wider text-indigo-600 dark:text-indigo-400 flex items-center gap-1.5">
                                        <i class="fa-solid fa-chart-line"></i> 综合统计监控（zOnepush & QBot）
                                    </h4>
                                    <span id="statsUpdatedTime" class="text-[10px] text-slate-400 font-mono">实时更新中</span>
                                </div>
                                <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 text-center">
                                    <div class="bg-white/70 dark:bg-slate-800/70 p-2.5 rounded-lg border border-slate-200/50 dark:border-slate-700/50">
                                        <div class="text-[10px] text-slate-500 dark:text-slate-400 mb-1">自动化检查次数</div>
                                        <div id="statAutoCheck" class="font-bold text-indigo-600 dark:text-indigo-400 text-sm">--</div>
                                    </div>
                                    <div class="bg-white/70 dark:bg-slate-800/70 p-2.5 rounded-lg border border-slate-200/50 dark:border-slate-700/50">
                                        <div class="text-[10px] text-slate-500 dark:text-slate-400 mb-1">Push处理次数</div>
                                        <div id="statPushCount" class="font-bold text-emerald-600 dark:text-emerald-400 text-sm">--</div>
                                    </div>
                                    <div class="bg-white/70 dark:bg-slate-800/70 p-2.5 rounded-lg border border-slate-200/50 dark:border-slate-700/50">
                                        <div class="text-[10px] text-slate-500 dark:text-slate-400 mb-1">累计运行时长</div>
                                        <div id="statRuntime" class="font-bold text-purple-600 dark:text-purple-400 text-sm">--</div>
                                    </div>
                                    <div class="bg-white/70 dark:bg-slate-800/70 p-2.5 rounded-lg border border-slate-200/50 dark:border-slate-700/50">
                                        <div class="text-[10px] text-slate-500 dark:text-slate-400 mb-1">Bot消息总通量</div>
                                        <div id="statBotTotalMsg" class="font-bold text-cyan-600 dark:text-cyan-400 text-sm">--</div>
                                    </div>
                                    <div class="bg-white/70 dark:bg-slate-800/70 p-2.5 rounded-lg border border-slate-200/50 dark:border-slate-700/50">
                                        <div class="text-[10px] text-slate-500 dark:text-slate-400 mb-1">Bot回复量</div>
                                        <div id="statBotReply" class="font-bold text-blue-600 dark:text-blue-400 text-sm">--</div>
                                    </div>
                                    <div class="bg-white/70 dark:bg-slate-800/70 p-2.5 rounded-lg border border-slate-200/50 dark:border-slate-700/50">
                                        <div class="text-[10px] text-slate-500 dark:text-slate-400 mb-1">Bot处理指令</div>
                                        <div id="statBotHandle" class="font-bold text-amber-600 dark:text-amber-400 text-sm">--</div>
                                    </div>
                                    <div class="bg-white/70 dark:bg-slate-800/70 p-2.5 rounded-lg border border-slate-200/50 dark:border-slate-700/50">
                                        <div class="text-[10px] text-slate-500 dark:text-slate-400 mb-1">活跃群聊数</div>
                                        <div id="statBotGroups" class="font-bold text-pink-600 dark:text-pink-400 text-sm">--</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        ` : ''}

                        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                `;

                if (sec.cards && sec.cards.length > 0) {
                    sec.cards.forEach((card, index) => {
                        const theme = CARD_COLOR_THEMES[index % CARD_COLOR_THEMES.length];
                        const borderClass = card.borderColor ? `border-l-2 border-l-${card.borderColor}-500` : theme.borderClass;
                        sectionsHtml += `
                            <div class="service-card glass-panel rounded-xl p-4 card-hover relative group flex flex-col justify-between ${borderClass}">
                                <div>
                                    <div class="flex items-center justify-between mb-2.5">
                                        <div class="w-9 h-9 rounded-lg ${theme.bg} ${theme.text} flex items-center justify-center text-base">
                                            <i class="${card.icon || 'fa-solid fa-server'}"></i>
                                        </div>
                                        <span class="text-[9px] font-bold uppercase tracking-wider ${theme.badgeText} ${theme.badgeBg} px-1.5 py-0.5 rounded">${card.tag}</span>
                                    </div>
                                    <h3 class="font-bold text-slate-900 dark:text-white text-sm mb-1">${card.title}</h3>
                                    <p class="text-xs text-slate-500 dark:text-slate-400 mb-3 line-clamp-2">${card.description}</p>
                                </div>
                                <div class="pt-2.5 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between">
                                    <code class="text-[10px] text-slate-400 truncate max-w-[120px]">${card.code}</code>
                                    <a href="${card.url}" target="_self" class="service-link inline-flex items-center gap-1 text-[11px] font-medium text-white ${theme.btnBg} px-2.5 py-1 rounded-md transition-colors shadow-sm">
                                        访问 <i class="fa-solid fa-chevron-right text-[9px]"></i>
                                    </a>
                                </div>
                            </div>
                        `;
                    });
                }
                sectionsHtml += `</div></section>`;
            }
        });

        dynamicContainer.innerHTML = sectionsHtml;

        // 3. 绑定动态生成的选项卡点击事件
        bindTabEvents();

        // 4. 应用打开目标模式 (当前页/新标签页)
        applyTargetMode();

    } catch (e) {
        console.error('加载 index.json 失败:', e);
        dynamicContainer.innerHTML = `<p class="text-xs text-rose-500 text-center py-10">加载 index.json 导航配置失败，请检查文件格式。</p>`;
    }
}

function bindTabEvents() {
    const tabBtns = document.querySelectorAll('.tab-btn[data-target]');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => {
                b.classList.remove('active', 'text-indigo-600', 'dark:text-indigo-400', 'font-semibold', 'border-b-2', 'border-indigo-600', 'dark:border-indigo-400');
                b.classList.add('text-slate-500', 'dark:text-slate-400', 'font-medium');
            });
            btn.classList.add('active', 'text-indigo-600', 'dark:text-indigo-400', 'font-semibold', 'border-b-2', 'border-indigo-600', 'dark:border-indigo-400');
            btn.classList.remove('text-slate-500', 'dark:text-slate-400', 'font-medium');

            const target = btn.dataset.target;
            const allSections = document.querySelectorAll('.region-section');

            allSections.forEach(sec => {
                if (target === 'all') {
                    sec.classList.remove('hidden');
                } else {
                    if (sec.id === 'section-' + target) {
                        sec.classList.remove('hidden');
                    } else {
                        sec.classList.add('hidden');
                    }
                }
            });

            if (target === 'status' || target === 'all') {
                loadStatusSectionContent().then(() => {
                    if (typeof loadAllStatusData === 'function') {
                        loadAllStatusData();
                    }
                });
            }
        });
    });
}

// Initialize theme, target mode and navigation on page load
initTheme();
applyTargetMode();
initNavigation();

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
            // 1. 获取 /main/stats/get 状态
            const svRes = await fetch('/main/stats/get');
            if (svRes.ok) {
                const svData = await svRes.json();
                const data = svData.data || svData;
                
                const hpEl = document.getElementById('indexSvHandlepush');
                const mumuEl = document.getElementById('indexSvMumu');
                const alasEl = document.getElementById('indexSvAlas');

                if (hpEl) {
                const active = data.handlepush !== undefined ? data.handlepush : true;
                hpEl.textContent = active ? '🟢 运行中' : '🔴 已暂停';
                hpEl.className = active ? 'text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300' : 'text-xs font-bold px-2 py-0.5 rounded bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300';
                }
                if (mumuEl) {
                const active = data.mumu_running !== undefined ? data.mumu_running : true;
                mumuEl.textContent = active ? '🟢 运行中' : '⚪ 未运行';
                mumuEl.className = active ? 'text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300' : 'text-xs font-bold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400';
                }
                if (alasEl) {
                const active = data.alas_running !== undefined ? data.alas_running : true;
                alasEl.textContent = active ? '🟢 运行中' : '⚪ 未运行';
                alasEl.className = active ? 'text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300' : 'text-xs font-bold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400';
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

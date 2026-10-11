document.addEventListener('DOMContentLoaded', () => {
    let allFiles = [];
    let currentSortColumn = 'lines';
    let currentSortAscending = false;
    let myChart = null;
    let topChart = null;

    const targetDirEl = document.getElementById('target-dir');
    const statFilesEl = document.getElementById('stat-files');
    const statLinesEl = document.getElementById('stat-lines');
    const statCharsEl = document.getElementById('stat-chars');
    
    // 顶部新增指标卡元素
    const statMaxFileEl = document.getElementById('stat-max-file');
    const statMaxMetaEl = document.getElementById('stat-max-meta');
    const statAvgLinesEl = document.getElementById('stat-avg-lines');
    const statAvgCharsEl = document.getElementById('stat-avg-chars');

    const langTableBody = document.querySelector('#lang-table tbody');
    const fileTableBody = document.querySelector('#file-table tbody');
    const searchInput = document.getElementById('search-input');
    const langFilterSelect = document.getElementById('lang-filter');
    const sortableHeaders = document.querySelectorAll('#file-table th.sortable');
    const langCountBadge = document.getElementById('lang-count-badge');
    const fileCountBadge = document.getElementById('file-count-badge');
    const chartBadge = document.getElementById('chart-badge');
    const topChartBadge = document.getElementById('top-chart-badge');

    const toggleLangChartCheckbox = document.getElementById('toggle-lang-chart');
    const toggleTopChartCheckbox = document.getElementById('toggle-top-chart');
    const sectionLangChart = document.getElementById('section-lang-chart');
    const sectionTopChart = document.getElementById('section-top-chart');

    function formatNumber(num) {
        return num.toLocaleString();
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    // 辅助函数：提取文件名
    function extractFileName(filePath) {
        if (!filePath) return '';
        const cleanPath = filePath.replace(/\\/g, '/');
        const lastSlash = cleanPath.lastIndexOf('/');
        if (lastSlash !== -1) {
            return cleanPath.substring(lastSlash + 1);
        }
        return cleanPath;
    }

    // 辅助函数：只提取文件夹名
    function extractFolderName(dirPath) {
        if (!dirPath) return '未知目录';
        const cleanPath = dirPath.replace(/[/\\]+$/, '');
        const lastSlash = Math.max(cleanPath.lastIndexOf('/'), cleanPath.lastIndexOf('\\'));
        if (lastSlash !== -1) {
            return cleanPath.substring(lastSlash + 1);
        }
        return cleanPath;
    }

    // 初始化并渲染 Apache ECharts 语言分布图
    function initECharts(languagesData) {
        const chartDom = document.getElementById('echarts-container');
        if (!chartDom) return;

        if (!myChart) {
            myChart = echarts.init(chartDom, 'dark', { renderer: 'canvas' });
        }

        const sortedLangs = Object.entries(languagesData)
            .map(([lang, stats]) => ({ lang, ...stats }))
            .sort((a, b) => b.lines - a.lines);

        const categories = sortedLangs.map(item => item.lang);
        const linesData = sortedLangs.map(item => item.lines);
        const filesData = sortedLangs.map(item => item.files);

        chartBadge.textContent = `${categories.length} 种编程语言`;

        const option = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: 'rgba(56, 189, 248, 0.4)',
                borderWidth: 1,
                textStyle: {
                    color: '#f8fafc',
                    fontSize: 13
                },
                axisPointer: {
                    type: 'shadow',
                    shadowStyle: {
                        color: 'rgba(56, 189, 248, 0.08)'
                    }
                },
                formatter: function (params) {
                    let result = `<div style="font-weight:600; margin-bottom:6px; color:#38bdf8;">${params[0].name}</div>`;
                    params.forEach(param => {
                        let unit = param.seriesName === '代码行数' ? ' 行' : ' 个';
                        result += `<div style="display:flex; justify-content:space-between; gap:16px;"><span>${param.marker} ${param.seriesName}:</span><span style="font-weight:bold; font-family:monospace;">${Number(param.value).toLocaleString()}${unit}</span></div>`;
                    });
                    return result;
                }
            },
            legend: {
                data: ['代码行数', '文件数'],
                textStyle: {
                    color: '#94a3b8',
                    fontSize: 12
                },
                top: 5,
                right: 10
            },
            grid: {
                top: 45,
                bottom: 35,
                left: 55,
                right: 40,
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: categories,
                axisLine: {
                    lineStyle: { color: 'rgba(51, 65, 85, 0.8)' }
                },
                axisTick: { show: false },
                axisLabel: {
                    color: '#94a3b8',
                    fontSize: 12,
                    interval: 0,
                    rotate: categories.length > 8 ? 25 : 0
                }
            },
            yAxis: [
                {
                    type: 'value',
                    name: '行数',
                    position: 'left',
                    splitLine: {
                        lineStyle: { color: 'rgba(51, 65, 85, 0.25)', type: 'dashed' }
                    },
                    axisLine: { show: false },
                    axisTick: { show: false },
                    axisLabel: { color: '#94a3b8' }
                },
                {
                    type: 'value',
                    name: '文件数',
                    position: 'right',
                    splitLine: { show: false },
                    axisLine: { show: false },
                    axisTick: { show: false },
                    axisLabel: { color: '#94a3b8' }
                }
            ],
            series: [
                {
                    name: '代码行数',
                    type: 'bar',
                    data: linesData,
                    barMaxWidth: 35,
                    itemStyle: {
                        borderRadius: [6, 6, 0, 0],
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#38bdf8' },
                            { offset: 1, color: '#0284c7' }
                        ]),
                        shadowColor: 'rgba(56, 189, 248, 0.4)',
                        shadowBlur: 12
                    },
                    animationDuration: 1500,
                    animationEasing: 'cubicOut'
                },
                {
                    name: '文件数',
                    type: 'bar',
                    yAxisIndex: 1,
                    data: filesData,
                    barMaxWidth: 20,
                    itemStyle: {
                        borderRadius: [4, 4, 0, 0],
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#4ade80' },
                            { offset: 1, color: '#16a34a' }
                        ]),
                        shadowColor: 'rgba(74, 222, 128, 0.3)',
                        shadowBlur: 10
                    },
                    animationDuration: 1800,
                    animationEasing: 'cubicOut'
                }
            ]
        };

        myChart.setOption(option);
    }

    // 初始化并渲染文件规模 Top 双 Y 轴柱状图（行数与字符数对等规模/多系列对比）
    function initTopChart(filesData) {
        const chartDom = document.getElementById('echarts-top-container');
        if (!chartDom) return;

        if (!topChart) {
            topChart = echarts.init(chartDom, 'dark', { renderer: 'canvas' });
        }

        // 按行数降序排序取前 15 个文件
        const topFiles = [...filesData]
            .sort((a, b) => b.lines - a.lines)
            .slice(0, 15)
            .reverse(); // reverse for horizontal bar chart (bottom to top)

        const fileNames = topFiles.map(f => f.name);
        const linesValues = topFiles.map(f => f.lines);
        const charsValues = topFiles.map(f => f.chars);

        topChartBadge.textContent = `Top ${topFiles.length} 文件`;

        const option = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                borderColor: 'rgba(192, 132, 252, 0.4)',
                borderWidth: 1,
                textStyle: {
                    color: '#f8fafc',
                    fontSize: 13
                },
                axisPointer: {
                    type: 'shadow',
                    shadowStyle: {
                        color: 'rgba(192, 132, 252, 0.08)'
                    }
                },
                formatter: function (params) {
                    const dataIndex = params[0].dataIndex;
                    const fullFile = topFiles[dataIndex];
                    let result = `<div style="font-weight:600; margin-bottom:4px; color:#c084fc;">${fullFile.path}</div>`;
                    result += `<div style="font-size:12px; color:#94a3b8; margin-bottom:6px;">语言: ${fullFile.language} | 大小: ${formatSize(fullFile.size)}</div>`;
                    params.forEach(param => {
                        let unit = param.seriesName === '代码行数' ? ' 行' : ' 字符';
                        result += `<div style="display:flex; justify-content:space-between; gap:16px;"><span>${param.marker} ${param.seriesName}:</span><span style="font-weight:bold; font-family:monospace;">${Number(param.value).toLocaleString()}${unit}</span></div>`;
                    });
                    return result;
                }
            },
            legend: {
                data: ['代码行数', '字符数'],
                textStyle: {
                    color: '#94a3b8',
                    fontSize: 12
                },
                top: 5,
                right: 10
            },
            grid: {
                top: 45,
                bottom: 25,
                left: 120,
                right: 60,
                containLabel: true
            },
            // 双 X 轴实现对等规模/多系列对比展示（底层 X 轴为行数，顶层 X 轴为字符数）
            xAxis: [
                {
                    type: 'value',
                    name: '行数',
                    position: 'bottom',
                    splitLine: {
                        lineStyle: { color: 'rgba(51, 65, 85, 0.25)', type: 'dashed' }
                    },
                    axisLine: { show: false },
                    axisTick: { show: false },
                    axisLabel: { color: '#38bdf8' }
                },
                {
                    type: 'value',
                    name: '字符数',
                    position: 'top',
                    splitLine: { show: false },
                    axisLine: { show: false },
                    axisTick: { show: false },
                    axisLabel: { color: '#c084fc' }
                }
            ],
            yAxis: {
                type: 'category',
                data: fileNames,
                axisLine: {
                    lineStyle: { color: 'rgba(51, 65, 85, 0.8)' }
                },
                axisTick: { show: false },
                axisLabel: {
                    color: '#f8fafc',
                    fontSize: 12,
                    fontWeight: 500
                }
            },
            series: [
                {
                    name: '代码行数',
                    type: 'bar',
                    xAxisIndex: 0,
                    data: linesValues,
                    barMaxWidth: 14,
                    itemStyle: {
                        borderRadius: [0, 4, 4, 0],
                        color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [
                            { offset: 0, color: '#38bdf8' },
                            { offset: 1, color: '#0284c7' }
                        ]),
                        shadowColor: 'rgba(56, 189, 248, 0.4)',
                        shadowBlur: 10
                    },
                    animationDuration: 1500,
                    animationEasing: 'cubicOut'
                },
                {
                    name: '字符数',
                    type: 'bar',
                    xAxisIndex: 1,
                    data: charsValues,
                    barMaxWidth: 14,
                    itemStyle: {
                        borderRadius: [0, 4, 4, 0],
                        color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [
                            { offset: 0, color: '#c084fc' },
                            { offset: 1, color: '#7c3aed' }
                        ]),
                        shadowColor: 'rgba(192, 132, 252, 0.4)',
                        shadowBlur: 10
                    },
                    animationDuration: 1800,
                    animationEasing: 'cubicOut'
                }
            ]
        };

        topChart.setOption(option);
    }

    // 监听窗口自适应图表大小
    window.addEventListener('resize', () => {
        if (myChart) myChart.resize();
        if (topChart) topChart.resize();
    });

    // 图表显隐控制面板交互
    toggleLangChartCheckbox.addEventListener('change', (e) => {
        sectionLangChart.style.display = e.target.checked ? 'block' : 'none';
        if (e.target.checked && myChart) {
            myChart.resize();
        }
    });

    toggleTopChartCheckbox.addEventListener('change', (e) => {
        sectionTopChart.style.display = e.target.checked ? 'block' : 'none';
        if (e.target.checked && topChart) {
            topChart.resize();
        }
    });

    function getFilteredAndSortedFiles() {
        const keyword = searchInput.value.toLowerCase().trim();
        const selectedLang = langFilterSelect.value;

        let result = allFiles.filter(file => {
            if (selectedLang && file.language !== selectedLang) {
                return false;
            }
            if (keyword) {
                const fileName = extractFileName(file.path).toLowerCase();
                return fileName.includes(keyword) || 
                       file.path.toLowerCase().includes(keyword) || 
                       file.language.toLowerCase().includes(keyword);
            }
            return true;
        });

        result.sort((a, b) => {
            let valA, valB;
            if (currentSortColumn === 'name') {
                valA = extractFileName(a.path).toLowerCase();
                valB = extractFileName(b.path).toLowerCase();
            } else {
                valA = a[currentSortColumn];
                valB = b[currentSortColumn];
            }

            if (typeof valA === 'string') {
                if (valA < valB) return currentSortAscending ? -1 : 1;
                if (valA > valB) return currentSortAscending ? 1 : -1;
                return 0;
            } else {
                return currentSortAscending ? valA - valB : valB - valA;
            }
        });

        return result;
    }

    function updateTableHeadersUI() {
        sortableHeaders.forEach(th => {
            const col = th.getAttribute('data-sort');
            let text = th.textContent.replace(/ [↕↑↓]/g, '');
            if (col === currentSortColumn) {
                text += currentSortAscending ? ' ↑' : ' ↓';
            } else {
                text += ' ↕';
            }
            th.textContent = text;
        });
    }

    function renderFiles() {
        const files = getFilteredAndSortedFiles();
        fileCountBadge.textContent = `${files.length} 个文件`;
        fileTableBody.innerHTML = '';
        
        if (files.length === 0) {
            fileTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">暂无匹配文件</td></tr>';
            return;
        }

        const fragment = document.createDocumentFragment();
        files.forEach(file => {
            const fileName = extractFileName(file.path);
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="path-cell" title="完整路径: ${file.path}">
                    <span class="file-name-highlight">${fileName}</span>
                </td>
                <td><span style="display:inline-block; padding: 3px 10px; background: rgba(56,189,248,0.1); border: 1px solid rgba(56,189,248,0.2); border-radius: 6px; color: var(--accent-blue); font-size: 12px; font-weight: 500;">${file.language}</span></td>
                <td>${formatNumber(file.lines)}</td>
                <td>${formatNumber(file.chars)}</td>
                <td>${formatSize(file.size)}</td>
            `;
            fragment.appendChild(tr);
        });
        fileTableBody.appendChild(fragment);
        updateTableHeadersUI();
    }

    function populateLangFilter(languages) {
        langFilterSelect.innerHTML = '<option value="">所有语言/类型</option>';
        const sortedLangs = Object.keys(languages).sort();
        sortedLangs.forEach(lang => {
            const option = document.createElement('option');
            option.value = lang;
            option.textContent = `${lang} (${languages[lang].files})`;
            langFilterSelect.appendChild(option);
        });
    }

    async function fetchStats() {
        try {
            const response = await fetch('/codestatus/api/stats');
            const data = await response.json();

            if (data.status === 'success') {
                const folderName = extractFolderName(data.target_directory);
                targetDirEl.innerHTML = `
                    <span class="pulse-dot"></span>
                    <span class="dir-text" title="完整路径: ${data.target_directory}">${folderName}</span>
                `;

                statFilesEl.textContent = formatNumber(data.total_files);
                statLinesEl.textContent = formatNumber(data.total_lines);
                statCharsEl.textContent = formatNumber(data.total_chars);

                // 计算并渲染额外指标卡片：“最大文件情况”与“平均文件情况”
                if (data.files && data.files.length > 0) {
                    // 最大文件（按行数最多或字符数最多，通常行数最多作为主指标）
                    const maxFile = [...data.files].sort((a, b) => b.lines - a.lines)[0];
                    statMaxFileEl.textContent = maxFile.path;
                    statMaxFileEl.title = maxFile.path;
                    statMaxMetaEl.innerHTML = `行数: <span style="color:var(--accent-blue); font-family:monospace;">${formatNumber(maxFile.lines)}</span> | 字符: <span style="color:var(--accent-purple); font-family:monospace;">${formatNumber(maxFile.chars)}</span>`;

                    // 平均文件情况
                    const avgLines = Math.round(data.total_lines / data.total_files);
                    const avgChars = Math.round(data.total_chars / data.total_files);
                    statAvgLinesEl.textContent = `${formatNumber(avgLines)} 行`;
                    statAvgCharsEl.textContent = `${formatNumber(avgChars)} 字符`;
                } else {
                    statMaxFileEl.textContent = '无文件';
                    statMaxMetaEl.textContent = '-';
                    statAvgLinesEl.textContent = '0 行';
                    statAvgCharsEl.textContent = '0 字符';
                }

                // 语言统计
                const sortedLangs = Object.entries(data.languages).sort((a, b) => b[1].lines - a[1].lines);
                langCountBadge.textContent = `${sortedLangs.length} 种语言`;
                
                langTableBody.innerHTML = '';
                const langFragment = document.createDocumentFragment();
                sortedLangs.forEach(([lang, stats]) => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong style="color: var(--text-main);">${lang}</strong></td>
                        <td>${formatNumber(stats.files)}</td>
                        <td><span style="color: var(--accent-blue); font-weight: 600;">${formatNumber(stats.lines)}</span></td>
                        <td>${formatNumber(stats.chars)}</td>
                    `;
                    langFragment.appendChild(tr);
                });
                langTableBody.appendChild(langFragment);

                populateLangFilter(data.languages);

                // 为每个 file 对象增加处理好的 name 属性
                allFiles = data.files.map(f => ({
                    ...f,
                    name: extractFileName(f.path)
                }));

                // 初始化并渲染 ECharts 图表
                initECharts(data.languages);
                initTopChart(allFiles);

                renderFiles();
            } else {
                targetDirEl.innerHTML = '<span class="dir-text" style="color: #f43f5e;">获取统计数据失败</span>';
            }
        } catch (e) {
            console.error('获取代码统计异常:', e);
            targetDirEl.innerHTML = '<span class="dir-text" style="color: #f43f5e;">请求错误，请检查服务器状态</span>';
        }
    }

    searchInput.addEventListener('input', () => {
        renderFiles();
    });

    langFilterSelect.addEventListener('change', () => {
        renderFiles();
    });

    sortableHeaders.forEach(th => {
        th.addEventListener('click', () => {
            const col = th.getAttribute('data-sort');
            if (currentSortColumn === col) {
                currentSortAscending = !currentSortAscending;
            } else {
                currentSortColumn = col;
                currentSortAscending = (col === 'name' || col === 'language');
            }
            renderFiles();
        });
    });

    fetchStats();
});

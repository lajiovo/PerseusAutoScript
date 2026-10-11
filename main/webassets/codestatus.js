document.addEventListener('DOMContentLoaded', () => {
    let allFiles = [];
    let currentSortColumn = 'lines';
    let currentSortAscending = false;

    const targetDirEl = document.getElementById('target-dir');
    const statFilesEl = document.getElementById('stat-files');
    const statLinesEl = document.getElementById('stat-lines');
    const statCharsEl = document.getElementById('stat-chars');
    const langTableBody = document.querySelector('#lang-table tbody');
    const fileTableBody = document.querySelector('#file-table tbody');
    const searchInput = document.getElementById('search-input');
    const langFilterSelect = document.getElementById('lang-filter');
    const sortableHeaders = document.querySelectorAll('#file-table th.sortable');

    function formatNumber(num) {
        return num.toLocaleString();
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function getFilteredAndSortedFiles() {
        const keyword = searchInput.value.toLowerCase().trim();
        const selectedLang = langFilterSelect.value;

        let result = allFiles.filter(file => {
            // 语言筛选
            if (selectedLang && file.language !== selectedLang) {
                return false;
            }
            // 关键字搜索
            if (keyword) {
                return file.path.toLowerCase().includes(keyword) || 
                       file.name.toLowerCase().includes(keyword) ||
                       file.language.toLowerCase().includes(keyword);
            }
            return true;
        });

        // 多维度排序
        result.sort((a, b) => {
            let valA = a[currentSortColumn];
            let valB = b[currentSortColumn];

            if (typeof valA === 'string') {
                valA = valA.toLowerCase();
                valB = valB.toLowerCase();
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
        fileTableBody.innerHTML = '';
        if (files.length === 0) {
            fileTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">暂无匹配文件</td></tr>';
            return;
        }

        const fragment = document.createDocumentFragment();
        files.forEach(file => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="path-cell" title="${file.path}">${file.path}</td>
                <td>${file.language}</td>
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
        // 清空现有选项（保留第一个）
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
                targetDirEl.textContent = `目标扫描目录: ${data.target_directory}`;
                statFilesEl.textContent = formatNumber(data.total_files);
                statLinesEl.textContent = formatNumber(data.total_lines);
                statCharsEl.textContent = formatNumber(data.total_chars);

                // 渲染语言统计表格
                langTableBody.innerHTML = '';
                const sortedLangs = Object.entries(data.languages).sort((a, b) => b[1].lines - a[1].lines);
                
                const langFragment = document.createDocumentFragment();
                sortedLangs.forEach(([lang, stats]) => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${lang}</strong></td>
                        <td>${formatNumber(stats.files)}</td>
                        <td>${formatNumber(stats.lines)}</td>
                        <td>${formatNumber(stats.chars)}</td>
                    `;
                    langFragment.appendChild(tr);
                });
                langTableBody.appendChild(langFragment);

                // 填充语言筛选下拉框
                populateLangFilter(data.languages);

                // 保存文件列表并渲染
                allFiles = data.files;
                renderFiles();
            } else {
                targetDirEl.textContent = '获取统计数据失败';
            }
        } catch (e) {
            console.error('获取代码统计异常:', e);
            targetDirEl.textContent = '请求错误，请检查服务器状态';
        }
    }

    // 事件监听
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
                // 默认对于路径和语言采用升序，数字指标采用降序
                currentSortAscending = (col === 'path' || col === 'language');
            }
            renderFiles();
        });
    });

    fetchStats();
});

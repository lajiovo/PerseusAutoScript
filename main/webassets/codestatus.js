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
    const langCountBadge = document.getElementById('lang-count-badge');
    const fileCountBadge = document.getElementById('file-count-badge');

    function formatNumber(num) {
        return num.toLocaleString();
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    // 辅助函数：从完整绝对路径或路径字符串中只提取文件夹名
    function extractFolderName(dirPath) {
        if (!dirPath) return '未知目录';
        // 去除尾部斜杠
        const cleanPath = dirPath.replace(/[/\\]+$/, '');
        // 查找最后一个斜杠或反斜杠
        const lastSlash = Math.max(cleanPath.lastIndexOf('/'), cleanPath.lastIndexOf('\\'));
        if (lastSlash !== -1) {
            return cleanPath.substring(lastSlash + 1);
        }
        return cleanPath;
    }

    function getFilteredAndSortedFiles() {
        const keyword = searchInput.value.toLowerCase().trim();
        const selectedLang = langFilterSelect.value;

        let result = allFiles.filter(file => {
            if (selectedLang && file.language !== selectedLang) {
                return false;
            }
            if (keyword) {
                return file.path.toLowerCase().includes(keyword) || 
                       file.name.toLowerCase().includes(keyword) ||
                       file.language.toLowerCase().includes(keyword);
            }
            return true;
        });

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
        fileCountBadge.textContent = `${files.length} 个文件`;
        fileTableBody.innerHTML = '';
        
        if (files.length === 0) {
            fileTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 30px;">暂无匹配文件</td></tr>';
            return;
        }

        const fragment = document.createDocumentFragment();
        files.forEach(file => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="path-cell" title="${file.path}">${file.path}</td>
                <td><span style="display:inline-block; padding: 2px 8px; background: rgba(56,189,248,0.1); border-radius: 4px; color: var(--accent-blue); font-size: 12px;">${file.language}</span></td>
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
                // 需求2：#target-dir 终端胶囊标签样式，并且只显示文件夹名（不显示完整绝对路径）
                const folderName = extractFolderName(data.target_directory);
                targetDirEl.innerHTML = `
                    <span class="pulse-dot"></span>
                    <span class="dir-text" title="完整路径: ${data.target_directory}">${folderName}</span>
                `;

                statFilesEl.textContent = formatNumber(data.total_files);
                statLinesEl.textContent = formatNumber(data.total_lines);
                statCharsEl.textContent = formatNumber(data.total_chars);

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

                allFiles = data.files;
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
                currentSortAscending = (col === 'path' || col === 'language');
            }
            renderFiles();
        });
    });

    fetchStats();
});

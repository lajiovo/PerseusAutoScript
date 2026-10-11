document.addEventListener('DOMContentLoaded', () => {
    let allFiles = [];

    const targetDirEl = document.getElementById('target-dir');
    const statFilesEl = document.getElementById('stat-files');
    const statLinesEl = document.getElementById('stat-lines');
    const statCharsEl = document.getElementById('stat-chars');
    const langTableBody = document.querySelector('#lang-table tbody');
    const fileTableBody = document.querySelector('#file-table tbody');
    const searchInput = document.getElementById('search-input');

    function formatNumber(num) {
        return num.toLocaleString();
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function renderFiles(files) {
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

                // 保存文件列表并渲染
                allFiles = data.files;
                renderFiles(allFiles);
            } else {
                targetDirEl.textContent = '获取统计数据失败';
            }
        } catch (e) {
            console.error('获取代码统计异常:', e);
            targetDirEl.textContent = '请求错误，请检查服务器状态';
        }
    }

    // 搜索过滤监听
    searchInput.addEventListener('input', (e) => {
        const keyword = e.target.value.toLowerCase().trim();
        if (!keyword) {
            renderFiles(allFiles);
            return;
        }
        const filtered = allFiles.filter(f => 
            f.path.toLowerCase().includes(keyword) || 
            f.name.toLowerCase().includes(keyword) ||
            f.language.toLowerCase().includes(keyword)
        );
        renderFiles(filtered);
    });

    fetchStats();
});

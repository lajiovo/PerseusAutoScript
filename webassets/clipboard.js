async function fetchData() {
    try {
        const response = await fetch('/clipboard');
        const data = await response.json();
        if (data.status === 'ok') {
            document.getElementById('textClipboard').value = data.text || '';
            renderHistory(data.history || []);
            renderGallery(data.images || []);
            renderFiles(data.files || []);
        }
    } catch (err) {
        showToast('获取数据失败: ' + err);
    }
}

function renderHistory(history) {
    const container = document.getElementById('textHistory');
    if (!history || history.length === 0) {
        container.innerHTML = '<div class="loading">暂无历史记录</div>';
        return;
    }

    container.innerHTML = history.map(item => `
        <div class="history-item" onclick="restoreHistory(${JSON.stringify(item.content).replace(/"/g, '"')})">
            <div class="history-meta">
                <span>🕒 ${item.time}</span>
                <span style="color: var(--primary);">点击回填</span>
            </div>
            <div class="history-preview">${escapeHtml(item.content)}</div>
        </div>
    `).join('');
}

function restoreHistory(content) {
    document.getElementById('textClipboard').value = content;
    showToast('已回填历史记录');
}

function renderGallery(images) {
    const gallery = document.getElementById('imageGallery');
    if (!images || images.length === 0) {
        gallery.innerHTML = '<div class="loading">暂无图片缓存</div>';
        return;
    }

    gallery.innerHTML = images.map(img => `
        <div class="image-item">
            <img src="${img.url}" alt="${img.name}" onclick="window.open('${img.url}')">
            <div class="image-actions">
                <button class="btn-icon" onclick="copyImageToClipboard('${img.url}')" title="复制图片到剪切板">📋 复制</button>
                <button class="btn-icon" onclick="copyUrl('${img.url}')" title="复制链接">🔗 链接</button>
                <button class="btn-icon del" onclick="deleteFile('${img.name}')" title="删除">🗑️</button>
            </div>
        </div>
    `).join('');
}

function renderFiles(files) {
    const list = document.getElementById('fileList');
    if (!files || files.length === 0) {
        list.innerHTML = '<div class="loading">暂无文件缓存</div>';
        return;
    }

    list.innerHTML = files.map(file => `
        <div class="file-item">
            <div class="file-info">
                <a href="${file.url}?download=1" class="file-name" title="${file.name}">${file.name}</a>
                <span class="file-meta">${file.size} · ${file.time}</span>
            </div>
            <div class="file-actions">
                <a href="${file.url}?download=1" class="btn-mini btn-success" style="text-decoration: none; display: inline-flex; align-items: center;">下载</a>
                <button class="btn-mini btn-danger" onclick="deleteFile('${file.name}')">删除</button>
            </div>
        </div>
    `).join('');
}

async function saveText() {
    const text = document.getElementById('textClipboard').value;
    try {
        const response = await fetch('/clipboard', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'save_text', text })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            showToast('保存成功');
            document.getElementById('textClipboard').value = data.text || '';
            renderHistory(data.history || []);
        } else {
            showToast('保存失败: ' + data.message);
        }
    } catch (err) {
        showToast('网络请求失败');
    }
}

async function clearText() {
    if (!confirm('确定要清空当前文本吗？')) return;
    try {
        const response = await fetch('/clipboard', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'clear_text' })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            document.getElementById('textClipboard').value = '';
            showToast('文本已清空');
        }
    } catch (err) {
        showToast('操作失败');
    }
}

async function clearHistory() {
    if (!confirm('确定要清空所有文本历史记录吗？')) return;
    try {
        const response = await fetch('/clipboard', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'clear_history' })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            renderHistory(data.history || []);
            showToast('历史记录已清空');
        }
    } catch (err) {
        showToast('操作失败');
    }
}

function copyText() {
    const text = document.getElementById('textClipboard').value;
    navigator.clipboard.writeText(text).then(() => {
        showToast('已复制到系统剪切板');
    }).catch(err => {
        showToast('复制失败');
    });
}

function copyUrl(url) {
    const fullUrl = window.location.origin + url;
    navigator.clipboard.writeText(fullUrl).then(() => {
        showToast('链接已复制');
    });
}

async function copyImageToClipboard(url) {
    try {
        const response = await fetch(url);
        const blob = await response.blob();
        
        let pngBlob = blob;
        if (blob.type !== 'image/png') {
            const bitmap = await createImageBitmap(blob);
            const canvas = document.createElement('canvas');
            canvas.width = bitmap.width;
            canvas.height = bitmap.height;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(bitmap, 0, 0);
            pngBlob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
        }

        await navigator.clipboard.write([
            new ClipboardItem({ 'image/png': pngBlob })
        ]);
        showToast('图片已复制到系统剪切板');
    } catch (err) {
        console.error(err);
        showToast('复制图片失败 (浏览器可能不支持或权限受限)');
    }
}

async function deleteFile(filename) {
    if (!confirm(`确定要删除 ${filename} 吗？`)) return;
    try {
        const response = await fetch('/clipboard', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'delete', filename })
        });
        const data = await response.json();
        if (data.status === 'ok') {
            showToast('文件已删除');
            renderGallery(data.images);
            renderFiles(data.files);
        } else {
            showToast('删除失败: ' + data.message);
        }
    } catch (err) {
        showToast('删除失败');
    }
}

async function pasteFromClipboard() {
    try {
        if (!navigator.clipboard || !navigator.clipboard.read) {
            showToast('当前浏览器不支持读取剪切板，请直接使用 Ctrl+V 粘贴');
            return;
        }
        const items = await navigator.clipboard.read();
        let uploaded = false;
        for (const item of items) {
            for (const type of item.types) {
                if (type.startsWith('image/')) {
                    const blob = await item.getType(type);
                    const file = new File([blob], `pasted_image_${Date.now()}.png`, { type });
                    await handleUpload(file);
                    uploaded = true;
                    break;
                }
            }
        }
        if (!uploaded) {
            showToast('剪切板中未发现图片');
        }
    } catch (err) {
        console.error(err);
        showToast('读取剪切板失败，请确保授予权限或直接使用 Ctrl+V');
    }
}

window.addEventListener('paste', async (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (const item of items) {
        if (item.kind === 'file') {
            const file = item.getAsFile();
            if (file) {
                e.preventDefault();
                await handleUpload(file);
                return;
            }
        }
    }
});

const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');

uploadArea.onclick = () => fileInput.click();

uploadArea.ondragover = (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = 'var(--primary)';
};

uploadArea.ondragleave = () => {
    uploadArea.style.borderColor = 'var(--card-border)';
};

uploadArea.ondrop = (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = 'var(--card-border)';
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        for (let i = 0; i < files.length; i++) {
            handleUpload(files[i]);
        }
    }
};

fileInput.onchange = (e) => {
    if (e.target.files.length > 0) {
        for (let i = 0; i < e.target.files.length; i++) {
            handleUpload(e.target.files[i]);
        }
    }
};

async function handleUpload(file) {
    const status = document.getElementById('uploadStatus');
    status.innerText = '正在上传: ' + file.name;
    
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/clipboard', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.status === 'ok') {
            showToast('上传成功: ' + file.name);
            status.innerText = '';
            renderGallery(data.images);
            renderFiles(data.files);
        } else {
            status.innerText = '上传失败: ' + data.message;
        }
    } catch (err) {
        status.innerText = '网络错误';
    }
}

function escapeHtml(str) {
    if (!str) return '';
    const map = {
        '&': '&',
        '<': '<',
        '>': '>',
        '"': '"',
        "'": '&#039;'
    };
    return str.replace(/[&<>"']/g, m => map[m]);
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.innerText = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2300);
}

document.addEventListener('DOMContentLoaded', fetchData);

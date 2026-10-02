/**
 * PerseusLogViewer - 独立前端 JS 脚本
 */

let allFoldersData = [];
let currentFolder = "";
let currentFile = "";
let autoRefreshTimer = null;
let allFilesData = [];
let rawLogContent = "";

const folderSelect = document.getElementById("folderSelect");
const fileList = document.getElementById("fileList");
const searchInput = document.getElementById("searchInput");
const logContent = document.getElementById("logContent");
const currentFilePath = document.getElementById("currentFilePath");
const currentFolderTag = document.getElementById("currentFolderTag");
const refreshBtn = document.getElementById("refreshBtn");
const autoRefreshToggle = document.getElementById("autoRefreshToggle");
const autoScrollToggle = document.getElementById("autoScrollToggle");
const timestampToggle = document.getElementById("timestampToggle");
const highlightToggle = document.getElementById("highlightToggle");
const themeToggleBtn = document.getElementById("themeToggleBtn");
const linesSelect = document.getElementById("linesSelect");
const fontSizeSelect = document.getElementById("fontSizeSelect");
const scrollTopBtn = document.getElementById("scrollTopBtn");
const scrollBottomBtn = document.getElementById("scrollBottomBtn");
const logContainer = document.getElementById("logContainer");
const fileStatusInfo = document.getElementById("fileStatusInfo");
const updateTimeInfo = document.getElementById("updateTimeInfo");
const categoryBar = document.getElementById("categoryBar");

let isDarkMode = true;
if (themeToggleBtn) {
    themeToggleBtn.onclick = function() {
        isDarkMode = !isDarkMode;
        if (isDarkMode) {
            document.body.classList.remove("light-theme");
            themeToggleBtn.textContent = "🌙 模式";
        } else {
            document.body.classList.add("light-theme");
            themeToggleBtn.textContent = "☀️ 模式";
        }
    };
}

if (fontSizeSelect) {
    fontSizeSelect.onchange = function(e) {
        var size = e.target.value;
        logContent.className = "font-" + size;
    };
}

async function loadFolders() {
    try {
        var res = await fetch("/logapi/folders");
        var data = await res.json();
        if (data.status === "success" && data.folders) {
            allFoldersData = data.folders;
            renderFolderSelect(allFoldersData);

            if (allFoldersData.length > 0) {
                var defaultFolder = allFoldersData.find(function(f) {
                    return f.category === "yunzai" || f.category === "perseus_logs" || f.path.indexOf("QBot") !== -1;
                }) || allFoldersData[0];
                currentFolder = defaultFolder.path;
                folderSelect.value = currentFolder;
                currentFolderTag.textContent = defaultFolder.tags.join(", ") || defaultFolder.name;
                await loadFiles(currentFolder, true);
            }
        } else {
            folderSelect.innerHTML = "<option value=''>加载失败</option>";
        }
    } catch (err) {
        console.error("加载文件夹失败:", err);
        folderSelect.innerHTML = "<option value=''>网络错误</option>";
    }
}

function renderFolderSelect(folders, filterCategory) {
    if (filterCategory === undefined) filterCategory = "all";
    folderSelect.innerHTML = "";
    var filtered = folders;
    if (filterCategory !== "all") {
        if (filterCategory === "azurpilot") {
            filtered = folders.filter(function(f) { return f.category === "azurpilot"; });
        } else if (filterCategory === "yunzai") {
            filtered = folders.filter(function(f) { return f.category === "yunzai"; });
        } else if (filterCategory === "perseus_logs") {
            filtered = folders.filter(function(f) { return f.category === "perseus_logs"; });
        } else if (filterCategory === "qbot_log") {
            filtered = folders.filter(function(f) { return f.category === "qbot_log"; });
        } else if (filterCategory === "qbot_sdk") {
            filtered = folders.filter(function(f) { return f.category === "qbot_sdk"; });
        }
        if (filtered.length === 0) {
            filtered = folders;
        }
    }

    filtered.forEach(function(f) {
        var opt = document.createElement("option");
        opt.value = f.path;
        opt.textContent = "[" + f.category.toUpperCase() + "] " + f.name + " (" + f.path + ")";
        folderSelect.appendChild(opt);
    });

    if (filtered.length > 0) {
        var exists = filtered.some(function(f) { return f.path === currentFolder; });
        if (!exists) {
            currentFolder = filtered[0].path;
            folderSelect.value = currentFolder;
            loadFiles(currentFolder, true);
        } else {
            folderSelect.value = currentFolder;
        }
    }
}

if (categoryBar) {
    var catBtns = categoryBar.querySelectorAll(".cat-btn");
    catBtns.forEach(function(btn) {
        btn.onclick = function(e) {
            catBtns.forEach(function(b) { b.classList.remove("active"); });
            e.target.classList.add("active");
            var cat = e.target.getAttribute("data-category");
            renderFolderSelect(allFoldersData, cat);
        };
    });
}

async function loadFiles(folderPath, autoSelectMainLog) {
    if (autoSelectMainLog === undefined) autoSelectMainLog = false;
    currentFolder = folderPath;
    var folderObj = allFoldersData.find(function(f) { return f.path === folderPath; });
    if (folderObj) {
        currentFolderTag.textContent = folderObj.tags.join(", ") || folderObj.name;
    }

    fileList.innerHTML = "<div style='padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.85rem;'>加载文件中...</div>";
    try {
        var res = await fetch("/logapi/files?folder=" + encodeURIComponent(folderPath));
        var data = await res.json();
        if (data.status === "success" && data.files) {
            allFilesData = data.files;
            renderFileList(allFilesData, folderObj ? folderObj.category : "");

            if (allFilesData.length > 0) {
                var targetFile = allFilesData[0].name;
                if (autoSelectMainLog) {
                    var mainLog = allFilesData.find(function(f) {
                        var n = f.name.toLowerCase();
                        return n.indexOf("botpy.log") !== -1 || n.indexOf("app.log") !== -1 || n.indexOf("main.log") !== -1 || n.indexOf("launcher") !== -1;
                    });
                    if (mainLog) {
                        targetFile = mainLog.name;
                    }
                }
                var fileExists = allFilesData.some(function(f) { return f.name === currentFile; });
                if (!currentFile || !fileExists) {
                    selectFile(targetFile, true);
                } else {
                    selectFile(currentFile, false);
                }
            } else {
                currentFile = "";
                logContent.textContent = "当前文件夹下没有日志文件";
                currentFilePath.textContent = currentFolder + " (空)";
            }
        } else {
            fileList.innerHTML = "<div style='padding: 16px; text-align: center; color: var(--danger-color); font-size: 0.85rem;'>" + (data.message || '无文件') + "</div>";
        }
    } catch (err) {
        console.error("加载文件列表失败:", err);
        fileList.innerHTML = "<div style='padding: 16px; text-align: center; color: var(--danger-color); font-size: 0.85rem;'>加载失败</div>";
    }
}

function renderFileList(files, folderCategory) {
    var filter = searchInput.value.toLowerCase();
    fileList.innerHTML = "";
    var filtered = files.filter(function(f) { return f.name.toLowerCase().indexOf(filter) !== -1; });

    if (filtered.length === 0) {
        fileList.innerHTML = "<div style='padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.85rem;'>没有匹配的日志文件</div>";
        return;
    }

    filtered.forEach(function(f) {
        var item = document.createElement("div");
        item.className = "file-item " + (currentFile === f.name ? 'active' : '');

        var sizeKb = (f.size / 1024).toFixed(1) + " KB";
        var dateStr = new Date(f.mtime * 1000).toLocaleString();

        var subTagHtml = "";
        var lowerName = f.name.toLowerCase();
        if (folderCategory === "azurpilot" || lowerName.indexOf("launcher") !== -1 || lowerName.indexOf("gui") !== -1 || lowerName.indexOf("alas") !== -1) {
            var subCatName = "general";
            var badgeClass = "badge-sub";
            if (lowerName.indexOf("launcher") !== -1) {
                subCatName = "launcher";
                badgeClass = "badge-launcher";
            } else if (lowerName.indexOf("gui") !== -1) {
                subCatName = "gui";
                badgeClass = "badge-gui";
            } else if (lowerName.indexOf("alas") !== -1) {
                subCatName = "alas";
                badgeClass = "badge-alas";
            }
            subTagHtml = "<span class='sub-badge " + badgeClass + "'>" + subCatName.toUpperCase() + "</span>";
        }

        item.innerHTML = "<div style='display: flex; justify-content: space-between; align-items: center;'>" +
            "<div class='file-name'>" + f.name + "</div>" +
            subTagHtml +
            "</div>" +
            "<div class='file-meta'>" +
            "<span>" + sizeKb + "</span>" +
            "<span>" + dateStr + "</span>" +
            "</div>";
        item.onclick = function() { selectFile(f.name, true); };
        fileList.appendChild(item);
    });
}

function selectFile(fileName, autoScroll) {
    if (autoScroll === undefined) autoScroll = false;
    currentFile = fileName;
    var fileItems = document.querySelectorAll(".file-item");
    fileItems.forEach(function(el) {
        var nameEl = el.querySelector(".file-name");
        if (nameEl && nameEl.textContent === fileName) {
            el.classList.add("active");
        } else {
            el.classList.remove("active");
        }
    });
    currentFilePath.textContent = currentFolder + " / " + fileName;
    loadContent(autoScroll);
}

function formatAndRenderContent() {
    if (!rawLogContent) {
        logContent.innerHTML = "(文件内容为空)";
        return;
    }

    var keepTimestamp = timestampToggle ? timestampToggle.checked : true;
    var enableHighlight = highlightToggle ? highlightToggle.checked : false;

    var lines = rawLogContent.split("\n");
    var processedLines = lines.map(function(line) {
        var displayLine = line;

        if (!keepTimestamp) {
            displayLine = displayLine.replace(/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}([,.]\d+)?\s*/, "");
        }

        displayLine = escapeHtml(displayLine);

        if (enableHighlight) {
            if (displayLine.indexOf("[ERROR]") !== -1 || displayLine.indexOf("ERROR") !== -1 || displayLine.indexOf("异常") !== -1) {
                return "<span class='log-error'>" + displayLine + "</span>";
            } else if (displayLine.indexOf("[WARNING]") !== -1 || displayLine.indexOf("WARNING") !== -1 || displayLine.indexOf("警告") !== -1) {
                return "<span class='log-warn'>" + displayLine + "</span>";
            } else if (displayLine.indexOf("[INFO]") !== -1 || displayLine.indexOf("INFO") !== -1) {
                return "<span class='log-info'>" + displayLine + "</span>";
            } else if (displayLine.indexOf("[DEBUG]") !== -1 || displayLine.indexOf("DEBUG") !== -1) {
                return "<span class='log-debug'>" + displayLine + "</span>";
            }
        }

        return displayLine;
    });

    logContent.innerHTML = processedLines.join("\n");
}

function escapeHtml(text) {
    var map = {
        '&': '&',
        '<': '<',
        '>': '>',
        '"': '"',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

async function loadContent(forceScroll) {
    if (forceScroll === undefined) forceScroll = false;
    if (!currentFolder || !currentFile) return;
    var lines = linesSelect ? linesSelect.value : "100";
    try {
        var res = await fetch("/logapi/content?folder=" + encodeURIComponent(currentFolder) + "&file=" + encodeURIComponent(currentFile) + "&lines=" + lines);
        var data = await res.json();
        if (data.status === "success") {
            rawLogContent = data.content || "";
            formatAndRenderContent();

            if (fileStatusInfo) fileStatusInfo.textContent = "大小: " + (data.size / 1024).toFixed(1) + " KB";
            if (updateTimeInfo) updateTimeInfo.textContent = "最后更新：" + new Date().toLocaleTimeString();

            if (forceScroll || (autoScrollToggle && autoScrollToggle.checked)) {
                logContainer.scrollTop = logContainer.scrollHeight;
            }
        } else {
            logContent.textContent = "加载失败: " + data.message;
        }
    } catch (err) {
        console.error("加载日志内容失败:", err);
    }
}

function setupAutoRefresh() {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    if (autoRefreshToggle && autoRefreshToggle.checked) {
        autoRefreshTimer = setInterval(function() { loadContent(false); }, 3000);
    }
}

if (folderSelect) {
    folderSelect.onchange = function(e) {
        currentFile = "";
        loadFiles(e.target.value, true);
    };
}

if (searchInput) {
    searchInput.oninput = function() {
        var folderObj = allFoldersData.find(function(f) { return f.path === currentFolder; });
        renderFileList(allFilesData, folderObj ? folderObj.category : "");
    };
}

if (refreshBtn) refreshBtn.onclick = function() { loadContent(true); };
if (linesSelect) linesSelect.onchange = function() { loadContent(true); };
if (timestampToggle) timestampToggle.onchange = function() { formatAndRenderContent(); };
if (highlightToggle) highlightToggle.onchange = function() { formatAndRenderContent(); };

if (scrollTopBtn) {
    scrollTopBtn.onclick = function() {
        logContainer.scrollTop = 0;
    };
}

if (scrollBottomBtn) {
    scrollBottomBtn.onclick = function() {
        logContainer.scrollTop = logContainer.scrollHeight;
    };
}

if (autoRefreshToggle) {
    autoRefreshToggle.onchange = function() {
        setupAutoRefresh();
    };
}

loadFolders();
setupAutoRefresh();

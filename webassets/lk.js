const { createApp, ref, computed, onMounted, onUnmounted } = Vue;

createApp({
  setup() {
    const bookshelfBooks = ref([]);
    const cachedBooks = ref([]);
    const tasks = ref([]);
    const broRunning = ref(false);
    const broHeadless = ref(true);

    // 灵动岛展开控制
    const showIsland = ref(false);

    const viewMode = ref("all"); // 'all' or 'cached'
    const filterStatus = ref("all");
    const filterHeart = ref("all");
    const sortBy = ref("time");

    const showCustomUrlModal = ref(false);
    const targetUrl = ref("https://www.lightnovel.fun/category/lightnovel");
    const maxScrolls = ref(20);

    let timer = null;

    const loadBookshelf = async () => {
      try {
        const res = await fetch("/lkapi/bookshelf/data");
        const data = await res.json();
        if (data.status === "ok") {
          bookshelfBooks.value = data.books.map(b => ({
            ...b,
            heart: localStorage.getItem(`heart_${b.book_id}`) || 'gray',
            catalog_status: 'no_catalog',
            download_status: 'none'
          }));
        }
      } catch (e) {
        console.error("加载书架失败", e);
      }
    };

    const loadCachedBooks = async () => {
      try {
        const res = await fetch("/lkapi/books/all");
        const data = await res.json();
        if (data.status === "ok") {
          cachedBooks.value = data.books.map(b => ({
            ...b,
            heart: localStorage.getItem(`heart_${b.book_id}`) || 'gray'
          }));
        }
      } catch (e) {
        console.error("加载本地缓存书籍失败", e);
      }
    };

    const loadStatus = async () => {
      try {
        const res = await fetch("/lkapi/status");
        const data = await res.json();
        if (data.status === "ok") {
          broRunning.value = data.browser.running;
          broHeadless.value = data.browser.headless;
          tasks.value = data.tasks;
        }
      } catch (e) {
        console.error("加载状态失败", e);
      }
    };

    const toggleIsland = () => {
      showIsland.value = !showIsland.value;
    };

    const activeTask = computed(() => {
      const active = tasks.value.filter(t => t.status === 'running' || t.status === 'pending');
      return active.length > 0 ? active[active.length - 1] : null;
    });

    const islandMainText = computed(() => {
      if (activeTask.value) {
        return activeTask.value.message || "任务处理中...";
      }
      if (broRunning.value) {
        return broHeadless.value ? "LKbro 就绪 (无头)" : "LKbro 就绪 (窗口)";
      }
      return "LKbro 待机中";
    });

    const startBrowser = async (headless) => {
      try {
        await fetch("/lkapi/browser", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "start", headless: headless })
        });
        loadStatus();
      } catch (e) {
        alert("启动浏览器失败: " + e);
      }
    };

    const closeBrowser = async () => {
      try {
        await fetch("/lkapi/browser", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "close" })
        });
        loadStatus();
      } catch (e) {
        alert("关闭浏览器失败: " + e);
      }
    };

    const openCustomUrlModal = () => {
      showCustomUrlModal.value = true;
      showIsland.value = false;
    };

    const executeFetchCustomBookshelf = async () => {
      try {
        const res = await fetch("/lkapi/bookshelf", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: targetUrl.value, max_scrolls: maxScrolls.value })
        });
        const data = await res.json();
        if (data.status === "ok") {
          showCustomUrlModal.value = false;
          showIsland.value = true;
          loadStatus();
        }
      } catch (e) {
        alert("启动抓取失败: " + e);
      }
    };

    const cancelTask = async (taskId) => {
      try {
        await fetch(`/lkapi/tasks/${taskId}/cancel`, { method: "POST" });
        loadStatus();
      } catch (e) {
        console.error("取消任务失败", e);
      }
    };

    const toggleHeart = (book) => {
      const states = ['gray', 'red', 'later'];
      let idx = states.indexOf(book.heart);
      book.heart = states[(idx + 1) % states.length];
      localStorage.setItem(`heart_${book.book_id}`, book.heart);
    };

    const openBook = (bookId) => {
      window.location.href = `/main/book.html?id=${bookId}`;
    };

    const getBookBadge = (book) => {
      if (book.download_status === 'downloaded_all') return '已下全';
      if (book.download_status === 'downloading') return '下载中';
      if (book.catalog_status === 'has_catalog') return '有目录';
      return '未抓取';
    };

    const refreshAllData = () => {
      loadBookshelf();
      loadCachedBooks();
      loadStatus();
    };

    const filteredBooks = computed(() => {
      const map = new Map();

      if (viewMode.value === "all") {
        for (const b of bookshelfBooks.value) {
          map.set(String(b.book_id), { ...b });
        }
      }

      for (const cb of cachedBooks.value) {
        const id = String(cb.book_id);
        if (map.has(id)) {
          const item = map.get(id);
          item.catalog_status = cb.catalog_status;
          item.download_status = cb.download_status;
          item.total_chapters = cb.total_chapters;
          item.downloaded_chapters = cb.downloaded_chapters;
          if (cb.title && cb.title !== `Book_${id}`) item.title = cb.title;
          if (cb.cover_url) item.cover_url = cb.cover_url;
        } else {
          if (viewMode.value === "all" || viewMode.value === "cached") {
            map.set(id, { ...cb });
          }
        }
      }

      let list = Array.from(map.values());

      if (filterStatus.value === "downloaded_all") {
        list = list.filter(b => b.download_status === "downloaded_all");
      } else if (filterStatus.value === "downloading") {
        list = list.filter(b => b.download_status === "downloading");
      } else if (filterStatus.value === "has_catalog") {
        list = list.filter(b => b.catalog_status === "has_catalog");
      } else if (filterStatus.value === "no_catalog") {
        list = list.filter(b => b.catalog_status === "no_catalog");
      }

      if (filterHeart.value !== "all") {
        list = list.filter(b => b.heart === filterHeart.value);
      }

      list.sort((a, b) => {
        if (sortBy.value === "title") {
          return (a.title || "").localeCompare(b.title || "");
        } else if (sortBy.value === "id") {
          return parseInt(b.book_id) - parseInt(a.book_id);
        } else {
          return 0;
        }
      });

      return list;
    });

    onMounted(() => {
      refreshAllData();
      timer = setInterval(() => {
        loadStatus();
      }, 2000);
    });

    onUnmounted(() => {
      if (timer) clearInterval(timer);
    });

    return {
      bookshelfBooks,
      cachedBooks,
      tasks,
      broRunning,
      broHeadless,
      showIsland,
      activeTask,
      islandMainText,
      viewMode,
      filterStatus,
      filterHeart,
      sortBy,
      showCustomUrlModal,
      targetUrl,
      maxScrolls,
      filteredBooks,
      toggleIsland,
      startBrowser,
      closeBrowser,
      openCustomUrlModal,
      executeFetchCustomBookshelf,
      cancelTask,
      toggleHeart,
      openBook,
      getBookBadge,
      refreshAllData
    };
  }
}).mount("#app");

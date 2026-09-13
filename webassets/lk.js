const { createApp, ref, computed, onMounted, onUnmounted } = Vue;

createApp({
  setup() {
    const bookshelfBooks = ref([]);
    const cachedBooks = ref([]);
    const tasks = ref([]);
    const broRunning = ref(false);
    const broHeadless = ref(true);

    const showIsland = ref(false);
    const sidebarCollapsed = ref(false);
    const layoutMode = ref("grid");

    const viewMode = ref("all");
    const filterStatus = ref("all");
    const filterHeart = ref("all");
    const sortBy = ref("time");

    const showCustomUrlModal = ref(false);
    const targetUrl = ref("https://www.lightnovel.fun/category/lightnovel");
    const maxScrolls = ref(50);

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
      } catch (e) {}
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
      } catch (e) {}
    };

    const loadStatus = async () => {
      try {
        const res = await fetch("/lkapi/status");
        const data = await res.json();
        if (data.status === "ok") {
          broRunning.value = data.browser.running;
          broHeadless.value = data.browser.headless;
          // 自动清理已完成或失败、取消超过一定时间的任务，或仅保留最多最近 10 条
          const rawTasks = data.tasks || [];
          tasks.value = rawTasks.slice(-10).reverse();
        }
      } catch (e) {}
    };

    const toggleIsland = () => {
      showIsland.value = !showIsland.value;
    };

    const toggleSidebar = () => {
      sidebarCollapsed.value = !sidebarCollapsed.value;
    };

    const activeTask = computed(() => {
      const active = tasks.value.filter(t => t.status === 'running' || t.status === 'pending');
      return active.length > 0 ? active[0] : null;
    });

    const islandMainText = computed(() => {
      if (activeTask.value) {
        return activeTask.value.message || "任务处理中...";
      }
      if (broRunning.value) {
        return broHeadless.value ? "LKbro 就绪 (无头)" : "LKbro 就绪 (窗口)";
      }
      return "LKbro 待机";
    });

    const startBrowser = async (headless) => {
      await fetch("/lkapi/browser", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "start", headless: headless })
      });
      loadStatus();
    };

    const closeBrowser = async () => {
      await fetch("/lkapi/browser", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "close" })
      });
      loadStatus();
    };

    const openCustomUrlModal = () => {
      showCustomUrlModal.value = true;
      showIsland.value = false;
    };

    const executeFetchCustomBookshelf = async () => {
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
    };

    const collectCurrentPage = async () => {
      const res = await fetch("/lkapi/collect_current_page", { method: "POST" });
      const data = await res.json();
      if (data.status === "ok") {
        showIsland.value = true;
        loadStatus();
      }
    };

    const cancelTask = async (taskId) => {
      await fetch(`/lkapi/tasks/${taskId}/cancel`, { method: "POST" });
      loadStatus();
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
        loadBookshelf();
        loadCachedBooks();
      }, 3000);
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
      sidebarCollapsed,
      layoutMode,
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
      toggleSidebar,
      startBrowser,
      closeBrowser,
      openCustomUrlModal,
      executeFetchCustomBookshelf,
      collectCurrentPage,
      cancelTask,
      toggleHeart,
      openBook,
      getBookBadge,
      refreshAllData
    };
  }
}).mount("#app");

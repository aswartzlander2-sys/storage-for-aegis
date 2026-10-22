
    // State Variables
    let currentPath = ''; // Root path
    let allS3Items = []; // Raw list of objects
    let activeCategory = 'all';
    const RECENT_VIEWS_KEY = 'robo-storage-recent-views-v1';
    function getRecentViews() { try { return JSON.parse(localStorage.getItem(RECENT_VIEWS_KEY) || '{}'); } catch (_) { return {}; } }
    function markRecentView(item) {
      if (!item || item.isFolder) return;
      const views = getRecentViews();
      views[item.key] = Date.now();
      const trimmed = Object.fromEntries(Object.entries(views).sort((a,b) => b[1]-a[1]).slice(0,100));
      try { localStorage.setItem(RECENT_VIEWS_KEY, JSON.stringify(trimmed)); } catch (_) {}
    }
    let searchQuery = '';
    let viewMode = 'grid'; // 'grid' | 'list'
    let selectedItem = null;
    let selectionMode = false;
    const selectedItems = new Map(); // item.key -> item (files and/or folders)

    // DOM Elements
    const fileGrid = document.getElementById('fileGrid');
    const fileList = document.getElementById('fileList');
    const emptyState = document.getElementById('emptyState');
    const loadingSpinner = document.getElementById('loadingSpinner');
    const breadcrumbContainer = document.getElementById('breadcrumbContainer');
    const searchInput = document.getElementById('searchInput');
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    
    // Stats
    const statTotalFiles = document.getElementById('statTotalFiles');
    const statTotalSize = document.getElementById('statTotalSize');

    // Modals & Drawers
    const previewDrawer = document.getElementById('previewDrawer');
    const previewViewer = document.getElementById('previewViewer');
    const uploadModal = document.getElementById('uploadModal');
    const newFolderModal = document.getElementById('newFolderModal');
    const deleteModal = document.getElementById('deleteModal');

    // Audio Player Elements
    const audioElement = document.getElementById('globalAudioElement');
    const customAudioPlayerUI = document.getElementById('customAudioPlayerUI');
    const audioPlayPauseBtn = document.getElementById('audioPlayPauseBtn');
    const audioCurrentTime = document.getElementById('audioCurrentTime');
    const audioDuration = document.getElementById('audioDuration');
    const audioMuteBtn = document.getElementById('audioMuteBtn');
    const audioSpeedBtn = document.getElementById('audioSpeedBtn');

    // Utility: Format bytes into human readable format
    function formatBytes(bytes, decimals = 2) {
      if (!bytes || bytes === 0) return '0 B';
      const k = 1000;
      const dm = decimals < 0 ? 0 : decimals;
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    // =====================================================================
    // STORAGE (Drive-style): sidebar tab + full Storage page
    // Quota is 10 GB, so 1 GB of usage == exactly 10% of the bar.
    // =====================================================================
    let STORAGE_QUOTA_BYTES = 0; // Supplied by the configured server allocation.
    const STORAGE_CATS = [
      { key: 'image', label: 'Images',      color: '#34d399', desc: 'Photos, icons and graphics' },
      { key: 'video', label: 'Videos',      color: '#a78bfa', desc: 'Video files and clips' },
      { key: 'audio', label: 'Audio',       color: '#f472b6', desc: 'Music, voice and sound files' },
      { key: 'code',  label: 'Docs & Code', color: '#fbbf24', desc: 'Documents, PDFs and source files' },
      { key: 'other', label: 'Other',       color: '#305CDE', desc: 'Archives and everything else' }
    ];

    // Every object in the whole bucket (root listing) — powers the storage stats
    let allBucketItems = [];

    // Sum up bytes per category for a raw S3 object list
    function storageTotals(items) {
      const totals = {};
      STORAGE_CATS.forEach(c => totals[c.key] = 0);
      let used = 0;
      (items || []).forEach(it => {
        const key = it.key || it.name || '';
        if (key.endsWith('/')) return; // folder placeholder object
        const cat = getFileCategory(key);
        totals[totals[cat] !== undefined ? cat : 'other'] += (it.size || 0);
        used += (it.size || 0);
      });
      return { totals, used };
    }

    // The hover card lives directly on <body>. Nested inside the frosted <main>, its
    // backdrop-filter had nothing to sample and the glass never showed; at body level it
    // blurs the real page behind it exactly like the modals and drawer do.
    let storageTipEl = null;
    function getStorageTipEl() {
      if (storageTipEl && document.body.contains(storageTipEl)) return storageTipEl;
      const el = document.createElement('div');
      el.id = 'storageHoverCard';
      el.className = 'hidden fixed z-[80] pointer-events-none glass-strong rounded-2xl px-5 py-3 text-center min-w-[152px]';
      el.innerHTML = `
        <p data-tip-label class="text-[9px] font-bold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400"></p>
        <p data-tip-value class="text-xl font-extrabold text-slate-900 dark:text-white leading-tight mt-0.5"></p>
        <p data-tip-desc class="text-[10px] text-slate-500 dark:text-slate-400 mt-1 leading-snug"></p>`;
      document.body.appendChild(el);
      storageTipEl = el;
      return el;
    }
    function hideStorageTip() { if (storageTipEl) storageTipEl.classList.add('hidden'); }
    window.addEventListener('scroll', hideStorageTip, true);
    window.addEventListener('resize', hideStorageTip);

    // Paint a segmented usage bar (+ optional hover card + legend) into any container pair
    function paintStorageBar(cfg, totals, used) {
      const bar = cfg.bar, legend = cfg.legend, wantTip = !!cfg.tooltip;
      if (!bar) return;
      const free = Math.max(0, STORAGE_QUOTA_BYTES - used);

      function showTip(el, label, value, desc) {
        const tip = getStorageTipEl();
        tip.querySelector('[data-tip-label]').textContent = label;
        tip.querySelector('[data-tip-value]').textContent = value;
        tip.querySelector('[data-tip-desc]').textContent = desc;
        tip.classList.remove('hidden');
        const r = el.getBoundingClientRect();
        const tw = tip.offsetWidth, th = tip.offsetHeight;
        let left = r.left + (r.width / 2) - (tw / 2);
        left = Math.max(8, Math.min(left, window.innerWidth - tw - 8));
        let top = r.top - th - 12;
        if (top < 8) top = r.bottom + 12;
        tip.style.left = left + 'px';
        tip.style.top = top + 'px';
      }
      const hideTip = hideStorageTip;

      bar.innerHTML = '';
      // Widths are strictly proportional: width% = bytes / 10 GB * 100. No minimums,
      // no gaps, nothing that would make a small amount look bigger than it is.
      if (cfg.solid) {
        // Single accurate blue bar (sidebar) — no colour coding
        if (used > 0) {
          const seg = document.createElement('div');
          seg.className = 'storage-seg rounded-full shrink-0 cursor-default';
          seg.style.background = '#305CDE';
          seg.style.width = ((used / STORAGE_QUOTA_BYTES) * 100) + '%';
          if (wantTip) {
            seg.addEventListener('mouseenter', () => showTip(seg, 'Storage used', formatBytes(used), 'Total size of every object in this bucket'));
            seg.addEventListener('mouseleave', hideTip);
          }
          bar.appendChild(seg);
        }
      } else {
        STORAGE_CATS.forEach(c => {
          const bytes = totals[c.key] || 0;
          if (bytes <= 0) return;
          const seg = document.createElement('div');
          seg.className = 'storage-seg rounded-full shrink-0 cursor-default';
          seg.style.background = c.color;
          seg.style.width = ((bytes / STORAGE_QUOTA_BYTES) * 100) + '%'; // 1 GB -> 10%
          if (wantTip) {
            seg.addEventListener('mouseenter', () => showTip(seg, c.label, formatBytes(bytes), c.desc));
            seg.addEventListener('mouseleave', hideTip);
          }
          bar.appendChild(seg);
        });
      }
      const rest = document.createElement('div');
      rest.className = 'flex-1 min-w-0 cursor-default';
      if (wantTip) {
        rest.addEventListener('mouseenter', () => showTip(rest, 'Available', formatBytes(free), 'Available storage remaining'));
        rest.addEventListener('mouseleave', hideTip);
      }
      bar.appendChild(rest);

      if (legend) {
        legend.innerHTML = '';
        const active = STORAGE_CATS.filter(c => (totals[c.key] || 0) > 0);
        active.forEach(c => {
          const item = document.createElement('span');
          item.className = `flex items-center gap-1.5 ${cfg.legendSize || 'text-[10px]'} text-slate-500 dark:text-slate-400`;
          item.innerHTML = `<span class="w-1.5 h-1.5 rounded-full shrink-0" style="background:${c.color}"></span>${c.label}`;
          legend.appendChild(item);
        });
        if (!active.length) legend.innerHTML = `<span class="${cfg.legendSize || 'text-[10px]'} text-slate-400 dark:text-slate-500">Bucket is empty</span>`;
      }
    }

    // Sidebar storage widget (always reflects the WHOLE bucket, not just this folder)
    function updateStorageWidget(items) {
      const list = items || allBucketItems;
      const quotaText = document.getElementById('storageQuotaText');
      if (quotaText) quotaText.textContent = formatBytes(STORAGE_QUOTA_BYTES, 0);
      const { totals } = storageTotals(list);
      const used = cloudUsage();
      const files = (list || []).filter(o => o.key && !o.key.endsWith('/'));
      if (statTotalSize) statTotalSize.textContent = formatBytes(used);
      if (statTotalFiles) statTotalFiles.textContent = files.length;
      paintStorageBar({
        bar: document.getElementById('storageBar'),
        legend: null,
        tooltip: false,  // no hover card in the sidebar
        solid: true,     // sidebar bar is a single, true-to-scale blue fill
      }, totals, used);
      if (isStoragePageOpen()) renderStoragePage();
    }

    // Pull a full root listing so the Storage tab/page covers every file in the bucket
    let bucketStorageBusy = false;
    async function refreshBucketStorage() {
      if (currentPath === '') { allBucketItems = allS3Items; updateStorageWidget(); return; }
      if (bucketStorageBusy) return;
      bucketStorageBusy = true;
      const { data, error } = await s3List('');
      bucketStorageBusy = false;
      if (!error) { allBucketItems = data; updateStorageWidget(); }
    }

    // ---------------------------------------------------------------------
    // Storage page: filters, sorting and the full "every file in the bucket" table
    // ---------------------------------------------------------------------
    let storageSort = { key: 'size', dir: 'desc' };

    // Sidebar tab styling: identical metrics to the category tabs, blue only when active
    const STORAGE_TAB_IDLE   = 'storage-tab w-full flex items-center gap-3 px-3 py-2 rounded-full text-xs font-bold text-slate-500 dark:text-slate-400 hover:bg-slate-900/[0.04] dark:hover:bg-white/10 hover:text-slate-700 dark:hover:text-slate-200 transition-colors';
    const STORAGE_TAB_ACTIVE = 'storage-tab w-full flex items-center gap-3 px-3 py-2 rounded-full text-xs font-bold bg-brand-500/10 text-brand-300 border border-brand-400/20';
    const CAT_BTN_IDLE   = 'cat-btn w-full flex items-center gap-3 px-3 py-2 rounded-full text-xs font-bold text-slate-500 dark:text-slate-400 hover:bg-slate-900/[0.04] dark:hover:bg-white/10 hover:text-slate-700 dark:hover:text-slate-200 transition-colors';
    const CAT_BTN_ACTIVE = 'cat-btn w-full flex items-center gap-3 px-3 py-2 rounded-full text-xs font-bold bg-brand-500/10 text-brand-300 border border-brand-400/20';

    function isStoragePageOpen() {
      const el = document.getElementById('storagePage');
      return !!el && !el.classList.contains('hidden');
    }

    function storagePageItems() {
      return (allBucketItems.length ? allBucketItems : allS3Items || [])
        .filter(o => o.key && !o.key.endsWith('/'))
        .map(o => ({
          isFolder: false,
          name: o.key.split('/').filter(Boolean).pop(),
          key: o.key,
          size: o.size || 0,
          lastModified: o.lastModified,
          category: getFileCategory(o.key)
        }))
        .sort((a, b) => {
          const dir = storageSort.dir === 'asc' ? 1 : -1;
          if (storageSort.key === 'name') return a.name.localeCompare(b.name, undefined, { numeric: true }) * dir;
          return (a.size - b.size) * dir;
        });
    }

    function renderStoragePage() {
      const rowsBox = document.getElementById('storageFileRows');
      if (!rowsBox) return;

      const { totals, used } = storageTotals(allBucketItems.length ? allBucketItems : allS3Items);
      const usedEl = document.getElementById('storagePageUsed');
      const quotaEl = document.getElementById('storagePageQuota');
      if (usedEl) usedEl.textContent = formatBytes(used);
      if (quotaEl) quotaEl.textContent = formatBytes(STORAGE_QUOTA_BYTES, 0);

      paintStorageBar({
        bar: document.getElementById('storagePageBar'),
        legend: document.getElementById('storagePageLegend'),
        tooltip: true,
        legendSize: 'text-[11px]'
      }, totals, used);

      // sort arrows
      document.querySelectorAll('[data-sort-arrow]').forEach(el => {
        const on = el.getAttribute('data-sort-arrow') === storageSort.key;
        el.classList.toggle('hidden', !on);
        const ic = el.querySelector('i');
        if (ic) ic.className = `fa-solid ${storageSort.dir === 'asc' ? 'fa-arrow-up' : 'fa-arrow-down'} text-[10px]`;
      });

      const items = storagePageItems();
      rowsBox.innerHTML = '';
      document.getElementById('storageEmptyRow').classList.toggle('hidden', items.length > 0);

      items.forEach(item => {
        const iconInfo = getFileIcon(item.name);
        const folder = item.key.includes('/') ? item.key.slice(0, item.key.lastIndexOf('/')) : 'root';
        const row = document.createElement('div');
        row.className = 'group flex items-center gap-4 px-3 py-2.5 border-b border-slate-200/70 dark:border-white/[0.06] hover:bg-slate-900/[0.035] dark:hover:bg-white/[0.05] cursor-pointer transition-colors';
        row.innerHTML = `
          <div class="w-7 h-7 shrink-0 rounded-md bg-slate-900/[0.04] dark:bg-white/[0.07] border border-slate-200 dark:border-white/10 flex items-center justify-center text-xs ${iconInfo.color}">
            <i class="fa-solid ${iconInfo.icon}"></i>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[13px] text-slate-700 dark:text-slate-200 truncate group-hover:text-brand-500 dark:group-hover:text-brand-300 transition-colors" title="${escapeHtml(item.key)}">${escapeHtml(item.name)}</p>
            <p class="text-[10px] font-mono text-slate-400 dark:text-slate-500 truncate">${folder}</p>
          </div>
          <div class="w-40 text-right text-[13px] text-slate-600 dark:text-slate-300 shrink-0">${formatBytes(item.size)}</div>`;
        row.addEventListener('click', () => openFilePreview(item));
        rowsBox.appendChild(row);
      });
    }

    function openStoragePage() {
      const page = document.getElementById('storagePage');
      if (!page) return;
      document.getElementById('explorerToolbar').classList.add('hidden');
      document.getElementById('selectionBar').classList.add('hidden');
      document.getElementById('fileDisplayArea').classList.add('hidden');
      page.classList.remove('hidden');
      document.getElementById('storageTabBtn').className = STORAGE_TAB_ACTIVE;
      // only one tab can look selected at a time
      document.querySelectorAll('.cat-btn').forEach(b => b.className = CAT_BTN_IDLE);
      renderStoragePage();
    }

    function closeStoragePage() {
      const page = document.getElementById('storagePage');
      if (!page || page.classList.contains('hidden')) return;
      page.classList.add('hidden');
      document.getElementById('explorerToolbar').classList.remove('hidden');
      document.getElementById('fileDisplayArea').classList.remove('hidden');
      document.getElementById('storageTabBtn').className = STORAGE_TAB_IDLE;
      // hand the highlight back to whichever category is active
      document.querySelectorAll('.cat-btn').forEach(b => {
        b.className = (b.getAttribute('data-cat') === activeCategory) ? CAT_BTN_ACTIVE : CAT_BTN_IDLE;
      });
      if (typeof selectionMode !== 'undefined' && selectionMode) {
        document.getElementById('selectionBar').classList.remove('hidden');
      }
    }

    // Utility: Categorize file by extension. Every previewable type gets a real
    // inline preview; archives/binaries/unknown fall back to the download-only card.
    function getFileCategory(filename) {
      const ext = filename.split('.').pop().toLowerCase();
      if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif', 'apng', 'jfif', 'jxl', 'tif', 'tiff', 'heic', 'heif'].includes(ext)) return 'image';
      if (['mp4', 'webm', 'mov', 'mkv', 'avi', 'ogv', 'm4v', '3gp', 'mpeg', 'mpg', 'wmv', 'flv'].includes(ext)) return 'video';
      if (['mp3', 'wav', 'ogg', 'oga', 'opus', 'aac', 'flac', 'm4a', 'weba', 'aiff', 'aif', 'amr', 'mid', 'midi', 'kar', 'smf'].includes(ext)) return 'audio';
      if (['html', 'htm', 'js', 'mjs', 'jsx', 'ts', 'tsx', 'json', 'css', 'scss', 'sass', 'less', 'txt', 'md', 'markdown', 'py', 'cpp', 'cc', 'cxx', 'c', 'h', 'hpp', 'java', 'xml', 'yaml', 'yml', 'sh', 'bash', 'zsh', 'sql', 'php', 'rb', 'go', 'rs', 'toml', 'ini', 'cfg', 'conf', 'env', 'properties', 'log', 'csv', 'vue', 'svelte', 'dockerfile', 'gitignore', 'makefile', 'pdf'].includes(ext)) return 'code';
      return 'other';
    }

    // Utility: Return icon for file extension
    function getFileIcon(filename, isFolder = false) {
      if (isFolder) return { icon: 'fa-folder', color: 'text-amber-400' };
      const cat = getFileCategory(filename);
      const ext = filename.split('.').pop().toLowerCase();
      if (['mid','midi','kar','smf'].includes(ext)) return { icon: 'fa-music', color: 'text-violet-400' };
      switch(cat) {
        case 'image': return { icon: 'fa-file-image', color: 'text-emerald-400' };
        case 'video': return { icon: 'fa-file-video', color: 'text-purple-400' };
        case 'audio': return { icon: 'fa-file-audio', color: 'text-pink-400' };
        case 'code':
          if (ext === 'pdf') return { icon: 'fa-file-pdf', color: 'text-rose-400' };
          if (ext === 'html') return { icon: 'fa-file-code', color: 'text-orange-400' };
          if (ext === 'json') return { icon: 'fa-file-lines', color: 'text-amber-300' };
          return { icon: 'fa-file-code', color: 'text-amber-400' };
        default: return { icon: 'fa-file', color: 'text-brand-300' };
      }
    }

    async function loadDirectory(retryCount = 0) {
      loadingSpinner.classList.remove('hidden');
      const { data, error } = await s3List(currentPath);
      loadingSpinner.classList.add('hidden');

      if (error) {
        // Transient network/CORS hiccups are common on cold start — retry before giving up
        if (retryCount < 3) {
          setTimeout(() => loadDirectory(retryCount + 1), 1200);
          return;
        }
        showToast('Unable to load storage', 'error');
        return;
      }

      allS3Items = data;
      renderExplorer();
      refreshBucketStorage(); // keep the Storage tab/page bucket-wide

    }

    // Parse current items into relative folders and files
    function getParsedDirectoryItems() {
      if (activeCategory === 'recent') {
        const views = getRecentViews();
        return allS3Items
          .filter(item => item.key && !item.key.endsWith('/') && views[item.key] && item.key.toLowerCase().includes(searchQuery.toLowerCase()))
          .map(item => ({
            isFolder:false,
            name:item.key.split('/').filter(Boolean).pop(),
            key:item.key,
            size:item.size || 0,
            lastModified:item.lastModified,
            viewedAt:views[item.key],
            category:getFileCategory(item.key)
          }))
          .sort((a,b) => b.viewedAt - a.viewedAt);
      }
      const items = [];
      const subfolderSet = new Set();
      cloudAddPartitions(items, subfolderSet, currentPath);

      allS3Items.forEach(item => {
        if(item.virtualPartition)return;
        const relativeKey = item.key.slice(currentPath.length);
        if (!relativeKey) return; // current directory placeholder

        const slashIndex = relativeKey.indexOf('/');
        if (slashIndex !== -1) {
          // It's a subdirectory item
          const folderName = relativeKey.substring(0, slashIndex);
          if (!subfolderSet.has(folderName)) {
            subfolderSet.add(folderName);
            items.push({
              isFolder: true,
              name: folderName,
              key: currentPath + folderName + '/',
              size: 0,
              lastModified: ''
            });
          }
        } else {
          // It's a file directly under current path
          items.push({
            isFolder: false,
            name: relativeKey,
            key: item.key,
            size: item.size,
            lastModified: item.lastModified,
            category: getFileCategory(relativeKey)
          });
        }
      });

      // Calculate bucket statistics

      // Filter by active category & search query
      const filtered = items.filter(item => {
        if (activeCategory === 'recent') return !item.isFolder && item.name.toLowerCase().includes(searchQuery.toLowerCase());
        if (item.isFolder) {
          return activeCategory === 'all' && item.name.toLowerCase().includes(searchQuery.toLowerCase());
        }
        const matchesCategory = activeCategory === 'all' || item.category === activeCategory;
        const matchesSearch = item.name.toLowerCase().includes(searchQuery.toLowerCase());
        return matchesCategory && matchesSearch;
      });
      if (activeCategory === 'recent') filtered.sort((a,b) => new Date(b.lastModified || 0) - new Date(a.lastModified || 0));
      return filtered;
    }

    function renderExplorer() {
      const items = getParsedDirectoryItems();

      fileGrid.innerHTML = '';
      fileList.innerHTML = '';

      if (items.length === 0) {
        emptyState.classList.remove('hidden');
        fileGrid.classList.add('hidden');
        fileList.classList.add('hidden');
      } else {
        emptyState.classList.add('hidden');
        if (viewMode === 'grid') {
          fileGrid.classList.remove('hidden');
          fileList.classList.add('hidden');
        } else {
          fileGrid.classList.add('hidden');
          fileList.classList.remove('hidden');
        }
      }

      items.forEach((item, itemIndex) => {
        const iconInfo = getFileIcon(item.name, item.isFolder);
        const isSelected = selectedItems.has(item.key);

        // Grid Card Component
        const gridCard = document.createElement('div');
        gridCard.className = `group p-4 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between h-36 relative shadow-xl shadow-black/20 hover:-translate-y-0.5 backdrop-blur-md ${
          isSelected
            ? 'bg-brand-500/15 border-brand-400/70'
            : selectionMode
              ? 'bg-white/60 dark:bg-white/[0.04] border-slate-200 dark:border-white/10 hover:border-brand-400/50 hover:bg-brand-500/10'
              : 'bg-white/60 dark:bg-white/[0.04] border-slate-200 dark:border-white/10 hover:border-brand-400/50 hover:bg-slate-900/[0.04] dark:hover:bg-white/[0.07]'
        }`;
        gridCard.innerHTML = `
          <div class="flex items-start justify-between">
            <div class="flex items-center gap-2 min-w-0">
              ${selectionMode ? `
                <div class="grid-select-checkbox absolute top-3 left-3 z-20 w-5 h-5 rounded-full ${isSelected ? 'is-selected bg-black' : 'bg-white/70 dark:bg-white/20'} flex items-center justify-center shrink-0">
                  <i class="fa-solid fa-check text-[9px] text-white ${isSelected ? '' : 'opacity-0'}"></i>
                </div>` : ''}
              ${(!item.isFolder && item.category === 'image') ? `
              <div data-grid-image class="grid-image-thumb">
                <img alt="${escapeHtml(item.name)}" draggable="false">
                <div class="grid-image-loading"><i class="fa-solid fa-image ${iconInfo.color}"></i></div>
              </div>` : `
              <div class="grid-file-icon bg-slate-900/[0.04] dark:bg-white/[0.07] border border-slate-200 dark:border-white/10 flex items-center justify-center ${iconInfo.color}">
                <i class="fa-solid ${iconInfo.icon}"></i>
              </div>`}
            </div>
            ${!selectionMode ? `
              <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
                <button title="Rename" data-rename-btn class="icon-circle icon-circle-sm rounded-full hover:bg-slate-900/[0.04] dark:hover:bg-white/10 text-slate-500 dark:text-slate-400 hover:text-brand-500 transition-colors">
                  <i class="fa-solid fa-pen text-[11px]"></i>
                </button>
                ${!item.isFolder ? `
                <button title="Options" class="icon-circle icon-circle-sm rounded-full hover:bg-slate-900/[0.04] dark:hover:bg-white/10 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-all">
                  <i class="fa-solid fa-ellipsis-vertical text-xs"></i>
                </button>` : ''}
              </div>
            ` : ''}
          </div>
          <div>
            <h4 class="font-medium text-xs text-slate-700 dark:text-slate-200 truncate group-hover:text-brand-300 transition-colors" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</h4>
            <p class="text-[11px] text-slate-600 dark:text-slate-500 mt-0.5 font-mono">${item.isFolder ? (item.isPartition ? 'Partition · '+(item.partitionLimit ? formatBytes(item.partitionLimit) : 'inherited') : 'Folder') : formatBytes(item.size)}</p>
          </div>
        `;
        gridCard.style.animationDelay = Math.min(itemIndex * 24, 180) + 'ms';
        gridCard.addEventListener('click', () => onItemClick(item));
        gridCard.addEventListener('contextmenu', (e) => showFileContextMenu(e, item));
        const renameBtn = gridCard.querySelector('[data-rename-btn]');
        if (renameBtn) renameBtn.addEventListener('click', (e) => { e.stopPropagation(); openRenameModal(item); });
        gridCard.dataset.cloudKey = item.key; fileGrid.appendChild(gridCard);
        const gridImage = gridCard.querySelector('[data-grid-image] img');
        if (gridImage) {
          s3PresignUrl(item.key).then((url) => {
            gridImage.onload = () => {
              gridImage.classList.add('is-loaded');
              const loading = gridImage.parentElement.querySelector('.grid-image-loading');
              if (loading) loading.remove();
            };
            gridImage.src = url;
          }).catch(() => {});
        }

        // List Row Component
        const listRow = document.createElement('div');
        listRow.className = `group flex items-center justify-between p-3 rounded-xl border transition-all cursor-pointer text-xs backdrop-blur-md ${
          isSelected
            ? 'bg-brand-500/15 border-brand-400/70'
            : 'bg-white/50 dark:bg-white/[0.03] border-slate-200/70 dark:border-white/5 hover:bg-slate-900/[0.04] dark:hover:bg-white/[0.07] hover:border-slate-200 dark:border-white/15'
        }`;
        listRow.innerHTML = `
          <div class="flex items-center gap-3 min-w-0 flex-1">
            ${selectionMode ? `
              <div class="w-4 h-4 rounded-full border ${isSelected ? 'bg-brand-500 border-brand-400' : 'border-slate-300 dark:border-white/25 bg-white/60 dark:bg-black/40'} flex items-center justify-center shrink-0">
                <i class="fa-solid fa-check text-[8px] text-slate-900 dark:text-white ${isSelected ? '' : 'opacity-0'}"></i>
              </div>` : ''}
            ${(!item.isFolder && item.category === 'image') ? `
            <div data-list-image class="list-image-thumb shrink-0">
              <img alt="${escapeHtml(item.name)}" draggable="false">
              <i class="fa-solid fa-image ${iconInfo.color}"></i>
            </div>` : `
            <div class="w-8 h-8 rounded-xl bg-slate-900/[0.04] dark:bg-white/[0.07] border border-slate-200 dark:border-white/10 flex items-center justify-center text-sm ${iconInfo.color} shrink-0">
              <i class="fa-solid ${iconInfo.icon}"></i>
            </div>`}
            <span class="font-medium text-slate-700 dark:text-slate-200 truncate pr-4">${escapeHtml(item.name)}</span>
          </div>
          <div class="flex items-center gap-4 shrink-0">
            <button title="Rename" data-rename-btn class="opacity-0 group-hover:opacity-100 icon-circle icon-circle-sm rounded-full hover:bg-slate-900/[0.04] dark:hover:bg-white/10 text-slate-500 dark:text-slate-400 hover:text-brand-500 transition-colors">
              <i class="fa-solid fa-pen text-[11px]"></i>
            </button>
            <span class="text-slate-600 dark:text-slate-500 font-mono w-24 text-right">${item.isFolder ? (item.isPartition ? 'Partition · '+(item.partitionLimit ? formatBytes(item.partitionLimit) : 'inherited') : 'Folder') : formatBytes(item.size)}</span>
            <span class="text-slate-600 dark:text-slate-500 font-mono w-32 hidden sm:inline text-right">${item.lastModified ? new Date(item.lastModified).toLocaleDateString() : '-'}</span>
          </div>
        `;
        listRow.addEventListener('click', () => onItemClick(item));
        listRow.addEventListener('contextmenu', (e) => showFileContextMenu(e, item));
        const listRenameBtn = listRow.querySelector('[data-rename-btn]');
        if (listRenameBtn) listRenameBtn.addEventListener('click', (e) => { e.stopPropagation(); openRenameModal(item); });
        listRow.dataset.cloudKey = item.key; fileList.appendChild(listRow);
        const listImage = listRow.querySelector('[data-list-image] img');
        if (listImage) {
          s3PresignUrl(item.key).then((url) => {
            listImage.onload = () => listImage.parentElement.classList.add('is-loaded');
            listImage.src = url;
          }).catch(() => {});
        }
      });

      renderBreadcrumbs();
    }

    let contextMenuItem = null;
    const fileContextMenu = document.getElementById('fileContextMenu');

    function hideFileContextMenu() {
      fileContextMenu.classList.add('hidden');
      contextMenuItem = null;
    }

    function showFileContextMenu(event, item) {
      event.preventDefault(); event.stopPropagation();
      contextMenuItem = item;
      const newTab = fileContextMenu.querySelector('[data-ctx="newtab"]');
      const copy = fileContextMenu.querySelector('[data-ctx="copy"]');
      const midiMp3 = fileContextMenu.querySelector('[data-ctx="midi-mp3"]');
      const isMidiFile = !item.isFolder && /\.(mid|midi|kar|smf)$/i.test(item.name || '');
      if (midiMp3) midiMp3.classList.toggle('hidden', !isMidiFile);
      [newTab, copy].forEach(btn => btn.classList.toggle('ctx-disabled', !!item.isFolder));
      fileContextMenu.classList.remove('hidden');
      const rect = fileContextMenu.getBoundingClientRect();
      const left = Math.max(8, Math.min(event.clientX, window.innerWidth - rect.width - 8));
      const top = Math.max(8, Math.min(event.clientY, window.innerHeight - rect.height - 8));
      fileContextMenu.style.left = left + 'px';
      fileContextMenu.style.top = top + 'px';
    }

    fileContextMenu.addEventListener('click', async (event) => {
      const btn = event.target.closest('[data-ctx]');
      const item = contextMenuItem;
      if (!btn || !item || btn.classList.contains('ctx-disabled')) return;
      const action = btn.dataset.ctx;
      hideFileContextMenu();
      if (action === 'open') return onItemClick(item);
      if (action === 'rename') return openRenameModal(item);
      if (action === 'delete') {
        selectedItem = item;
        pendingBulkDeletePaths = null;
        deleteModalTitle.textContent = item.isFolder ? 'Delete Folder?' : 'Delete File?';
        deleteModalMessage.innerHTML = `Are you sure you want to permanently delete <span class="text-slate-700 dark:text-slate-200 font-mono font-semibold">${escapeHtml(item.name)}</span>?`;
        deleteModal.classList.remove('hidden');
        return;
      }
      const url = await s3PresignUrl(item.key);
      if (action === 'midi-mp3') return exportMidiToMp3(item, url);
      if (action === 'newtab') window.open(url, '_blank', 'noopener');
      if (action === 'copy') {
        await navigator.clipboard.writeText(url);
        showToast('Link copied');
      }
    });
    document.addEventListener('pointerdown', (e) => { if (!fileContextMenu.contains(e.target)) hideFileContextMenu(); });
    document.addEventListener('scroll', hideFileContextMenu, true);
    window.addEventListener('resize', hideFileContextMenu);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideFileContextMenu(); });

    // Render Navigation Breadcrumb
    function renderBreadcrumbs() {
      breadcrumbContainer.innerHTML = '';

      const rootBtn = document.createElement('button');
      rootBtn.className = 'hover:text-brand-300 transition-colors flex items-center gap-1 font-medium text-slate-600 dark:text-slate-300';
      rootBtn.innerHTML = activeCategory === 'recent' ? '<i class="fa-regular fa-clock text-xs"></i> Recent' : '<i class="fa-solid fa-house text-xs"></i> root';
      rootBtn.onclick = () => { currentPath = ''; loadDirectory(); };
      breadcrumbContainer.appendChild(rootBtn);

      if (currentPath) {
        const parts = currentPath.split('/').filter(Boolean);
        let accumulated = '';
        parts.forEach((part, index) => {
          accumulated += part + '/';
          const targetPath = accumulated;

          const slash = document.createElement('span');
          slash.className = 'text-slate-600 text-xs';
          slash.innerHTML = '/';
          breadcrumbContainer.appendChild(slash);

          const btn = document.createElement('button');
          btn.className = `hover:text-brand-300 transition-colors ${index === parts.length - 1 ? 'font-bold text-brand-300 robo-link' : 'text-slate-600 dark:text-slate-300'}`;
          btn.textContent = part;
          btn.onclick = () => { currentPath = targetPath; loadDirectory(); };
          breadcrumbContainer.appendChild(btn);
        });
      }
    }

    // Handle File / Folder Click
    async function onItemClick(item) {
      if (selectionMode) { toggleSelection(item); return; }
      markRecentView(item);
      if (item.isFolder) {
        currentPath = item.key;
        loadDirectory();
      } else {
        openFilePreview(item);
      }
    }

    async function openFilePreview(item, drawerOnly = false) {
      // Warn before discarding unsaved edits in the code editor
      if ((codeEditor && codeEditorDirty) || (expandedCodeEditor && expandedCodeEditorDirty)) {
        if (!confirm('You have unsaved changes in the code editor. Discard them and open a different file?')) return;
      }
      destroyPdfViewer(pdfViewerDrawer); pdfViewerDrawer = null;
      if (!drawerOnly) closeExpandedPreview(); // keep fullscreen viewer visible while opening its info panel
      selectedItem = item;
      if (!drawerOnly) {
        // The audio fullscreen player reuses the fully wired player from the details
        // drawer. Initialize it off-screen first; otherwise the fullscreen shell has
        // nothing to move and appears empty until the three-dot panel is opened.
        if ((item.category || getFileCategory(item.name)) === 'audio') {
          await openFilePreview(item, true);
          previewDrawer.classList.add('translate-x-full');
          previewDrawer.classList.remove('preview-info-over-modal');
          await openExpandedPreview();
          return;
        }
        previewDrawer.classList.add('translate-x-full');
        await openExpandedPreview();
        return;
      }
      previewDrawer.classList.remove('translate-x-full');

      const fileNameElem = document.getElementById('previewFileName');
      const fileIconElem = document.getElementById('previewFileIcon');
      const metaFileSize = document.getElementById('metaFileSize');
      const metaFileExt = document.getElementById('metaFileExt');
      const metaFilePath = document.getElementById('metaFilePath');
      const previewExternalLink = document.getElementById('previewExternalLink');

      const ext = item.name.split('.').pop().toLowerCase();
      const renderMidiMp3Btn = document.getElementById('renderMidiMp3Btn');
      if (renderMidiMp3Btn) {
        const readyLink = document.getElementById('midiMp3DownloadLink');
        if (readyLink) { readyLink.classList.add('hidden'); readyLink.classList.remove('flex'); readyLink.removeAttribute('href'); }
        const isMidi = ['mid','midi','kar','smf'].includes(ext);
        renderMidiMp3Btn.classList.toggle('hidden', !isMidi);
        renderMidiMp3Btn.classList.toggle('flex', isMidi);
      }
      const iconInfo = getFileIcon(item.name);

      fileNameElem.textContent = item.name;
      fileIconElem.className = `text-lg ${iconInfo.color} shrink-0`;
      fileIconElem.innerHTML = `<i class="fa-solid ${iconInfo.icon}"></i>`;
      metaFileSize.textContent = formatBytes(item.size);
      metaFileExt.textContent = ext;
      metaFilePath.textContent = item.key;

      previewViewer.classList.remove('hidden');
      previewViewer.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin text-2xl text-brand-400"></i>`;
      customAudioPlayerUI.classList.add('hidden');

      // Generate Presigned URL (inline disposition → opens in browser, no forced download)
      const presignedUrl = await s3PresignUrl(item.key);
      previewExternalLink.href = presignedUrl;
      const metaFileUrl = document.getElementById('metaFileUrl');
      metaFileUrl.href = presignedUrl;
      metaFileUrl.textContent = presignedUrl;

      const category = item.category || getFileCategory(item.name);

      if (category === 'image') {
        previewViewer.innerHTML = `
          <div class="relative w-full max-h-[350px] bg-black rounded-xl overflow-hidden flex items-center justify-center">
            <img src="${presignedUrl}" alt="${escapeHtml(item.name)}" class="max-h-[350px] w-auto max-w-full object-contain cursor-zoom-in" title="Click to open full size in a new tab">
            <div class="absolute top-3 left-3 drive-pill-dark px-3 py-1.5 flex items-center gap-2 pointer-events-none">
              <i class="fa-solid fa-image text-white/80 text-xs"></i>
              <span class="text-white text-xs font-medium truncate max-w-[180px]">${escapeHtml(item.name)}</span>
            </div>
            <button data-cloud-open="${presignedUrl}" class="absolute top-3 right-3 drive-pill-white w-9 h-9 flex items-center justify-center hover:scale-[1.05] active:scale-95 transition-transform">
              <i class="fa-solid fa-arrow-up-right-from-square text-black text-xs"></i>
            </button>
          </div>`;
        previewViewer.querySelector('img').onclick = () => window.open(presignedUrl, '_blank');
      } 
      else if (category === 'video') {
        previewViewer.innerHTML = `
          <div class="drive-video-wrap w-full max-h-[350px] aspect-video bg-black group/drive relative">
            <video id="drawerDriveVideo" autoplay playsinline class="w-full h-full object-contain bg-black" src="${presignedUrl}"></video>
            <!-- PiP placeholder: rounded square with a Font Awesome PiP icon while the video is popped out (same treatment as the audio icon square) -->
            <div data-pip-placeholder class="hidden absolute inset-0 flex items-center justify-center pointer-events-none">
              <div class="w-28 h-28 sm:w-36 sm:h-36 rounded-3xl bg-white/[0.07] border border-white/15 backdrop-blur-sm flex items-center justify-center shadow-2xl">
                <i class="fa-solid fa-clone text-purple-400" style="font-size:48px"></i>
              </div>
            </div>
            <div data-drive-menu class="hidden absolute bottom-[72px] right-3 drive-menu pointer-events-auto p-1.5 w-[260px] flex flex-col gap-1.5 z-20 p-2">
              <div data-menu-main class="flex flex-col gap-1">
                <button data-menu-pip class="video-menu-row"><span><span class="material-icons">picture_in_picture_alt</span> Picture in picture</span></button>
                <button data-menu-cc class="video-menu-row"><span><span class="material-icons">closed_caption</span> Subtitles/CC</span><span class="material-icons menu-check" data-menu-cc-check style="visibility:hidden">check</span></button>
                <button data-menu-quality class="video-menu-row"><span><span class="material-icons">tune</span> Quality</span><span class="menu-value"><span data-menu-quality-val>Auto</span> <span class="material-icons menu-chevron">chevron_right</span></span></button>
                <button data-menu-speed class="video-menu-row"><span><span class="material-icons">speed</span> Playback speed</span><span class="menu-value"><span data-menu-speed-val>1x</span> <span class="material-icons menu-chevron">chevron_right</span></span></button>
                <button class="video-menu-row disabled" disabled><span><span class="material-icons">summarize</span> Transcript</span></button>
              </div>
              <div data-quality-submenu class="hidden video-submenu">
                <button data-menu-back class="video-menu-row submenu-title"><span><span class="material-icons">arrow_back</span> Settings</span></button>
                <div class="video-menu-separator"></div>
                <button data-quality-opt="1080p" class="video-menu-row"><span>1080p</span></button>
                <button data-quality-opt="720p" class="video-menu-row active"><span><span class="material-icons menu-check">check</span>720p</span></button>
                <button data-quality-opt="360p" class="video-menu-row"><span>360p</span></button>
                <button data-quality-opt="Auto" class="video-menu-row"><span>Auto</span></button>
              </div>
              <div data-speed-submenu class="hidden video-submenu">
                <button data-menu-back class="video-menu-row submenu-title"><span><span class="material-icons">arrow_back</span> Playback speed</span></button>
                <div class="video-menu-separator"></div>
                <button data-speed-opt="0.25" class="video-menu-row"><span>0.25</span></button>
                <button data-speed-opt="0.5" class="video-menu-row"><span>0.5</span></button>
                <button data-speed-opt="0.75" class="video-menu-row"><span>0.75</span></button>
                <button data-speed-opt="1" class="video-menu-row active"><span><span class="material-icons menu-check">check</span>1</span></button>
                <button data-speed-opt="1.25" class="video-menu-row"><span>1.25</span></button>
                <button data-speed-opt="1.5" class="video-menu-row"><span>1.5</span></button>
                <button data-speed-opt="1.75" class="video-menu-row"><span>1.75</span></button>
                <button data-speed-opt="2" class="video-menu-row"><span>2</span></button>
              </div>
            </div>
            <div class="absolute left-3 right-3 bottom-[72px] drive-progress" data-drive-progress>
              <div class="drive-progress-fill"></div>
              <div class="drive-progress-thumb"></div>
            </div>
            <!-- Drive bottom pills -->
            <div class="absolute left-3 right-3 bottom-3 flex items-center justify-between gap-3 pointer-events-none">
              <div class="flex items-center gap-2 pointer-events-auto">
                <button data-drive-play class="media-play-btn hover:scale-[1.02] active:scale-95">
                  <span class="material-icons text-black" style="font-size:22px">play_arrow</span>
                </button>
                <div class="drive-pill-dark flex items-center gap-1.5 px-3 py-2">
                  <button data-drive-back class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Replay 10s"><span class="material-icons" style="font-size:20px">replay_10</span></button>
                  <button data-drive-forward class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Forward 10s"><span class="material-icons" style="font-size:20px">forward_10</span></button>
                  <span class="text-white text-sm font-mono tabular-nums px-3" data-drive-time>0:00 / 0:02</span>
                </div>
              </div>
              <div class="drive-pill-dark flex items-center gap-1 px-2 py-2 pointer-events-auto">
                <button data-drive-mute class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Mute"><span class="material-icons" style="font-size:20px">volume_up</span></button>
                <button data-drive-cc class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent" title="Captions (no captions)"><span class="material-icons" style="font-size:20px">closed_caption</span></button>
                <button data-drive-pip class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Picture-in-Picture"><span class="material-icons" style="font-size:20px">picture_in_picture_alt</span></button>
                <button data-drive-speed class="px-3 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white text-sm font-bold tabular-nums">1x</button>
                <button data-drive-settings class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Settings"><span class="material-icons" style="font-size:20px">settings</span></button>
                <button data-drive-full class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Fullscreen"><span class="material-icons" style="font-size:20px">fullscreen</span></button>
              </div>

            </div>
          </div>`;
        setTimeout(() => setupDrivePlayer('drawerDriveVideo'), 30);
      } 
      else if (category === 'audio') {
        // The Drive-style audio player below IS the viewer — its rounded audio
        // icon square takes the place of the video frame, so hide the plain viewer.
        previewViewer.classList.add('hidden');
        setupCustomAudioPlayer(presignedUrl, item.name);
      } 
      else if (category === 'code') {
        if (ext === 'pdf') {
          destroyPdfViewer(pdfViewerDrawer); pdfViewerDrawer = null;
          pdfViewerDrawer = createPdfViewer('previewViewer', presignedUrl, 'drawer');
        } else {
          try {
            const res = await fetch(presignedUrl);
            const textContent = await res.text();
            cachedCodeKey = item.key; cachedCodeText = textContent; cachedCodeExt = ext;

            // Dispose of any previous drawer editor
            if (codeEditor) { destroyAceEditor(codeEditor); codeEditor = null; }

            previewViewer.innerHTML = `
              <div class="w-full rounded-xl overflow-hidden border border-white/10 bg-[#101318] flex flex-col" style="height:360px;">
                <div class="p-2 border-b border-white/10 bg-white/[0.04] flex justify-between items-center text-xs shrink-0">
                  <span class="text-slate-400 font-mono flex items-center gap-2">
                    <i class="fa-solid fa-code text-amber-400"></i>
                    <span id="codeLangLabel">${ACE_LABELS[ext] || 'Text'}</span>
                  </span>
                  <span class="flex items-center gap-2">
                    <button id="saveCodeBtn" disabled class="px-3 py-1.5 rounded-full bg-brand-500/15 text-brand-300 border border-brand-400/30 text-[10px] font-bold hover:bg-brand-500 hover:text-slate-900 dark:hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                      <i class="fa-solid fa-floppy-disk"></i> Save
                    </button>
                    ${ext === 'html' ? `<button id="toggleHtmlRender" class="px-2.5 py-1 rounded-full bg-brand-500/15 text-brand-300 text-[10px] font-bold border border-brand-400/30 hover:bg-brand-500 hover:text-slate-900 dark:hover:text-white transition-colors">Render View</button>` : ''}
                  </span>
                </div>
                <div id="codeEditorContainer" class="relative flex-1 min-h-0 w-full bg-[#101318]"></div>
                <iframe sandbox="" id="htmlRenderIframe" class="hidden flex-1 min-h-0 w-full border-none bg-white"></iframe>
              </div>
            `;

            codeFallbackBox = null;
            if (window.ace) {
              codeEditor = createAceEditor('codeEditorContainer', textContent, ext, 'saveCodeBtn');
            } else {
              const box = document.createElement('pre');
              box.className = 'flex-1 min-h-0 overflow-auto p-3 text-xs text-slate-200 font-mono leading-relaxed select-text whitespace-pre';
              box.contentEditable = 'true'; box.spellcheck = false;
              box.textContent = textContent;
              document.getElementById('codeEditorContainer').appendChild(box);
              codeFallbackBox = box;
              box.addEventListener('input', () => { codeEditorDirty = true; updateSaveButtonState('saveCodeBtn', true); });
            }
            codeEditorDirty = false;
            updateSaveButtonState('saveCodeBtn', false);
            document.getElementById('saveCodeBtn').onclick = () => saveCodeToS3(codeEditor, 'saveCodeBtn');

            if (ext === 'html') {
              let isRendered = false;
              document.getElementById('toggleHtmlRender').addEventListener('click', () => {
                isRendered = !isRendered;
                const editorBox = document.getElementById('codeEditorContainer');
                const iframe = document.getElementById('htmlRenderIframe');
                if (isRendered) {
                  editorBox.classList.add('hidden');
                  iframe.classList.remove('hidden');
                  iframe.srcdoc = codeEditor ? codeEditor.getValue() : textContent;
                } else {
                  iframe.classList.add('hidden');
                  editorBox.classList.remove('hidden');
                  if (codeEditor) codeEditor.resize();
                }
              });
            }

          } catch(e) {
            previewViewer.innerHTML = `<div class="p-6 text-xs text-rose-400 text-center"><i class="fa-solid fa-circle-exclamation text-lg mb-2"></i><br>Unable to load raw text file content.</div>`;
          }
        }
      } 
      else {
        // Fallback file card
        previewViewer.innerHTML = `
          <div class="p-8 text-center space-y-3">
            <div class="w-16 h-16 rounded-2xl bg-white/60 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 text-brand-300 flex items-center justify-center text-2xl mx-auto">
              <i class="fa-solid fa-file"></i>
            </div>
            <p class="text-xs text-slate-500 dark:text-slate-400">Binary or unrecognized file format.</p>
            <a href="${presignedUrl}" target="_blank" download class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-500 hover:bg-brand-400 text-white text-xs font-extrabold shadow-lg shadow-brand-500/30 transition-all">
              <i class="fa-solid fa-download"></i> Download File
            </a>
          </div>`;
      }
    }

    // Helper functions for escaping HTML strings
    function escapeHtml(str) {
      return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }
    function escapeAttr(str) {
      return escapeHtml(String(str)).replace(/'/g, "&#39;");
    }

    // =====================================================================
    // ACE CODE EDITOR (syntax-highlighted file previews)
    // =====================================================================
    if (window.ace) {
      ace.config.set('basePath', 'assets/vendor');
    }

    const aceColorMode = window.matchMedia('(prefers-color-scheme: dark)');
    const currentAceTheme = () => aceColorMode.matches ? 'ace/theme/monokai' : 'ace/theme/tomorrow';
    const syncPreviewSchemeClass = () => {
      const card = document.getElementById('expandedModalCard');
      if (card) {
        card.classList.toggle('preview-dark', aceColorMode.matches);
        card.classList.toggle('preview-light', !aceColorMode.matches);
      }
    };
    syncPreviewSchemeClass();
    if (aceColorMode.addEventListener) aceColorMode.addEventListener('change', syncPreviewSchemeClass);
    else if (aceColorMode.addListener) aceColorMode.addListener(syncPreviewSchemeClass);
    const ACE_MODES = { html:'html', htm:'html', js:'javascript', mjs:'javascript', jsx:'jsx', json:'json', css:'css', scss:'scss', sass:'sass', less:'less', txt:'text', md:'markdown', markdown:'markdown', py:'python', cpp:'c_cpp', cc:'c_cpp', cxx:'c_cpp', c:'c_cpp', h:'c_cpp', hpp:'c_cpp', java:'java', ts:'typescript', tsx:'typescript', xml:'xml', yml:'yaml', yaml:'yaml', sh:'sh', bash:'sh', zsh:'sh', sql:'sql', php:'php', rb:'ruby', go:'golang', rs:'rust', ini:'ini', cfg:'ini', conf:'ini', toml:'ini', env:'text', properties:'text', log:'text', csv:'text', vue:'html', svelte:'html', dockerfile:'dockerfile', gitignore:'text', makefile:'makefile' };
    const ACE_LABELS = { html:'HTML', htm:'HTML', js:'JavaScript', mjs:'JavaScript', jsx:'JSX', json:'JSON', css:'CSS', scss:'SCSS', sass:'Sass', less:'Less', txt:'Plain Text', md:'Markdown', markdown:'Markdown', py:'Python', cpp:'C++', cc:'C++', cxx:'C++', c:'C', h:'C Header', hpp:'C++ Header', java:'Java', ts:'TypeScript', tsx:'TypeScript', xml:'XML', yml:'YAML', yaml:'YAML', sh:'Shell', bash:'Shell', zsh:'Shell', sql:'SQL', php:'PHP', rb:'Ruby', go:'Go', rs:'Rust', ini:'INI', cfg:'INI', conf:'INI', toml:'TOML', env:'Env', properties:'Properties', log:'Log', csv:'CSV', vue:'Vue', svelte:'Svelte', dockerfile:'Dockerfile', gitignore:'GitIgnore', makefile:'Makefile' };

    let codeEditor = null;           // Ace instance inside the drawer
    let expandedCodeEditor = null;   // Ace instance inside the expanded modal
    let codeEditorDirty = false, expandedCodeEditorDirty = false;
    let codeFallbackBox = null, expandedCodeFallbackBox = null;
    let cachedCodeKey = null, cachedCodeText = '', cachedCodeExt = '';
    let expandedVideoElement = null, expandedVideoOrigClass = null;
    let expandedAudioMoved = false, expandedAudioOrigClass = null;

    function createAceEditor(containerId, text, ext, saveBtnId) {
      if (!window.ace) return null;
      const mode = ACE_MODES[ext] || 'text';
      const editor = ace.edit(containerId, {
        mode: 'ace/mode/' + mode,
        theme: currentAceTheme(),
        fontSize: 12.5,
        fontFamily: "'JetBrains Mono', Menlo, Monaco, Consolas, monospace",
        showPrintMargin: false,   // no vertical line running down the middle
        showGutter: true,
        wrap: false,
        readOnly: !cloudCanWrite(selectedItem?.key || ''), // permission-aware; Save persists them back to S3
        highlightActiveLine: true,
        useWorker: false,
        tabSize: 2
      });
      editor._baseline = text; // last-known saved content, used for dirty tracking
      editor.setValue(text, -1);
      editor.clearSelection();
      editor.renderer.setScrollMargin(0, 0, 0, 0);

      // Dirty tracking: the Save button lights up only when content differs from S3
      editor.on('change', () => {
        const dirty = editor.getValue() !== editor._baseline;
        if (saveBtnId === 'saveCodeBtn') codeEditorDirty = dirty;
        else if (saveBtnId === 'expandedSaveCodeBtn') expandedCodeEditorDirty = dirty;
        updateSaveButtonState(saveBtnId, dirty);
      });

      // Ctrl/Cmd + S saves the file
      editor.commands.addCommand({
        name: 'saveFile',
        bindKey: { win: 'Ctrl-S', mac: 'Cmd-S' },
        exec: () => saveCodeToS3(editor, saveBtnId)
      });

      return editor;
    }

    const syncAceColorMode = () => {
      [codeEditor, expandedCodeEditor].forEach(editor => {
        if (editor && editor.setTheme) {
          editor.setTheme(currentAceTheme());
          requestAnimationFrame(() => editor.resize(true));
        }
      });
    };
    if (aceColorMode.addEventListener) aceColorMode.addEventListener('change', syncAceColorMode);
    else if (aceColorMode.addListener) aceColorMode.addListener(syncAceColorMode);

    function destroyAceEditor(editor) {
      if (editor && editor.destroy) { try { editor.destroy(); } catch(e) {} }
    }

    function updateSaveButtonState(btnId, dirty) {
      const btn = document.getElementById(btnId);
      if (!btn) return;
      btn.disabled = !dirty || (selectedItem && !cloudCanWrite(selectedItem.key));
      btn.classList.toggle('opacity-40', !dirty);
      btn.classList.toggle('cursor-not-allowed', !dirty);
    }

    // Persist the editor contents back to S3 (overwrites the object in the bucket)
    async function saveCodeToS3(editor, btnId) {
      if (!selectedItem) return;
      const isDrawer = btnId === 'saveCodeBtn';
      const box = isDrawer ? codeFallbackBox : expandedCodeFallbackBox;
      if (!editor && !box) return;

      const btn = document.getElementById(btnId);
      if (!btn) return;
      const originalLabel = btn.innerHTML;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
      btn.disabled = true;

      try {
        const content = editor ? editor.getValue() : box.textContent;
        const file = new File([content], selectedItem.name, { type: 'text/plain;charset=utf-8' });
        const { error } = await s3Upload(selectedItem.key, file);

        if (error) {
          showToast('Save failed: ' + error.message, 'error');
        } else {
          // Update the shared cache and this editor's baseline
          cachedCodeKey = selectedItem.key;
          cachedCodeText = content;
          cachedCodeExt = selectedItem.name.split('.').pop().toLowerCase();
          if (editor) editor._baseline = content;
          if (isDrawer) { codeEditorDirty = false; } else { expandedCodeEditorDirty = false; }
          updateSaveButtonState(btnId, false);

          // Keep the sibling editor in sync if it's showing the same file
          if (isDrawer && expandedCodeEditor) {
            const pos = expandedCodeEditor.getCursorPosition();
            expandedCodeEditor._baseline = content;
            expandedCodeEditor.setValue(content, -1);
            expandedCodeEditor.moveCursorToPosition(pos);
            expandedCodeEditorDirty = false;
            updateSaveButtonState('expandedSaveCodeBtn', false);
          } else if (!isDrawer && codeEditor) {
            const pos = codeEditor.getCursorPosition();
            codeEditor._baseline = content;
            codeEditor.setValue(content, -1);
            codeEditor.moveCursorToPosition(pos);
            codeEditorDirty = false;
            updateSaveButtonState('saveCodeBtn', false);
          }

          const sizeElem = document.getElementById('metaFileSize');
          if (sizeElem) sizeElem.textContent = formatBytes(new Blob([content]).size);
          showToast(`Saved ${escapeHtml(selectedItem.name)} to Robo Cloud`);
          loadDirectory(); // refresh sizes/stats without closing the preview
        }
      } catch(e) {
        showToast('Save failed: ' + e.message, 'error');
      }

      btn.innerHTML = originalLabel;
      btn.disabled = isDrawer ? !codeEditorDirty : !expandedCodeEditorDirty;
      updateSaveButtonState(btnId, isDrawer ? codeEditorDirty : expandedCodeEditorDirty);
    }

    // =====================================================================
    // CUSTOM PDF VIEWER (PDF.js — drawer = single page, modal = scrollable + glass thumbnails)
    // =====================================================================
    let pdfViewerDrawer = null;
    let pdfViewerExpanded = null;

    function destroyPdfViewer(handle) {
      if (!handle) return;
      try { if (handle.renderTask) handle.renderTask.cancel(); } catch(e) {}
      try { if (handle.renderTasks) handle.renderTasks.forEach(t=>{ try{t.cancel();}catch(e){} }); } catch(e) {}
      try { if (handle.thumbTasks) handle.thumbTasks.forEach(t=>{ try{t.cancel();}catch(e){} }); } catch(e) {}
      try { if (handle.observer) handle.observer.disconnect(); } catch(e) {}
      try { if (handle.doc) handle.doc.destroy(); } catch(e) {}
      try { if (handle.resizeHandler) window.removeEventListener('resize', handle.resizeHandler); } catch(e) {}
    }

    // --- Drawer viewer: SCROLLABLE (no 1/5 pagination) — just scroll ---
    function createPdfViewer(containerId, url, mode) {
      const container = document.getElementById(containerId);
      const id = (s) => containerId + '_' + s;

      container.innerHTML = `
        <div class="rounded-2xl overflow-hidden border border-slate-200 dark:border-white/10 bg-white/70 dark:bg-black/30 flex flex-col w-full" style="height:420px;">
          <div class="p-2 border-b border-slate-200 dark:border-white/10 bg-white/60 dark:bg-white/[0.04] backdrop-blur-xl flex justify-between items-center text-xs shrink-0">
            <span class="text-slate-500 dark:text-slate-400 font-mono flex items-center gap-2">
              <i class="fa-solid fa-file-pdf text-rose-400"></i>
              <span class="font-bold tracking-wide">PDF</span>
              <span id="${id('drawerCount')}" class="px-2 py-0.5 rounded-full bg-slate-900/5 dark:bg-white/10 border border-slate-200 dark:border-white/10 text-[10px] font-bold text-slate-600 dark:text-slate-300">– pages</span>
            </span>
            <span class="flex items-center gap-1">
              <button id="${id('drawerZoomOut')}" class="w-6 h-6 rounded-full hover:bg-slate-900/5 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 transition-colors" title="Zoom out"><i class="fa-solid fa-magnifying-glass-minus text-[9px]"></i></button>
              <button id="${id('drawerZoomIn')}" class="w-6 h-6 rounded-full hover:bg-slate-900/5 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 transition-colors" title="Zoom in"><i class="fa-solid fa-magnifying-glass-plus text-[9px]"></i></button>
              <button id="${id('drawerFit')}" class="px-2 h-6 rounded-full hover:bg-slate-900/5 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 transition-colors" title="Fit to width">Fit</button>
              <a id="${id('drawerDownload')}" href="${url}" download title="Download PDF" class="w-6 h-6 rounded-full hover:bg-slate-900/5 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 flex items-center justify-center transition-colors"><i class="fa-solid fa-download text-[10px]"></i></a>
            </span>
          </div>
          <div id="${id('drawerWrap')}" class="pdf-scroll flex-1 min-h-0 overflow-y-auto bg-[#f8fafc] dark:bg-black/20 p-3 relative scroll-smooth">
            <div id="${id('drawerLoading')}" class="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-white/70 dark:bg-black/30 backdrop-blur-sm">
              <i class="fa-solid fa-circle-notch fa-spin text-2xl text-brand-400"></i>
              <span class="text-xs text-slate-500 dark:text-slate-400">Loading PDF…</span>
            </div>
            <div id="${id('drawerPages')}" class="hidden flex flex-col items-center gap-4 max-w-full mx-auto"></div>
            <div id="${id('drawerError')}" class="hidden flex-col items-center justify-center gap-3 py-10 text-center">
              <i class="fa-solid fa-circle-exclamation text-2xl text-rose-400"></i>
              <p class="text-xs text-slate-500 dark:text-slate-400">Unable to render this PDF.</p>
              <a href="${url}" target="_blank" class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-500 hover:bg-brand-400 text-white text-xs font-extrabold shadow-lg shadow-brand-500/30 transition-all"><i class="fa-solid fa-download"></i> Open / Download</a>
            </div>
          </div>
        </div>`;

      const handle = {
        containerId, url,
        doc: null, totalPages: 0, scale: 1, fitWidth: true, dpr: window.devicePixelRatio || 1,
        wrap: document.getElementById(id('drawerWrap')),
        pagesWrap: document.getElementById(id('drawerPages')),
        loading: document.getElementById(id('drawerLoading')),
        errorEl: document.getElementById(id('drawerError')),
        countBadge: document.getElementById(id('drawerCount')),
        renderTasks: [], pageEls: []
      };

      (async () => {
        if (!window.pdfjsLib) {
          handle.loading.innerHTML = '<p class="text-[11px] text-rose-400 text-center">PDF.js blocked</p>';
          handle.errorEl.classList.remove('hidden'); handle.errorEl.classList.add('flex');
          return;
        }
        try {
          const task = pdfjsLib.getDocument({ url, isEvalSupported: false });
          handle.doc = await task.promise;
          handle.totalPages = handle.doc.numPages;
          handle.countBadge.textContent = handle.totalPages + ' pages';
          handle.loading.classList.add('hidden');
          handle.pagesWrap.classList.remove('hidden');
          // build placeholders for all pages
          handle.pagesWrap.innerHTML = '';
          handle.pageEls = [];
          for (let i = 1; i <= handle.totalPages; i++) {
            const wrap = document.createElement('div');
            wrap.id = id('drawerPage-' + i);
            wrap.className = 'w-full flex flex-col items-center gap-1.5';
            wrap.innerHTML = `
              <canvas id="${id('drawerCanvas-' + i)}" class="block bg-white rounded-xl shadow-xl shadow-black/10 border border-slate-200/50 dark:border-white/10 max-w-full h-auto" style="display:block;"></canvas>
              <span class="text-[10px] font-mono font-bold tracking-widest uppercase px-2 py-0.5 rounded-full bg-white/70 dark:bg-white/10 border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 shadow-sm">${i} / ${handle.totalPages}</span>
            `;
            handle.pagesWrap.appendChild(wrap);
            handle.pageEls.push(wrap);
          }
          await renderAllDrawerPdfPages(handle);
          wireDrawerPdfControls(handle);
          handle.resizeHandler = () => { if (handle.fitWidth) renderAllDrawerPdfPages(handle); };
          window.addEventListener('resize', handle.resizeHandler);
        } catch(e) {
          console.error('drawer pdf error', e);
          handle.loading.classList.add('hidden');
          handle.errorEl.classList.remove('hidden'); handle.errorEl.classList.add('flex');
        }
      })();

      return handle;
    }

    async function renderAllDrawerPdfPages(handle) {
      if (!handle.doc) return;
      const dpr = handle.dpr;
      handle.renderTasks.forEach(t=>{ try{t.cancel();}catch(e){} });
      handle.renderTasks = [];
      const available = Math.max((handle.wrap.clientWidth || 320) - 24, 200);
      for (let i = 1; i <= handle.totalPages; i++) {
        try {
          const page = await handle.doc.getPage(i);
          const base = page.getViewport({ scale: 1 });
          let pageScale = handle.fitWidth ? (available / base.width) : handle.scale;
          if (handle.fitWidth) pageScale = Math.max(0.35, Math.min(pageScale, 2.2));
          else pageScale = Math.max(0.25, Math.min(pageScale, 3.2));
          const viewport = page.getViewport({ scale: pageScale });
          if (handle.fitWidth) handle.scale = pageScale; // keep for zoom reference (first page width)
          const canvas = document.getElementById(handle.containerId + '_drawerCanvas-' + i);
          if (!canvas) continue;
          canvas.width = Math.max(1, Math.floor(viewport.width * dpr));
          canvas.height = Math.max(1, Math.floor(viewport.height * dpr));
          canvas.style.width = Math.floor(viewport.width) + 'px';
          canvas.style.height = Math.floor(viewport.height) + 'px';
          const ctx = canvas.getContext('2d');
          const task = page.render({ canvasContext: ctx, viewport, transform: dpr !== 1 ? [dpr,0,0,dpr,0,0] : undefined });
          handle.renderTasks.push(task);
          await task.promise;
        } catch(e) { /* ignore single page */ }
      }
    }

    function wireDrawerPdfControls(handle) {
      const id = (s) => handle.containerId + '_' + s;
      const zoomOutEl = document.getElementById(id('drawerZoomOut'));
      const zoomInEl = document.getElementById(id('drawerZoomIn'));
      const fitEl = document.getElementById(id('drawerFit'));
      if (zoomOutEl) zoomOutEl.onclick = async () => { handle.fitWidth = false; handle.scale = Math.max(0.35, handle.scale / 1.18); await renderAllDrawerPdfPages(handle); };
      if (zoomInEl) zoomInEl.onclick = async () => { handle.fitWidth = false; handle.scale = Math.min(3.2, handle.scale * 1.18); await renderAllDrawerPdfPages(handle); };
      if (fitEl) fitEl.onclick = async () => { handle.fitWidth = true; await renderAllDrawerPdfPages(handle); };
    }

    // legacy single-page helpers kept for compatibility (unused by drawer now)
    async function renderPdfPage(handle) {
      try {
        const page = await handle.doc.getPage(handle.pageNum || 1);
        const base = page.getViewport({ scale: 1 });
        if (handle.fitWidth) {
          const w = Math.max((handle.wrap.clientWidth || 600) - 32, 200);
          handle.scale = w / base.width;
        }
        const viewport = page.getViewport({ scale: handle.scale });
        const dpr = handle.dpr;
        if (!handle.canvas) return;
        handle.canvas.width = Math.max(1, Math.floor(viewport.width * dpr));
        handle.canvas.height = Math.max(1, Math.floor(viewport.height * dpr));
        handle.canvas.style.width = Math.floor(viewport.width) + 'px';
        handle.canvas.style.height = Math.floor(viewport.height) + 'px';
        if (handle.renderTask) { try { handle.renderTask.cancel(); } catch(e) {} }
        const ctx = handle.canvas.getContext('2d');
        handle.renderTask = page.render({ canvasContext: ctx, viewport, transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined });
        await handle.renderTask.promise;
        if (handle.pageInfo) handle.pageInfo.textContent = (handle.pageNum||1) + ' / ' + handle.totalPages;
      } catch(e) {}
    }
    function wirePdfControls(handle) {
      const id = (s) => handle.containerId + '_' + s;
      const prev = document.getElementById(id('pdfPrev')); if (prev) prev.onclick = () => { if (handle.pageNum > 1) { handle.pageNum--; renderPdfPage(handle); } };
      const next = document.getElementById(id('pdfNext')); if (next) next.onclick = () => { if (handle.pageNum < handle.totalPages) { handle.pageNum++; renderPdfPage(handle); } };
      const zo = document.getElementById(id('pdfZoomOut')); if (zo) zo.onclick = () => { handle.fitWidth = false; handle.scale = Math.max(0.25, handle.scale / 1.25); renderPdfPage(handle); };
      const zi = document.getElementById(id('pdfZoomIn')); if (zi) zi.onclick = () => { handle.fitWidth = false; handle.scale = Math.min(8, handle.scale * 1.25); renderPdfPage(handle); };
      const fit = document.getElementById(id('pdfFit')); if (fit) fit.onclick = () => { handle.fitWidth = true; renderPdfPage(handle); };
    }

    // --- Expanded modal viewer: scrollable + glass thumbnail sidebar ---
    async function renderNativeExpandedPdf(url) {
      const container = expandedPreviewContent;
      let ratio = 0.7727; // US Letter fallback
      try {
        if (window.pdfjsLib) {
          const doc = await pdfjsLib.getDocument({ url, isEvalSupported: false }).promise;
          const first = await doc.getPage(1);
          const vp = first.getViewport({ scale: 1 });
          if (vp.width && vp.height) ratio = vp.width / vp.height;
          try { await doc.destroy(); } catch (_) {}
        }
      } catch (_) { /* native viewer still works if dimension probing fails */ }
      container.style.setProperty('--pdf-page-ratio', String(ratio));
      container.innerHTML = `
        <iframe class="native-pdf-frame" src="${url}#view=FitH&toolbar=1&navpanes=0"
          title="${selectedItem ? escapeAttr(selectedItem.name) : 'PDF document'}"
          allow="clipboard-read; clipboard-write" loading="eager"></iframe>`;
    }

    function createExpandedPdfViewer(containerId, url) {
      const container = document.getElementById(containerId);
      const id = (s) => containerId + '_' + s;

      container.innerHTML = `
        <div class="w-full h-full flex flex-col rounded-2xl overflow-hidden border border-slate-200 dark:border-white/10 bg-white/70 dark:bg-black/30">
          <!-- Header -->
          <div class="p-2.5 border-b border-slate-200 dark:border-white/10 bg-white/60 dark:bg-white/[0.04] backdrop-blur-xl flex justify-between items-center text-xs shrink-0">
            <span class="text-slate-500 dark:text-slate-400 font-mono flex items-center gap-2">
              <i class="fa-solid fa-file-pdf text-rose-400"></i>
              <span class="hidden sm:inline font-bold tracking-wide">PDF</span>
              <span id="${id('expPageInfo')}" class="ml-1 px-2.5 py-1 rounded-full bg-slate-900/5 dark:bg-white/10 border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-200 font-bold">– / –</span>
            </span>
            <span class="flex items-center gap-1">
              <button id="${id('expPrev')}" class="w-7 h-7 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 hover:bg-white dark:hover:bg-white/15 text-slate-600 dark:text-slate-300 transition-colors shadow-sm" title="Previous page"><i class="fa-solid fa-chevron-up text-[10px]"></i></button>
              <button id="${id('expNext')}" class="w-7 h-7 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 hover:bg-white dark:hover:bg-white/15 text-slate-600 dark:text-slate-300 transition-colors shadow-sm" title="Next page"><i class="fa-solid fa-chevron-down text-[10px]"></i></button>
              <span class="w-px h-6 bg-slate-200 dark:bg-white/10 mx-1 hidden sm:block"></span>
              <button id="${id('expZoomOut')}" class="w-7 h-7 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 hover:bg-white dark:hover:bg-white/15 text-slate-600 dark:text-slate-300 transition-colors shadow-sm" title="Zoom out"><i class="fa-solid fa-magnifying-glass-minus text-[10px]"></i></button>
              <button id="${id('expZoomIn')}" class="w-7 h-7 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 hover:bg-white dark:hover:bg-white/15 text-slate-600 dark:text-slate-300 transition-colors shadow-sm" title="Zoom in"><i class="fa-solid fa-magnifying-glass-plus text-[10px]"></i></button>
              <button id="${id('expFit')}" class="hidden sm:inline-flex px-3 h-7 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 hover:bg-white dark:hover:bg-white/15 text-slate-600 dark:text-slate-300 transition-colors shadow-sm items-center gap-1 font-bold" title="Fit to width"><i class="fa-solid fa-arrows-left-right text-[9px]"></i> Fit</button>
              <a id="${id('expDownload')}" href="${url}" download title="Download PDF" class="w-7 h-7 rounded-full bg-brand-500 hover:bg-brand-400 text-white flex items-center justify-center transition-colors shadow-md shadow-brand-500/30"><i class="fa-solid fa-download text-[10px]"></i></a>
            </span>
          </div>
          <!-- Body: sidebar + scrollable pages -->
          <div class="flex flex-1 min-h-0 overflow-hidden">
            <!-- Glass thumbnail sidebar -->
            <aside id="${id('thumbSidebar')}" class="w-[112px] sm:w-[140px] shrink-0 border-r border-slate-200 dark:border-white/10 bg-white/55 dark:bg-white/[0.06] backdrop-blur-xl flex flex-col overflow-hidden">
              <div class="px-2 py-2.5 border-b border-slate-200/60 dark:border-white/5 flex items-center justify-center gap-1.5 shrink-0">
                <i class="fa-solid fa-images text-[10px] text-slate-500 dark:text-slate-400"></i>
                <span class="text-[10px] font-bold tracking-widest uppercase text-slate-600 dark:text-slate-400">Pages</span>
                <span id="${id('thumbCount')}" class="ml-1 text-[10px] font-mono bg-slate-900/5 dark:bg-white/10 px-1.5 py-0.5 rounded-full border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-300">–</span>
              </div>
              <div id="${id('thumbList')}" class="pdf-scroll flex-1 overflow-y-auto p-2 flex flex-col gap-3 content-start">
                <div id="${id('thumbLoading')}" class="flex flex-col items-center justify-center gap-2 py-8">
                  <i class="fa-solid fa-circle-notch fa-spin text-lg text-brand-400"></i>
                  <span class="text-[11px] text-slate-500 dark:text-slate-400">Loading…</span>
                </div>
              </div>
            </aside>
            <!-- Scrollable pages -->
            <div id="${id('mainScroll')}" class="pdf-scroll flex-1 overflow-y-auto overflow-x-hidden bg-[#f8fafc] dark:bg-black/20 p-3 sm:p-6 scroll-smooth">
              <div id="${id('expLoading')}" class="flex flex-col items-center justify-center gap-3 py-16">
                <i class="fa-solid fa-circle-notch fa-spin text-2xl text-brand-400"></i>
                <span class="text-xs text-slate-500 dark:text-slate-400">Loading PDF…</span>
              </div>
              <div id="${id('pages')}" class="hidden flex flex-col items-center gap-5 sm:gap-6 max-w-4xl mx-auto"></div>
              <div id="${id('expError')}" class="hidden flex-col items-center justify-center gap-3 py-16 text-center">
                <i class="fa-solid fa-circle-exclamation text-2xl text-rose-400"></i>
                <p class="text-xs text-slate-500 dark:text-slate-400">Unable to render this PDF.</p>
                <a href="${url}" target="_blank" class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-500 hover:bg-brand-400 text-white text-xs font-extrabold shadow-lg shadow-brand-500/30 transition-all"><i class="fa-solid fa-download"></i> Open / Download</a>
              </div>
            </div>
          </div>
        </div>`;

      const handle = {
        containerId, url,
        doc: null, totalPages: 0, scale: 1, fitWidth: true, dpr: window.devicePixelRatio || 1,
        mainScroll: document.getElementById(id('mainScroll')),
        pagesWrap: document.getElementById(id('pages')),
        thumbList: document.getElementById(id('thumbList')),
        thumbSidebar: document.getElementById(id('thumbSidebar')),
        thumbLoading: document.getElementById(id('thumbLoading')),
        thumbCount: document.getElementById(id('thumbCount')),
        expLoading: document.getElementById(id('expLoading')),
        expError: document.getElementById(id('expError')),
        pageInfo: document.getElementById(id('expPageInfo')),
        renderTasks: [], thumbTasks: [],
        pageEls: [], thumbBtns: [],
        currentPage: 1,
        observer: null,
        resizeHandler: null
      };

      (async () => {
        if (!window.pdfjsLib) {
          handle.expLoading.classList.add('hidden');
          handle.thumbLoading.innerHTML = '<p class="text-[11px] text-rose-400 text-center">PDF.js blocked</p>';
          handle.expError.classList.remove('hidden'); handle.expError.classList.add('flex');
          return;
        }
        try {
          const task = pdfjsLib.getDocument({ url, isEvalSupported: false });
          handle.doc = await task.promise;
          handle.totalPages = handle.doc.numPages;
          handle.pageInfo.textContent = '1 / ' + handle.totalPages;
          handle.thumbCount.textContent = handle.totalPages;
          handle.expLoading.classList.add('hidden');
          handle.pagesWrap.classList.remove('hidden');
          // build placeholders for all pages
          handle.thumbList.innerHTML = '';
          handle.pagesWrap.innerHTML = '';
          handle.pageEls = [];
          handle.thumbBtns = [];
          for (let i = 1; i <= handle.totalPages; i++) {
            // Main page wrapper
            const pageWrap = document.createElement('div');
            pageWrap.id = id('page-' + i);
            pageWrap.className = 'w-full flex flex-col items-center gap-2 scroll-mt-4';
            pageWrap.innerHTML = `
              <div class="w-full flex justify-center items-start">
                <div id="${id('stage-' + i)}" class="pdf-page-stage relative bg-white rounded-xl shadow-xl shadow-black/10 border border-slate-200/50 dark:border-white/10 overflow-hidden">
                  <canvas id="${id('canvas-' + i)}" class="block bg-white" style="display:block;"></canvas>
                  <div id="${id('text-' + i)}" class="pdf-text-layer absolute inset-0 overflow-hidden" aria-label="Selectable PDF text"></div>
                </div>
              </div>
              <span class="text-[10px] font-mono font-bold tracking-widest uppercase px-2 py-1 rounded-full bg-white/70 dark:bg-white/10 border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 shadow-sm">${i} / ${handle.totalPages}</span>
            `;
            handle.pagesWrap.appendChild(pageWrap);
            handle.pageEls.push(pageWrap);

            // Thumbnail button + shape + number below
            const thumbBtn = document.createElement('button');
            thumbBtn.type = 'button';
            thumbBtn.id = id('thumb-' + i);
            thumbBtn.className = 'group w-full flex flex-col items-center gap-1.5 p-1.5 rounded-xl border border-transparent hover:bg-white/70 dark:hover:bg-white/10 hover:border-slate-200 dark:hover:border-white/10 transition-all';
            thumbBtn.innerHTML = `
              <div id="${id('thumbStage-' + i)}" class="pdf-thumb-stage bg-white rounded-lg overflow-hidden shadow-md border border-slate-200/70 dark:border-white/10 group-hover:shadow-lg transition-shadow inline-flex justify-center items-center">
                <canvas id="${id('thumbCanvas-' + i)}" class="block" style="display:block;"></canvas>
              </div>
              <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-full bg-white/60 dark:bg-white/10 border border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 group-hover:text-slate-900 dark:group-hover:text-white transition-colors">${i}</span>
            `;
            thumbBtn.onclick = () => {
              document.getElementById(id('canvas-' + i)).scrollIntoView({ behavior: 'smooth', block: 'start' });
            };
            handle.thumbList.appendChild(thumbBtn);
            handle.thumbBtns.push(thumbBtn);
          }
          // initial active
          updateExpandedThumbActive(handle, 1);
          // render all pages
          await renderAllExpandedPdfPages(handle);
          // wire controls + scroll observer + resize
          wireExpandedPdfControls(handle);
          setupExpandedScrollObserver(handle);
          handle.resizeHandler = () => { if (handle.fitWidth) renderAllExpandedPdfPages(handle); };
          window.addEventListener('resize', handle.resizeHandler);
        } catch(e) {
          console.error('expanded pdf load error', e);
          handle.expLoading.classList.add('hidden');
          handle.thumbLoading.innerHTML = '<p class="text-[11px] text-rose-400 text-center">Failed to load</p>';
          handle.expError.classList.remove('hidden'); handle.expError.classList.add('flex');
        }
      })();

      return handle;
    }

    async function renderSelectablePdfText(page, viewport, layer) {
      if (!layer || !window.pdfjsLib) return;
      layer.innerHTML = '';
      layer.style.width = Math.floor(viewport.width) + 'px';
      layer.style.height = Math.floor(viewport.height) + 'px';
      try {
        const content = await page.getTextContent();
        const styles = content.styles || {};
        for (const item of content.items || []) {
          if (!item.str) continue;
          const tx = pdfjsLib.Util.transform(viewport.transform, item.transform);
          const angle = Math.atan2(tx[1], tx[0]);
          const fontHeight = Math.hypot(tx[2], tx[3]);
          const span = document.createElement('span');
          span.textContent = item.str;
          span.style.left = tx[4] + 'px';
          span.style.top = (tx[5] - fontHeight) + 'px';
          span.style.fontSize = fontHeight + 'px';
          span.style.fontFamily = (styles[item.fontName] && styles[item.fontName].fontFamily) || 'sans-serif';
          span.style.transform = angle ? `rotate(${angle}rad)` : '';
          layer.appendChild(span);
          if (item.width > 0 && span.getBoundingClientRect().width > 0) {
            const target = item.width * viewport.scale;
            const measured = span.getBoundingClientRect().width;
            span.style.transform += ` scaleX(${target / measured})`;
          }
        }
      } catch (_) { layer.innerHTML = ''; }
    }

    async function renderAllExpandedPdfPages(handle) {
      if (!handle.doc) return;
      const dpr = handle.dpr;
      handle.renderTasks.forEach(t=>{ try{t.cancel();}catch(e){} });
      handle.thumbTasks.forEach(t=>{ try{t.cancel();}catch(e){} });
      handle.renderTasks = []; handle.thumbTasks = [];
      const mainW = handle.mainScroll.clientWidth || 700;
      const mainAvailable = Math.max(mainW - 48, 280);
      // thumb available width: sidebar inner width minus padding (sidebar is 112-140px, list has p-2)
      const thumbAvailable = Math.max((handle.thumbList?.clientWidth || 120) - 12, 84);
      for (let i = 1; i <= handle.totalPages; i++) {
        try {
          // Use separate page instances for main + thumb to avoid render collision and keep shapes exact
          const page = await handle.doc.getPage(i);
          const base = page.getViewport({ scale: 1 });
          // CORRECT SHAPE: per-page scale so every page keeps its own aspect ratio, not first-page ratio
          let pageScale;
          if (handle.fitWidth) {
            pageScale = mainAvailable / base.width;
            pageScale = Math.max(0.35, Math.min(pageScale, 2.4));
            // do not overwrite handle.scale inside loop for fitWidth (would distort later pages with different widths); keep handle.scale as last computed for zoom reference
            if (i === 1) handle.scale = pageScale;
          } else {
            pageScale = Math.max(0.35, Math.min(handle.scale, 3.2));
          }
          const viewport = page.getViewport({ scale: pageScale });
          const canvas = document.getElementById(handle.containerId + '_canvas-' + i);
          if (canvas) {
            canvas.width = Math.max(1, Math.floor(viewport.width * dpr));
            canvas.height = Math.max(1, Math.floor(viewport.height * dpr));
            canvas.style.width = Math.floor(viewport.width) + 'px';
            canvas.style.height = Math.floor(viewport.height) + 'px';
            const stage = document.getElementById(handle.containerId + '_stage-' + i);
            if (stage) { stage.style.width = Math.floor(viewport.width) + 'px'; stage.style.height = Math.floor(viewport.height) + 'px'; }
            const ctx = canvas.getContext('2d');
            const task = page.render({ canvasContext: ctx, viewport, transform: dpr !== 1 ? [dpr,0,0,dpr,0,0] : undefined });
            handle.renderTasks.push(task);
            await task.promise; // await main before thumb to avoid same-page concurrent render race
            await renderSelectablePdfText(page, viewport, document.getElementById(handle.containerId + '_text-' + i));
          }
          // Thumbnail: compute scale from thumbAvailable so shape always fits sidebar without stretch
          const tCanvas = document.getElementById(handle.containerId + '_thumbCanvas-' + i);
          if (tCanvas) {
            const thumbPage = await handle.doc.getPage(i); // fresh page instance for thumb (prevents shape glitches)
            const thumbBase = thumbPage.getViewport({ scale: 1 });
            let thumbScale = thumbAvailable / thumbBase.width;
            thumbScale = Math.max(0.12, Math.min(thumbScale, 0.32)); // keep sharp but not huge
            const tViewport = thumbBase.viewport ? thumbPage.getViewport({ scale: thumbScale }) : thumbPage.getViewport({ scale: thumbScale });
            // above line handles both PDF.js versions
            const tVP = thumbPage.getViewport({ scale: thumbScale });
            tCanvas.width = Math.max(1, Math.floor(tVP.width * dpr));
            tCanvas.height = Math.max(1, Math.floor(tVP.height * dpr));
            tCanvas.style.width = Math.floor(tVP.width) + 'px';
            tCanvas.style.height = Math.floor(tVP.height) + 'px';
            const thumbStage = document.getElementById(handle.containerId + '_thumbStage-' + i);
            if (thumbStage) {
              thumbStage.style.width = Math.floor(tVP.width) + 'px';
              thumbStage.style.height = Math.floor(tVP.height) + 'px';
              thumbStage.style.aspectRatio = tVP.width + ' / ' + tVP.height;
            }
            // ensure thumb canvas container keeps aspect ratio (no CSS stretch)
            tCanvas.style.display = 'block';
            tCanvas.style.objectFit = 'contain';
            const tCtx = tCanvas.getContext('2d');
            const tTask = thumbPage.render({ canvasContext: tCtx, viewport: tVP, transform: dpr !== 1 ? [dpr,0,0,dpr,0,0] : undefined });
            handle.thumbTasks.push(tTask);
            await tTask.promise;
          }
        } catch(e) { /* ignore single page failure */ }
      }
    }

    function updateExpandedThumbActive(handle, pageNum) {
      handle.currentPage = pageNum;
      handle.pageInfo.textContent = pageNum + ' / ' + handle.totalPages;
      handle.thumbBtns.forEach((btn, idx) => {
        const n = idx + 1;
        if (n === pageNum) {
          btn.classList.add('is-active', 'bg-brand-500/10', 'border-brand-400/30', 'shadow-sm');
          btn.classList.remove('border-transparent');
          const badge = btn.querySelector('span:last-child');
          if (badge) { badge.classList.add('bg-brand-500', 'text-white', 'border-brand-400'); badge.classList.remove('bg-white/60','dark:bg-white/10','text-slate-600','dark:text-slate-400'); }
        } else {
          btn.classList.remove('is-active', 'bg-brand-500/10', 'border-brand-400/30', 'shadow-sm');
          btn.classList.add('border-transparent');
          const badge = btn.querySelector('span:last-child');
          if (badge) { badge.classList.remove('bg-brand-500', 'text-white', 'border-brand-400'); badge.classList.add('bg-white/60','dark:bg-white/10'); }
        }
      });
    }

    function setupExpandedScrollObserver(handle) {
      if (!handle.pageEls.length) return;
      const opts = { root: handle.mainScroll, rootMargin: '-45% 0px -45% 0px', threshold: 0 };
      handle.observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const id = entry.target.id || '';
            const m = id.match(/page-(\d+)$/);
            if (m) {
              const n = parseInt(m[1], 10);
              updateExpandedThumbActive(handle, n);
            }
          }
        });
      }, opts);
      handle.pageEls.forEach(el => handle.observer.observe(el));
      // also fallback scroll handler for browsers without observer precision
      let ticking = false;
      handle.mainScroll.addEventListener('scroll', () => {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(() => {
          ticking = false;
          // find closest page to top
          const top = handle.mainScroll.scrollTop;
          let best = 1, bestDist = Infinity;
          handle.pageEls.forEach((el, idx) => {
            const dist = Math.abs(el.offsetTop - top - 16);
            if (dist < bestDist) { bestDist = dist; best = idx + 1; }
          });
          if (best !== handle.currentPage) updateExpandedThumbActive(handle, best);
        });
      }, { passive: true });
    }

    function wireExpandedPdfControls(handle) {
      const id = (s) => handle.containerId + '_' + s;
      const goTo = (n) => {
        const clamped = Math.max(1, Math.min(handle.totalPages, n));
        const target = document.getElementById(id('canvas-' + clamped));
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      };
      document.getElementById(id('expPrev')).onclick = () => goTo(handle.currentPage - 1);
      document.getElementById(id('expNext')).onclick = () => goTo(handle.currentPage + 1);
      document.getElementById(id('expZoomOut')).onclick = async () => {
        handle.fitWidth = false;
        handle.scale = Math.max(0.4, handle.scale / 1.18);
        await renderAllExpandedPdfPages(handle);
      };
      document.getElementById(id('expZoomIn')).onclick = async () => {
        handle.fitWidth = false;
        handle.scale = Math.min(3.2, handle.scale * 1.18);
        await renderAllExpandedPdfPages(handle);
      };
      document.getElementById(id('expFit')).onclick = async () => {
        handle.fitWidth = true;
        await renderAllExpandedPdfPages(handle);
      };
    }


    // =====================================================================
    // EXPANDED PREVIEW (big, centered viewer opened by the expand button)
    // =====================================================================
    const expandedPreviewModal = document.getElementById('expandedPreviewModal');
    const expandedModalCard = document.getElementById('expandedModalCard');
    const expandedPreviewContent = document.getElementById('expandedPreviewContent');
    const expandedPreviewFileName = document.getElementById('expandedPreviewFileName');
    const expandedPreviewMeta = document.getElementById('expandedPreviewMeta');
    const expandedPreviewIcon = document.getElementById('expandedPreviewIcon');
    const expandedExternalLink = document.getElementById('expandedExternalLink');
    const expandedCodeModeBtn = document.getElementById('expandedCodeModeBtn');

    async function openExpandedPreview() {
      if (!selectedItem) return;
      syncPreviewSchemeClass();

      const iconInfo = getFileIcon(selectedItem.name);
      expandedPreviewFileName.textContent = selectedItem.name;
      const previewDate = selectedItem.lastModified ? new Date(selectedItem.lastModified) : null;
      const ageMs = previewDate && !isNaN(previewDate) ? Math.max(0, Date.now() - previewDate.getTime()) : null;
      let ageText = '';
      if (ageMs !== null) {
        const mins = Math.floor(ageMs / 60000);
        if (mins < 1) ageText = 'just now';
        else if (mins < 60) ageText = mins + ' min ago';
        else if (mins < 1440) ageText = Math.floor(mins / 60) + ' hr ago';
        else if (mins < 10080) ageText = Math.floor(mins / 1440) + ' day ago';
        else ageText = previewDate.toLocaleDateString();
      }
      expandedPreviewMeta.textContent = formatBytes(selectedItem.size || 0) + (ageText ? ' · ' + ageText : '');
      expandedPreviewIcon.className = `text-lg ${iconInfo.color} shrink-0`;
      expandedPreviewIcon.innerHTML = `<i class="fa-solid ${iconInfo.icon}"></i>`;
      expandedExternalLink.href = await s3PresignUrl(selectedItem.key);

      const ext = selectedItem.name.split('.').pop().toLowerCase();
      const category = selectedItem.category || getFileCategory(selectedItem.name);
      expandedModalCard.classList.remove('code-edit-mode');
      expandedCodeModeBtn.classList.toggle('hidden', category !== 'code' || ext === 'pdf');
      expandedCodeModeBtn.title = 'Edit code';
      expandedCodeModeBtn.innerHTML = '<i class="fa-solid fa-code text-xs"></i>';

      // Reset previous expanded state
      if (expandedCodeEditor) { destroyAceEditor(expandedCodeEditor); expandedCodeEditor = null; }
      destroyPdfViewer(pdfViewerExpanded); pdfViewerExpanded = null;
      expandedCodeFallbackBox = null; expandedCodeEditorDirty = false;
      if (expandedVideoElement) {
        if (expandedVideoOrigClass) expandedVideoElement.className = expandedVideoOrigClass;
        expandedVideoElement = null; expandedVideoOrigClass = null;
      }
      if (expandedAudioMoved) {
        if (expandedAudioOrigClass) customAudioPlayerUI.className = expandedAudioOrigClass;
        expandedAudioMoved = false; expandedAudioOrigClass = null;
      }
      expandedPreviewContent.innerHTML = '';
      expandedPreviewContent.className = 'flex flex-col items-center justify-center gap-4 p-4 overflow-auto min-h-0';

      // Show the modal first so the content has measurable dimensions
      expandedPreviewModal.classList.remove('hidden');
      expandedModalCard.classList.remove('preview-modal-open');
      void expandedModalCard.offsetWidth; // restart entrance animation
      expandedModalCard.classList.add('preview-modal-open');

      // Let the fullscreen shell receive real dimensions before creating Ace/PDF/media.
      // Without this paint boundary, some browsers initialize the viewer at 0×0 and it
      // only becomes visible after opening the information panel changes the layout.
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

      if (category === 'code') {
        if (ext === 'pdf') {
          expandedPreviewContent.className = 'expanded-pdf-content overflow-hidden p-0';
          pdfViewerExpanded = createExpandedPdfViewer('expandedPreviewContent', expandedExternalLink.href);
        } else {
          let text = (cachedCodeKey === selectedItem.key) ? cachedCodeText : '';
          if (!text) {
            try {
              const r = await fetch(expandedExternalLink.href);
              text = await r.text();
              cachedCodeKey = selectedItem.key; cachedCodeText = text; cachedCodeExt = ext;
            } catch(e) { text = '// Unable to load file content'; }
          }
          renderExpandedCode(text, ext);
        }
      }
      else if (category === 'image') {
        expandedPreviewContent.innerHTML = `
          <div class="drive-image-stage">
            <img src="${expandedExternalLink.href}" alt="${escapeHtml(selectedItem.name)}" title="Click to open full size in a new tab">
          </div>`;
        expandedPreviewContent.querySelector('img').onclick = () => window.open(expandedExternalLink.href, '_blank');
      }
      else if (category === 'video') {
        const drawerVid = document.getElementById('drawerDriveVideo');
        if (drawerVid) { try { drawerVid.pause(); } catch (e) {} }
        // Drive glass viewer — recreate (keep sync with presignedUrl)
        expandedPreviewContent.innerHTML = `
          <div class="drive-video-wrap w-[min(92vw,1024px,152vh)] aspect-video bg-black group/drive relative">
            <video id="expandedDriveVideo" autoplay playsinline class="w-full h-full object-contain bg-black" src="${expandedExternalLink.href}"></video>
            <!-- PiP placeholder: rounded square with a Font Awesome PiP icon while the video is popped out (same treatment as the audio icon square) -->
            <div data-pip-placeholder class="hidden absolute inset-0 flex items-center justify-center pointer-events-none">
              <div class="w-28 h-28 sm:w-36 sm:h-36 rounded-3xl bg-white/[0.07] border border-white/15 backdrop-blur-sm flex items-center justify-center shadow-2xl">
                <i class="fa-solid fa-clone text-purple-400" style="font-size:48px"></i>
              </div>
            </div>
            <div data-drive-menu class="hidden absolute bottom-[76px] right-4 drive-menu pointer-events-auto p-2 w-[276px] flex flex-col gap-1 z-20">
              <div data-menu-main class="flex flex-col gap-1">
                <button data-menu-pip class="video-menu-row"><span><span class="material-icons">picture_in_picture_alt</span> Picture in picture</span></button>
                <button data-menu-cc class="video-menu-row"><span><span class="material-icons">closed_caption</span> Subtitles/CC</span><span class="material-icons menu-check" data-menu-cc-check style="visibility:hidden">check</span></button>
                <button data-menu-quality class="video-menu-row"><span><span class="material-icons">tune</span> Quality</span><span class="menu-value"><span data-menu-quality-val>Auto</span> <span class="material-icons menu-chevron">chevron_right</span></span></button>
                <button data-menu-speed class="video-menu-row"><span><span class="material-icons">speed</span> Playback speed</span><span class="menu-value"><span data-menu-speed-val>1x</span> <span class="material-icons menu-chevron">chevron_right</span></span></button>
                <button class="video-menu-row disabled" disabled><span><span class="material-icons">summarize</span> Transcript</span></button>
              </div>
              <div data-quality-submenu class="hidden video-submenu">
                <button data-menu-back class="video-menu-row submenu-title"><span><span class="material-icons">arrow_back</span> Settings</span></button>
                <div class="video-menu-separator"></div>
                <button data-quality-opt="1080p" class="video-menu-row"><span>1080p</span></button>
                <button data-quality-opt="720p" class="video-menu-row active"><span><span class="material-icons menu-check">check</span>720p</span></button>
                <button data-quality-opt="360p" class="video-menu-row"><span>360p</span></button>
                <button data-quality-opt="Auto" class="video-menu-row"><span>Auto</span></button>
              </div>
              <div data-speed-submenu class="hidden video-submenu">
                <button data-menu-back class="video-menu-row submenu-title"><span><span class="material-icons">arrow_back</span> Playback speed</span></button>
                <div class="video-menu-separator"></div>
                <button data-speed-opt="0.25" class="video-menu-row"><span>0.25</span></button>
                <button data-speed-opt="0.5" class="video-menu-row"><span>0.5</span></button>
                <button data-speed-opt="0.75" class="video-menu-row"><span>0.75</span></button>
                <button data-speed-opt="1" class="video-menu-row active"><span><span class="material-icons menu-check">check</span>1</span></button>
                <button data-speed-opt="1.25" class="video-menu-row"><span>1.25</span></button>
                <button data-speed-opt="1.5" class="video-menu-row"><span>1.5</span></button>
                <button data-speed-opt="1.75" class="video-menu-row"><span>1.75</span></button>
                <button data-speed-opt="2" class="video-menu-row"><span>2</span></button>
              </div>
            </div>
            <div class="absolute left-4 right-4 bottom-[76px] drive-progress" data-drive-progress>
              <div class="drive-progress-fill"></div>
              <div class="drive-progress-thumb"></div>
            </div>
            <div class="absolute left-4 right-4 bottom-4 flex items-center justify-between gap-3 pointer-events-none">
              <div class="flex items-center gap-2 pointer-events-auto">
                <button data-drive-play class="media-play-btn lg hover:scale-[1.02] active:scale-95">
                  <span class="material-icons text-black" style="font-size:24px">play_arrow</span>
                </button>
                <div class="drive-pill-dark flex items-center gap-1.5 px-3 py-2">
                  <button data-drive-back class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Replay 10s"><span class="material-icons" style="font-size:20px">replay_10</span></button>
                  <button data-drive-forward class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Forward 10s"><span class="material-icons" style="font-size:20px">forward_10</span></button>
                  <span class="text-white text-sm font-mono tabular-nums px-3" data-drive-time>0:00 / 0:02</span>
                </div>
              </div>
              <div class="drive-pill-dark flex items-center gap-1 px-2 py-2 pointer-events-auto">
                <button data-drive-mute class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Mute"><span class="material-icons" style="font-size:20px">volume_up</span></button>
                <button data-drive-cc class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent" title="Captions (no captions)"><span class="material-icons" style="font-size:20px">closed_caption</span></button>
                <button data-drive-pip class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Picture-in-Picture"><span class="material-icons" style="font-size:20px">picture_in_picture_alt</span></button>
                <button data-drive-speed class="px-3 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white text-sm font-bold tabular-nums">1x</button>
                <button data-drive-settings class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Settings"><span class="material-icons" style="font-size:20px">settings</span></button>
                <button data-drive-full class="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-white transition-colors" title="Fullscreen"><span class="material-icons" style="font-size:20px">fullscreen</span></button>
              </div>

            </div>
          </div>`;
        setTimeout(() => setupDrivePlayer('expandedDriveVideo'), 30);
        // keep for close logic (no need to move old vid)
        expandedVideoElement = null;
      }
      else if (category === 'audio') {
        // Move the shared Drive-style player into the modal (audio keeps playing).
        // The rounded audio icon square takes the place of the video frame.
        expandedPreviewContent.innerHTML = '';
        expandedAudioMoved = true;
        expandedAudioOrigClass = customAudioPlayerUI.className;
        customAudioPlayerUI.className = (expandedAudioOrigClass || '') + ' w-[min(94vw,1100px)]';
        expandedPreviewContent.appendChild(customAudioPlayerUI);
        requestAnimationFrame(() => fitAudioArtBg());
      }
      else {
        expandedPreviewContent.innerHTML = `
          <div class="p-8 text-center space-y-3">
            <div class="w-16 h-16 rounded-2xl bg-white/60 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 text-brand-300 flex items-center justify-center text-2xl mx-auto">
              <i class="fa-solid fa-file"></i>
            </div>
            <p class="text-xs text-slate-500 dark:text-slate-400">Binary or unrecognized file format.</p>
            <a href="${expandedExternalLink.href}" target="_blank" download class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-brand-500 hover:bg-brand-400 text-white text-xs font-extrabold shadow-lg shadow-brand-500/30 transition-all">
              <i class="fa-solid fa-download"></i> Download File
            </a>
          </div>`;
      }

      const settleExpandedViewer = () => {
        if (expandedCodeEditor) expandedCodeEditor.resize(true);
        if (pdfViewerExpanded && typeof pdfViewerExpanded.resize === 'function') pdfViewerExpanded.resize();
        window.dispatchEvent(new Event('resize'));
      };
      requestAnimationFrame(() => requestAnimationFrame(settleExpandedViewer));
      setTimeout(settleExpandedViewer, 120);
    }

    function renderExpandedCode(text, ext) {
      // Remove transport/BOM padding so line 1 starts directly beneath the language bar.
      text = String(text || '').replace(/^\uFEFF?[\r\n]+/, '');
      expandedPreviewContent.className = 'w-[min(95vw,1100px)] h-[min(88vh,820px)] flex flex-col p-0 overflow-hidden';
      expandedPreviewContent.innerHTML = `
        <div data-expanded-code-toolbar class="p-2 border-b border-white/10 bg-white/[0.04] flex justify-between items-center text-xs shrink-0">
          <span class="text-slate-400 font-mono flex items-center gap-2">
            <i class="fa-solid fa-code text-amber-400"></i>
            <span>${ACE_LABELS[ext] || 'Text'}</span>
          </span>
          <span class="flex items-center gap-2">
            <button id="expandedSaveCodeBtn" disabled class="px-3 py-1.5 rounded-full bg-brand-500/15 text-brand-300 border border-brand-400/30 text-[10px] font-bold hover:bg-brand-500 hover:text-slate-900 dark:hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
              <i class="fa-solid fa-floppy-disk"></i> Save
            </button>
            ${ext === 'html' ? `<button id="expandedToggleHtmlRender" class="px-2.5 py-1 rounded-full bg-brand-500/15 text-brand-300 text-[10px] font-bold border border-brand-400/30 hover:bg-brand-500 hover:text-slate-900 dark:hover:text-white transition-colors">Render View</button>` : ''}
          </span>
        </div>
        <div class="relative flex-1 min-h-0">
          <div id="expandedCodeEditorContainer" class="absolute inset-0 bg-[#101318]"></div>
          <iframe sandbox="" id="expandedHtmlRenderIframe" class="hidden absolute inset-0 w-full h-full border-none bg-white"></iframe>
        </div>
      `;

      expandedCodeFallbackBox = null;
      if (window.ace) {
        expandedCodeEditor = createAceEditor('expandedCodeEditorContainer', text, ext, 'expandedSaveCodeBtn');
        expandedCodeEditor.setReadOnly(true);
        requestAnimationFrame(() => requestAnimationFrame(() => {
          if (expandedCodeEditor) { expandedCodeEditor.resize(true); expandedCodeEditor.renderer.updateFull(); }
        }));
      } else {
        const box = document.createElement('pre');
        box.className = 'absolute inset-0 overflow-auto p-3 text-xs text-slate-200 font-mono leading-relaxed select-text whitespace-pre';
        box.contentEditable = 'true'; box.spellcheck = false;
        box.textContent = text;
        document.getElementById('expandedCodeEditorContainer').appendChild(box);
        expandedCodeFallbackBox = box;
        box.addEventListener('input', () => { expandedCodeEditorDirty = true; updateSaveButtonState('expandedSaveCodeBtn', true); });
      }
      expandedCodeEditorDirty = false;
      updateSaveButtonState('expandedSaveCodeBtn', false);
      document.getElementById('expandedSaveCodeBtn').onclick = () => saveCodeToS3(expandedCodeEditor, 'expandedSaveCodeBtn');

      if (ext === 'html') {
        let isRendered = false;
        document.getElementById('expandedToggleHtmlRender').addEventListener('click', () => {
          isRendered = !isRendered;
          const editorBox = document.getElementById('expandedCodeEditorContainer');
          const iframe = document.getElementById('expandedHtmlRenderIframe');
          if (isRendered) {
            editorBox.classList.add('hidden');
            iframe.classList.remove('hidden');
            iframe.srcdoc = expandedCodeEditor ? expandedCodeEditor.getValue() : text;
          } else {
            iframe.classList.add('hidden');
            editorBox.classList.remove('hidden');
            if (expandedCodeEditor) expandedCodeEditor.resize();
          }
        });
      }
    }

    function closeExpandedPreview() {
      if (expandedCodeEditor) { destroyAceEditor(expandedCodeEditor); expandedCodeEditor = null; }
      destroyPdfViewer(pdfViewerExpanded); pdfViewerExpanded = null;
      expandedCodeFallbackBox = null; expandedCodeEditorDirty = false;
      const expVid = document.getElementById('expandedDriveVideo');
      const drawerVid = document.getElementById('drawerDriveVideo');
      if (expVid && drawerVid) {
        try {
          drawerVid.currentTime = expVid.currentTime;
          drawerVid.pause();
        } catch (e) {}
      }
      if (expVid) { try { expVid.pause(); } catch (e) {} }
      const closingAudio = document.getElementById('globalAudioElement');
      if (closingAudio) { try { closingAudio.pause(); } catch (e) {} }
      if (expandedVideoElement) {
        if (expandedVideoOrigClass) expandedVideoElement.className = expandedVideoOrigClass;
        previewViewer.appendChild(expandedVideoElement);
        expandedVideoElement = null; expandedVideoOrigClass = null;
      }
      if (expandedAudioMoved) {
        if (expandedAudioOrigClass) customAudioPlayerUI.className = expandedAudioOrigClass;
        previewViewer.insertAdjacentElement('afterend', customAudioPlayerUI);
        expandedAudioMoved = false; expandedAudioOrigClass = null;
      }
      expandedPreviewContent.className = 'flex flex-col items-center justify-center gap-4 p-4 overflow-auto min-h-0';
      expandedPreviewContent.innerHTML = '';
      expandedPreviewModal.classList.add('hidden');
    }

    // Expand / collapse wiring: button, modal close button, backdrop click, Escape key
    document.getElementById('expandPreviewBtn').onclick = () => openExpandedPreview();
    document.getElementById('expandedInfoBtn').onclick = async () => {
      if (!selectedItem) return;
      // Rendering the details drawer must never restart the active media.
      const expVideo = document.getElementById('expandedDriveVideo');
      const audio = document.getElementById('globalAudioElement');
      const videoState = expVideo ? { time: expVideo.currentTime || 0, paused: expVideo.paused } : null;
      const audioState = audio ? { time: audio.currentTime || 0, paused: audio.paused } : null;
      await openFilePreview(selectedItem, true);
      previewDrawer.classList.add('preview-info-over-modal');
      previewDrawer.classList.remove('translate-x-full');
      requestAnimationFrame(() => {
        if (videoState && expVideo) {
          try { expVideo.currentTime = videoState.time; if (!videoState.paused) expVideo.play().catch(() => {}); } catch (_) {}
        }
        if (audioState && audio) {
          const restoreAudio = () => {
            try { audio.currentTime = audioState.time; if (!audioState.paused) audio.play().catch(() => {}); } catch (_) {}
          };
          restoreAudio();
          if (audio.readyState < 1) audio.addEventListener('loadedmetadata', restoreAudio, { once: true });
        }
      });
    };

    expandedCodeModeBtn.onclick = () => {
      if (!expandedCodeEditor || !cloudCanWrite(selectedItem.key)) return;
      const editing = expandedModalCard.classList.toggle('code-edit-mode');
      expandedCodeEditor.setReadOnly(!editing);
      expandedCodeModeBtn.title = editing ? 'Preview code' : 'Edit code';
      expandedCodeModeBtn.innerHTML = editing
        ? '<i class="fa-solid fa-eye text-xs"></i>'
        : '<i class="fa-solid fa-code text-xs"></i>';
      requestAnimationFrame(() => expandedCodeEditor && expandedCodeEditor.resize(true));
    };

    function requestCloseExpandedPreview() {
      if (expandedCodeEditor && expandedCodeEditorDirty) {
        if (!confirm('You have unsaved changes in the code editor. Discard them?')) return;
      }
      closeExpandedPreview();
    }
    document.getElementById('closeExpandedPreviewBtn').onclick = () => requestCloseExpandedPreview();
    expandedPreviewModal.addEventListener('click', (e) => { if (e.target === expandedPreviewModal) requestCloseExpandedPreview(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !expandedPreviewModal.classList.contains('hidden')) requestCloseExpandedPreview(); });

    function setDriveProgress(fill, thumb, track, ratio) {
      const p = Math.max(0, Math.min(1, ratio || 0));
      if (fill) fill.style.transform = 'scaleX(' + p + ')';
      if (thumb && track) {
        const w = track.getBoundingClientRect().width;
        thumb.style.transform = 'translate(' + (p * w) + 'px, -50%) translate(-50%, 0)';
      }
    }

    let localFfmpegPromise = null;
    async function getLocalFfmpeg() {
      if (localFfmpegPromise) return localFfmpegPromise;
      localFfmpegPromise = (async () => {
        const [{ FFmpeg }, { fetchFile, toBlobURL }] = await Promise.all([
          import('https://unpkg.com/@ffmpeg/ffmpeg@0.12.10/dist/esm/index.js'),
          import('https://unpkg.com/@ffmpeg/util@0.12.1/dist/esm/index.js')
        ]);
        const ffmpeg = new FFmpeg();
        const base = 'https://unpkg.com/@ffmpeg/core@0.12.6/dist/esm';
        // A file:// document has origin "null", so FFmpeg's default CDN Worker URL
        // is blocked. Build a same-origin Blob worker and inline its two tiny imports.
        const workerSourceUrl = 'https://unpkg.com/@ffmpeg/ffmpeg@0.12.10/dist/esm/worker.js';
        let workerSource = await (await fetch(workerSourceUrl)).text();
        workerSource = workerSource.replace(/import\s*\{[^;]+\}\s*from\s*["']\.\/const\.js["'];?/, `const CORE_URL='https://unpkg.com/@ffmpeg/core@0.12.6/dist/umd/ffmpeg-core.js'; const FFMessageType={LOAD:'LOAD',EXEC:'EXEC',WRITE_FILE:'WRITE_FILE',READ_FILE:'READ_FILE',DELETE_FILE:'DELETE_FILE',RENAME:'RENAME',CREATE_DIR:'CREATE_DIR',LIST_DIR:'LIST_DIR',DELETE_DIR:'DELETE_DIR',ERROR:'ERROR',DOWNLOAD:'DOWNLOAD',PROGRESS:'PROGRESS',LOG:'LOG',MOUNT:'MOUNT',UNMOUNT:'UNMOUNT'};`);
        workerSource = workerSource.replace(/import\s*\{[^;]+\}\s*from\s*["']\.\/errors\.js["'];?/, `const ERROR_UNKNOWN_MESSAGE_TYPE=new Error('unknown message type'), ERROR_NOT_LOADED=new Error('ffmpeg is not loaded'), ERROR_IMPORT_FAILURE=new Error('failed to import ffmpeg core');`);
        const classWorkerURL = URL.createObjectURL(new Blob([workerSource], { type:'text/javascript' }));
        try {
          await ffmpeg.load({
            classWorkerURL,
            coreURL: await toBlobURL(base + '/ffmpeg-core.js', 'text/javascript'),
            wasmURL: await toBlobURL(base + '/ffmpeg-core.wasm', 'application/wasm')
          });
        } finally { setTimeout(() => URL.revokeObjectURL(classWorkerURL), 1000); }
        return { ffmpeg, fetchFile };
      })().catch(err => { localFfmpegPromise = null; throw err; });
      return localFfmpegPromise;
    }

    let lameJsPromise = null;
    function loadLameJs() {
      if (window.lamejs) return Promise.resolve(window.lamejs);
      if (lameJsPromise) return lameJsPromise;
      lameJsPromise = new Promise((resolve, reject) => {
        const script=document.createElement('script');
        script.src='https://unpkg.com/lamejs@1.2.1/lame.min.js';
        script.onload=()=>window.lamejs?resolve(window.lamejs):reject(new Error('MP3 encoder did not initialize'));
        script.onerror=()=>reject(new Error('Could not load the MP3 encoder'));
        document.head.appendChild(script);
      }).catch(e=>{lameJsPromise=null;throw e;});
      return lameJsPromise;
    }
    async function encodeWavUrlsToMp3(urls, sampleRate=24000) {
      const lame=await loadLameJs(), encoder=new lame.Mp3Encoder(1,sampleRate,128), mp3=[];
      let processed=0;
      for(const url of urls){
        const ab=await (await fetch(url)).arrayBuffer(), view=new DataView(ab);
        let off=12, dataOffset=44, dataSize=Math.max(0,ab.byteLength-44), rate=sampleRate;
        while(off+8<=ab.byteLength){ const id=String.fromCharCode(view.getUint8(off),view.getUint8(off+1),view.getUint8(off+2),view.getUint8(off+3)), size=view.getUint32(off+4,true); if(id==='fmt ') rate=view.getUint32(off+12,true); if(id==='data'){dataOffset=off+8;dataSize=size;break;} off+=8+size+(size&1); }
        if(rate!==sampleRate) throw new Error('Unexpected MIDI render sample rate');
        const pcm=new Int16Array(ab,dataOffset,Math.floor(Math.min(dataSize,ab.byteLength-dataOffset)/2));
        for(let i=0;i<pcm.length;i+=1152){ const out=encoder.encodeBuffer(pcm.subarray(i,Math.min(i+1152,pcm.length))); if(out.length) mp3.push(new Uint8Array(out)); if((++processed%180)===0) await new Promise(r=>setTimeout(r,0)); }
      }
      const tail=encoder.flush(); if(tail.length)mp3.push(new Uint8Array(tail));
      return new Blob(mp3,{type:'audio/mpeg'});
    }

    async function exportMidiToMp3(item, sourceUrl) {
      const key=item.key || item.name;
      try {
        showToast('Preparing MIDI instruments for MP3…');
        await renderMidiToAudioUrl(sourceUrl,key,0);
        const song=midiSongCache.get(key); if(!song) throw new Error('MIDI could not be parsed');
        const starts=[]; for(let t=0;t<song.duration;t+=MIDI_CHUNK_SECONDS) starts.push(t);
        const urls=[];
        for(let i=0;i<starts.length;i++){
          showToast('Rendering MIDI section '+(i+1)+' of '+starts.length+'…');
          urls.push(await renderMidiToAudioUrl(sourceUrl,key,starts[i]));
        }
        showToast('Encoding MP3 locally…');
        const mp3Blob=await encodeWavUrlsToMp3(urls,24000);
        const outUrl=URL.createObjectURL(mp3Blob);
        const downloadName=(item.name||'midi').replace(/\.(mid|midi|kar|smf)$/i,'')+'.mp3';
        const readyLink=document.getElementById('midiMp3DownloadLink');
        if(readyLink){ readyLink.href=outUrl; readyLink.download=downloadName; readyLink.querySelector('span').textContent='Download '+downloadName; readyLink.classList.remove('hidden'); readyLink.classList.add('flex'); }
        const a=document.createElement('a'); a.href=outUrl; a.download=downloadName; a.style.display='none'; document.body.appendChild(a); a.click(); a.remove();
        showToast('MP3 ready — use the Download button if it did not start automatically');
      } catch(err){ console.error(err); showToast('MIDI MP3 export failed: '+err.message,'error'); }
    }

    async function applyLocalVideoQuality(video, wrap, quality) {
      if (!video || !wrap) return;
      if (!wrap._qualityUrls) wrap._qualityUrls = new Map();
      if (!wrap.dataset.originalVideoSrc) wrap.dataset.originalVideoSrc = video.currentSrc || video.src;
      const wasPaused = video.paused;
      const resumeAt = video.currentTime || 0;
      const qualityLabel = wrap.querySelector('[data-menu-quality-val]');
      if (quality === 'Auto') {
        video.src = wrap.dataset.originalVideoSrc;
        video.load();
        video.addEventListener('loadedmetadata', () => {
          video.currentTime = Math.min(resumeAt, video.duration || resumeAt);
          if (!wasPaused) video.play().catch(() => {});
        }, { once:true });
        if (qualityLabel) qualityLabel.textContent = 'Auto';
        showToast('Using original video');
        return;
      }
      const height = parseInt(quality, 10);
      if (!height) return;
      let localUrl = wrap._qualityUrls.get(quality);
      if (!localUrl) {
        showToast('Preparing ' + quality + ' locally…');
        const { ffmpeg, fetchFile } = await getLocalFfmpeg();
        const source = wrap.dataset.originalVideoSrc;
        const ext = ((source.split('?')[0].split('.').pop() || 'mp4').toLowerCase().match(/^[a-z0-9]+$/) || ['mp4'])[0];
        const inputName = 'quality-input.' + ext;
        const outputName = 'quality-' + height + '.mp4';
        await ffmpeg.writeFile(inputName, await fetchFile(source));
        await ffmpeg.exec([
          '-i', inputName,
          '-vf', 'scale=-2:' + height + ':force_original_aspect_ratio=decrease',
          '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', height >= 1080 ? '25' : height >= 720 ? '27' : '30',
          '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
          outputName
        ]);
        const data = await ffmpeg.readFile(outputName);
        localUrl = URL.createObjectURL(new Blob([data.buffer], { type:'video/mp4' }));
        wrap._qualityUrls.set(quality, localUrl);
        try { await ffmpeg.deleteFile(inputName); await ffmpeg.deleteFile(outputName); } catch (_) {}
      }
      video.src = localUrl;
      video.load();
      video.addEventListener('loadedmetadata', () => {
        video.currentTime = Math.min(resumeAt, video.duration || resumeAt);
        if (!wasPaused) video.play().catch(() => {});
      }, { once:true });
      if (qualityLabel) qualityLabel.textContent = quality;
      showToast(quality + ' applied locally');
    }

    function attachHoverVolume(button, media) {
      if (!button || !media || button.dataset.volumeHover === '1') return;
      button.dataset.volumeHover = '1';
      const host = button.parentElement;
      if (getComputedStyle(host).position === 'static') host.style.position = 'relative';
      host.style.position = 'relative';
      const pop = document.createElement('div');
      pop.className = 'media-volume-popover';
      pop.style.left = 'auto';
      pop.style.right = '0';
      pop.style.bottom = 'calc(100% + 10px)';
      pop.innerHTML = '<span class="material-icons">volume_down</span><input type="range" min="0" max="1" step="0.01" value="' + (media.volume || 1) + '"><span class="material-icons">volume_up</span>';
      const mediaRoot = host.closest('.drive-video-wrap') || host.parentElement;
      mediaRoot.appendChild(pop);
      const positionPopover = () => {
        const rootRect = mediaRoot.getBoundingClientRect(), hostRect = host.getBoundingClientRect();
        pop.style.setProperty('left', 'auto', 'important');
        pop.style.setProperty('right', Math.max(0, rootRect.right - hostRect.right) + 'px', 'important');
        pop.style.setProperty('top', 'auto', 'important');
        pop.style.setProperty('bottom', Math.max(0, rootRect.bottom - hostRect.top + 10) + 'px', 'important');
      };
      const slider = pop.querySelector('input');
      slider.addEventListener('input', () => { media.volume = Number(slider.value); media.muted = media.volume === 0; });
      media.addEventListener('volumechange', () => { slider.value = media.muted ? 0 : media.volume; });
      let timer;
      const show = () => {
        clearTimeout(timer);
        const width = Math.round(host.getBoundingClientRect().width);
        if (width) pop.style.setProperty('--media-menu-width', width + 'px');
        positionPopover();
        pop.classList.add('is-visible');
      };
      const hide = () => { timer = setTimeout(() => pop.classList.remove('is-visible'), 180); };
      button.addEventListener('mouseenter', show); button.addEventListener('mouseleave', hide);
      pop.addEventListener('mouseenter', show); pop.addEventListener('mouseleave', hide);
    }

    function setupDrivePlayer(videoId) {
      const wrap = document.getElementById(videoId)?.closest('.drive-video-wrap');
      if (!wrap) return;
      if (wrap.dataset.driveWired === '1') return;
      wrap.dataset.driveWired = '1';
      const video = document.getElementById(videoId);
      const playBtn = wrap.querySelector('[data-drive-play]');
      const backBtn = wrap.querySelector('[data-drive-back]');
      const fwdBtn = wrap.querySelector('[data-drive-forward]');
      const muteBtn = wrap.querySelector('[data-drive-mute]');
      const ccBtn = wrap.querySelector('[data-drive-cc]');
      const pipBtn = wrap.querySelector('[data-drive-pip]');
      const speedBtn = wrap.querySelector('[data-drive-speed]');
      const settingsBtn = wrap.querySelector('[data-drive-settings]');
      const fullBtn = wrap.querySelector('[data-drive-full]');
      const progress = wrap.querySelector('[data-drive-progress]');
      const fill = progress?.querySelector('.drive-progress-fill');
      const thumb = progress?.querySelector('.drive-progress-thumb');
      const timeEl = wrap.querySelector('[data-drive-time]');
      if (!video) return;
      attachHoverVolume(muteBtn, video);
      const fmt = (s) => {
        if (isNaN(s) || !isFinite(s)) return '0:00';
        const m = Math.floor(s/60), sec = Math.floor(s%60);
        return m + ':' + String(sec).padStart(2,'0');
      };
      const updatePlayIcon = () => {
        if (!playBtn) return;
        playBtn.classList.toggle('is-playing', !video.paused);
        const iconSize = playBtn.classList.contains('lg') ? 24 : 22;
        playBtn.innerHTML = video.paused
          ? '<span class="material-icons text-black" style="font-size:' + iconSize + 'px">play_arrow</span>'
          : '<span class="material-icons" style="font-size:' + iconSize + 'px">pause</span>';
      };
      const updateMuteIcon = () => {
        if (!muteBtn) return;
        muteBtn.innerHTML = (video.muted || video.volume===0) ? '<span class="material-icons md-18">volume_off</span>' : '<span class="material-icons md-18">volume_up</span>';
      };
      const updateFullscreenIcon = () => {
        if (!fullBtn) return;
        const isFs = !!document.fullscreenElement;
        fullBtn.innerHTML = isFs ? '<span class="material-icons md-18">fullscreen_exit</span>' : '<span class="material-icons md-18">fullscreen</span>';
      };
      // play/pause — click video also toggles (not when hitting overlay buttons)
      playBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        if (video.paused) {
          playBtn.classList.add('is-playing');
          const iconSize = playBtn.classList.contains('lg') ? 24 : 22;
          playBtn.innerHTML = '<span class="material-icons" style="font-size:' + iconSize + 'px">pause</span>';
          video.play().catch(() => {
            playBtn.classList.remove('is-playing');
            updatePlayIcon();
          });
        } else {
          playBtn.classList.remove('is-playing');
          const iconSize = playBtn.classList.contains('lg') ? 24 : 22;
          playBtn.innerHTML = '<span class="material-icons text-black" style="font-size:' + iconSize + 'px">play_arrow</span>';
          video.pause();
        }
      });
      video.addEventListener('click', (e) => {
        if (e.target !== video) return;
        video.paused ? video.play() : video.pause();
      });
      backBtn?.addEventListener('click', () => { video.currentTime = Math.max(0, video.currentTime - 10); });
      fwdBtn?.addEventListener('click', () => { video.currentTime = Math.min(video.duration || Infinity, video.currentTime + 10); });
      muteBtn?.addEventListener('click', () => {
        video.muted = !video.muted;
        if (!video.muted) video.volume = video.volume || 1;
        updateMuteIcon();
      });
      video.addEventListener('volumechange', updateMuteIcon);
      // If no captions tracks (usually none), disable CC button
      const hasCaptions = () => {
        if (!video.textTracks) return false;
        for (let i=0;i<video.textTracks.length;i++) {
          const t = video.textTracks[i];
          if (t.kind === 'captions' || t.kind === 'subtitles') return true;
          try { if (t.cues && t.cues.length) return true; } catch(e) {}
        }
        return false;
      };
      const updateCcState = () => {
        const has = hasCaptions();
        const ccB = wrap.querySelector('[data-drive-cc]');
        const menuCcDis = wrap.querySelector('[data-menu-cc]');
        if (ccB) {
          ccB.disabled = !has;
          ccB.style.opacity = has ? '1' : '0.35';
          ccB.style.cursor = has ? '' : 'not-allowed';
          ccB.title = has ? 'Captions' : 'No captions available';
          if (menuCcDis) { menuCcDis.disabled = !has; menuCcDis.style.opacity = has ? '1' : '0.45'; }
        }
      };
      video.addEventListener('loadedmetadata', updateCcState);
      setTimeout(updateCcState, 400);
      setTimeout(updateCcState, 1500);
      if (video.textTracks) {
        try { video.textTracks.addEventListener('addtrack', updateCcState); } catch(e) {}
      }
      // CC toggle (only if has captions)
      // ccBtn and ccCheck already defined above, reuse
      ccBtn?.addEventListener('click', () => {
        if (ccBtn.disabled) return;
        const isOn = ccBtn.classList.toggle('bg-white/20');
        if (ccCheck) ccCheck.style.visibility = isOn ? 'visible' : 'hidden';
        const menuCheck = wrap.querySelector('[data-menu-cc-check]');
        if (menuCheck) menuCheck.style.visibility = isOn ? 'visible' : 'hidden';
        for (let i=0;i<video.textTracks.length;i++) {
          try { video.textTracks[i].mode = isOn ? 'showing' : 'hidden'; } catch(e) {}
        }
        showToast(isOn ? 'Captions on' : 'Captions off');
      });
      // PiP
      const updatePipIcon = () => {
        if (!pipBtn) return;
        const isPip = !!document.pictureInPictureElement;
        pipBtn.innerHTML = isPip ? '<span class="material-icons" style="font-size:20px">picture_in_picture</span>' : '<span class="material-icons" style="font-size:20px">picture_in_picture_alt</span>';
        pipBtn.title = isPip ? 'Exit Picture-in-Picture' : 'Picture-in-Picture';
      };
      pipBtn?.addEventListener('click', async () => {
        try {
          if (document.pictureInPictureElement) {
            await document.exitPictureInPicture();
          } else {
            if (video.readyState === 0) await video.play().catch(()=>{});
            if (document.pictureInPictureEnabled && video.disablePictureInPicture !== true) {
              await video.requestPictureInPicture();
            } else {
              showToast('PiP not supported', 'error');
            }
          }
        } catch(e) {
          showToast('PiP failed: ' + (e.message || 'unsupported'), 'error');
        }
      });
      video.addEventListener('enterpictureinpicture', updatePipIcon);
      video.addEventListener('leavepictureinpicture', updatePipIcon);
      document.addEventListener('leavepictureinpicture', updatePipIcon);
      // While the video is popped out, show the audio-style rounded square with a PiP icon
      const pipPlaceholder = wrap.querySelector('[data-pip-placeholder]');
      video.addEventListener('enterpictureinpicture', () => pipPlaceholder?.classList.remove('hidden'));
      video.addEventListener('leavepictureinpicture', () => pipPlaceholder?.classList.add('hidden'));
      if (pipBtn && !document.pictureInPictureEnabled) {
        pipBtn.disabled = true;
        pipBtn.style.opacity = '0.35';
        pipBtn.title = 'PiP not supported';
      }
      const driveMenu = wrap.querySelector('[data-drive-menu]');
      const speedSubmenu = wrap.querySelector('[data-speed-submenu]');
      const qualitySubmenu = wrap.querySelector('[data-quality-submenu]');
      const menuMain = wrap.querySelector('[data-menu-main]');
      const speedVal = wrap.querySelector('[data-menu-speed-val]');
      const ccCheck = wrap.querySelector('[data-menu-cc-check]');
      const menuSpeedBtn = wrap.querySelector('[data-menu-speed]');
      const menuCcBtn = wrap.querySelector('[data-menu-cc]');
      const resetMenuView = () => {
        menuMain?.classList.remove('hidden');
        speedSubmenu?.classList.add('hidden');
        qualitySubmenu?.classList.add('hidden');
      };
      const closeMenu = () => {
        if (driveMenu) driveMenu.classList.add('hidden');
        resetMenuView();
      };
      const toggleMenu = (e) => {
        e?.stopPropagation();
        if (!driveMenu) return;
        const controlsPill = settingsBtn?.closest('.drive-pill-dark');
        const controlsWidth = Math.round(controlsPill?.getBoundingClientRect().width || 0);
        if (controlsWidth) driveMenu.style.setProperty('--media-menu-width', controlsWidth + 'px');
        const hidden = driveMenu.classList.contains('hidden');
        // close all other drive menus on page
        document.querySelectorAll('[data-drive-menu]').forEach(m => { if (m!==driveMenu) m.classList.add('hidden'); });
        if (hidden) driveMenu.classList.remove('hidden');
        else closeMenu();
      };
      settingsBtn?.addEventListener('click', toggleMenu);
      wrap.querySelector('[data-menu-pip]')?.addEventListener('click', () => pipBtn?.click());
      const qualityBtn = wrap.querySelector('[data-menu-quality]');
      qualityBtn?.addEventListener('click', (e) => { e.stopPropagation(); menuMain?.classList.add('hidden'); qualitySubmenu?.classList.remove('hidden'); });
      wrap.querySelectorAll('[data-menu-back]').forEach(btn => btn.addEventListener('click', (e) => { e.stopPropagation(); resetMenuView(); }));
      wrap.querySelectorAll('[data-quality-opt]').forEach(btn => btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const quality = btn.dataset.qualityOpt;
        wrap.querySelectorAll('[data-quality-opt]').forEach(b => { b.disabled = true; });
        try {
          await applyLocalVideoQuality(video, wrap, quality);
          wrap.querySelectorAll('[data-quality-opt]').forEach(b => { b.classList.remove('active'); const c=b.querySelector('.menu-check'); if(c)c.remove(); });
          btn.classList.add('active'); btn.querySelector('span').insertAdjacentHTML('afterbegin','<span class="material-icons menu-check">check</span>');
          closeMenu();
        } catch (err) {
          console.error('Local FFmpeg quality conversion failed', err);
          showToast('Local quality conversion failed: ' + (err.message || 'unsupported browser'), 'error');
        } finally {
          wrap.querySelectorAll('[data-quality-opt]').forEach(b => { b.disabled = false; });
        }
      }));
      // 1x button also opens menu to speed section
      speedBtn?.addEventListener('click', (e) => {
        toggleMenu(e);
        if (driveMenu && !driveMenu.classList.contains('hidden')) {
          menuMain?.classList.add('hidden'); speedSubmenu?.classList.remove('hidden');
        }
      });
      menuSpeedBtn?.addEventListener('click', (e) => { e.stopPropagation(); menuMain?.classList.add('hidden'); speedSubmenu?.classList.remove('hidden'); });
      menuCcBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOn = ccBtn ? !ccBtn.classList.contains('bg-white/20') : true;
        if (ccBtn) ccBtn.classList.toggle('bg-white/20', isOn);
        const mCheck = wrap.querySelector('[data-menu-cc-check]');
        if (mCheck) mCheck.style.visibility = isOn ? 'visible' : 'hidden';
        const cCheck = wrap.querySelector('[data-menu-cc-check]');
        // reuse
        showToast(isOn ? 'Captions on' : 'Captions off');
        closeMenu();
      });
      // speed options inside menu
      wrap.querySelectorAll('[data-speed-opt]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const s = parseFloat(btn.getAttribute('data-speed-opt'));
          video.playbackRate = s;
          if (speedBtn) speedBtn.textContent = s + 'x';
          if (speedVal) speedVal.textContent = s + 'x ▸';
          // update active state
          wrap.querySelectorAll('[data-speed-opt]').forEach(b => {
            b.classList.remove('active','bg-white/10','text-white','font-bold');
            b.classList.add('text-white/80');
            b.classList.remove('drive-menu-item','active');
            // re-add base glass
            b.classList.add('drive-menu-item');
            b.textContent = b.getAttribute('data-speed-opt') + 'x';
          });
          btn.classList.add('active','text-white','font-bold');
          btn.classList.remove('text-white/80');
          btn.textContent = s + 'x ✓';
          showToast('Speed ' + s + 'x');
          closeMenu();
        });
      });
      // click outside to close
      const outsideHandler = (e) => {
        if (!wrap.contains(e.target)) closeMenu();
        else if (!driveMenu?.contains(e.target) && !settingsBtn?.contains(e.target) && !speedBtn?.contains(e.target)) {
          // if click on video but not menu, close menu
          if (driveMenu && !driveMenu.classList.contains('hidden') && !driveMenu.contains(e.target)) closeMenu();
        }
      };
      setTimeout(()=> document.addEventListener('click', outsideHandler), 100);
      // keep old speed cycle as fallback if menu not used
      let speedIdxFallback = 0; const speedsFallback = [1, 1.25, 1.5, 2, 0.5];
      // (speedBtn already wired to open menu, keep cycle on double-click or keep as is)
      // clicking video also closes menu
      wrap.addEventListener('click', (e) => {
        if (e.target.closest('[data-drive-menu]') || e.target.closest('[data-drive-settings]') || e.target.closest('[data-drive-speed]')) return;
        // otherwise let video toggle handle, but close menu
        if (driveMenu && !driveMenu.classList.contains('hidden')) closeMenu();
      });
      fullBtn?.addEventListener('click', () => {
        if (document.fullscreenElement) document.exitFullscreen();
        else wrap.requestFullscreen?.();
      });
      document.addEventListener('fullscreenchange', updateFullscreenIcon);
      // progress scrub — click + drag
      let isDragging = false;
      const seek = (e) => {
        const rect = progress.getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        if (video.duration) video.currentTime = pct * video.duration;
      };
      progress?.addEventListener('click', seek);
      progress?.addEventListener('mousedown', () => { isDragging = true; });
      window.addEventListener('mouseup', () => { isDragging = false; });
      window.addEventListener('mousemove', (e) => { if (isDragging && progress) seek(e); });
      // keyboard
      wrap.tabIndex = 0;
      wrap.addEventListener('keydown', (e) => {
        if (e.code === 'Space') { e.preventDefault(); video.paused ? video.play() : video.pause(); }
        if (e.code === 'ArrowLeft') { e.preventDefault(); video.currentTime = Math.max(0, video.currentTime - 10); }
        if (e.code === 'ArrowRight') { e.preventDefault(); video.currentTime = Math.min(video.duration || Infinity, video.currentTime + 10); }
        if (e.code === 'KeyM') { video.muted = !video.muted; updateMuteIcon(); }
        if (e.code === 'KeyF') { if (document.fullscreenElement) document.exitFullscreen(); else wrap.requestFullscreen?.(); }
      });
      video.addEventListener('play', updatePlayIcon);
      video.addEventListener('pause', updatePlayIcon);
      let videoBarRaf = 0;
      let vMediaT = 0, vWallT = 0, vRate = 1, vLive = false;
      const syncVideoClock = () => {
        vMediaT = video.currentTime || 0;
        vWallT = performance.now();
        vRate = video.playbackRate || 1;
        vLive = !video.paused && !video.ended;
      };
      const videoNow = () => vLive ? vMediaT + ((performance.now() - vWallT) / 1000) * vRate : vMediaT;
      const paintVideoBar = () => {
        videoBarRaf = requestAnimationFrame(paintVideoBar);
        if (isDragging || !video.duration || !isFinite(video.duration)) return;
        const t = Math.max(0, Math.min(video.duration, videoNow()));
        setDriveProgress(fill, thumb, progress, t / video.duration);
        if (timeEl) timeEl.textContent = fmt(t) + ' / ' + fmt(video.duration);
      };
      const startVideoBar = () => { if (!videoBarRaf) videoBarRaf = requestAnimationFrame(paintVideoBar); };
      video.addEventListener('play', () => { syncVideoClock(); startVideoBar(); });
      video.addEventListener('pause', () => { syncVideoClock(); vLive = false; });
      video.addEventListener('seeking', syncVideoClock);
      video.addEventListener('seeked', syncVideoClock);
      video.addEventListener('ratechange', syncVideoClock);
      video.addEventListener('timeupdate', syncVideoClock);
      video.addEventListener('loadedmetadata', () => {
        syncVideoClock();
        if (timeEl) timeEl.textContent = '0:00 / ' + fmt(video.duration);
      });
      video.addEventListener('ended', () => {
        updatePlayIcon();
        vLive = false;
        vMediaT = video.duration || vMediaT;
        setDriveProgress(fill, thumb, progress, 1);
      });
      startVideoBar();
      // Auto-hide controls after 3s still — show on mouse move
      const driveControls = [progress, wrap.querySelectorAll('.drive-pill-dark'), wrap.querySelectorAll('.drive-pill-white')].flatMap(el => {
        if (!el) return [];
        if (el instanceof NodeList || Array.isArray(el)) return Array.from(el);
        return [el];
      });
      // flatten NodeLists inside
      const allControls = [];
      wrap.querySelectorAll('.drive-progress, .drive-pill-dark, .drive-pill-white, .media-play-btn, [data-drive-play], [data-drive-menu]').forEach(el => allControls.push(el));
      const showDriveControls = () => {
        allControls.forEach(el => {
          if (!el) return;
          el.classList.remove('drive-controls-hidden');
          el.classList.add('drive-controls-visible');
          el.style.opacity = '1';
          el.style.pointerEvents = 'auto';
        });
      };
      const hideDriveControls = () => {
        // don't hide if video is paused or menu is open
        if (video.paused) return;
        const menuOpen = driveMenu && !driveMenu.classList.contains('hidden');
        if (menuOpen) return;
        allControls.forEach(el => {
          if (!el || el === driveMenu) return;
          // keep menu visible if open
          if (el.hasAttribute('data-drive-menu')) return;
          el.classList.remove('drive-controls-visible');
          el.classList.add('drive-controls-hidden');
        });
      };
      let idleTimer = null;
      const resetIdle = () => {
        showDriveControls();
        clearTimeout(idleTimer);
        idleTimer = setTimeout(hideDriveControls, 3000);
      };
      // initial show then hide after 3s
      showDriveControls();
      idleTimer = setTimeout(hideDriveControls, 3000);
      ['mousemove','mousedown','keydown','touchstart','wheel'].forEach(evt => {
        wrap.addEventListener(evt, resetIdle, { passive: true });
      });
      wrap.addEventListener('mouseleave', () => { clearTimeout(idleTimer); hideDriveControls(); });
      wrap.addEventListener('mouseenter', resetIdle);
      video.addEventListener('play', resetIdle);
      video.addEventListener('pause', showDriveControls);
      // when menu toggles, keep controls visible

      updatePlayIcon(); updateMuteIcon(); updateFullscreenIcon();
      // auto-focus for keyboard
      setTimeout(()=>wrap.focus(), 100);
    }

    function fitAudioArtBg() {
      const wrap = document.getElementById('audioPlayerWrap');
      const bg = document.getElementById('audioAlbumArtBg');
      if (!wrap || !bg || !bg.naturalWidth || !bg.naturalHeight) return;
      const wr = Math.max(wrap.clientWidth, 1);
      const hr = Math.max(wrap.clientHeight, 1);
      const nw = bg.naturalWidth, nh = bg.naturalHeight;
      // Cover + extra zoom so extreme aspect ratios never leave a black gap
      const s = Math.max(wr / nw, hr / nh) * 1.18;
      const w = nw * s, h = nh * s;
      bg.style.width = w + 'px';
      bg.style.height = h + 'px';
      bg.style.left = ((wr - w) / 2) + 'px';
      bg.style.top = ((hr - h) / 2) + 'px';
    }

    function resetAudioAlbumArt() {
      const wrap = document.getElementById('audioPlayerWrap');
      const tile = document.getElementById('audioAlbumArtTile');
      const bg = document.getElementById('audioAlbumArtBg');
      if (tile) {
        if (tile.src && tile.src.startsWith('blob:')) URL.revokeObjectURL(tile.src);
        tile.removeAttribute('src');
      }
      if (bg) { bg.removeAttribute('src'); bg.classList.add('hidden'); }
      if (wrap) wrap.classList.remove('has-album-art');
    }

    function showAudioAlbumArt(blob) {
      if (!blob || !blob.size) return false;
      const wrap = document.getElementById('audioPlayerWrap');
      const tile = document.getElementById('audioAlbumArtTile');
      const bg = document.getElementById('audioAlbumArtBg');
      if (!tile) return false;
      if (tile.src && tile.src.startsWith('blob:')) URL.revokeObjectURL(tile.src);
      const url = URL.createObjectURL(blob);
      tile.src = url;
      if (bg) bg.src = url;
      const reveal = () => {
        if (bg) bg.classList.remove('hidden');
        if (wrap) wrap.classList.add('has-album-art');
        fitAudioArtBg();
      };
      tile.onload = reveal;
      if (bg) bg.onload = () => fitAudioArtBg();
      tile.onerror = () => resetAudioAlbumArt();
      return true;
    }
    window.addEventListener('resize', fitAudioArtBg);

    function _u32(v, o) { return (v[o] << 24) | (v[o+1] << 16) | (v[o+2] << 8) | v[o+3]; }
    function _u24(v, o) { return (v[o] << 16) | (v[o+1] << 8) | v[o+2]; }
    function _synchsafe(v, o) { return ((v[o] & 0x7f) << 21) | ((v[o+1] & 0x7f) << 14) | ((v[o+2] & 0x7f) << 7) | (v[o+3] & 0x7f); }

    function extractId3Apic(buf) {
      const v = new Uint8Array(buf);
      if (v.length < 10 || v[0] !== 0x49 || v[1] !== 0x44 || v[2] !== 0x33) return null;
      const ver = v[3];
      const tagSize = _synchsafe(v, 6);
      let i = 10;
      if (v[5] & 0x40) {
        if (ver >= 4) i += _synchsafe(v, 10) + 4;
        else i += _u32(v, 10);
      }
      const end = Math.min(v.length, 10 + tagSize);
      while (i + 10 <= end) {
        const id = String.fromCharCode(v[i], v[i+1], v[i+2], v[i+3]);
        if (id === '\0\0\0\0' || id.charCodeAt(0) === 0) break;
        const size = ver === 4 ? _synchsafe(v, i + 4) : _u32(v, i + 4);
        const dataStart = i + 10;
        if (size <= 0 || dataStart + size > v.length) break;
        if (id === 'APIC') {
          let p = dataStart;
          const enc = v[p++];
          let mime = '';
          while (p < dataStart + size && v[p] !== 0) { mime += String.fromCharCode(v[p++]); }
          p++;
          p++; // picture type
          if (enc === 0 || enc === 3) {
            while (p < dataStart + size && v[p] !== 0) p++;
            p++;
          } else {
            while (p + 1 < dataStart + size && !(v[p] === 0 && v[p+1] === 0)) p += 2;
            p += 2;
          }
          const pic = v.slice(p, dataStart + size);
          if (pic.length > 32) {
            const type = (mime && mime.indexOf('/') > 0) ? mime : 'image/jpeg';
            return new Blob([pic], { type });
          }
        }
        i = dataStart + size;
      }
      return null;
    }

    function extractFlacPicture(buf) {
      const v = new Uint8Array(buf);
      if (v.length < 42 || v[0] !== 0x66 || v[1] !== 0x4c || v[2] !== 0x61 || v[3] !== 0x43) return null;
      let o = 4;
      while (o + 4 < v.length) {
        const last = !!(v[o] & 0x80);
        const type = v[o] & 0x7f;
        const size = _u24(v, o + 1);
        o += 4;
        if (type === 6 && size > 32 && o + size <= v.length) {
          let p = o + 4;
          const mimeLen = _u32(v, p); p += 4;
          let mime = '';
          for (let k = 0; k < mimeLen && p < v.length; k++) mime += String.fromCharCode(v[p++]);
          const descLen = _u32(v, p); p += 4 + descLen + 16;
          const picLen = _u32(v, p); p += 4;
          if (picLen > 32 && p + picLen <= v.length) {
            return new Blob([v.slice(p, p + picLen)], { type: mime || 'image/jpeg' });
          }
        }
        o += size;
        if (last) break;
      }
      return null;
    }

    function extractMp4Cover(buf) {
      const v = new Uint8Array(buf);
      const n = v.length;
      function findAtom(start, end, name) {
        let o = start;
        while (o + 8 <= end) {
          let size = _u32(v, o);
          const typ = String.fromCharCode(v[o+4], v[o+5], v[o+6], v[o+7]);
          if (size === 1 && o + 16 <= end) size = Number((BigInt(v[o+8])<<56n)|(BigInt(v[o+9])<<48n)|(BigInt(v[o+10])<<40n)|(BigInt(v[o+11])<<32n)|(BigInt(v[o+12])<<24n)|(BigInt(v[o+13])<<16n)|(BigInt(v[o+14])<<8n)|BigInt(v[o+15]));
          if (size < 8) break;
          const next = Math.min(o + size, end);
          if (typ === name) return { start: o + 8, end: next, hdr: 8 };
          o = next;
        }
        return null;
      }
      const moov = findAtom(0, n, 'moov');
      if (!moov) return null;
      const udta = findAtom(moov.start, moov.end, 'udta');
      const metaParent = udta || moov;
      const meta = findAtom(metaParent.start, metaParent.end, 'meta');
      if (!meta) return null;
      const ilstStart = meta.start + 4;
      const ilst = findAtom(ilstStart, meta.end, 'ilst') || findAtom(meta.start, meta.end, 'ilst');
      if (!ilst) return null;
      const covr = findAtom(ilst.start, ilst.end, 'covr');
      if (!covr) return null;
      const data = findAtom(covr.start, covr.end, 'data');
      if (!data || data.end - data.start < 12) return null;
      const payload = v.slice(data.start + 8, data.end);
      if (payload.length < 32) return null;
      const isPng = payload[0] === 0x89 && payload[1] === 0x50;
      return new Blob([payload], { type: isPng ? 'image/png' : 'image/jpeg' });
    }

    function extractEmbeddedAlbumArt(buf) {
      return extractId3Apic(buf) || extractFlacPicture(buf) || extractMp4Cover(buf);
    }

    async function findSiblingCoverArt(audioKey) {
      const slash = audioKey.lastIndexOf('/');
      const prefix = slash >= 0 ? audioKey.slice(0, slash + 1) : '';
      const names = ['cover.jpg','cover.jpeg','cover.png','folder.jpg','folder.png','album.jpg','album.png','artwork.jpg','front.jpg'];
      const pool = (allBucketItems.length ? allBucketItems : allS3Items || []);
      const hit = pool.find(it => {
        if (!it.key || it.key.endsWith('/')) return false;
        const rel = it.key.startsWith(prefix) ? it.key.slice(prefix.length) : '';
        return rel && !rel.includes('/') && names.includes(rel.toLowerCase());
      });
      if (!hit) return null;
      try {
        const url = await s3PresignUrl(hit.key);
        const res = await fetch(url);
        if (!res.ok) return null;
        return await res.blob();
      } catch (e) { return null; }
    }

    async function loadAudioAlbumArt(audioUrl, audioKey) {
      resetAudioAlbumArt();
      try {
        const res = await fetch(audioUrl, { headers: { Range: 'bytes=0-1048575' } });
        if (res.ok) {
          const buf = await res.arrayBuffer();
          const art = extractEmbeddedAlbumArt(buf);
          if (art && showAudioAlbumArt(art)) return;
        }
      } catch (e) { /* fall through */ }
      const sib = await findSiblingCoverArt(audioKey);
      if (sib) showAudioAlbumArt(sib);
    }

    let audioBarRaf = 0;
    let audioSeekDragging = false;
    let aMediaT = 0, aWallT = 0, aRate = 1, aLive = false;
    function syncAudioClock() {
      aMediaT = audioElement.currentTime || 0;
      aWallT = performance.now();
      aRate = audioElement.playbackRate || 1;
      aLive = !audioElement.paused && !audioElement.ended;
    }
    function audioNow() {
      return aLive ? aMediaT + ((performance.now() - aWallT) / 1000) * aRate : aMediaT;
    }
    function paintAudioBar() {
      audioBarRaf = requestAnimationFrame(paintAudioBar);
      if (audioSeekDragging || !audioElement.duration || isNaN(audioElement.duration)) return;
      const total = midiStream ? midiStream.duration : audioElement.duration;
      const local = Math.max(0, Math.min(audioElement.duration, audioNow()));
      const t = midiStream ? Math.min(total,midiStream.offset+local) : local;
      audioCurrentTime.textContent = formatTime(t);
      audioDuration.textContent = formatTime(total);
      const fill = customAudioPlayerUI.querySelector('.drive-progress-fill');
      const thumb = customAudioPlayerUI.querySelector('.drive-progress-thumb');
      const track = customAudioPlayerUI.querySelector('[data-audio-progress]');
      setDriveProgress(fill, thumb, track, t / total);
    }
    function startAudioBarLoop() {
      syncAudioClock();
      if (!audioBarRaf) audioBarRaf = requestAnimationFrame(paintAudioBar);
    }

    let midiRenderedUrl = null;
    const midiRenderCache = new Map(), midiSongCache = new Map();
    let midiStream = null;
    const MIDI_CHUNK_SECONDS = 120;
    function midiVlq(data, pos) {
      let value = 0, b = 0, guard = 0;
      do { if (pos >= data.length) throw new Error('Unexpected end of MIDI'); b = data[pos++]; value = (value << 7) | (b & 127); } while ((b & 128) && ++guard < 5);
      return { value, pos };
    }
    function parseMidiForPlayback(buffer) {
      const d = new Uint8Array(buffer), text = (p,n) => String.fromCharCode(...d.slice(p,p+n));
      const u16 = p => (d[p] << 8) | d[p+1], u32 = p => ((d[p]*0x1000000)+(d[p+1]<<16)+(d[p+2]<<8)+d[p+3]) >>> 0;
      if (text(0,4) !== 'MThd') throw new Error('This is not a Standard MIDI file');
      const division = u16(12); if (!division || division & 0x8000) throw new Error('SMPTE MIDI timing is not supported');
      const tracks = u16(10); let p = 8 + u32(4), all = [], tempos = [{tick:0, us:500000}], programs = new Array(16).fill(0);
      for (let tr=0; tr<tracks && p+8<=d.length; tr++) {
        if (text(p,4) !== 'MTrk') break;
        const end = p + 8 + u32(p+4); let q=p+8, tick=0, running=0;
        while(q<end) {
          const delta=midiVlq(d,q); q=delta.pos; tick+=delta.value;
          let st=d[q]; if(st<128) st=running; else { q++; running=st; }
          if(st===255) { const type=d[q++], len=midiVlq(d,q); q=len.pos; if(type===81 && len.value>=3) tempos.push({tick,us:(d[q]<<16)|(d[q+1]<<8)|d[q+2]}); q+=len.value; continue; }
          if(st===240 || st===247) { const len=midiVlq(d,q); q=len.pos+len.value; continue; }
          const type=st&240, ch=st&15;
          if(type===192) { programs[ch]=d[q++]; all.push({tick,type:'program',ch,program:programs[ch]}); continue; }
          if(type===208) { q++; continue; }
          const a=d[q++], b=d[q++];
          if(type===144 || type===128) all.push({tick,type:(type===144&&b>0)?'on':'off',ch,pitch:a,vel:b});
        }
        p=end;
      }
      tempos.sort((a,b)=>a.tick-b.tick); const compact=[]; tempos.forEach(t=>{ if(compact.length&&compact.at(-1).tick===t.tick) compact[compact.length-1]=t; else compact.push(t); });
      const tickToSec = tick => { let sec=0,last=0,us=500000; for(const t of compact){ if(t.tick>tick) break; sec+=(t.tick-last)*us/division/1e6; last=t.tick; us=t.us; } return sec+(tick-last)*us/division/1e6; };
      all.sort((a,b)=>a.tick-b.tick); const active=new Map(), currentPrograms=new Array(16).fill(0), notes=[];
      for(const e of all) { if(e.type==='program'){currentPrograms[e.ch]=e.program; continue;} const key=e.ch+':'+e.pitch; if(e.type==='on') active.set(key,{...e,program:currentPrograms[e.ch]}); else { const on=active.get(key); if(on){ notes.push({ch:on.ch,pitch:on.pitch,vel:on.vel,program:on.program,start:tickToSec(on.tick),end:tickToSec(e.tick)}); active.delete(key); } } }
      const lastTick=all.length?all[all.length-1].tick:division; for(const on of active.values()) notes.push({ch:on.ch,pitch:on.pitch,vel:on.vel,program:on.program,start:tickToSec(on.tick),end:tickToSec(lastTick+division)});
      let duration=1; for(const n of notes) duration=Math.max(duration,n.end+1);
      return {notes,duration};
    }
    const roboMidiSampleBuffers = new Map();
    const roboMidiDecodeCtx = new (window.AudioContext||window.webkitAudioContext)();
    const roboNoteNames={'C':0,'C#':1,'D':2,'D#':3,'E':4,'F':5,'F#':6,'G':7,'G#':8,'A':9,'A#':10,'B':11};
    const roboSamplePitch = key => { const m=key.match(/_([A-G]#?)(-?\d)$/); return m ? (parseInt(m[2])+1)*12+roboNoteNames[m[1]] : 60; };
    const roboProgramKind = p => ['piano','musicbox','organ','aguitar','bass','strings','strings','brass','flute','flute','lead','pad','pad','kalimba','marimba','lead'][Math.floor((p||0)/8)] || 'piano';
    const roboDrumKey = p => p<=36?'drum_kick':(p===38||p===40?'drum_snare':(p===39?'drum_clap':(p===42||p===44?'drum_hat':(p===46?'drum_ohat':(p>=49&&p<=57?'drum_crash':(p===51||p===59?'drum_ride':(p<45?'drum_tom_l':p<49?'drum_tom_m':'drum_tom_h')))))));
    function roboSampleKey(note){
      if(note.ch===9) return roboDrumKey(note.pitch);
      const kind=roboProgramKind(note.program), keys=Object.keys(window.__ROBO_MIDI_SAMPLES__||{}).filter(k=>k.startsWith(kind+'_'));
      let best=keys[0], dist=Infinity; for(const k of keys){const d=Math.abs(roboSamplePitch(k)-note.pitch);if(d<dist){dist=d;best=k;}} return best;
    }
    async function roboDecodeSamples(notes){
      const keys=[...new Set(notes.map(roboSampleKey).filter(Boolean))];
      await Promise.all(keys.map(async key=>{ if(roboMidiSampleBuffers.has(key)) return; const b64=window.__ROBO_MIDI_SAMPLES__?.[key]; if(!b64)return; const bin=atob(b64),u8=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u8[i]=bin.charCodeAt(i);try{roboMidiSampleBuffers.set(key,await roboMidiDecodeCtx.decodeAudioData(u8.buffer));}catch(e){} }));
    }
    function midiWaveform(program) { const family=Math.floor(program/8); if([4,5,6,7,9].includes(family)) return 'sine'; if([10,11,12,13].includes(family)) return 'sawtooth'; return 'triangle'; }
    async function renderMidiToAudioUrl(sourceUrl, cacheKey, chunkStart=0) {
      const baseKey=cacheKey || sourceUrl, key=baseKey+'@'+chunkStart;
      if(midiRenderCache.has(key)) return midiRenderCache.get(key);
      let song=midiSongCache.get(baseKey);
      if(!song){ const res=await fetch(sourceUrl); if(!res.ok) throw new Error('Could not download MIDI data'); song=parseMidiForPlayback(await res.arrayBuffer()); midiSongCache.set(baseKey,song); }
      const duration=Math.max(.1,Math.min(MIDI_CHUNK_SECONDS,song.duration-chunkStart)), dense=true, rate=24000;
      const chunkNotes=song.notes.filter(n=>n.end>chunkStart&&n.start<chunkStart+duration).slice(0,5000);
      await roboDecodeSamples(chunkNotes);
      const Offline=window.OfflineAudioContext||window.webkitOfflineAudioContext; if(!Offline) throw new Error('MIDI rendering is not supported by this browser');
      const ctx=new Offline(1,Math.ceil(duration*rate),rate), master=ctx.createGain(), comp=ctx.createDynamicsCompressor();
      master.gain.value=.34;
      comp.threshold.value=-22; comp.knee.value=18; comp.ratio.value=8; comp.attack.value=.004; comp.release.value=.24;
      master.connect(comp); comp.connect(ctx.destination);
      let seed=0x12345678; const random=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296);
      const noiseBuffer=ctx.createBuffer(1,rate,rate); const nd=noiseBuffer.getChannelData(0); for(let i=0;i<nd.length;i++) nd[i]=random()*2-1;
      let scheduledNotes=0;
      for(const n of chunkNotes) {
        if(n.end<=chunkStart || n.start>=chunkStart+duration || scheduledNotes++ >= 5000) continue; const start=Math.max(0,n.start-chunkStart), len=Math.max(.05,Math.min(n.end-n.start,8)), amp=Math.max(.008,(n.vel/127)*.105);
        const sampleKey=roboSampleKey(n), sampleBuf=roboMidiSampleBuffers.get(sampleKey);
        if(sampleBuf){ const src=ctx.createBufferSource(), gain=ctx.createGain(); src.buffer=sampleBuf; src.playbackRate.value=n.ch===9?1:Math.pow(2,(n.pitch-roboSamplePitch(sampleKey))/12); gain.gain.value=Math.max(.02,(n.vel/127)*.55); src.connect(gain); gain.connect(master); src.start(start); src.stop(Math.min(duration,start+Math.max(.12,len+.2))); continue; }
        if(n.ch===9) { const src=ctx.createBufferSource(), filter=ctx.createBiquadFilter(), gain=ctx.createGain(); src.buffer=noiseBuffer; filter.type=n.pitch<41?'lowpass':'highpass'; filter.frequency.value=n.pitch<41?180:4500; gain.gain.setValueAtTime(amp*.7,start); gain.gain.exponentialRampToValueAtTime(.0001,start+Math.min(.28,len)); src.connect(filter); filter.connect(gain); gain.connect(master); src.start(start); src.stop(start+Math.min(.5,len)+.02); continue; }
        const freq=440*Math.pow(2,(n.pitch-69)/12), family=Math.floor(n.program/8), bus=ctx.createGain(), filter=ctx.createBiquadFilter();
        filter.type='lowpass'; filter.Q.value=.7; filter.frequency.value=family===4?900:(family===5?1800:2600+((n.program%8)*180));
        bus.gain.setValueAtTime(.0001,start);
        const attack=([5,6,11].includes(family)?0.09:0.012), release=([5,6,11].includes(family)?.65:.32);
        bus.gain.linearRampToValueAtTime(amp,start+attack);
        bus.gain.setValueAtTime(amp*.82,start+Math.max(attack,len*.72));
        bus.gain.exponentialRampToValueAtTime(.0001,start+len+release);
        bus.connect(filter); filter.connect(master);
        const layers=dense?[[1,midiWaveform(n.program),1]]:(family===0?[[1,'triangle',.78],[2,'sine',.16],[3,'sine',.06]]:[[1,midiWaveform(n.program),.82],[2,'sine',.12]]);
        for(const [ratio,wave,level] of layers){ const osc=ctx.createOscillator(), og=ctx.createGain(); osc.type=wave; osc.frequency.value=freq*ratio; og.gain.value=level; osc.connect(og); og.connect(bus); osc.start(start); osc.stop(start+len+release+.04); }
      }
      const rendered=await ctx.startRendering(), channels=rendered.numberOfChannels, frames=rendered.length, out=new ArrayBuffer(44+frames*channels*2), view=new DataView(out); let o=0;
      const str=x=>{for(let i=0;i<x.length;i++)view.setUint8(o++,x.charCodeAt(i));}, u16=x=>{view.setUint16(o,x,true);o+=2;}, u32=x=>{view.setUint32(o,x,true);o+=4;};
      str('RIFF');u32(36+frames*channels*2);str('WAVEfmt ');u32(16);u16(1);u16(channels);u32(rendered.sampleRate);u32(rendered.sampleRate*channels*2);u16(channels*2);u16(16);str('data');u32(frames*channels*2);
      const data=[]; for(let c=0;c<channels;c++)data.push(rendered.getChannelData(c)); for(let i=0;i<frames;i++)for(let c=0;c<channels;c++){const v=Math.max(-1,Math.min(1,data[c][i]));view.setInt16(o,v<0?v*32768:v*32767,true);o+=2;}
      midiRenderedUrl=URL.createObjectURL(new Blob([out],{type:'audio/wav'}));
      midiRenderCache.set(key,midiRenderedUrl);
      while(midiRenderCache.size>6){ const first=midiRenderCache.keys().next().value, oldUrl=midiRenderCache.get(first); midiRenderCache.delete(first); if(oldUrl!==midiRenderedUrl) URL.revokeObjectURL(oldUrl); }
      return midiRenderedUrl;
    }

    async function setupCustomAudioPlayer(audioUrl, fileName) {
      customAudioPlayerUI.classList.remove('hidden');
      const isMidi = /\.(mid|midi|kar|smf)$/i.test(fileName || '');
      let playableUrl = audioUrl;
      if (isMidi) {
        document.getElementById('audioPlayerWrap')?.classList.add('is-midi');
        audioElement.loop = false;
        resetAudioAlbumArt();
        const icon = document.getElementById('audioFileIcon'); if (icon) { icon.textContent='music_note'; icon.classList.remove('text-pink-400'); icon.classList.add('text-violet-400'); }
        showToast('Reading MIDI notes and instruments…');
        try { const midiKey=(selectedItem && selectedItem.key) || fileName; playableUrl = await renderMidiToAudioUrl(audioUrl,midiKey,0); const song=midiSongCache.get(midiKey); midiStream={sourceUrl:audioUrl,key:midiKey,duration:song.duration,offset:0,nextPromise:null}; midiStream.nextPromise=song.duration>MIDI_CHUNK_SECONDS?renderMidiToAudioUrl(audioUrl,midiKey,MIDI_CHUNK_SECONDS):null; showToast('MIDI ready — buffering ahead'); }
        catch (err) { showToast('Could not render MIDI: '+err.message, 'error'); return; }
      } else {
        midiStream = null;
        document.getElementById('audioPlayerWrap')?.classList.remove('is-midi');
        const icon = document.getElementById('audioFileIcon'); if (icon) { icon.textContent='audio_file'; icon.classList.add('text-pink-400'); icon.classList.remove('text-violet-400'); }
        loadAudioAlbumArt(audioUrl, (selectedItem && selectedItem.key) || fileName);
      }

      // CORS-clean source so the Web Audio equalizer can process the stream
      audioElement.crossOrigin = 'anonymous';
      audioElement.src = playableUrl;
      audioElement.load();
      let started = false;
      try { await audioElement.play(); started = !audioElement.paused; }
      catch (e) { started = false; }

      updatePlayPauseState(started);
      startAudioBarLoop();
      if (isMidi && !started) showToast('MIDI ready — press play');

      audioElement.onended = async () => {
        if(midiStream && midiStream.offset+MIDI_CHUNK_SECONDS < midiStream.duration){
          try{
            const nextOffset=midiStream.offset+MIDI_CHUNK_SECONDS;
            const nextUrl=await (midiStream.nextPromise || renderMidiToAudioUrl(midiStream.sourceUrl,midiStream.key,nextOffset));
            midiStream.offset=nextOffset;
            const following=nextOffset+MIDI_CHUNK_SECONDS;
            midiStream.nextPromise=following<midiStream.duration?renderMidiToAudioUrl(midiStream.sourceUrl,midiStream.key,following):null;
            audioElement.src=nextUrl; audioElement.load(); await audioElement.play(); updatePlayPauseState(true); syncAudioClock(); return;
          }catch(err){ showToast('Could not buffer the next MIDI section','error'); }
        }
        audioElement.loop = false;
        updatePlayPauseState(false); paintAudioBar();
      };
    }

    function updatePlayPauseState(isPlaying) {
      audioPlayPauseBtn.classList.toggle('is-playing', !!isPlaying);
      audioPlayPauseBtn.innerHTML = isPlaying
        ? `<span class="material-icons" style="font-size:22px">pause</span>`
        : `<span class="material-icons text-black" style="font-size:22px">play_arrow</span>`;
    }

    function formatTime(seconds) {
      const mins = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60);
      return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    // Audio Player Controls Listener
    audioPlayPauseBtn.onclick = (e) => {
      e.stopPropagation();
      if (audioElement.paused) {
        audioElement.play();
        updatePlayPauseState(true);
        startAudioBarLoop();
      } else {
        audioElement.pause();
        updatePlayPauseState(false);
        paintAudioBar();
      }
    };

    // Drive-style progress (new) + keep old seekbar as fallback
    const audioProgress = customAudioPlayerUI.querySelector('[data-audio-progress]');
    const audioProgressFill = audioProgress?.querySelector('.drive-progress-fill');
    const audioProgressThumb = audioProgress?.querySelector('.drive-progress-thumb');
    if (audioProgress) {
      let isDraggingAudio = false;
      const seekAudio = async (e) => {
        const rect = audioProgress.getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        if(midiStream){
          const target=pct*midiStream.duration, offset=Math.floor(target/MIDI_CHUNK_SECONDS)*MIDI_CHUNK_SECONDS, wasPlaying=!audioElement.paused;
          if(offset!==midiStream.offset){ const url=await renderMidiToAudioUrl(midiStream.sourceUrl,midiStream.key,offset); midiStream.offset=offset; audioElement.src=url; audioElement.load(); }
          audioElement.currentTime=Math.max(0,target-offset); if(wasPlaying) audioElement.play().catch(()=>{}); syncAudioClock();
        } else if (audioElement.duration) audioElement.currentTime = pct * audioElement.duration;
      };
      audioProgress.addEventListener('click', seekAudio);
      audioProgress.addEventListener('mousedown', () => { isDraggingAudio = true; audioSeekDragging = true; });
      window.addEventListener('mouseup', () => { isDraggingAudio = false; audioSeekDragging = false; paintAudioBar(); });
      window.addEventListener('mousemove', (e) => { if (isDraggingAudio) seekAudio(e); });
    }
    const updateAudioMuteIcon = () => {
      const isMuted = audioElement.muted || audioElement.volume === 0;
      audioMuteBtn.innerHTML = isMuted ? '<span class="material-icons" style="font-size:18px">volume_off</span>' : '<span class="material-icons" style="font-size:18px">volume_up</span>';
    };
    audioMuteBtn.onclick = () => {
      audioElement.muted = !audioElement.muted;
      updateAudioMuteIcon();
    };
    audioElement.addEventListener('volumechange', updateAudioMuteIcon);
    attachHoverVolume(audioMuteBtn, audioElement);
    audioElement.addEventListener('timeupdate', syncAudioClock);
    audioElement.addEventListener('seeked', syncAudioClock);
    audioElement.addEventListener('seeking', syncAudioClock);
    audioElement.addEventListener('ratechange', syncAudioClock);
    audioElement.addEventListener('play', () => { syncAudioClock(); startAudioBarLoop(); });
    audioElement.addEventListener('pause', () => { syncAudioClock(); aLive = false; });

    // sync drive progress + wave + times
    const _origSetupAudio = audioElement.ontimeupdate;
    // will be handled in setupCustomAudioPlayer below, but also need drive bar sync there

    let speeds = [1.0, 1.25, 1.5, 2.0, 0.5];
    let currentSpeedIdx = 0;
    const updateAudioSpeedBtns = (speed) => {
      audioSpeedBtn.textContent = speed.toFixed(1).replace('.0','') + 'x';
      const menuVal = customAudioPlayerUI.querySelector('[data-audio-menu-speed-val]');
      if (menuVal) menuVal.textContent = speed.toFixed(1).replace('.0','') + 'x ▸';
      // update submenu active
      customAudioPlayerUI.querySelectorAll('[data-audio-speed-opt]').forEach(b => {
        const s = parseFloat(b.getAttribute('data-audio-speed-opt'));
        const isActive = Math.abs(s - speed) < 0.01;
        b.classList.toggle('active', isActive);
        b.classList.toggle('font-bold', isActive);
        b.textContent = s + 'x' + (isActive ? ' ✓' : '');
        if (isActive) { b.classList.add('text-white'); b.classList.remove('text-white/80'); } else { b.classList.remove('text-white'); b.classList.add('text-white/80'); }
      });
    };
    audioSpeedBtn.onclick = (e) => {
      e.stopPropagation();
      // open menu to speed submenu instead of just cycling
      const menu = customAudioPlayerUI.querySelector('[data-audio-menu]');
      const sub = customAudioPlayerUI.querySelector('[data-audio-speed-submenu]');
      if (menu && sub) {
        const controlsPill = audioSpeedBtn.closest('.glass-strong');
        const controlsWidth = Math.round(controlsPill?.getBoundingClientRect().width || 0);
        if (controlsWidth) menu.style.setProperty('--media-menu-width', controlsWidth + 'px');
        menu.classList.remove('hidden');
        showAudioSubmenu(sub, 'Playback speed');
      } else {
        currentSpeedIdx = (currentSpeedIdx + 1) % speeds.length;
        const speed = speeds[currentSpeedIdx];
        audioElement.playbackRate = speed;
        updateAudioSpeedBtns(speed);
        showToast('Speed ' + speed.toFixed(1).replace('.0','') + 'x');
      }
    };
    // Audio settings menu (gear)
    const audioSettingsBtn = customAudioPlayerUI.querySelector('[data-audio-settings]');
    const audioMenu = customAudioPlayerUI.querySelector('[data-audio-menu]');
    const audioMenuSpeedBtn = customAudioPlayerUI.querySelector('[data-audio-menu-speed]');
    const audioSpeedSubmenu = customAudioPlayerUI.querySelector('[data-audio-speed-submenu]');
    const audioMenuLoopBtn = customAudioPlayerUI.querySelector('[data-audio-menu-loop]');
    const audioMenuLoopCheck = audioMenu?.querySelector('[data-audio-menu-loop-check]');
    // Keep the menu in the player backdrop root so backdrop-filter samples the artwork, not the page behind the player.
    const audioPlayerBackdrop = document.getElementById('audioPlayerWrap');
    if (audioMenu && audioPlayerBackdrop && audioMenu.parentElement !== audioPlayerBackdrop) audioPlayerBackdrop.appendChild(audioMenu);
    const audioEqSubmenuNav = customAudioPlayerUI.querySelector('[data-audio-eq-submenu]');
    const audioMainRows = audioMenu ? [...audioMenu.children].filter(el => !el.matches('[data-audio-speed-submenu], [data-audio-eq-submenu]')) : [];
    const ensureAudioBack = (submenu, title) => {
      if (!submenu || submenu.querySelector('[data-audio-menu-back]')) return;
      const back = document.createElement('button');
      back.type = 'button'; back.dataset.audioMenuBack = '';
      back.className = 'drive-menu-item audio-submenu-title';
      back.innerHTML = '<span class="flex items-center gap-2"><span class="material-icons">arrow_back</span>' + title + '</span>';
      back.onclick = (e) => { e.stopPropagation(); resetAudioMenuView(); };
      submenu.prepend(back);
    };
    const resetAudioMenuView = () => {
      if (!audioMenu) return;
      [...audioMenu.children].forEach(el => {
        const isSubmenu = el.matches('[data-audio-speed-submenu], [data-audio-eq-submenu]');
        el.classList.toggle('hidden', isSubmenu);
      });
    };
    const showAudioSubmenu = (submenu, title) => {
      if (!audioMenu || !submenu) return;
      ensureAudioBack(submenu, title);
      [...audioMenu.children].forEach(el => el.classList.toggle('hidden', el !== submenu));
      submenu.classList.remove('hidden');
    };
    const toggleAudioMenu = (e) => {
      e?.stopPropagation();
      if (!audioMenu) return;
      const controlsPill = audioSettingsBtn?.closest('.glass-strong');
      const controlsWidth = Math.round(controlsPill?.getBoundingClientRect().width || 0);
      if (controlsWidth) audioMenu.style.setProperty('--media-menu-width', controlsWidth + 'px');
      const hidden = audioMenu.classList.contains('hidden');
      document.querySelectorAll('[data-audio-menu], [data-drive-menu]').forEach(m => { if (m!==audioMenu) m.classList.add('hidden'); });
      if (hidden) { resetAudioMenuView(); audioMenu.classList.remove('hidden'); }
      else { audioMenu.classList.add('hidden'); resetAudioMenuView(); }
    };
    audioSettingsBtn?.addEventListener('click', toggleMenu => toggleAudioMenu(toggleMenu));
    audioMenuSpeedBtn?.addEventListener('click', (e) => { e.stopPropagation(); showAudioSubmenu(audioSpeedSubmenu, 'Playback speed'); });
    audioMenuLoopBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      audioElement.loop = !audioElement.loop;
      const on = audioElement.loop;
      if (audioMenuLoopCheck) audioMenuLoopCheck.style.visibility = on ? 'visible' : 'hidden';
      showToast(on ? 'Loop on' : 'Loop off');
    });
    // =====================================================================
    // EQUALIZER — real 5-band EQ via Web Audio API (biquad filter chain)
    // =====================================================================
    let audioCtx = null, eqSource = null; const eqFilters = [];
    const EQ_BANDS = [
      { type: 'lowshelf',  freq: 60 },
      { type: 'peaking',   freq: 250,  q: 1 },
      { type: 'peaking',   freq: 1000, q: 1 },
      { type: 'peaking',   freq: 4000, q: 1 },
      { type: 'highshelf', freq: 12000 }
    ];
    const EQ_PRESETS = {
      flat:   [0, 0, 0, 0, 0],
      bass:   [6, 4, 0, 0, 0],
      vocal:  [-2, 0, 4, 3, 0],
      treble: [0, 0, 0, 3, 6]
    };
    function ensureEqualizer() {
      if (audioCtx) return true;
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return false;
      try {
        audioCtx = new Ctx();
        eqSource = audioCtx.createMediaElementSource(audioElement);
        let node = eqSource;
        EQ_BANDS.forEach(b => {
          const f = audioCtx.createBiquadFilter();
          f.type = b.type; f.frequency.value = b.freq; if (b.q) f.Q.value = b.q; f.gain.value = 0;
          node.connect(f); node = f; eqFilters.push(f);
        });
        node.connect(audioCtx.destination);
        audioElement.addEventListener('play', () => { if (audioCtx.state === 'suspended') audioCtx.resume(); });
        return true;
      } catch(e) { console.error('equalizer init failed', e); audioCtx = null; return false; }
    }
    function applyEqGains(gains) {
      customAudioPlayerUI.querySelectorAll('[data-eq-band]').forEach((slider, idx) => {
        const g = gains[idx] || 0;
        slider.value = g;
        if (eqFilters[idx]) eqFilters[idx].gain.value = g;
        const valEl = customAudioPlayerUI.querySelector('[data-eq-val="' + idx + '"]');
        if (valEl) valEl.textContent = (g > 0 ? '+' : '') + g;
      });
      updateEqPresetLabel();
    }
    function updateEqPresetLabel() {
      const current = eqFilters.map(f => Math.round(f.gain.value)).join(',');
      let name = 'Custom';
      for (const [k, v] of Object.entries(EQ_PRESETS)) {
        if (v.join(',') === current) { name = k.charAt(0).toUpperCase() + k.slice(1); break; }
      }
      const label = customAudioPlayerUI.querySelector('[data-audio-menu-eq-val]');
      if (label) label.textContent = name + ' ▸';
    }
    const audioEqBtn = customAudioPlayerUI.querySelector('[data-audio-menu-eq]');
    const audioEqSubmenu = customAudioPlayerUI.querySelector('[data-audio-eq-submenu]');
    audioEqBtn?.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!ensureEqualizer()) { showToast('Equalizer not supported in this browser', 'error'); return; }
      if (audioCtx.state === 'suspended') audioCtx.resume();
      showAudioSubmenu(audioEqSubmenu, 'Equalizer');
    });
    customAudioPlayerUI.querySelectorAll('[data-eq-band]').forEach((slider, idx) => {
      slider.addEventListener('input', () => {
        if (!ensureEqualizer()) return;
        const g = parseFloat(slider.value);
        if (eqFilters[idx]) eqFilters[idx].gain.value = g;
        const valEl = customAudioPlayerUI.querySelector('[data-eq-val="' + idx + '"]');
        if (valEl) valEl.textContent = (g > 0 ? '+' : '') + g;
        updateEqPresetLabel();
      });
    });
    customAudioPlayerUI.querySelectorAll('[data-eq-preset]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!ensureEqualizer()) { showToast('Equalizer not supported in this browser', 'error'); return; }
        if (audioCtx.state === 'suspended') audioCtx.resume();
        applyEqGains(EQ_PRESETS[btn.getAttribute('data-eq-preset')] || EQ_PRESETS.flat);
      });
    });

    // speed submenu clicks
    customAudioPlayerUI.querySelectorAll('[data-audio-speed-opt]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const s = parseFloat(btn.getAttribute('data-audio-speed-opt'));
        audioElement.playbackRate = s;
        updateAudioSpeedBtns(s);
        showToast('Speed ' + s + 'x');
        audioMenu?.classList.add('hidden');
        resetAudioMenuView();
      });
    });
    document.addEventListener('click', (e) => {
      if (!customAudioPlayerUI.contains(e.target) || e.target.closest('[data-audio-settings]') || e.target.closest('[data-audio-menu-speed]')) return;
      if (audioMenu && !audioMenu.classList.contains('hidden') && !audioMenu.contains(e.target)) audioMenu.classList.add('hidden');
    });

    document.getElementById('audioRewindBtn').onclick = () => { audioElement.currentTime=Math.max(0,audioElement.currentTime-10); };
    document.getElementById('audioForwardBtn').onclick = () => { audioElement.currentTime = Math.min(audioElement.duration, audioElement.currentTime + 10); };

    (function setupAudioIdleHide() {
      const wrap = document.getElementById('audioPlayerWrap');
      if (!wrap) return;
      const audioControls = [];
      wrap.querySelectorAll('.drive-progress, .drive-pill-dark, .glass-strong, .media-play-btn, [data-audio-menu]').forEach(el => {
        if (el.id === 'audioGlassSheet' || el.id === 'audioIconSquare') return;
        audioControls.push(el);
      });
      const show = () => {
        audioControls.forEach(el => {
          el.classList.remove('drive-controls-hidden');
          el.classList.add('drive-controls-visible');
          el.style.opacity = '1';
          el.style.pointerEvents = 'auto';
        });
      };
      const hide = () => {
        if (audioElement.paused) return;
        const menu = customAudioPlayerUI.querySelector('[data-audio-menu]');
        if (menu && !menu.classList.contains('hidden')) return;
        audioControls.forEach(el => {
          if (el.hasAttribute('data-audio-menu')) return;
          el.classList.remove('drive-controls-visible');
          el.classList.add('drive-controls-hidden');
        });
      };
      let t = null;
      const reset = () => { show(); clearTimeout(t); t = setTimeout(hide, 3000); };
      show(); t = setTimeout(hide, 3000);
      ['mousemove','mousedown','keydown','touchstart','wheel'].forEach(evt => wrap.addEventListener(evt, reset, { passive: true }));
      wrap.addEventListener('mouseleave', () => { clearTimeout(t); hide(); });
      wrap.addEventListener('mouseenter', reset);
      audioElement.addEventListener('play', reset);
      audioElement.addEventListener('pause', show);
    })();

    // Upload Modal Events
    const openUploadModalBtn = document.getElementById('openUploadModalBtn');
    const closeUploadModalBtn = document.getElementById('closeUploadModalBtn');
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const folderInput = document.getElementById('folderInput');
    const uploadTargetFolder = document.getElementById('uploadTargetFolder');
    const uploadStatus = document.getElementById('uploadStatus');
    const uploadStatusText = document.getElementById('uploadStatusText');

    openUploadModalBtn.onclick = () => {
      uploadTargetFolder.textContent = currentPath || 'root';
      uploadModal.classList.remove('hidden');
      uploadStatus.classList.add('hidden');
    };

    closeUploadModalBtn.onclick = () => uploadModal.classList.add('hidden');
    dropZone.onclick = () => fileInput.click();

    fileInput.onchange = (e) => {
      if (e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
      }
    };

    folderInput.onchange = async (e) => {
      const files = [...e.target.files];
      if (!files.length) return;
      uploadModal.classList.remove('hidden');
      uploadStatus.classList.remove('hidden');
      let completed = 0;
      for (const file of files) {
        const relative = file.webkitRelativePath || file.name;
        uploadStatusText.textContent = `Uploading ${relative} (${completed + 1}/${files.length})...`;
        const { error } = await s3Upload(currentPath + relative, file);
        if (error) { showToast('Folder upload stopped: ' + error.message, 'error'); break; }
        completed++;
        const pct = Math.round((completed / files.length) * 100);
        document.getElementById('uploadStatusPercent').textContent = pct + '%';
        document.getElementById('uploadProgressBar').style.width = pct + '%';
      }
      if (completed === files.length) {
        showToast(`Uploaded folder with ${completed} file${completed === 1 ? '' : 's'}`);
        uploadModal.classList.add('hidden');
        loadDirectory();
      }
      folderInput.value = '';
    };

    // Drag and Drop support
    dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add('border-brand-400', 'bg-brand-500/10'); };
    dropZone.ondragleave = () => { dropZone.classList.remove('border-brand-400', 'bg-brand-500/10'); };
    dropZone.ondrop = (e) => {
      e.preventDefault();
      dropZone.classList.remove('border-brand-400', 'bg-brand-500/10');
      if (e.dataTransfer.files.length > 0) {
        handleFileUpload(e.dataTransfer.files[0]);
      }
    };

    // =====================================================================
    // NEW FILE MODAL (name a file + create & edit, or upload one instead)
    // =====================================================================
    const newFileModal = document.getElementById('newFileModal');
    const newFileNameInput = document.getElementById('newFileNameInput');
    const newFileError = document.getElementById('newFileError');
    const newFileTargetFolder = document.getElementById('newFileTargetFolder');
    const createAndEditFileBtn = document.getElementById('createAndEditFileBtn');
    const newFileDropZone = document.getElementById('newFileDropZone');
    const newFileInput = document.getElementById('newFileInput');

    document.getElementById('openNewFileModalBtn').onclick = () => {
      newFileTargetFolder.textContent = currentPath || 'root';
      newFileNameInput.value = '';
      newFileError.classList.add('hidden');
      newFileModal.classList.remove('hidden');
      setTimeout(() => newFileNameInput.focus(), 50);
    };

    document.getElementById('closeNewFileModalBtn').onclick = () => newFileModal.classList.add('hidden');
    newFileModal.addEventListener('click', (e) => { if (e.target === newFileModal) newFileModal.classList.add('hidden'); });

    function showNewFileError(msg) {
      newFileError.textContent = msg;
      newFileError.classList.remove('hidden');
    }

    function validateNewFileName(name) {
      if (!name) return 'Please enter a file name.';
      if (name.includes('/') || name.includes('\\')) return 'Use a simple file name — folders cannot be created here.';
      if (!name.includes('.')) return 'Include an extension (e.g. notes.txt) so the file can be opened in the editor.';
      return null;
    }

    newFileNameInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') createAndEditFileBtn.click(); });
    newFileNameInput.addEventListener('input', () => newFileError.classList.add('hidden'));

    createAndEditFileBtn.onclick = async () => {
      const name = newFileNameInput.value.trim();
      const err = validateNewFileName(name);
      if (err) { showNewFileError(err); return; }

      createAndEditFileBtn.disabled = true;
      const originalLabel = createAndEditFileBtn.innerHTML;
      createAndEditFileBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Creating...';
      try {
        const key = currentPath + name;
        const file = new File([''], name, { type: 'text/plain;charset=utf-8' });
        const { error } = await s3Upload(key, file);
        if (error) {
          showToast('Failed to create file: ' + error.message, 'error');
        } else {
          newFileModal.classList.add('hidden');
          showToast(`Created ${name}`);
          await loadDirectory();
          // Open the brand-new file in the editable code editor
          openFilePreview({ isFolder: false, name, key, size: 0, lastModified: new Date().toISOString(), category: 'code' });
        }
      } finally {
        createAndEditFileBtn.disabled = false;
        createAndEditFileBtn.innerHTML = originalLabel;
      }
    };

    // Upload path inside the New File modal (reuses the standard upload flow)
    newFileDropZone.onclick = () => newFileInput.click();
    newFileInput.onchange = (e) => {
      if (e.target.files.length > 0) {
        newFileModal.classList.add('hidden');
        handleFileUpload(e.target.files[0]);
      }
    };
    newFileDropZone.ondragover = (e) => { e.preventDefault(); newFileDropZone.classList.add('border-brand-400', 'bg-brand-500/10'); };
    newFileDropZone.ondragleave = () => { newFileDropZone.classList.remove('border-brand-400', 'bg-brand-500/10'); };
    newFileDropZone.ondrop = (e) => {
      e.preventDefault();
      newFileDropZone.classList.remove('border-brand-400', 'bg-brand-500/10');
      if (e.dataTransfer.files.length > 0) {
        newFileModal.classList.add('hidden');
        handleFileUpload(e.dataTransfer.files[0]);
      }
    };

    async function handleFileUpload(file) {
      const uploadPath = currentPath + file.name;
      uploadStatus.classList.remove('hidden');
      uploadStatusText.textContent = `Uploading ${file.name}...`;

      const { error } = await s3Upload(uploadPath, file);
      
      if (error) {
        showToast('Upload failed: ' + error.message, 'error');
      } else {
        showToast(`Successfully uploaded ${file.name}`);
        uploadModal.classList.add('hidden');
        loadDirectory();
      }
    }

    // New Folder Creator
    const openNewFolderModalBtn = document.getElementById('openNewFolderModalBtn');
    const newFolderNameInput = document.getElementById('newFolderNameInput');
    const confirmNewFolderBtn = document.getElementById('confirmNewFolderBtn');
    const cancelNewFolderBtn = document.getElementById('cancelNewFolderBtn');

    openNewFolderModalBtn.onclick = () => { closeMobileSidebar(); newFolderModal.classList.remove('hidden'); };
    cancelNewFolderBtn.onclick = () => newFolderModal.classList.add('hidden');

    confirmNewFolderBtn.onclick = async () => {
      const folderName = newFolderNameInput.value.trim();
      if (!folderName) return;

      const folderKey = currentPath + folderName + '/.keep';
      const dummyFile = new File([""], ".keep", { type: "text/plain" });
      
      const { error } = await s3Upload(folderKey, dummyFile);
      newFolderModal.classList.add('hidden');
      newFolderNameInput.value = '';

      if (!error) {
        showToast(`Created folder "${folderName}"`);
        loadDirectory();
      } else {
        showToast('Failed to create folder', 'error');
      }
    };

    // File Deletion Modal Handler (single file + bulk selection)
    const deleteFileBtn = document.getElementById('deleteFileBtn');
    const renderMidiMp3Btn = document.getElementById('renderMidiMp3Btn');
    if (renderMidiMp3Btn) renderMidiMp3Btn.onclick = async () => {
      if (!selectedItem || !/\.(mid|midi|kar|smf)$/i.test(selectedItem.name || '')) return;
      try { const url = await s3PresignUrl(selectedItem.key); await exportMidiToMp3(selectedItem, url); }
      catch (err) { showToast('Could not open MIDI for export: ' + err.message, 'error'); }
    };
    const deleteModalTitle = document.getElementById('deleteModalTitle');
    const deleteModalMessage = document.getElementById('deleteModalMessage');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
    let pendingBulkDeletePaths = null;

    deleteFileBtn.onclick = () => {
      if (!selectedItem) return;
      pendingBulkDeletePaths = null;
      deleteModalTitle.textContent = 'Delete File?';
      deleteModalMessage.innerHTML = `Are you sure you want to permanently delete <span class="text-slate-700 dark:text-slate-200 font-mono font-semibold">${escapeHtml(selectedItem.name)}</span> from Robo Cloud?`;
      deleteModal.classList.remove('hidden');
    };

    cancelDeleteBtn.onclick = () => deleteModal.classList.add('hidden');

    // ==================== RENAME LOGIC ====================
    let pendingRenameItem = null;
    const renameModal = document.getElementById('renameModal');
    const renameInput = document.getElementById('renameInput');
    const renameError = document.getElementById('renameError');
    const renameTargetFolder = document.getElementById('renameTargetFolder');
    const renameOldName = document.getElementById('renameOldName');

    function showRenameError(msg) {
      renameError.textContent = msg;
      renameError.classList.remove('hidden');
    }
    function openRenameModal(item) {
      if(item?.isFolder && cloudIsPartitionFolder(item.key)){showToast('Partition folders are managed in Aegis.', 'error');return;}
      if (!item) return;
      pendingRenameItem = item;
      renameInput.value = item.name;
      renameError.classList.add('hidden');
      renameTargetFolder.textContent = currentPath || 'root';
      renameOldName.querySelector('span').textContent = item.name;
      renameModal.classList.remove('hidden');
      setTimeout(() => { renameInput.focus(); renameInput.select(); }, 50);
    }
    // Rename from drawer button (file preview)
    const renameFileBtn = document.getElementById('renameFileBtn');
    if (renameFileBtn) {
      renameFileBtn.onclick = () => {
        if (!selectedItem) return;
        // if code editor dirty, warn?
        openRenameModal({ name: selectedItem.name, key: selectedItem.key, isFolder: false });
      };
    }
    document.getElementById('cancelRenameBtn').onclick = () => renameModal.classList.add('hidden');
    renameModal.addEventListener('click', (e) => { if (e.target === renameModal) renameModal.classList.add('hidden'); });
    renameInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') document.getElementById('confirmRenameBtn').click();
      if (e.key === 'Escape') renameModal.classList.add('hidden');
    });
    renameInput.addEventListener('input', () => renameError.classList.add('hidden'));

    async function handleRename() {
      if (!pendingRenameItem) return;
      const name=renameInput.value.trim();
      if (!name || /[\\/\x00-\x1f]/.test(name) || name.length>180) { showRenameError('Choose a valid name without slashes.'); return; }
      const button=document.getElementById('confirmRenameBtn');button.disabled=true;
      try {
        const folder=!!pendingRenameItem.isFolder;
        await cloudRename(pendingRenameItem.key,currentPath+name+(folder?'/':''),folder);
        renameModal.classList.add('hidden');showToast('Renamed successfully');loadDirectory();
      } catch(error) { showRenameError(error.message); }
      finally { button.disabled=false; }
    }
    document.getElementById('confirmRenameBtn').onclick = handleRename;

    // Expand folders to every object inside them so a folder delete wipes its contents
    async function collectDeletePathsForItems(items) {
      const paths = [];
      for (const it of items) {
        if (it.isFolder) {
          try {
            const { data } = await s3List(it.key);
            data.forEach(d => paths.push(d.key));
          } catch(e) { /* still delete the folder marker below */ }
          paths.push(it.key); // folder marker / trailing-slash key
        } else {
          paths.push(it.key);
        }
      }
      return paths;
    }

    async function openBulkDeleteConfirm() {
      if (selectedItems.size === 0) return;
      const count = selectedItems.size;
      const paths = await collectDeletePathsForItems([...selectedItems.values()]);
      pendingBulkDeletePaths = paths;
      deleteModalTitle.textContent = count > 1 ? `Delete ${count} Items?` : 'Delete Item?';
      deleteModalMessage.innerHTML = `Are you sure you want to permanently delete <span class="text-slate-700 dark:text-slate-200 font-semibold">${count} item${count === 1 ? '' : 's'}</span> from Robo Cloud?<br><span class="text-slate-600 dark:text-slate-500 text-[11px]">Folders will delete everything inside them.</span>`;
      deleteModal.classList.remove('hidden');
    }

    document.getElementById('deleteSelectedBtn').onclick = () => openBulkDeleteConfirm();

    confirmDeleteBtn.onclick = async () => {
      deleteModal.classList.add('hidden');

      // Bulk delete of selected files/folders
      if (pendingBulkDeletePaths) {
        const paths = pendingBulkDeletePaths;
        pendingBulkDeletePaths = null;
        const count = selectedItems.size;
        const { error } = await s3Remove(paths);
        if (!error) {
          selectionMode = false; // done selecting — exit selection mode after deleting
          clearSelection();
          closeExpandedPreview();
          destroyPdfViewer(pdfViewerDrawer); pdfViewerDrawer = null;
          if (codeEditor) { destroyAceEditor(codeEditor); codeEditor = null; codeEditorDirty = false; codeFallbackBox = null; }
          previewDrawer.classList.add('translate-x-full');
          if (audioElement) audioElement.pause();
          showToast(`Deleted ${count} item${count === 1 ? '' : 's'}`);
          loadDirectory();
        } else {
          showToast('Failed to delete files', 'error');
        }
        return;
      }

      // Single-file delete from the preview drawer
      if (!selectedItem) return;
      const { error } = await s3Remove([selectedItem.key]);
      if (!error) {
        showToast(`Deleted ${escapeHtml(selectedItem.name)}`);
        closeExpandedPreview();
        destroyPdfViewer(pdfViewerDrawer); pdfViewerDrawer = null;
        if (codeEditor) { destroyAceEditor(codeEditor); codeEditor = null; codeEditorDirty = false; codeFallbackBox = null; }
        previewDrawer.classList.add('translate-x-full');
        if (audioElement) audioElement.pause();
        loadDirectory();
      } else {
        showToast('Failed to delete file', 'error');
      }
    };

    // Copy-to-clipboard helper (fallback method works everywhere)
    function copyTextToClipboard(text) {
      const tempInput = document.createElement('textarea');
      tempInput.value = text;
      document.body.appendChild(tempInput);
      tempInput.select();
      document.execCommand('copy');
      document.body.removeChild(tempInput);
    }

    // Copy Direct URL handlers (drawer action button, drawer metadata button, expanded header)
    document.getElementById('copySignedUrlBtn').onclick = async () => {
      if (!selectedItem) return;
      copyTextToClipboard(await s3PresignUrl(selectedItem.key));
      showToast('Direct URL copied to clipboard!');
    };

    document.getElementById('copyDirectUrlBtn').onclick = () => {
      const url = document.getElementById('metaFileUrl').href;
      if (!url || url === '#') return;
      copyTextToClipboard(url);
      showToast('Direct URL copied to clipboard!');
    };

    document.getElementById('expandedCopyUrlBtn').onclick = () => {
      if (!expandedExternalLink.href || expandedExternalLink.href === '#') return;
      copyTextToClipboard(expandedExternalLink.href);
      showToast('Direct URL copied to clipboard!');
    };

    // Notification Toast System
    function showToast(msg, type = 'success') {
      const toast = document.getElementById('toastNotification');
      const toastMessage = document.getElementById('toastMessage');
      const toastIcon = document.getElementById('toastIcon');

      toastMessage.textContent = msg;
      if (type === 'error') {
        toastIcon.className = 'fa-solid fa-circle-xmark text-rose-400 text-base';
      } else if (type === 'info') {
        toastIcon.className = 'fa-solid fa-circle-info text-brand-300 text-base';
      } else {
        toastIcon.className = 'fa-solid fa-circle-check text-emerald-400 text-base';
      }

      toast.classList.remove('translate-y-20', 'opacity-0');
      setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
      }, 3500);
    }

    // View Switcher Handlers
    document.getElementById('viewGridBtn').onclick = () => {
      viewMode = 'grid';
      document.getElementById('viewGridBtn').className = 'px-3 py-1.5 rounded-full text-xs font-bold text-slate-900 dark:text-slate-100 bg-slate-900/5 dark:bg-white/15 shadow-sm transition-all';
      document.getElementById('viewListBtn').className = 'px-3 py-1.5 rounded-full text-xs font-bold text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-all';
      renderExplorer();
    };

    document.getElementById('viewListBtn').onclick = () => {
      viewMode = 'list';
      document.getElementById('viewListBtn').className = 'px-3 py-1.5 rounded-full text-xs font-bold text-slate-900 dark:text-slate-100 bg-slate-900/5 dark:bg-white/15 shadow-sm transition-all';
      document.getElementById('viewGridBtn').className = 'px-3 py-1.5 rounded-full text-xs font-bold text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-all';
      renderExplorer();
    };

    // =====================================================================
    // MULTI-SELECT & MASS DELETE (files and/or folders)
    // =====================================================================
    const selectToggleBtn = document.getElementById('selectToggleBtn');
    const selectionBar = document.getElementById('selectionBar');
    const selectionCount = document.getElementById('selectionCount');

    function updateSelectionUI() {
      const count = selectedItems.size;
      selectionCount.textContent = count;
      selectionBar.classList.toggle('hidden', count === 0);
      selectToggleBtn.setAttribute('aria-pressed', selectionMode ? 'true' : 'false');
      if (selectionMode) {
        selectToggleBtn.className = 'is-selection-active px-3 py-1.5 rounded-full text-xs font-bold bg-black text-white transition-all';
        selectToggleBtn.innerHTML = '<i class="fa-solid fa-square-check"></i>';
      } else {
        selectToggleBtn.className = 'px-3 py-1.5 rounded-full text-xs font-bold text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-all';
        selectToggleBtn.innerHTML = '<i class="fa-regular fa-square-check"></i>';
      }
    }

    selectToggleBtn.onclick = () => {
      selectionMode = !selectionMode;
      if (!selectionMode) selectedItems.clear();
      updateSelectionUI();
      renderExplorer();
    };

    function toggleSelection(item) {
      if (selectedItems.has(item.key)) selectedItems.delete(item.key);
      else selectedItems.set(item.key, item);
      updateSelectionUI();
      renderExplorer();
    }

    function clearSelection() {
      selectedItems.clear();
      updateSelectionUI();
      renderExplorer();
    }

    document.getElementById('clearSelectionBtn').onclick = () => clearSelection();

    // Category Sidebar Buttons
    document.querySelectorAll('.cat-btn').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('.cat-btn').forEach(b => {
          b.className = 'cat-btn w-full flex items-center gap-3 px-3 py-2 rounded-full text-xs font-bold text-slate-500 dark:text-slate-400 hover:bg-slate-900/[0.04] dark:hover:bg-white/10 hover:text-slate-700 dark:hover:text-slate-200 transition-colors';
        });
        btn.className = 'cat-btn w-full flex items-center gap-3 px-3 py-2 rounded-full text-xs font-bold bg-brand-500/10 text-brand-300 border border-brand-400/20';
        activeCategory = btn.getAttribute('data-cat');
        if (activeCategory === 'recent' || activeCategory === 'all') currentPath = '';
        closeStoragePage();
        renderExplorer();
        closeMobileSidebar(); // picking a category on a phone closes the overlay
      };
    });

    // Sidebar New menu
    const sidebarNewBtn = document.getElementById('sidebarNewBtn');
    const sidebarNewMenu = document.getElementById('sidebarNewMenu');
    // Portal the menu to <body>; nested backdrop filters cannot blur through the sidebar's own glass layer.
    document.body.appendChild(sidebarNewMenu);
    sidebarNewMenu.classList.remove('hidden');
    sidebarNewBtn.onclick = (e) => {
      e.stopPropagation();
      const opening = !sidebarNewMenu.classList.contains('is-visible');
      sidebarNewMenu.classList.toggle('is-visible', opening);
      sidebarNewBtn.classList.toggle('is-open', opening);
      if (opening) {
        const r = sidebarNewBtn.getBoundingClientRect();
        sidebarNewMenu.style.left = r.left + 'px';
        sidebarNewMenu.style.top = (r.bottom + 8) + 'px';
        sidebarNewMenu.style.width = r.width + 'px';
      }
    };
    sidebarNewMenu.onclick = (e) => {
      const action = e.target.closest('[data-new-action]')?.dataset.newAction;
      if (!action) return;
      sidebarNewMenu.classList.remove('is-visible'); sidebarNewBtn.classList.remove('is-open');
      if (action === 'upload') document.getElementById('openUploadModalBtn').click();
      if (action === 'upload-folder') document.getElementById('folderInput').click();
      if (action === 'folder') document.getElementById('openNewFolderModalBtn').click();
      if (action === 'file') document.getElementById('openNewFileModalBtn').click();
    };
    document.addEventListener('click', (e) => {
      if (!sidebarNewMenu.contains(e.target) && e.target !== sidebarNewBtn) {
        sidebarNewMenu.classList.remove('is-visible'); sidebarNewBtn.classList.remove('is-open');
      }
    });

    // Search Input
    searchInput.oninput = (e) => {
      searchQuery = e.target.value.trim();
      clearSearchBtn.classList.toggle('hidden', searchQuery === '');
      closeStoragePage();
      renderExplorer();
    };

    clearSearchBtn.onclick = () => {
      searchInput.value = '';
      searchQuery = '';
      clearSearchBtn.classList.add('hidden');
      renderExplorer();
    };

    // Drawer Close
    document.getElementById('closePreviewBtn').onclick = () => {
      if (previewDrawer.classList.contains('preview-info-over-modal')) {
        previewDrawer.classList.add('translate-x-full');
        previewDrawer.classList.remove('preview-info-over-modal');
        return;
      }
      if (codeEditor && codeEditorDirty) {
        if (!confirm('You have unsaved changes in the code editor. Close without saving?')) return;
      }
      closeExpandedPreview();
      destroyPdfViewer(pdfViewerDrawer); pdfViewerDrawer = null;
      if (codeEditor) { destroyAceEditor(codeEditor); codeEditor = null; codeEditorDirty = false; codeFallbackBox = null; }
      previewDrawer.classList.add('translate-x-full');
      if (audioElement) audioElement.pause();
    };

    // Refresh Button
    document.getElementById('refreshBtn').onclick = () => loadDirectory();

    // Storage tab -> full Drive-style Storage page
    document.getElementById('storageTabBtn').onclick = () => {
      openStoragePage();
      closeMobileSidebar();
    };

    // Storage page: column sorting
    document.getElementById('storageSortName').onclick = () => {
      storageSort = { key: 'name', dir: storageSort.key === 'name' && storageSort.dir === 'asc' ? 'desc' : 'asc' };
      renderStoragePage();
    };
    document.getElementById('storageSortSize').onclick = () => {
      storageSort = { key: 'size', dir: storageSort.key === 'size' && storageSort.dir === 'desc' ? 'asc' : 'desc' };
      renderStoragePage();
    };

    // =====================================================================
    // MOBILE: hamburger opens the left sidebar as a slide-in overlay
    // =====================================================================
    const sidebarAside = document.getElementById('sidebarAside');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');
    function openMobileSidebar() { sidebarAside.classList.add('sidebar-open'); sidebarBackdrop.classList.remove('hidden'); }
    function closeMobileSidebar() { sidebarAside.classList.remove('sidebar-open'); sidebarBackdrop.classList.add('hidden'); }
    document.getElementById('openSidebarBtn').onclick = openMobileSidebar;
    sidebarBackdrop.onclick = closeMobileSidebar;
    // If the viewport grows to desktop size, drop the mobile overlay state
    window.matchMedia('(min-width: 768px)').addEventListener?.('change', (e) => { if (e.matches) closeMobileSidebar(); });

    // Live auto-refresh: silently re-poll the bucket and update the list when something changes
    let autoRefreshTimer = null;
    function startAutoRefresh() {
      if (autoRefreshTimer) clearInterval(autoRefreshTimer);
      autoRefreshTimer = setInterval(async () => {
        // Skip while the user is previewing / editing (drawer or any modal open)
        if (!previewDrawer.classList.contains('translate-x-full')) return;
        if (selectionMode) return;
        if (!expandedPreviewModal.classList.contains('hidden')) return;
        if (!uploadModal.classList.contains('hidden') || !newFolderModal.classList.contains('hidden') || !deleteModal.classList.contains('hidden') || !renameModal.classList.contains('hidden')) return;
        try {
          const { data, error } = await s3List(currentPath);
          if (error) return;
          const current = JSON.stringify(allS3Items.map(i => i.key + ':' + i.size + ':' + i.lastModified));
          const fresh = JSON.stringify(data.map(i => i.key + ':' + i.size + ':' + i.lastModified));
          if (current !== fresh) {
            allS3Items = data;
            renderExplorer();
            refreshBucketStorage();
          }
        } catch(e) { /* keep polling */ }
      }, 8000);
    }

    // Application Initialization — run as soon as the DOM is parsed instead of waiting for
    // window.onload (which can be stalled for a long time by slow CDN scripts and left the
    // explorer empty on first load). Retries + live refresh handle the rest.
    let bootstrapped = false;
    function bootstrap() {
      if (bootstrapped) return;
      bootstrapped = true;
      loadDirectory();
      startAutoRefresh();
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', bootstrap);
    } else {
      bootstrap();
    }
    window.addEventListener('load', bootstrap); // safety net (idempotent)
  
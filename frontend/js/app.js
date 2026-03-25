/**
 * Smart Memo — 主应用逻辑
 * 通过 HTTP API 与后端通信；失去连接时优雅降级到 localStorage
 */
import * as API from './api.js';
import { initVoice, toggleVoice, startBroadcast, stopBroadcast,
         pauseBroadcast, resumeBroadcast, nextItem, prevItem,
         isPaused, getProgress } from './voice.js';

// ── 状态 ────────────────────────────────────────────────────────────────────
let memos = [];
let currentCategory = 'all';
let currentSchedules = [];
let broadcastActive = false;

// ── DOM 辅助 ────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const CATEGORY_META = {
  work:     { name: '工作',   icon: 'fa-briefcase' },
  life:     { name: '生活',   icon: 'fa-home'       },
  study:    { name: '学习',   icon: 'fa-book'       },
  health:   { name: '健康',   icon: 'fa-heart'      },
  shopping: { name: '购物',   icon: 'fa-shopping-cart' },
  ideas:    { name: '想法',   icon: 'fa-lightbulb'  },
  travel:   { name: '出行',   icon: 'fa-plane'      },
  other:    { name: '其他',   icon: 'fa-tag'        },
};

const PRIORITY_LABEL = { urgent: '紧急', high: '高', medium: '中', low: '低' };

// ── 初始化 ──────────────────────────────────────────────────────────────────
async function init() {
  // 日期选择器默认今天
  const today = new Date().toISOString().slice(0, 10);
  $('scheduleDate').value = today;

  // 检测 API
  const online = await API.checkHealth();
  renderApiBadge(online);

  // 加载备忘
  await loadMemos();

  // 语音
  initVoice(
    text => { $('memoInput').value = text; onInputChange(); },
    err  => showToast('语音识别失败: ' + err),
  );

  // 输入防抖分类提示
  let debounce;
  $('memoInput').addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(onInputChange, 400);
  });

  // 搜索防抖
  let searchDebounce;
  $('searchInput').addEventListener('input', () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(doSearch, 350);
  });

  // 播报进度定时更新
  setInterval(updateBroadcastProgress, 500);
}

// ── API 状态徽章 ─────────────────────────────────────────────────────────────
function renderApiBadge(online) {
  const el = $('apiBadge');
  if (!el) return;
  el.className = `api-badge ${online ? 'online' : 'offline'}`;
  el.innerHTML = online
    ? '<i class="fas fa-circle"></i> MCP 在线'
    : '<i class="fas fa-circle"></i> 离线模式';
}

// ── 加载备忘录 ──────────────────────────────────────────────────────────────
async function loadMemos() {
  try {
    const data = await API.getMemos({ category: currentCategory });
    memos = data.memos || [];
    renderMemos(memos);
    renderStats(data.stats || {});
    renderCategoryBadges(data.stats?.by_category || {});
  } catch {
    // 离线回退
    const local = JSON.parse(localStorage.getItem('sm_memos') || '[]');
    memos = local;
    renderMemos(local);
  }
}

// ── 分类筛选 ─────────────────────────────────────────────────────────────────
window.filterByCategory = async function(category) {
  currentCategory = category;
  document.querySelectorAll('.category-item').forEach(el => {
    el.classList.toggle('active', el.dataset.category === category);
  });
  await loadMemos();
};

// ── 输入变化 → 实时分类提示 ──────────────────────────────────────────────────
async function onInputChange() {
  const text = $('memoInput').value.trim();
  const hintEl = $('categoryHint');
  if (!text) { hintEl.innerHTML = '<span>AI 建议分类：</span>'; return; }

  try {
    const r = await API.classifyText(text);
    const meta = CATEGORY_META[r.category] || CATEGORY_META.other;
    hintEl.innerHTML = `
      <span>AI 建议分类：</span>
      <span class="hint-tag"><i class="fas ${meta.icon}"></i> ${meta.name}
        ${r.confidence > 0 ? `(${r.confidence}%)` : ''}
      </span>
      ${r.time_info ? `<span style="color:#667eea;font-size:.8rem"><i class="fas fa-clock"></i> ${r.time_info.date}</span>` : ''}
    `;
  } catch {
    hintEl.innerHTML = '';
  }
}

// ── 添加备忘录 ───────────────────────────────────────────────────────────────
window.addMemo = async function() {
  const input = $('memoInput');
  const content = input.value.trim();
  if (!content) { showToast('请输入备忘内容'); return; }

  const btn = $('addBtn');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 处理中...';

  try {
    const data = await API.addMemo(content);
    if (data.success) {
      input.value = '';
      $('categoryHint').innerHTML = '<span>AI 建议分类：</span>';
      showToast('已添加 ✓');
      await loadMemos();
    } else {
      showToast('添加失败，请重试');
    }
  } catch {
    // 离线本地保存
    const local = JSON.parse(localStorage.getItem('sm_memos') || '[]');
    local.unshift({ id: Date.now(), content, category: 'other', created_at: new Date().toISOString() });
    localStorage.setItem('sm_memos', JSON.stringify(local));
    memos = local;
    renderMemos(local);
    showToast('已离线保存');
    input.value = '';
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-plus"></i> 添加备忘录';
  }
};

// ── 删除备忘录 ───────────────────────────────────────────────────────────────
window.deleteMemo = async function(id) {
  try {
    await API.deleteMemo(id);
    showToast('已删除');
    await loadMemos();
  } catch {
    showToast('删除失败');
  }
};

// ── 搜索 ─────────────────────────────────────────────────────────────────────
async function doSearch() {
  const q = $('searchInput').value.trim();
  if (!q) { await loadMemos(); return; }
  try {
    const data = await API.searchMemos(q);
    renderMemos(data.results || []);
  } catch {
    const filtered = memos.filter(m => m.content.includes(q));
    renderMemos(filtered);
  }
}

// ── 生成行程 ─────────────────────────────────────────────────────────────────
window.generateSchedule = async function() {
  const date = $('scheduleDate').value;
  const btn = $('genBtn');
  btn.disabled = true;
  btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
  try {
    const data = await API.generateSchedule(date);
    currentSchedules = data.schedules || [];
    renderSchedule(currentSchedules);
    showToast(`生成了 ${currentSchedules.length} 条行程`);
  } catch {
    // 离线：从本地备忘中提取有时间信息的
    currentSchedules = memos
      .filter(m => m.scheduled_at && m.scheduled_at.startsWith(date))
      .map(m => ({ title: m.content.slice(0, 30), description: m.content,
                   time_slot: m.scheduled_at.slice(11, 16), priority: m.priority }));
    renderSchedule(currentSchedules);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-magic"></i> 生成行程';
  }
};

// ── 行程播报 ─────────────────────────────────────────────────────────────────
window.toggleBroadcast = function() {
  if (broadcastActive) {
    stopBroadcast();
    broadcastActive = false;
    $('broadcastPanel').classList.remove('active');
  } else {
    if (!currentSchedules.length) { showToast('请先生成行程'); return; }
    const started = startBroadcast(currentSchedules, {
      rate:   parseFloat($('bcRate').value),
      volume: parseFloat($('bcVolume').value),
    });
    if (started) {
      broadcastActive = true;
      $('broadcastPanel').classList.add('active');
    } else {
      showToast('浏览器不支持语音播报');
    }
  }
};

window.pauseResumeBroadcast = function() {
  const icon = $('pauseIcon');
  if (isPaused()) { resumeBroadcast(); icon.className = 'fas fa-pause'; }
  else            { pauseBroadcast();  icon.className = 'fas fa-play';  }
};
window.stopBroadcast_  = function() { stopBroadcast(); broadcastActive = false; $('broadcastPanel').classList.remove('active'); };
window.nextBroadcast   = nextItem;
window.prevBroadcast   = prevItem;

function updateBroadcastProgress() {
  if (!broadcastActive) return;
  $('bcFill').style.width = getProgress() + '%';
  $('bcStatus').textContent = `第 ${Math.ceil(getProgress() / 100 * (currentSchedules.length || 1))} / ${currentSchedules.length} 条`;
}

// ── 渲染 ─────────────────────────────────────────────────────────────────────
function renderMemos(list) {
  const el = $('memoList');
  if (!list.length) {
    el.innerHTML = `<div class="empty-state">
      <i class="fas fa-clipboard-list"></i>
      <p>还没有备忘录</p>
      <p>在左侧输入框中添加第一条备忘吧！</p>
    </div>`;
    return;
  }

  el.innerHTML = list.map(m => {
    const meta = CATEGORY_META[m.category] || CATEGORY_META.other;
    const date = m.created_at ? m.created_at.slice(0, 16).replace('T', ' ') : '';
    const priorityClass = m.priority || 'medium';
    return `
      <div class="memo-card ${m.category}">
        <div class="memo-head">
          <span class="cat-badge ${m.category}">
            <i class="fas ${meta.icon}"></i> ${meta.name}
            ${m.confidence > 0 ? `<span style="opacity:.7;font-size:.75rem">${m.confidence}%</span>` : ''}
          </span>
          <div class="memo-actions">
            <button onclick="deleteMemo(${m.id})" title="删除"><i class="fas fa-trash-alt"></i></button>
          </div>
        </div>
        <div class="memo-content">${escHtml(m.content)}</div>
        <div class="memo-meta">
          <span>
            <span class="priority-dot ${priorityClass}"></span>
            ${PRIORITY_LABEL[priorityClass] || '中'} 优先级
            ${m.tags && m.tags.length ? ' · ' + m.tags.map(t => `<span style="background:#f0f0ff;padding:1px 6px;border-radius:8px;font-size:.75rem">${escHtml(t)}</span>`).join(' ') : ''}
          </span>
          <span>${date}</span>
        </div>
      </div>`;
  }).join('');
}

function renderStats(stats) {
  $('totalCount').textContent   = stats.total || 0;
  $('scheduleCount').textContent = stats.today_schedules || 0;
  const cats = Object.keys(stats.by_category || {}).length;
  $('catCount').textContent = cats;
}

function renderCategoryBadges(byCat) {
  const total = Object.values(byCat).reduce((a, b) => a + b, 0);
  document.querySelectorAll('.category-item').forEach(el => {
    const cat = el.dataset.category;
    const countEl = el.querySelector('.badge');
    if (!countEl) return;
    countEl.textContent = cat === 'all' ? total : (byCat[cat] || 0);
  });
}

function renderSchedule(schedules) {
  const el = $('scheduleTimeline');
  if (!schedules.length) {
    el.innerHTML = `<div class="no-schedule">
      <i class="fas fa-calendar-times"></i>
      <p>暂无行程安排</p>
      <p>添加含时间的备忘后点击「生成行程」</p>
    </div>`;
    return;
  }

  const sorted = [...schedules].sort((a, b) =>
    (a.time_slot || '99:99').localeCompare(b.time_slot || '99:99'));

  el.innerHTML = sorted.map(s => `
    <div class="time-slot ${s.priority || 'medium'}">
      <div class="time-label">
        <i class="fas fa-clock"></i>
        ${s.time_slot || '待定'}
      </div>
      <div class="time-desc">${escHtml(s.title)}
        ${s.description && s.description !== s.title
          ? `<br><small style="color:#888">${escHtml(s.description)}</small>` : ''}
      </div>
    </div>`).join('');
}

// ── 工具函数 ─────────────────────────────────────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
            .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

let toastTimer;
function showToast(msg) {
  const el = $('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2800);
}
window.showToast = showToast;

// ── 语音输入按钮 ─────────────────────────────────────────────────────────────
window.toggleVoiceInput = function() {
  toggleVoice($('voiceBtn'), $('voiceStatus'), $('voiceStatusText'));
};

// ── 启动 ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);

// ===== 页面导航 =====
const navItems = document.querySelectorAll('.nav-item');
const pages = document.querySelectorAll('.page');
const pageTitle = document.getElementById('pageTitle');

const pageTitles = {
    dashboard: '系统概览',
    crawl: '数据采集',
    topic: '主题挖掘',
    sentiment: '情感分析',
    visual: '数据可视化'
};

navItems.forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const target = item.dataset.page;

        navItems.forEach(n => n.classList.remove('active'));
        item.classList.add('active');

        pages.forEach(p => p.classList.remove('active'));
        document.getElementById('page-' + target).classList.add('active');

        pageTitle.textContent = pageTitles[target];

        if (document.getElementById('sidebar').classList.contains('open')) {
            document.getElementById('sidebar').classList.remove('open');
        }

        initPageCharts(target);
    });
});

document.getElementById('menuToggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
});

const trendActions = document.querySelector('#trendChart')?.previousElementSibling?.querySelector('.card-actions');
if (trendActions) {
    trendActions.innerHTML = '<span class="badge badge-pending">最近7个有数据日期</span>';
}

function updateTime() {
    const now = new Date();
    const str = now.getFullYear() + '/' +
        String(now.getMonth() + 1).padStart(2, '0') + '/' +
        String(now.getDate()).padStart(2, '0') + ' ' +
        String(now.getHours()).padStart(2, '0') + ':' +
        String(now.getMinutes()).padStart(2, '0') + ':' +
        String(now.getSeconds()).padStart(2, '0');
    document.getElementById('currentTime').textContent = str;
}
updateTime();
setInterval(updateTime, 1000);

document.querySelectorAll('.card-actions').forEach(group => {
    group.querySelectorAll('.btn-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            group.querySelectorAll('.btn-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
});

// ===== 通用 =====
const colors = {
    primary: '#4F46E5', blue: '#0EA5E9', green: '#10B981',
    yellow: '#F59E0B', red: '#EF4444', purple: '#8B5CF6', pink: '#EC4899'
};

const chartInstances = {};
function getChart(id) {
    if (chartInstances[id]) chartInstances[id].dispose();
    const dom = document.getElementById(id);
    if (!dom) return null;
    const chart = echarts.init(dom);
    chartInstances[id] = chart;
    return chart;
}
window.addEventListener('resize', () => {
    Object.values(chartInstances).forEach(c => c && c.resize());
});

let currentTaskId = null;

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[ch]));
}

function showError(error, fallback = '操作失败，请稍后重试') {
    const message = error && error.message ? error.message : fallback;
    console.error(error);
    alert(message || fallback);
}

function toNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
}

async function api(url, opts = {}) {
    const resp = await fetch(url, opts);
    const text = await resp.text();
    let data = {};

    if (text) {
        try {
            data = JSON.parse(text);
        } catch (e) {
            throw new Error('服务器返回了无法解析的数据');
        }
    }

    if (!resp.ok) {
        throw new Error(data.error || `请求失败 (${resp.status})`);
    }

    return data;
}

// ===== 加载数据集下拉框 =====
async function loadDatasets() {
    let data = [];
    try {
        data = await api('/api/datasets');
    } catch (e) {
        showError(e, '加载数据集失败');
        return;
    }

    const selected = currentTaskId && data.some(d => String(d.id) === String(currentTaskId))
        ? String(currentTaskId)
        : (data[0] ? String(data[0].id) : '');

    document.querySelectorAll('select[data-role="dataset"]').forEach(sel => {
        sel.innerHTML = '';
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = '请先采集数据';
        sel.appendChild(placeholder);

        data.forEach(d => {
            const option = document.createElement('option');
            option.value = d.id;
            option.textContent = d.label;
            sel.appendChild(option);
        });
        sel.value = selected;
    });
    if (selected) currentTaskId = parseInt(selected);
}

// ===== 仪表盘 =====
async function initDashboard() {
    try {
        const stats = await api('/api/dashboard/stats');
        document.getElementById('totalData').textContent = stats.total_data.toLocaleString();
        document.querySelectorAll('.stat-value')[1].textContent = stats.hot_topics;
        document.querySelectorAll('.stat-value')[2].textContent = stats.positive_pct + '%';
        document.querySelectorAll('.stat-value')[3].textContent = stats.negative_pct + '%';
    } catch (e) { /* 无数据时保持默认 */ }

    // 情感趋势
    try {
        const trend = await api('/api/dashboard/trend');
        const chart = getChart('trendChart');
        if (chart && trend.days.length) {
            chart.setOption({
                tooltip: { trigger: 'axis' },
                legend: { data: ['正面', '中性', '负面'], right: 20, top: 0 },
                grid: { left: 40, right: 20, top: 40, bottom: 42 },
                xAxis: {
                    type: 'category',
                    data: trend.days,
                    boundaryGap: false,
                    axisLabel: {
                        interval: 0,
                        hideOverlap: false,
                        formatter: value => String(value || '').slice(5)
                    }
                },
                yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } } },
                series: [
                    { name: '正面', type: 'line', smooth: true, data: trend.positive,
                      itemStyle: { color: colors.green },
                      areaStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(16,185,129,0.25)'},{offset:1,color:'rgba(16,185,129,0.02)'}]) } },
                    { name: '中性', type: 'line', smooth: true, data: trend.neutral,
                      itemStyle: { color: colors.yellow },
                      areaStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(245,158,11,0.15)'},{offset:1,color:'rgba(245,158,11,0.02)'}]) } },
                    { name: '负面', type: 'line', smooth: true, data: trend.negative,
                      itemStyle: { color: colors.red },
                      areaStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(239,68,68,0.15)'},{offset:1,color:'rgba(239,68,68,0.02)'}]) } },
                ]
            });
        }
    } catch (e) {}

    // 情感分布饼图
    try {
        const stats = await api('/api/dashboard/stats');
        const pie = getChart('pieChart');
        if (pie) {
            pie.setOption({
                tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
                legend: { bottom: 10, itemGap: 20 },
                series: [{
                    type: 'pie', radius: ['45%', '70%'], center: ['50%', '45%'],
                    itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 3 },
                    label: { show: false },
                    emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } },
                    data: [
                        { value: stats.positive_pct, name: '正面', itemStyle: { color: colors.green } },
                        { value: 100 - stats.positive_pct - stats.negative_pct, name: '中性', itemStyle: { color: colors.yellow } },
                        { value: stats.negative_pct, name: '负面', itemStyle: { color: colors.red } },
                    ]
                }]
            });
        }
    } catch (e) {}

    // 词云
    try {
        const words = await api('/api/dashboard/wordcloud');
        const wc = getChart('wordCloudChart');
        if (wc && words.length) {
            wc.setOption({
                series: [{
                    type: 'wordCloud', shape: 'circle', gridSize: 12,
                    sizeRange: [14, 48], rotationRange: [-30, 30], rotationStep: 15,
                    textStyle: {
                        fontFamily: 'Microsoft YaHei',
                        color: function() {
                            const cs = [colors.primary, colors.blue, colors.green, colors.yellow, colors.red, colors.purple, colors.pink];
                            return cs[Math.floor(Math.random() * cs.length)];
                        }
                    },
                    data: words
                }]
            });
        }
    } catch (e) {}

    // 热点排行
    try {
        const topics = await api('/api/dashboard/hot_topics');
        const tbody = document.querySelector('#page-dashboard .data-table tbody');
        if (tbody && topics.length) {
            tbody.innerHTML = topics.map((t, i) => {
                const rankClass = i < 3 ? ` rank-${i+1}` : '';
                const tagClass = t.sentiment_key === 'positive' ? 'tag-positive' :
                                 t.sentiment_key === 'negative' ? 'tag-negative' : 'tag-neutral';
                const score = Math.max(0, Math.min(100, toNumber(t.heat_score)));
                const tip = t.heat_components
                    ? `评论热度 ${t.heat_components.comment_heat_norm}，评论点赞 ${t.heat_components.comment_likes_norm}`
                    : `热度分 ${score.toFixed(1)}`;
                return `<tr>
                    <td><span class="rank${rankClass}">${i+1}</span></td>
                    <td>${escapeHtml(t.keyword)}</td>
                    <td>${toNumber(t.count).toLocaleString()}</td>
                    <td><span class="tag ${tagClass}">${escapeHtml(t.sentiment)}</span></td>
                    <td>
                        <div class="heat-cell" title="${escapeHtml(tip)}">
                            <div class="heat-bar"><div class="heat-fill" style="width:${score}%"></div></div>
                            <span class="heat-score">${score.toFixed(1)}</span>
                        </div>
                    </td>
                </tr>`;
            }).join('');
        }
    } catch (e) {}
}

// ===== 数据采集 =====
let crawlTimer = null;
let crawlInProgress = false;

function setCrawlStatus(message, type = '') {
    const statusEl = document.getElementById('crawlStatus');
    if (!statusEl) return;
    statusEl.style.display = message ? 'block' : 'none';
    statusEl.className = `crawl-status ${type}`.trim();
    statusEl.textContent = message || '';
}

function setCookieStatus(message, type = '') {
    const statusEl = document.getElementById('cookieStatus');
    if (!statusEl) return;
    statusEl.style.display = message ? 'block' : 'none';
    statusEl.className = `crawl-status ${type}`.trim();
    statusEl.textContent = message || '';
}

function setImportStatus(message, type = '') {
    const statusEl = document.getElementById('importStatus');
    if (!statusEl) return;
    statusEl.style.display = message ? 'block' : 'none';
    statusEl.className = `crawl-status ${type}`.trim();
    statusEl.textContent = message || '';
}

function updateCookieBadge(status) {
    const badge = document.getElementById('cookieBadge');
    if (!badge) return;
    if (status && status.configured) {
        badge.textContent = '已配置';
        badge.className = 'badge badge-done';
    } else {
        badge.textContent = '未配置';
        badge.className = 'badge badge-pending';
    }
}

async function loadCookieStatus(showMessage = false) {
    try {
        const status = await api('/api/crawl/cookie?platform=bilibili');
        updateCookieBadge(status);
        if (showMessage) {
            const message = status.configured
                ? `B站 Cookie 已配置，长度 ${status.length}，预览：${status.preview}`
                : '尚未配置 B站 Cookie';
            setCookieStatus(message, status.configured ? 'ok' : '');
        }
    } catch (e) {
        setCookieStatus(e.message || '读取 B站 Cookie 状态失败', 'fail');
    }
}

function setCrawlControlsLocked(locked) {
    crawlInProgress = locked;
    const startBtn = document.getElementById('startCrawlBtn');
    const checkBtn = document.getElementById('checkCrawlerBtn');
    if (startBtn) startBtn.disabled = locked;
    if (checkBtn) checkBtn.disabled = locked;
}

document.getElementById('saveCookieBtn').addEventListener('click', async function() {
    const cookieInput = document.getElementById('bilibiliCookie');
    const cookie = cookieInput.value.trim();
    if (!cookie) { alert('请先粘贴 B站 Cookie'); return; }

    this.disabled = true;
    setCookieStatus('正在保存 B站 Cookie...', '');
    try {
        const status = await api('/api/crawl/cookie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ platform: 'bilibili', cookie })
        });
        cookieInput.value = '';
        updateCookieBadge(status);
        setCookieStatus(`B站 Cookie 已保存，长度 ${status.length}，预览：${status.preview}`, 'ok');
    } catch (e) {
        setCookieStatus(e.message || '保存 B站 Cookie 失败', 'fail');
    } finally {
        this.disabled = false;
    }
});

document.getElementById('clearCookieBtn').addEventListener('click', async function() {
    if (!confirm('确定清除已保存的 B站 Cookie？')) return;
    this.disabled = true;
    try {
        const status = await api('/api/crawl/cookie?platform=bilibili', { method: 'DELETE' });
        updateCookieBadge(status);
        setCookieStatus('B站 Cookie 已清除。', '');
    } catch (e) {
        setCookieStatus(e.message || '清除 B站 Cookie 失败', 'fail');
    } finally {
        this.disabled = false;
    }
});

document.getElementById('checkCrawlerBtn').addEventListener('click', async function() {
    const keyword = document.getElementById('keyword').value.trim();
    if (!keyword) { alert('请先输入关键词'); return; }

    this.disabled = true;
    setCrawlStatus('正在检测B站采集接口...', '');
    try {
        const res = await api('/api/crawl/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ platform: 'bilibili', keyword })
        });
        const type = res.ok ? 'ok' : 'fail';
        const source = res.source ? `${res.source}：` : '';
        const note = res.note ? ` ${res.note}` : '';
        setCrawlStatus(`${source}${res.message}。本次检测样本数：${toNumber(res.sample_count)}。${note}`, type);
    } catch (e) {
        setCrawlStatus(e.message || '检测失败', 'fail');
    } finally {
        this.disabled = false;
    }
});

document.getElementById('crawlForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    if (crawlInProgress) {
        alert('当前已有采集任务在运行，请等待它完成后再开始新的任务。');
        return;
    }

    const keyword = document.getElementById('keyword').value.trim();
    if (!keyword) { alert('请输入关键词'); return; }

    const target = parseInt(document.getElementById('crawlCount').value) || 500;

    let res;
    try {
        setCrawlControlsLocked(true);
        setCrawlStatus('B站采集任务已创建，正在等待返回数据...', '');
        res = await api('/api/crawl/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ platform: 'bilibili', keyword, target_count: target })
        });
    } catch (e) {
        showError(e, '创建采集任务失败');
        setCrawlControlsLocked(false);
        return;
    }

    if (res.error) {
        alert(res.error);
        setCrawlControlsLocked(false);
        return;
    }

    const taskId = res.task_id;
    setCrawlControlsLocked(true);
    const progress = document.getElementById('crawlProgress');
    const fill = document.getElementById('progressFill');
    const countEl = document.getElementById('crawledCount');
    const percentEl = document.getElementById('crawlPercent');
    document.getElementById('crawlTarget').textContent = target;
    progress.style.display = 'block';
    progress.querySelector('.badge').textContent = '采集中';
    progress.querySelector('.badge').className = 'badge badge-running';

    if (crawlTimer) clearInterval(crawlTimer);
    crawlTimer = setInterval(async () => {
        try {
            const p = await api(`/api/crawl/progress/${taskId}`);
            const crawledCount = toNumber(p.crawled_count);
            const taskTarget = toNumber(p.target_count, target) || target;
            const pct = Math.min(Math.round(crawledCount / taskTarget * 100), 100);
            fill.style.width = pct + '%';
            countEl.textContent = crawledCount;
            percentEl.textContent = pct + '%';

            if (p.status === 'done') {
                clearInterval(crawlTimer);
                progress.querySelector('.badge').textContent = '已完成';
                progress.querySelector('.badge').className = 'badge badge-done';
                setCrawlStatus(p.error_message || `采集完成，共采集到 ${crawledCount} 条有效数据。`, 'ok');
                setCrawlControlsLocked(false);
                loadCrawlHistory();
                loadDatasets();
            } else if (p.status === 'failed') {
                clearInterval(crawlTimer);
                progress.querySelector('.badge').textContent = '失败';
                progress.querySelector('.badge').className = 'badge badge-failed';
                setCrawlStatus(p.error_message || '采集失败，请查看采集历史', 'fail');
                setCrawlControlsLocked(false);
                loadCrawlHistory();
                alert(p.error_message || '采集失败，请查看采集历史');
            } else if (p.status === 'running' && p.error_message) {
                setCrawlStatus(p.error_message, '');
            }
        } catch (e) {
            clearInterval(crawlTimer);
            progress.querySelector('.badge').textContent = '异常';
            progress.querySelector('.badge').className = 'badge badge-failed';
            setCrawlControlsLocked(false);
            setCrawlStatus(e.message || '读取采集进度失败', 'fail');
            showError(e, '读取采集进度失败');
        }
    }, 2000);
});

const importForm = document.getElementById('importForm');
if (importForm) {
    importForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const fileInput = document.getElementById('importFile');
        const datasetInput = document.getElementById('importDatasetName');
        const submitBtn = document.getElementById('importDataBtn');
        const file = fileInput && fileInput.files ? fileInput.files[0] : null;

        if (!file) {
            setImportStatus('请选择 CSV 或 Excel 文件。', 'fail');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('dataset_name', datasetInput ? datasetInput.value.trim() : '');

        if (submitBtn) submitBtn.disabled = true;
        setImportStatus('正在导入、清洗并去重数据...', '');
        try {
            const res = await api('/api/import/upload', {
                method: 'POST',
                body: formData
            });
            setImportStatus(res.message || '导入完成。', 'ok');
            if (fileInput) fileInput.value = '';
            loadCrawlHistory();
            loadDatasets();
            initDashboard();
        } catch (err) {
            setImportStatus(err.message || '导入失败，请检查文件格式和文本列。', 'fail');
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });
}

async function loadCrawlHistory() {
    let data = [];
    try {
        data = await api('/api/crawl/history');
    } catch (e) {
        showError(e, '加载采集历史失败');
        return;
    }
    const tbody = document.querySelector('#page-crawl .data-table tbody');
    if (!tbody) return;
    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:24px;">暂无采集记录</td></tr>';
        return;
    }
    tbody.innerHTML = data.map(r => {
        const statusMap = {
            done: ['badge-done', '已完成'],
            failed: ['badge-failed', '失败'],
            running: ['badge-running', '采集中'],
            pending: ['badge-pending', '等待中']
        };
        const [statusClass, statusText] = statusMap[r.status] || statusMap.pending;
        const errorTitle = r.error_message ? ` title="${escapeHtml(r.error_message)}"` : '';
        return `<tr>
            <td>#${r.id}</td>
            <td>${escapeHtml(r.keyword)}</td>
            <td>B站</td>
            <td>${toNumber(r.crawled_count).toLocaleString()}</td>
            <td>${escapeHtml(r.created_at || '')}</td>
            <td><span class="badge ${statusClass}"${errorTitle}>${statusText}</span></td>
            <td>
                <button class="btn btn-sm" onclick="selectTask(${r.id})">查看</button>
                <button class="btn btn-sm btn-danger" onclick="deleteTask(${r.id})">删除</button>
            </td>
        </tr>`;
    }).join('');
    tbody.querySelectorAll('tr').forEach((row, index) => {
        const sourceCell = row.children[2];
        if (sourceCell && data[index] && data[index].source) {
            sourceCell.textContent = data[index].source;
        }
    });
}

function selectTask(id) {
    currentTaskId = id;
    alert('已选择任务 #' + id + '，可前往主题挖掘或情感分析页面进行分析');
}

async function deleteTask(id) {
    if (!confirm('确定删除该任务及其所有数据？')) return;
    try {
        await api(`/api/crawl/${id}`, { method: 'DELETE' });
        loadCrawlHistory();
        loadDatasets();
    } catch (e) {
        showError(e, '删除任务失败');
    }
}

document.getElementById('clearHistoryBtn').addEventListener('click', async function() {
    if (!confirm('确定清除所有采集历史和对应数据吗？')) return;
    try {
        await api('/api/crawl/history', { method: 'DELETE' });
        currentTaskId = null;
        loadCrawlHistory();
        loadDatasets();
        setCrawlStatus('采集历史已清空。', 'ok');
    } catch (e) {
        showError(e, '清空采集历史失败');
    }
});

// ===== 主题挖掘 =====
async function initTopic() {
    await loadDatasets();
    if (!currentTaskId) return;

    try {
        const results = await api(`/api/topic/results/${currentTaskId}`);
        renderTopicResults(results);
    } catch (e) {
        showError(e, '加载主题结果失败');
    }
}

function renderTopicResults(results) {
    const listEl = document.querySelector('#page-topic .topic-list');
    if (!results || !results.length) {
        if (listEl) {
            listEl.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:20px;">暂无主题结果</p>';
        }
        return;
    }

    const dist = getChart('topicDistChart');
    if (dist) {
        const topicColors = ['#4F46E5', '#0EA5E9', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];
        dist.setOption({
            tooltip: { trigger: 'item' },
            legend: { bottom: 10 },
            series: [{
                type: 'pie', radius: '65%', center: ['50%', '45%'],
                roseType: 'area', itemStyle: { borderRadius: 6 },
                data: results.map((r, i) => ({
                    value: Math.round(r.weight * 100),
                    name: escapeHtml(r.topic_name),
                    itemStyle: { color: topicColors[i % topicColors.length] }
                }))
            }]
        });
    }

    if (listEl) {
        const topicColors = ['#4F46E5', '#0EA5E9', '#10B981', '#F59E0B', '#EF4444'];
        listEl.innerHTML = results.map((r, i) => `
            <div class="topic-item">
                <div class="topic-header">
                    <span class="topic-badge" style="background:${topicColors[i % topicColors.length]}">${escapeHtml(r.topic_name)}</span>
                    <span class="topic-weight">权重 ${Math.round(toNumber(r.weight) * 100)}%</span>
                </div>
                <div class="topic-explanation">${escapeHtml(r.explanation || '')}</div>
                <div class="topic-keywords">
                    ${r.keywords.map(k => `<span class="keyword-tag">${escapeHtml(k)}</span>`).join('')}
                </div>
                ${(r.representative_docs || []).length ? `
                    <div class="topic-representatives">
                        <div class="topic-subtitle">代表文本</div>
                        ${(r.representative_docs || []).map(doc => `
                            <div class="topic-doc">${escapeHtml(doc.text || '')}</div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `).join('');
    }
}

document.getElementById('startTopic').addEventListener('click', async function() {
    const sel = document.querySelector('#page-topic select[data-role="dataset"]');
    const taskId = sel ? sel.value : currentTaskId;
    if (!taskId) { alert('请先采集数据'); return; }

    const numTopics = document.querySelector('#page-topic input[type="number"]').value || 5;

    this.textContent = '分析中...';
    this.disabled = true;

    try {
        const results = await api('/api/topic/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: parseInt(taskId), num_topics: parseInt(numTopics) })
        });
        renderTopicResults(results);
    } catch (e) {
        showError(e, '主题分析失败');
    } finally {
        this.textContent = '开始分析';
        this.disabled = false;
    }
});

// ===== 情感分析 =====
let sentimentCommentState = {
    taskId: null,
    label: 'all',
    page: 1,
    pageSize: 10,
    total: 0,
    pages: 0
};

async function initSentiment() {
    await loadDatasets();
    if (!currentTaskId) return;

    try {
        const data = await api(`/api/sentiment/results/${currentTaskId}`);
        renderSentimentResults(data);
        loadComments(currentTaskId, 'all', 1);
    } catch (e) {}
}

function renderSentimentResults(data) {
    if (!data || !data.stats) return;
    const s = data.stats;

    const statCards = document.querySelectorAll('#page-sentiment .stat-card');
    if (statCards[0]) {
        statCards[0].querySelector('.stat-value').textContent = s.positive;
        statCards[0].querySelector('.stat-percent').textContent = s.positive_pct + '%';
    }
    if (statCards[1]) {
        statCards[1].querySelector('.stat-value').textContent = s.neutral;
        statCards[1].querySelector('.stat-percent').textContent = s.neutral_pct + '%';
    }
    if (statCards[2]) {
        statCards[2].querySelector('.stat-value').textContent = s.negative;
        statCards[2].querySelector('.stat-percent').textContent = s.negative_pct + '%';
    }

    // 得分分布
    const score = getChart('sentimentScoreChart');
    if (score && data.distribution) {
        const bins = [];
        for (let i = 0; i <= 10; i++) bins.push((i / 10).toFixed(1));
        score.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 72, right: 20, top: 42, bottom: 46 },
            xAxis: { type: 'category', data: bins, name: '情感得分', nameLocation: 'center', nameGap: 30 },
            yAxis: { type: 'value', name: '数量', nameLocation: 'middle', nameGap: 44, splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } } },
            series: [{
                type: 'bar', barWidth: '60%',
                data: data.distribution.map((v, i) => ({
                    value: v,
                    itemStyle: {
                        color: i <= 3 ? colors.red : i <= 6 ? colors.yellow : colors.green,
                        borderRadius: [4, 4, 0, 0]
                    }
                }))
            }]
        });
    }

    // 情感倾向结构图
    const radar = getChart('sentimentRadarChart');
    if (radar) {
        const tendencyValues = [
            Math.round(s.positive_pct),
            Math.round(s.neutral_pct),
            Math.round(s.negative_pct),
            Math.round(100 - Math.max(s.positive_pct, s.neutral_pct, s.negative_pct))
        ];
        radar.setOption({
            radar: {
                center: ['50%', '58%'],
                radius: '58%',
                indicator: [
                    { name: `正面倾向\n${tendencyValues[0]}%`, max: 100 },
                    { name: `中立倾向\n${tendencyValues[1]}%`, max: 100 },
                    { name: `负面倾向\n${tendencyValues[2]}%`, max: 100 },
                    { name: `情绪波动\n${tendencyValues[3]}%`, max: 100 }
                ],
                shape: 'polygon',
                splitArea: { areaStyle: { color: ['#fff', '#f8fafc'] } }
            },
            tooltip: {
                trigger: 'item',
                formatter: params => {
                    const values = params.value || [];
                    return [
                        `正面倾向：${values[0]}%`,
                        `中立倾向：${values[1]}%`,
                        `负面倾向：${values[2]}%`,
                        `情绪波动：${values[3]}%`
                    ].join('<br>');
                }
            },
            series: [{
                type: 'radar',
                data: [{
                    value: tendencyValues,
                    name: '情感倾向结构',
                    label: { show: false },
                    areaStyle: { color: 'rgba(79,70,229,0.15)' },
                    lineStyle: { color: colors.primary },
                    itemStyle: { color: colors.primary }
                }]
            }]
        });
    }
}

async function loadComments(taskId, label, page = 1) {
    const pageSize = sentimentCommentState.pageSize || 10;
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (label !== 'all') params.set('label', label);
    let data = { items: [], total: 0, page, page_size: pageSize, pages: 0 };
    try {
        const res = await api(`/api/sentiment/comments/${taskId}?${params.toString()}`);
        data = Array.isArray(res)
            ? { items: res, total: res.length, page: 1, page_size: res.length || pageSize, pages: res.length ? 1 : 0 }
            : res;
    } catch (e) {
        showError(e, '加载评论失败');
        return;
    }
    sentimentCommentState = {
        taskId,
        label,
        page: data.page || page,
        pageSize: data.page_size || pageSize,
        total: data.total || 0,
        pages: data.pages || 0
    };

    const listEl = document.querySelector('#page-sentiment .comment-list');
    if (!listEl) return;
    const items = data.items || [];

    if (!items.length) {
        listEl.innerHTML = '<p style="color:#94a3b8;text-align:center;padding:20px;">暂无数据</p>';
        renderCommentPagination();
        return;
    }

    listEl.innerHTML = items.map(r => {
        const tagClass = r.label === 'positive' ? 'tag-positive' : r.label === 'negative' ? 'tag-negative' : 'tag-neutral';
        const score = toNumber(r.score).toFixed(2);
        return `<div class="comment-item">
            <div class="comment-header">
                <span class="comment-user">${escapeHtml(r.user_name)}</span>
                <span class="comment-time">${escapeHtml(r.publish_time || '')}</span>
                <span class="tag ${tagClass}">${escapeHtml(r.label_cn)} ${score}</span>
            </div>
            <p class="comment-text">${escapeHtml(r.content)}</p>
        </div>`;
    }).join('');
    renderCommentPagination();
}

function renderCommentPagination() {
    const el = document.getElementById('commentPagination');
    if (!el) return;
    const { page, pages, total, label, taskId } = sentimentCommentState;
    if (!total) {
        el.innerHTML = '';
        return;
    }
    el.innerHTML = `
        <span class="pagination-info">共 ${total} 条，第 ${page}/${Math.max(pages, 1)} 页</span>
        <button class="btn btn-sm" id="commentPrevPage" ${page <= 1 ? 'disabled' : ''}>上一页</button>
        <button class="btn btn-sm" id="commentNextPage" ${page >= pages ? 'disabled' : ''}>下一页</button>
    `;
    const prev = document.getElementById('commentPrevPage');
    const next = document.getElementById('commentNextPage');
    if (prev) prev.onclick = () => loadComments(taskId, label, page - 1);
    if (next) next.onclick = () => loadComments(taskId, label, page + 1);
}

document.getElementById('startSentiment').addEventListener('click', async function() {
    const sel = document.querySelector('#page-sentiment select[data-role="dataset"]');
    const taskId = sel ? sel.value : currentTaskId;
    if (!taskId) { alert('请先采集数据'); return; }

    this.textContent = '分析中...';
    this.disabled = true;

    try {
        const res = await api('/api/sentiment/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: parseInt(taskId) })
        });

        if (res.stats) {
            renderSentimentResults({ stats: res.stats, distribution: null });
            const full = await api(`/api/sentiment/results/${taskId}`);
            renderSentimentResults(full);
            loadComments(taskId, 'all', 1);
        }
    } catch (e) {
        showError(e, '情感分析失败');
    } finally {
        this.textContent = '开始分析';
        this.disabled = false;
    }
});

// 评论筛选
document.querySelectorAll('#page-sentiment .card-actions .btn-tab').forEach(btn => {
    btn.addEventListener('click', () => {
        const filter = btn.dataset.filter;
        const sel = document.querySelector('#page-sentiment select[data-role="dataset"]');
        const taskId = sel ? sel.value : currentTaskId;
        if (taskId) {
            const labelMap = { all: 'all', positive: 'positive', neutral: 'neutral', negative: 'negative' };
            document.querySelectorAll('#page-sentiment .card-actions .btn-tab').forEach(item => item.classList.remove('active'));
            btn.classList.add('active');
            loadComments(taskId, labelMap[filter] || 'all', 1);
        }
    });
});

// ===== 数据可视化 =====
async function initVisual() {
    await loadDatasets();
    if (!currentTaskId) return;
    loadVisualCharts(currentTaskId);
}

async function loadVisualCharts(taskId) {
    try {
        const vol = await api(`/api/visual/volume/${taskId}`);
        const chart = getChart('volumeChart');
        if (chart && vol.labels && vol.labels.length) {
            chart.setOption({
                tooltip: { trigger: 'axis', formatter: params => `${params[0].axisValue}<br/>评论样本数：${params[0].value}` },
                grid: { left: 70, right: 20, top: 28, bottom: 78 },
                xAxis: { type: 'category', data: vol.labels, axisLabel: { rotate: 25, width: 90, overflow: 'truncate' }, name: '热门笔记', nameLocation: 'center', nameGap: 56 },
                yAxis: { type: 'value', name: '评论数', nameLocation: 'middle', nameGap: 46, splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } } },
                series: [{
                    name: '评论数',
                    type: 'bar',
                    barWidth: '48%',
                    data: vol.counts,
                    itemStyle: { color: colors.primary, borderRadius: [4, 4, 0, 0] }
                }]
            });
        } else if (chart) {
            chart.clear();
        }
    } catch (e) {}

    try {
        const risk = await api(`/api/visual/active/${taskId}`);
        const chart = getChart('activeChart');
        if (chart) {
            const riskColor = risk.level === 'high' ? colors.red : (risk.level === 'medium' ? colors.yellow : colors.green);
            const riskText = risk.level === 'high' ? '需要重点留意' : (risk.level === 'medium' ? '建议关注' : '状态良好');
            const riskValue = risk.negative_pct || 0;
            chart.setOption({
                tooltip: { formatter: () => `${riskText}<br/>负面评论占比：${riskValue}%<br/>${risk.message || ''}` },
                title: {
                    text: riskText,
                    subtext: `负面评论占比 ${riskValue}%`,
                    left: 'center',
                    bottom: 10,
                    textStyle: { color: riskColor, fontSize: 16, fontWeight: 600 },
                    subtextStyle: { color: '#64748B', fontSize: 12 }
                },
                series: [{
                    type: 'gauge',
                    min: 0,
                    max: 100,
                    startAngle: 210,
                    endAngle: -30,
                    progress: { show: true, width: 14, itemStyle: { color: riskColor } },
                    axisLine: {
                        lineStyle: {
                            width: 14,
                            color: [
                                [0.25, colors.green],
                                [0.4, colors.yellow],
                                [1, colors.red]
                            ]
                        }
                    },
                    axisTick: { show: false },
                    splitLine: { length: 10, lineStyle: { color: '#CBD5E1' } },
                    axisLabel: {
                        distance: 18,
                        color: '#64748B',
                        formatter: value => {
                            if (value === 0) return '0';
                            if (value === 20) return '良好';
                            if (value === 40) return '关注';
                            if (value === 100) return '高风险';
                            return '';
                        }
                    },
                    pointer: { width: 5, itemStyle: { color: riskColor } },
                    anchor: { show: true, size: 8, itemStyle: { color: riskColor } },
                    title: { show: false },
                    detail: { formatter: '{value}%', fontSize: 26, offsetCenter: [0, '42%'], color: riskColor },
                    data: [{ value: riskValue, name: '负面评论占比' }],
                    itemStyle: { color: riskColor }
                }]
            });
        }
    } catch (e) {}

    try {
        const sentiment = await api(`/api/visual/sentiment/${taskId}`);
        const chart = getChart('compareChart');
        if (chart && sentiment.counts && sentiment.counts.length) {
            chart.setOption({
                tooltip: { trigger: 'item', formatter: '{b}<br/>数量：{c}<br/>占比：{d}%' },
                legend: { top: 0 },
                series: [{
                    name: '情感占比',
                    type: 'pie',
                    radius: ['42%', '68%'],
                    center: ['50%', '56%'],
                    data: [
                        { value: sentiment.counts[0] || 0, name: '正面', itemStyle: { color: colors.green } },
                        { value: sentiment.counts[1] || 0, name: '中立', itemStyle: { color: colors.yellow } },
                        { value: sentiment.counts[2] || 0, name: '负面', itemStyle: { color: colors.red } },
                    ],
                    label: { formatter: '{b}: {d}%' }
                }]
            });
        } else if (chart) {
            chart.clear();
        }
    } catch (e) {}

    try {
        const net = await api(`/api/visual/network/${taskId}`);
        const chart = getChart('networkChart');
        if (chart && net.nodes.length) {
            const palette = ['#4F46E5', '#059669', '#F59E0B', '#DC2626', '#0891B2', '#7C3AED', '#DB2777', '#0F766E', '#EA580C', '#2563EB'];
            const values = net.nodes.map(n => n.value || 0);
            const maxValue = Math.max(...values, 1);
            const minValue = Math.min(...values, maxValue);
            const scaleNode = value => {
                if (maxValue === minValue) return 32;
                return 22 + ((value || 0) - minValue) / (maxValue - minValue) * 34;
            };
            chart.setOption({
                animationDuration: 900,
                animationDurationUpdate: 900,
                animationEasingUpdate: 'quinticInOut',
                tooltip: {
                    formatter: params => {
                        if (params.dataType === 'edge') {
                            return `${params.data.source} - ${params.data.target}<br/>共现次数：${params.data.value}`;
                        }
                        return `${params.data.name}<br/>出现次数：${params.data.value || 0}`;
                    }
                },
                series: [{
                    type: 'graph',
                    layout: 'force',
                    roam: true,
                    draggable: true,
                    label: { show: true, fontSize: 12, color: '#0F172A' },
                    edgeLabel: { show: false },
                    force: { repulsion: 360, gravity: 0.08, edgeLength: [90, 180], friction: 0.35 },
                    data: net.nodes.map((n, i) => ({
                        ...n,
                        draggable: true,
                        symbolSize: scaleNode(n.value),
                        itemStyle: {
                            color: palette[i % palette.length],
                            borderColor: '#FFFFFF',
                            borderWidth: 2,
                            shadowBlur: 10,
                            shadowColor: 'rgba(15, 23, 42, 0.18)'
                        }
                    })),
                    links: net.links.map(link => ({
                        ...link,
                        lineStyle: {
                            width: Math.min((link.value || 1) + 0.5, 5),
                            opacity: 0.5,
                            color: '#94A3B8',
                            curveness: 0.18
                        }
                    })),
                    emphasis: { focus: 'adjacency', lineStyle: { opacity: 0.9, width: 4 } },
                    lineStyle: { color: '#CBD5E1', curveness: 0.2 }
                }]
            });
        } else if (chart) {
            chart.clear();
        }
    } catch (e) {}
}

// ===== 页面调度 =====
function initPageCharts(page) {
    setTimeout(() => {
        switch (page) {
            case 'dashboard': initDashboard(); break;
            case 'crawl':
                loadCookieStatus();
                loadCrawlHistory();
                break;
            case 'topic': initTopic(); break;
            case 'sentiment': initSentiment(); break;
            case 'visual': initVisual(); break;
        }
    }, 100);
}

document.querySelectorAll('select[data-role="dataset"]').forEach(sel => {
    sel.addEventListener('change', () => {
        if (!sel.value) return;
        currentTaskId = parseInt(sel.value);
        if (sel.id === 'visualDataset') {
            loadVisualCharts(currentTaskId);
        }
    });
});

const visualRefreshBtn = document.querySelector('#page-visual .visual-controls .btn-primary');
if (visualRefreshBtn) {
    visualRefreshBtn.addEventListener('click', () => {
        const sel = document.getElementById('visualDataset');
        const taskId = sel && sel.value ? parseInt(sel.value) : currentTaskId;
        if (!taskId) { alert('请先采集数据'); return; }
        currentTaskId = taskId;
        loadVisualCharts(taskId);
    });
}

// 首次加载
initDashboard();
loadCookieStatus();
loadDatasets();

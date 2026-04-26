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

// 移动端菜单
document.getElementById('menuToggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('open');
});

// 时间
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

// Tab切换
document.querySelectorAll('.card-actions').forEach(group => {
    group.querySelectorAll('.btn-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            group.querySelectorAll('.btn-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
});

// ===== 通用颜色 =====
const colors = {
    primary: '#4F46E5',
    blue: '#0EA5E9',
    green: '#10B981',
    yellow: '#F59E0B',
    red: '#EF4444',
    purple: '#8B5CF6',
    pink: '#EC4899'
};

// ===== 图表初始化 =====
const chartInstances = {};

function getChart(id) {
    if (chartInstances[id]) {
        chartInstances[id].dispose();
    }
    const dom = document.getElementById(id);
    if (!dom) return null;
    const chart = echarts.init(dom);
    chartInstances[id] = chart;
    return chart;
}

// 监听窗口变化
window.addEventListener('resize', () => {
    Object.values(chartInstances).forEach(c => c && c.resize());
});

// ===== 仪表盘图表 =====
function initDashboard() {
    // 情感趋势图
    const trend = getChart('trendChart');
    if (trend) {
        const days = ['04-20', '04-21', '04-22', '04-23', '04-24', '04-25', '04-26'];
        trend.setOption({
            tooltip: { trigger: 'axis' },
            legend: { data: ['正面', '中性', '负面'], right: 20, top: 0 },
            grid: { left: 40, right: 20, top: 40, bottom: 30 },
            xAxis: { type: 'category', data: days, boundaryGap: false },
            yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } } },
            series: [
                {
                    name: '正面', type: 'line', smooth: true,
                    data: [620, 732, 701, 834, 890, 930, 748],
                    itemStyle: { color: colors.green },
                    areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(16,185,129,0.25)' },
                        { offset: 1, color: 'rgba(16,185,129,0.02)' }
                    ])}
                },
                {
                    name: '中性', type: 'line', smooth: true,
                    data: [200, 282, 251, 324, 290, 310, 263],
                    itemStyle: { color: colors.yellow },
                    areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(245,158,11,0.15)' },
                        { offset: 1, color: 'rgba(245,158,11,0.02)' }
                    ])}
                },
                {
                    name: '负面', type: 'line', smooth: true,
                    data: [150, 182, 191, 174, 210, 170, 189],
                    itemStyle: { color: colors.red },
                    areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(239,68,68,0.15)' },
                        { offset: 1, color: 'rgba(239,68,68,0.02)' }
                    ])}
                }
            ]
        });
    }

    // 情感分布饼图
    const pie = getChart('pieChart');
    if (pie) {
        pie.setOption({
            tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
            legend: { bottom: 10, itemGap: 20 },
            series: [{
                type: 'pie', radius: ['45%', '70%'], center: ['50%', '45%'],
                avoidLabelOverlap: false,
                itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 3 },
                label: { show: false },
                emphasis: { label: { show: true, fontSize: 16, fontWeight: 'bold' } },
                data: [
                    { value: 748, name: '正面', itemStyle: { color: colors.green } },
                    { value: 263, name: '中性', itemStyle: { color: colors.yellow } },
                    { value: 189, name: '负面', itemStyle: { color: colors.red } }
                ]
            }]
        });
    }

    // 词云
    const wc = getChart('wordCloudChart');
    if (wc) {
        const words = [
            { name: '人工智能', value: 1200 }, { name: '大模型', value: 980 },
            { name: '创新', value: 860 }, { name: '芯片', value: 750 },
            { name: '算力', value: 700 }, { name: '自动驾驶', value: 650 },
            { name: '新能源', value: 600 }, { name: '数字化', value: 580 },
            { name: '智能制造', value: 520 }, { name: '深度学习', value: 500 },
            { name: '机器人', value: 480 }, { name: '数据安全', value: 450 },
            { name: '5G', value: 420 }, { name: '元宇宙', value: 400 },
            { name: '区块链', value: 380 }, { name: '云计算', value: 360 },
            { name: '物联网', value: 340 }, { name: '生物科技', value: 320 },
            { name: '量子计算', value: 300 }, { name: '碳中和', value: 280 },
            { name: '智慧城市', value: 260 }, { name: '教育改革', value: 240 },
            { name: '医疗健康', value: 220 }, { name: '乡村振兴', value: 200 },
            { name: '航天科技', value: 190 }, { name: '半导体', value: 180 },
            { name: '科技创新', value: 170 }, { name: '产业升级', value: 160 },
        ];
        wc.setOption({
            series: [{
                type: 'wordCloud',
                shape: 'circle',
                gridSize: 12,
                sizeRange: [14, 48],
                rotationRange: [-30, 30],
                rotationStep: 15,
                textStyle: {
                    fontFamily: 'Microsoft YaHei',
                    color: function () {
                        const cs = [colors.primary, colors.blue, colors.green, colors.yellow, colors.red, colors.purple, colors.pink];
                        return cs[Math.floor(Math.random() * cs.length)];
                    }
                },
                data: words
            }]
        });
    }
}

// ===== 主题挖掘图表 =====
function initTopic() {
    const dist = getChart('topicDistChart');
    if (dist) {
        dist.setOption({
            tooltip: { trigger: 'item' },
            legend: { bottom: 10 },
            series: [{
                type: 'pie', radius: '65%', center: ['50%', '45%'],
                roseType: 'area',
                itemStyle: { borderRadius: 6 },
                data: [
                    { value: 35, name: '技术发展与创新', itemStyle: { color: '#4F46E5' } },
                    { value: 28, name: '产业应用与落地', itemStyle: { color: '#0EA5E9' } },
                    { value: 18, name: '政策与监管', itemStyle: { color: '#10B981' } },
                    { value: 12, name: '就业与教育', itemStyle: { color: '#F59E0B' } },
                    { value: 7, name: '社会影响与讨论', itemStyle: { color: '#EF4444' } }
                ]
            }]
        });
    }
}

// ===== 情感分析图表 =====
function initSentiment() {
    // 情感得分分布
    const score = getChart('sentimentScoreChart');
    if (score) {
        const bins = [];
        const values = [];
        for (let i = 0; i <= 10; i++) {
            bins.push((i / 10).toFixed(1));
        }
        values.push(15, 28, 42, 55, 38, 80, 120, 180, 210, 160, 72);
        score.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 50, right: 20, top: 20, bottom: 40 },
            xAxis: {
                type: 'category', data: bins,
                name: '情感得分', nameLocation: 'center', nameGap: 30
            },
            yAxis: {
                type: 'value', name: '数量',
                splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } }
            },
            series: [{
                type: 'bar', barWidth: '60%',
                data: values.map((v, i) => ({
                    value: v,
                    itemStyle: {
                        color: i <= 3 ? colors.red : i <= 6 ? colors.yellow : colors.green,
                        borderRadius: [4, 4, 0, 0]
                    }
                }))
            }]
        });
    }

    // 雷达图
    const radar = getChart('sentimentRadarChart');
    if (radar) {
        radar.setOption({
            radar: {
                indicator: [
                    { name: '喜悦', max: 100 }, { name: '期待', max: 100 },
                    { name: '信任', max: 100 }, { name: '惊讶', max: 100 },
                    { name: '愤怒', max: 100 }, { name: '恐惧', max: 100 },
                    { name: '悲伤', max: 100 }, { name: '厌恶', max: 100 }
                ],
                shape: 'polygon',
                splitArea: { areaStyle: { color: ['#fff', '#f8fafc'] } }
            },
            series: [{
                type: 'radar',
                data: [{
                    value: [82, 75, 68, 45, 22, 18, 15, 12],
                    name: '情感维度',
                    areaStyle: { color: 'rgba(79,70,229,0.15)' },
                    lineStyle: { color: colors.primary },
                    itemStyle: { color: colors.primary }
                }]
            }]
        });
    }
}

// ===== 数据可视化图表 =====
function initVisual() {
    // 发布量趋势
    const volume = getChart('volumeChart');
    if (volume) {
        const dates = [];
        const data = [];
        for (let i = 29; i >= 0; i--) {
            const d = new Date();
            d.setDate(d.getDate() - i);
            dates.push((d.getMonth() + 1) + '-' + d.getDate());
            data.push(Math.floor(Math.random() * 400 + 200));
        }
        volume.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 50, right: 20, top: 20, bottom: 30 },
            xAxis: { type: 'category', data: dates, boundaryGap: false },
            yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } } },
            series: [{
                type: 'line', smooth: true, data: data,
                itemStyle: { color: colors.primary },
                areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(79,70,229,0.3)' },
                    { offset: 1, color: 'rgba(79,70,229,0.02)' }
                ])}
            }]
        });
    }

    // 用户活跃度
    const active = getChart('activeChart');
    if (active) {
        active.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 50, right: 10, top: 20, bottom: 30 },
            xAxis: {
                type: 'category',
                data: ['0-4', '4-8', '8-12', '12-16', '16-20', '20-24'],
                name: '时段'
            },
            yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } } },
            series: [{
                type: 'bar', barWidth: '50%',
                data: [
                    { value: 120, itemStyle: { color: '#C7D2FE', borderRadius: [4,4,0,0] } },
                    { value: 280, itemStyle: { color: '#A5B4FC', borderRadius: [4,4,0,0] } },
                    { value: 560, itemStyle: { color: '#818CF8', borderRadius: [4,4,0,0] } },
                    { value: 480, itemStyle: { color: '#6366F1', borderRadius: [4,4,0,0] } },
                    { value: 620, itemStyle: { color: '#4F46E5', borderRadius: [4,4,0,0] } },
                    { value: 380, itemStyle: { color: '#4338CA', borderRadius: [4,4,0,0] } }
                ]
            }]
        });
    }

    // 情感对比
    const compare = getChart('compareChart');
    if (compare) {
        compare.setOption({
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            legend: { data: ['正面', '中性', '负面'], top: 0 },
            grid: { left: 60, right: 20, top: 40, bottom: 30 },
            yAxis: { type: 'category', data: ['微博', '知乎', 'B站', '头条'] },
            xAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } } },
            series: [
                { name: '正面', type: 'bar', stack: 'total', data: [620, 480, 350, 420], itemStyle: { color: colors.green, borderRadius: [0,0,0,0] } },
                { name: '中性', type: 'bar', stack: 'total', data: [220, 180, 160, 150], itemStyle: { color: colors.yellow } },
                { name: '负面', type: 'bar', stack: 'total', data: [160, 140, 90, 130], itemStyle: { color: colors.red, borderRadius: [0,4,4,0] } }
            ]
        });
    }

    // 关键词共现网络
    const network = getChart('networkChart');
    if (network) {
        const nodes = [
            { name: '人工智能', symbolSize: 50, category: 0 },
            { name: '大模型', symbolSize: 40, category: 0 },
            { name: '深度学习', symbolSize: 35, category: 0 },
            { name: '芯片', symbolSize: 30, category: 1 },
            { name: '算力', symbolSize: 28, category: 1 },
            { name: '自动驾驶', symbolSize: 32, category: 2 },
            { name: '机器人', symbolSize: 26, category: 2 },
            { name: '数据安全', symbolSize: 24, category: 3 },
            { name: '监管', symbolSize: 22, category: 3 },
            { name: '就业', symbolSize: 25, category: 4 },
            { name: '教育', symbolSize: 23, category: 4 },
            { name: '创新', symbolSize: 30, category: 0 },
        ];
        const links = [
            { source: '人工智能', target: '大模型' },
            { source: '人工智能', target: '深度学习' },
            { source: '人工智能', target: '芯片' },
            { source: '人工智能', target: '自动驾驶' },
            { source: '人工智能', target: '数据安全' },
            { source: '人工智能', target: '就业' },
            { source: '人工智能', target: '创新' },
            { source: '大模型', target: '算力' },
            { source: '大模型', target: '深度学习' },
            { source: '芯片', target: '算力' },
            { source: '自动驾驶', target: '机器人' },
            { source: '数据安全', target: '监管' },
            { source: '就业', target: '教育' },
            { source: '创新', target: '大模型' },
        ];
        network.setOption({
            tooltip: {},
            series: [{
                type: 'graph', layout: 'force', roam: true,
                label: { show: true, fontSize: 12 },
                force: { repulsion: 200, edgeLength: [80, 150] },
                categories: [
                    { name: '核心技术', itemStyle: { color: colors.primary } },
                    { name: '硬件基础', itemStyle: { color: colors.blue } },
                    { name: '应用场景', itemStyle: { color: colors.green } },
                    { name: '政策监管', itemStyle: { color: colors.yellow } },
                    { name: '社会影响', itemStyle: { color: colors.red } }
                ],
                data: nodes,
                links: links,
                lineStyle: { color: '#CBD5E1', curveness: 0.2 }
            }]
        });
    }
}

// 页面图表初始化调度
function initPageCharts(page) {
    setTimeout(() => {
        switch (page) {
            case 'dashboard': initDashboard(); break;
            case 'topic': initTopic(); break;
            case 'sentiment': initSentiment(); break;
            case 'visual': initVisual(); break;
        }
    }, 100);
}

// 首次加载
initPageCharts('dashboard');

// ===== 采集表单模拟 =====
document.getElementById('crawlForm').addEventListener('submit', function (e) {
    e.preventDefault();
    const keyword = document.getElementById('keyword').value;
    if (!keyword) { alert('请输入关键词'); return; }

    const target = parseInt(document.getElementById('crawlCount').value) || 500;
    const progress = document.getElementById('crawlProgress');
    const fill = document.getElementById('progressFill');
    const countEl = document.getElementById('crawledCount');
    const percentEl = document.getElementById('crawlPercent');
    document.getElementById('crawlTarget').textContent = target;

    progress.style.display = 'block';
    let current = 0;

    const timer = setInterval(() => {
        current += Math.floor(Math.random() * 30 + 10);
        if (current >= target) {
            current = target;
            clearInterval(timer);
            progress.querySelector('.badge').textContent = '已完成';
            progress.querySelector('.badge').className = 'badge badge-done';
        }
        const pct = Math.min(Math.round(current / target * 100), 100);
        fill.style.width = pct + '%';
        countEl.textContent = current;
        percentEl.textContent = pct + '%';
    }, 200);
});

// 主题分析按钮
document.getElementById('startTopic').addEventListener('click', function () {
    this.textContent = '分析中...';
    this.disabled = true;
    setTimeout(() => {
        this.textContent = '开始分析';
        this.disabled = false;
        initTopic();
    }, 1500);
});

// 情感分析按钮
document.getElementById('startSentiment').addEventListener('click', function () {
    this.textContent = '分析中...';
    this.disabled = true;
    setTimeout(() => {
        this.textContent = '开始分析';
        this.disabled = false;
        initSentiment();
    }, 1500);
});

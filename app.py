import os
import threading
import webbrowser
from io import BytesIO, StringIO
from collections import Counter
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
import pandas as pd
from crawler_config import clear_platform_cookie, get_cookie_status, set_platform_cookie
from database import init_db, get_conn, update_task_status
from crawler import check_bilibili, crawl_bilibili
from preprocessor import preprocess_task, deduplicate_task, segment
from sentiment import analyze_sentiment, get_sentiment_stats, get_score_distribution
from topic_model import run_lda, get_topic_results

app = Flask(__name__, static_folder='.', static_url_path='')
MAX_TARGET_COUNT = 5000
MAX_IMPORT_ROWS = 10000
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 5001
PLATFORM_LABELS = {
    'bilibili': 'B站',
    'import': '本地导入',
}


def _json_body():
    return request.get_json(silent=True) or {}


def _parse_int(value, default, min_value=None, max_value=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(parsed, min_value)
    if max_value is not None:
        parsed = min(parsed, max_value)
    return parsed


def _validate_crawl_date_range(data):
    start_date = str(data.get('start_date') or '').strip()
    end_date = str(data.get('end_date') or '').strip()
    if not start_date or not end_date:
        return '', '', '请填写开始时间和结束时间，系统将只按指定时间范围采集。'

    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return '', '', '时间格式不正确，请使用日期选择器重新选择开始时间和结束时间。'

    if start_dt > end_dt:
        return '', '', '开始时间不能晚于结束时间。'

    return start_date, end_date, ''


def _crawl_time_range(data, platform, crawl_mode):
    if platform == 'bilibili':
        return '', '', ''
    return _validate_crawl_date_range(data)


def _parse_platform(data):
    return 'bilibili'


def _effective_crawl_mode(platform, data):
    return 'api'


def _platform_label(platform):
    return PLATFORM_LABELS.get(platform, 'B站')


def _task_exists(task_id):
    conn = get_conn()
    task = conn.execute("SELECT id FROM crawl_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return task is not None


def _pick_column(columns, aliases):
    normalized = {str(col).strip().lower(): col for col in columns}
    for alias in aliases:
        key = alias.strip().lower()
        if key in normalized:
            return normalized[key]
    for col in columns:
        text = str(col).strip().lower()
        if any(alias.strip().lower() in text for alias in aliases):
            return col
    return None


def _to_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _format_import_time(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return datetime.now().strftime('%Y-%m-%d %H:%M')
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    try:
        parsed = pd.to_datetime(value, errors='coerce')
        if not pd.isna(parsed):
            return parsed.strftime('%Y-%m-%d %H:%M')
    except Exception:
        pass
    text = str(value or '').strip()
    return text or datetime.now().strftime('%Y-%m-%d %H:%M')


def _read_import_dataframe(file_storage):
    filename = (file_storage.filename or '').lower()
    raw = file_storage.read()
    if not raw:
        raise ValueError('文件为空，请选择包含文本数据的文件')

    if filename.endswith('.csv'):
        last_error = None
        for encoding in ('utf-8-sig', 'utf-8', 'gb18030'):
            try:
                return pd.read_csv(StringIO(raw.decode(encoding)))
            except Exception as exc:
                last_error = exc
        raise ValueError(f'CSV 解析失败：{last_error}')

    if filename.endswith(('.xlsx', '.xls')):
        try:
            return pd.read_excel(BytesIO(raw))
        except ImportError as exc:
            raise ValueError('导入 Excel 需要安装 openpyxl，请先执行：python -m pip install openpyxl') from exc
        except Exception as exc:
            raise ValueError(f'Excel 解析失败：{exc}') from exc

    raise ValueError('仅支持 CSV、XLSX、XLS 文件')


def _import_dataframe_to_task(df, dataset_name):
    if df.empty:
        raise ValueError('文件中没有可导入的数据')
    if len(df) > MAX_IMPORT_ROWS:
        df = df.head(MAX_IMPORT_ROWS)

    columns = list(df.columns)
    content_col = _pick_column(columns, [
        'content', 'text', 'clean_content', '正文', '内容', '评论内容', '文本'
    ])
    if content_col is None:
        raise ValueError('未找到文本列，请至少提供 content/text/正文/内容/评论内容 其中一列')

    user_col = _pick_column(columns, ['user_name', 'username', 'user', '昵称', '用户名', '用户', '作者'])
    time_col = _pick_column(columns, ['publish_time', 'created_at', 'time', 'date', '发布时间', '时间', '日期'])
    id_col = _pick_column(columns, ['weibo_id', 'id', 'mid', '评论ID'])
    likes_col = _pick_column(columns, ['likes', 'attitudes_count', '点赞', '点赞数'])
    comments_col = _pick_column(columns, ['comments', 'comments_count', '评论', '评论数'])
    reposts_col = _pick_column(columns, ['reposts', 'reposts_count', '转发', '转发数'])

    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO crawl_tasks (keyword, start_date, end_date, source, target_count, status, error_message) VALUES (?, ?, ?, ?, ?, 'running', ?)",
        (dataset_name, '', '', 'import', len(df), '正在导入本地数据')
    )
    task_id = cur.lastrowid

    imported = 0
    for _, row in df.iterrows():
        content = str(row.get(content_col, '') if content_col in row else '').strip()
        if not content or content.lower() == 'nan':
            continue

        user_name = str(row.get(user_col, '导入用户') if user_col else '导入用户').strip() or '导入用户'
        publish_time = _format_import_time(row.get(time_col) if time_col else None)
        weibo_id = str(row.get(id_col, '') if id_col else '').strip()
        if weibo_id.lower() == 'nan':
            weibo_id = ''

        conn.execute(
            '''INSERT INTO weibo_posts
               (task_id, weibo_id, user_name, content, clean_content,
                publish_time, likes, comments, reposts)
               VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?)''',
            (
                task_id,
                weibo_id,
                user_name,
                content,
                publish_time,
                _to_int(row.get(likes_col) if likes_col else 0),
                _to_int(row.get(comments_col) if comments_col else 0),
                _to_int(row.get(reposts_col) if reposts_col else 0),
            )
        )
        imported += 1

    conn.commit()
    conn.close()

    if imported <= 0:
        update_task_status(task_id, 'failed', crawled_count=0, error_message='文件中没有有效文本内容')
        raise ValueError('文件中没有有效文本内容')

    preprocess_task(task_id)
    deduplicate_task(task_id)

    conn = get_conn()
    final_count = conn.execute(
        "SELECT COUNT(*) as c FROM weibo_posts WHERE task_id=?",
        (task_id,)
    ).fetchone()['c']
    conn.close()
    update_task_status(task_id, 'done', crawled_count=final_count, error_message='')
    return task_id, imported, final_count


# ===== 静态文件 =====
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


# ===== 仪表盘 =====
@app.route('/api/dashboard/stats')
def dashboard_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM weibo_posts").fetchone()['c']
    tasks = conn.execute(
        "SELECT COUNT(*) as c FROM crawl_tasks WHERE status='done' AND crawled_count>0"
    ).fetchone()['c']

    sentiment = conn.execute(
        "SELECT label, COUNT(*) as c FROM sentiment_results GROUP BY label"
    ).fetchall()
    conn.close()

    s_map = {r['label']: r['c'] for r in sentiment}
    s_total = sum(s_map.values()) or 1
    return jsonify({
        'total_data': total,
        'hot_topics': tasks,
        'positive_pct': round(s_map.get('positive', 0) / s_total * 100, 1),
        'negative_pct': round(s_map.get('negative', 0) / s_total * 100, 1),
    })


@app.route('/api/dashboard/trend')
def dashboard_trend():
    conn = get_conn()
    rows = conn.execute('''
        SELECT substr(w.publish_time, 1, 10) as day, s.label, COUNT(*) as cnt
        FROM sentiment_results s
        JOIN weibo_posts w ON s.post_id = w.id
        GROUP BY day, s.label
        ORDER BY day
    ''').fetchall()
    conn.close()

    days_data = {}
    for r in rows:
        day = r['day']
        if day not in days_data:
            days_data[day] = {'positive': 0, 'neutral': 0, 'negative': 0}
        days_data[day][r['label']] = r['cnt']

    days = sorted(days_data.keys())[-7:]
    return jsonify({
        'days': days,
        'positive': [days_data.get(d, {}).get('positive', 0) for d in days],
        'neutral': [days_data.get(d, {}).get('neutral', 0) for d in days],
        'negative': [days_data.get(d, {}).get('negative', 0) for d in days],
    })


@app.route('/api/dashboard/wordcloud')
def dashboard_wordcloud():
    conn = get_conn()
    rows = conn.execute(
        "SELECT clean_content FROM weibo_posts WHERE clean_content IS NOT NULL AND clean_content!=''"
    ).fetchall()
    conn.close()

    word_counter = Counter()
    for r in rows:
        words = segment(r['clean_content'])
        word_counter.update(words)

    top_words = [{'name': w, 'value': c} for w, c in word_counter.most_common(60)]
    return jsonify(top_words)


@app.route('/api/dashboard/hot_topics')
def dashboard_hot_topics():
    conn = get_conn()
    tasks = conn.execute(
        "SELECT t.id, t.keyword, t.crawled_count, t.created_at FROM crawl_tasks t WHERE t.status='done' AND t.crawled_count>0 ORDER BY t.created_at DESC"
    ).fetchall()

    items = []
    for t in tasks:
        note_rows = conn.execute('''
            SELECT
                COALESCE(NULLIF(parent_note_id, ''), weibo_id, CAST(id AS TEXT)) as note_key,
                MAX(CASE WHEN COALESCE(parent_note_heat, 0) > 0 THEN parent_note_heat ELSE COALESCE(comments, 0) END) as note_heat
            FROM weibo_posts
            WHERE task_id=?
            GROUP BY note_key
        ''', (t['id'],)).fetchall()
        comment_heat = sum((r['note_heat'] or 0) for r in note_rows) or t['crawled_count']
        like_row = conn.execute(
            "SELECT COALESCE(SUM(likes), 0) as likes FROM weibo_posts WHERE task_id=?",
            (t['id'],)
        ).fetchone()
        comment_likes = like_row['likes'] if like_row else 0

        sentiment = conn.execute(
            "SELECT label, COUNT(*) as c FROM sentiment_results WHERE task_id=? GROUP BY label",
            (t['id'],)
        ).fetchall()
        s_map = {r['label']: r['c'] for r in sentiment}
        dominant = max(s_map, key=s_map.get) if s_map else 'neutral'
        label_map = {'positive': '正面', 'neutral': '中性', 'negative': '负面'}
        items.append({
            'keyword': t['keyword'],
            'count': t['crawled_count'],
            'sentiment': label_map.get(dominant, '中性'),
            'sentiment_key': dominant,
            'comment_heat': comment_heat,
            'comment_likes': comment_likes,
        })
    conn.close()

    max_heat = max((item['comment_heat'] for item in items), default=0) or 1
    max_likes = max((item['comment_likes'] for item in items), default=0) or 1
    for item in items:
        heat_norm = item['comment_heat'] / max_heat * 100
        likes_norm = item['comment_likes'] / max_likes * 100 if max_likes else 0
        heat_score = heat_norm * 0.7 + likes_norm * 0.3
        item['heat_score'] = round(heat_score, 1)
        item['heat_components'] = {
            'comment_heat_norm': round(heat_norm, 1),
            'comment_likes_norm': round(likes_norm, 1),
        }

    items.sort(key=lambda item: item['heat_score'], reverse=True)
    return jsonify(items[:10])


# ===== 数据采集 =====
@app.route('/api/crawl/cookie', methods=['GET'])
def crawl_cookie_status():
    platform = str(request.args.get('platform') or 'bilibili').strip().lower()
    return jsonify(get_cookie_status(platform if platform in {'bilibili'} else 'bilibili'))


@app.route('/api/crawl/cookie', methods=['POST'])
def crawl_cookie_save():
    data = _json_body()
    platform = _parse_platform(data)
    cookie = str(data.get('cookie') or '').strip()
    if not cookie:
        return jsonify({'error': 'Cookie 不能为空'}), 400
    set_platform_cookie(platform, cookie)
    return jsonify(get_cookie_status(platform))


@app.route('/api/crawl/cookie', methods=['DELETE'])
def crawl_cookie_clear():
    platform = str(request.args.get('platform') or 'bilibili').strip().lower()
    platform = platform if platform in {'bilibili'} else 'bilibili'
    clear_platform_cookie(platform)
    return jsonify(get_cookie_status(platform))


@app.route('/api/crawl/check', methods=['POST'])
def crawl_check():
    data = _json_body()
    platform = _parse_platform(data)
    crawl_mode = _effective_crawl_mode(platform, data)
    keyword = str(data.get('keyword') or '').strip()
    if not keyword:
        return jsonify({'error': '请先输入关键词再检测'}), 400

    start_date, end_date, date_error = _crawl_time_range(data, platform, crawl_mode)
    if date_error:
        return jsonify({'error': date_error}), 400
    try:
        result = check_bilibili(keyword, start_date, end_date)
    except Exception as exc:
        return jsonify({
            'ok': False,
            'message': f'检测失败：{str(exc) or exc.__class__.__name__}',
            'sample_count': 0,
        }), 502
    return jsonify(result)


@app.route('/api/crawl/start', methods=['POST'])
def crawl_start():
    data = _json_body()
    platform = _parse_platform(data)
    crawl_mode = _effective_crawl_mode(platform, data)
    keyword = str(data.get('keyword') or '').strip()
    if not keyword:
        return jsonify({'error': '关键词不能为空'}), 400

    target = _parse_int(data.get('target_count'), 500, 1, MAX_TARGET_COUNT)
    start_date, end_date, date_error = _crawl_time_range(data, platform, crawl_mode)
    if date_error:
        return jsonify({'error': date_error}), 400
    if platform == 'bilibili' and not get_cookie_status('bilibili').get('configured'):
        return jsonify({'error': '请先配置 B站 Cookie 后再开始热门视频评论采集'}), 400

    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO crawl_tasks (keyword, start_date, end_date, source, target_count) VALUES (?, ?, ?, ?, ?)",
        (keyword, start_date, end_date, platform, target)
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()

    thread = threading.Thread(
        target=_crawl_worker,
        args=(task_id, keyword, target, start_date, end_date, platform, crawl_mode),
        name=f'crawl-task-{task_id}'
    )
    thread.start()

    return jsonify({'task_id': task_id})


def _crawl_worker(task_id, keyword, target, start_date, end_date, platform='bilibili', crawl_mode='api'):
    try:
        crawl_bilibili(task_id, keyword, target, start_date, end_date)
        conn = get_conn()
        status_row = conn.execute("SELECT status FROM crawl_tasks WHERE id=?", (task_id,)).fetchone()
        conn.close()
        preprocess_task(task_id)
        deduplicate_task(task_id)
        conn = get_conn()
        final_count = conn.execute(
            "SELECT COUNT(*) as c FROM weibo_posts WHERE task_id=?",
            (task_id,)
        ).fetchone()['c']
        conn.close()
        if final_count <= 0:
            update_task_status(
                task_id,
                'failed',
                crawled_count=0,
                error_message=f'没有采集到有效{_platform_label(platform)}内容，可能是接口限制、关键词无结果或日期范围过窄'
            )
            return
        update_task_status(task_id, 'done', crawled_count=final_count, error_message='')
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        conn = get_conn()
        row = conn.execute("SELECT status FROM crawl_tasks WHERE id=?", (task_id,)).fetchone()
        conn.close()
        update_task_status(task_id, 'failed', error_message=message[:500])


@app.route('/api/crawl/progress/<int:task_id>')
def crawl_progress(task_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM crawl_tasks WHERE id=?", (task_id,)
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify({
        'task_id': row['id'],
        'keyword': row['keyword'],
        'target_count': row['target_count'],
        'crawled_count': row['crawled_count'],
        'status': row['status'],
        'error_message': row['error_message'],
    })


@app.route('/api/crawl/history')
def crawl_history():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM crawl_tasks ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([{
        'id': r['id'],
        'keyword': r['keyword'],
        'source': _platform_label(r['source'] or ('import' if not r['start_date'] and not r['end_date'] else 'bilibili')),
        'crawled_count': r['crawled_count'],
        'created_at': r['created_at'],
        'status': r['status'],
        'error_message': r['error_message'],
    } for r in rows])


@app.route('/api/crawl/history', methods=['DELETE'])
def crawl_history_clear():
    conn = get_conn()
    conn.execute("DELETE FROM crawl_tasks")
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/crawl/<int:task_id>', methods=['DELETE'])
def crawl_delete(task_id):
    conn = get_conn()
    conn.execute("DELETE FROM crawl_tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


# ===== 主题挖掘 =====
@app.route('/api/import/upload', methods=['POST'])
def import_upload():
    file_storage = request.files.get('file')
    if not file_storage or not file_storage.filename:
        return jsonify({'error': '请选择 CSV 或 Excel 文件'}), 400

    dataset_name = str(request.form.get('dataset_name') or '').strip()
    if not dataset_name:
        base_name = os.path.splitext(os.path.basename(file_storage.filename))[0]
        dataset_name = f'导入数据-{base_name[:30] or "未命名"}'

    try:
        df = _read_import_dataframe(file_storage)
        task_id, raw_count, final_count = _import_dataframe_to_task(df, dataset_name)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        return jsonify({'error': f'导入失败：{exc}'}), 500

    return jsonify({
        'ok': True,
        'task_id': task_id,
        'raw_count': raw_count,
        'final_count': final_count,
        'message': f'导入完成：读取 {raw_count} 条，清洗去重后保留 {final_count} 条有效数据。'
    })


@app.route('/api/import/template')
def import_template():
    content = (
        'weibo_id,user_name,content,publish_time,likes,comments,reposts\n'
        '10001,示例用户,这是一条公开数据集里的文本内容,2026-04-28 10:00,12,3,1\n'
        '10002,示例用户2,也可以导入评论或其他文本内容,2026-04-28 11:30,8,1,0\n'
    )
    return app.response_class(
        content,
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=import_template.csv'}
    )


@app.route('/api/topic/analyze', methods=['POST'])
def topic_analyze():
    data = _json_body()
    task_id = _parse_int(data.get('task_id'), 0, 0)
    num_topics = _parse_int(data.get('num_topics'), 5, 2, 20)

    if not _task_exists(task_id):
        return jsonify({'error': '任务不存在'}), 404

    try:
        results = run_lda(task_id, num_topics)
    except ValueError as exc:
        return jsonify({'error': f'主题分析失败：{exc}'}), 400
    if not results:
        return jsonify({'error': '可用于主题分析的文本不足，请先采集更多有效内容'}), 400
    return jsonify(results)


@app.route('/api/topic/results/<int:task_id>')
def topic_results(task_id):
    results = get_topic_results(task_id)
    return jsonify(results)


# ===== 情感分析 =====
@app.route('/api/sentiment/analyze', methods=['POST'])
def sentiment_analyze():
    data = _json_body()
    task_id = _parse_int(data.get('task_id'), 0, 0)

    if not _task_exists(task_id):
        return jsonify({'error': '任务不存在'}), 404

    count = analyze_sentiment(task_id)
    stats = get_sentiment_stats(task_id)
    return jsonify({'analyzed_count': count, 'stats': stats})


@app.route('/api/sentiment/results/<int:task_id>')
def sentiment_results(task_id):
    stats = get_sentiment_stats(task_id)
    distribution = get_score_distribution(task_id)
    return jsonify({'stats': stats, 'distribution': distribution})


@app.route('/api/sentiment/comments/<int:task_id>')
def sentiment_comments(task_id):
    label_filter = request.args.get('label', 'all')
    page = _parse_int(request.args.get('page'), 1, 1)
    page_size = _parse_int(request.args.get('page_size'), 10, 1, 100)
    offset = (page - 1) * page_size
    conn = get_conn()
    if label_filter == 'all':
        total = conn.execute(
            "SELECT COUNT(*) as c FROM sentiment_results WHERE task_id=?",
            (task_id,)
        ).fetchone()['c']
        rows = conn.execute('''
            SELECT w.user_name, w.clean_content, w.publish_time, s.score, s.label
            FROM sentiment_results s
            JOIN weibo_posts w ON s.post_id = w.id
            WHERE s.task_id=?
            ORDER BY w.publish_time DESC, w.id DESC
            LIMIT ? OFFSET ?
        ''', (task_id, page_size, offset)).fetchall()
    else:
        total = conn.execute(
            "SELECT COUNT(*) as c FROM sentiment_results WHERE task_id=? AND label=?",
            (task_id, label_filter)
        ).fetchone()['c']
        rows = conn.execute('''
            SELECT w.user_name, w.clean_content, w.publish_time, s.score, s.label
            FROM sentiment_results s
            JOIN weibo_posts w ON s.post_id = w.id
            WHERE s.task_id=? AND s.label=?
            ORDER BY s.score DESC
            LIMIT ? OFFSET ?
        ''', (task_id, label_filter, page_size, offset)).fetchall()
    conn.close()

    label_cn = {'positive': '正面', 'neutral': '中性', 'negative': '负面'}
    items = [{
        'user_name': r['user_name'],
        'content': r['clean_content'],
        'publish_time': r['publish_time'],
        'score': r['score'],
        'label': r['label'],
        'label_cn': label_cn.get(r['label'], '中性'),
    } for r in rows]
    return jsonify({
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
        'pages': (total + page_size - 1) // page_size if total else 0,
    })


# ===== 数据可视化 =====
@app.route('/api/visual/volume/<int:task_id>')
def visual_volume(task_id):
    conn = get_conn()
    rows = conn.execute('''
        SELECT
            COALESCE(NULLIF(parent_note_title, ''), '未知笔记') as note_title,
            COUNT(*) as cnt,
            MAX(COALESCE(parent_note_heat, 0)) as heat
        FROM weibo_posts
        WHERE task_id=?
        GROUP BY COALESCE(NULLIF(parent_note_id, ''), weibo_id), note_title
        ORDER BY cnt DESC, heat DESC
        LIMIT 10
    ''', (task_id,)).fetchall()
    conn.close()
    return jsonify({
        'labels': [r['note_title'][:24] for r in rows],
        'counts': [r['cnt'] for r in rows],
        'heats': [r['heat'] for r in rows],
    })


@app.route('/api/visual/active/<int:task_id>')
def visual_active(task_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT label, COUNT(*) as cnt FROM sentiment_results WHERE task_id=? GROUP BY label",
        (task_id,)
    ).fetchall()
    conn.close()
    stats = {'positive': 0, 'neutral': 0, 'negative': 0}
    for r in rows:
        stats[r['label']] = r['cnt']
    total = sum(stats.values())
    negative_pct = round(stats['negative'] / total * 100, 1) if total else 0
    if negative_pct >= 40:
        level = 'high'
        message = '负面情绪占比较高，建议重点关注争议观点与风险表达。'
    elif negative_pct >= 25:
        level = 'medium'
        message = '负面情绪处于中等水平，话题存在一定争议。'
    else:
        level = 'low'
        message = '负面情绪占比较低，整体舆情风险较弱。'
    return jsonify({
        'negative_pct': negative_pct,
        'level': level,
        'message': message,
        'total': total,
        'stats': stats,
    })


@app.route('/api/visual/sentiment/<int:task_id>')
def visual_sentiment(task_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT label, COUNT(*) as cnt FROM sentiment_results WHERE task_id=? GROUP BY label",
        (task_id,)
    ).fetchall()
    conn.close()
    data = {'positive': 0, 'neutral': 0, 'negative': 0}
    for r in rows:
        data[r['label']] = r['cnt']
    return jsonify({
        'labels': ['正面', '中立', '负面'],
        'counts': [data['positive'], data['neutral'], data['negative']],
        'keys': ['positive', 'neutral', 'negative'],
        'total': sum(data.values()),
    })


@app.route('/api/visual/network/<int:task_id>')
def visual_network(task_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT clean_content FROM weibo_posts WHERE task_id=? AND clean_content IS NOT NULL AND clean_content!=''",
        (task_id,)
    ).fetchall()
    conn.close()

    word_counter = Counter()
    co_counter = Counter()
    for r in rows:
        words = list(set(segment(r['clean_content'])))
        word_counter.update(words)
        for i in range(len(words)):
            for j in range(i + 1, len(words)):
                pair = tuple(sorted([words[i], words[j]]))
                co_counter[pair] += 1

    top_words = [w for w, _ in word_counter.most_common(20)]
    nodes = [{'name': w, 'value': word_counter[w], 'symbolSize': min(word_counter[w] / 2 + 10, 50)} for w in top_words]
    links = []
    for (w1, w2), cnt in co_counter.most_common(40):
        if w1 in top_words and w2 in top_words:
            links.append({'source': w1, 'target': w2, 'value': cnt})

    return jsonify({'nodes': nodes, 'links': links})


# ===== 数据集列表（供前端下拉框使用） =====
@app.route('/api/datasets')
def datasets():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, keyword, source, crawled_count, created_at FROM crawl_tasks WHERE status='done' AND crawled_count>0 ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([{
        'id': r['id'],
        'keyword': r['keyword'],
        'count': r['crawled_count'],
        'label': f"{r['keyword']} - {_platform_label(r['source'] or 'bilibili')} ({r['crawled_count']}条)",
    } for r in rows])


init_db()


def _open_browser_later(host, port):
    if os.getenv('AUTO_OPEN_BROWSER', '1').lower() not in {'1', 'true', 'yes'}:
        return
    url = f'http://{host}:{port}/'
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()


if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', '').lower() in {'1', 'true', 'yes'}
    host = os.getenv('HOST', DEFAULT_HOST)
    port = _parse_int(os.getenv('PORT'), DEFAULT_PORT, 1, 65535)
    _open_browser_later(host, port)
    app.run(host=host, debug=debug, port=port, use_reloader=False)

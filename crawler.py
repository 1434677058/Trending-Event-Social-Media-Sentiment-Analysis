import hashlib
import json
import random
import re
import string
import time
from datetime import datetime, timedelta
from html import unescape
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

import requests
from bs4 import BeautifulSoup

from crawler_config import get_bilibili_cookie
from database import get_conn


MAX_FAILURES = 5
MAX_EMPTY_PAGES = 2
BILIBILI_SEARCH_URL = 'https://api.bilibili.com/x/web-interface/search/type'
BILIBILI_VIEW_URL = 'https://api.bilibili.com/x/web-interface/view'
BILIBILI_REPLY_URL = 'https://api.bilibili.com/x/v2/reply/wbi/main'
BILIBILI_WBI_MIXIN_KEY = 'ea1db124af3c7062474693fa704f4ff8'
BILIBILI_HOT_VIDEO_LIMIT = 10
BILIBILI_COMMENT_PAGE_SIZE = 20
BILIBILI_COMMENT_MAX_PAGES_PER_VIDEO = 4
BILIBILI_REQUEST_DELAY_RANGE = (1.5, 3.5)


def check_bilibili(keyword, start_date=None, end_date=None):
    """检测 B站热门视频评论采集入口是否可用。"""
    cookie = get_bilibili_cookie()
    if not cookie:
        return {
            'ok': False,
            'source': 'B站热门视频评论采集',
            'status_code': 0,
            'message': '请先配置 B站 Cookie 后再检测热门视频评论采集',
            'sample_count': 0,
            'note': 'B站采集支持 BV号/视频链接直采，也支持关键词先搜索热门视频再采集公开一级评论。',
        }

    try:
        direct_id = _extract_bili_video_id(keyword)
        if direct_id:
            video = _fetch_bili_video_info(direct_id, cookie)
            samples = _extract_bili_comments_for_video(video, cookie, min(10, BILIBILI_COMMENT_PAGE_SIZE))
            return {
                'ok': bool(samples),
                'source': 'B站单视频评论采集',
                'status_code': 200,
                'message': f'已识别到视频 {video.get("bvid") or direct_id}，可读取公开一级评论' if samples else '已识别到视频，但当前没有检测到可读取评论',
                'sample_count': len(samples),
                'note': '检测样本数只表示本次探测读取到的评论样本，不是该视频评论总量。',
            }

        videos = _search_bili_hot_videos(keyword, cookie, max_videos=5)
        available = [item for item in videos if _safe_int(item.get('reply_count')) > 0]
        return {
            'ok': bool(available),
            'source': 'B站关键词热门视频采集',
            'status_code': 200,
            'message': f'已找到 {len(available)} 条带评论的热门视频候选' if available else '接口可访问，但当前关键词没有检测到带评论的热门视频候选',
            'sample_count': len(available),
            'note': '正式采集会优先选择评论数较高的视频，并读取公开视频的一层评论，达到目标评论数后停止。',
        }
    except Exception as exc:
        return {
            'ok': False,
            'source': 'B站热门视频评论采集',
            'status_code': 0,
            'message': str(exc) or exc.__class__.__name__,
            'sample_count': 0,
            'note': '如果 Cookie 过期或接口临时失败，请在浏览器重新登录 B站后更新 Cookie。',
        }


def crawl_bilibili(task_id, keyword, target_count=500, start_date=None, end_date=None):
    """采集 B站热门视频下的公开一级评论。"""
    cookie = get_bilibili_cookie()
    if not cookie:
        raise RuntimeError('B站评论采集需要先配置 B站 Cookie')
    return _crawl_bilibili_hot_comments(task_id, keyword, target_count, cookie)


# ---------------------------------------------------------------------------
#  共用工具函数
# ---------------------------------------------------------------------------

def _normalize_date(value):
    value = str(value or '').strip()
    if not value:
        return ''
    digits = re.sub(r'\D', '', value)
    return digits if len(digits) == 8 else ''


def _parse_date_value(value):
    normalized = _normalize_date(value)
    if not normalized:
        return None
    try:
        return datetime.strptime(normalized, '%Y%m%d').date()
    except ValueError:
        return None


def _clean_weibo_text(text):
    text = unescape(text or '')
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'#[^#]+#', '', text)
    text = re.sub(r'@[\w一-鿿]+', '', text)
    text = re.sub(r'https?://\S+', '', text)
    return text.strip()


def _safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _post_date_in_range(post, start_date, end_date):
    post_date = _parse_date_value(str(post.get('publish_time') or '')[:10])
    start_dt = _parse_date_value(start_date)
    end_dt = _parse_date_value(end_date)
    if not start_dt and not end_dt:
        return True
    if not post_date:
        return False
    if start_dt and post_date < start_dt:
        return False
    if end_dt and post_date > end_dt:
        return False
    return True


def _candidate_key(post):
    return post.get('weibo_id') or post.get('clean_content') or ''


def _insert_mobile_post(conn, task_id, post, seen_ids, seen_contents):
    weibo_id = post['weibo_id']
    clean_content = post['clean_content']
    if weibo_id and weibo_id in seen_ids:
        return False
    if clean_content in seen_contents:
        return False

    if weibo_id:
        exists = conn.execute(
            "SELECT 1 FROM weibo_posts WHERE task_id=? AND weibo_id=? LIMIT 1",
            (task_id, weibo_id)
        ).fetchone()
        if exists:
            seen_ids.add(weibo_id)
            return False

    columns = [
        'task_id', 'weibo_id', 'user_name', 'content', 'clean_content',
        'publish_time', 'likes', 'comments', 'reposts'
    ]
    values = [
        task_id,
        weibo_id,
        post['user_name'],
        post['content'],
        clean_content,
        post['publish_time'],
        post['likes'],
        post['comments'],
        post['reposts'],
    ]
    optional_columns = {
        'data_type': 'data_type',
        'parent_note_id': 'parent_note_id',
        'parent_note_title': 'parent_note_title',
        'parent_note_author': 'parent_note_author',
        'parent_note_heat': 'parent_note_heat',
    }
    for key, column in optional_columns.items():
        if key in post:
            columns.append(column)
            values.append(post.get(key))

    placeholders = ', '.join(['?'] * len(columns))
    conn.execute(
        f"INSERT INTO weibo_posts ({', '.join(columns)}) VALUES ({placeholders})",
        values
    )
    if weibo_id:
        seen_ids.add(weibo_id)
    seen_contents.add(clean_content)
    return True


# ---------------------------------------------------------------------------
#  B站相关函数
# ---------------------------------------------------------------------------

def _bili_headers(cookie=''):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://www.bilibili.com/',
        'Origin': 'https://www.bilibili.com',
    }
    if cookie:
        headers['Cookie'] = cookie
    return headers


def _extract_bili_video_id(value):
    text = str(value or '').strip()
    if not text:
        return ''
    match = re.search(r'(BV[0-9A-Za-z]{10,})', text)
    if match:
        return match.group(1)
    match = re.search(r'(?:^|[^\w])av(\d{3,})', text, re.IGNORECASE)
    if match:
        return f'av{match.group(1)}'
    try:
        parsed = urlparse(text)
        if parsed.netloc and 'bilibili.com' in parsed.netloc:
            path_match = re.search(r'/video/(BV[0-9A-Za-z]{10,}|av\d+)', parsed.path, re.IGNORECASE)
            if path_match:
                return path_match.group(1)
            query = parse_qs(parsed.query)
            bvid = (query.get('bvid') or [''])[0]
            if bvid:
                return bvid
    except Exception:
        pass
    return ''


def _normalize_bili_title(title):
    text = unescape(re.sub(r'<[^>]+>', '', str(title or '')))
    return re.sub(r'\s+', ' ', text).strip()


def _parse_bili_count(value):
    text = str(value or '').replace(',', '').strip()
    if not text or text == '--':
        return 0
    multiplier = 1
    if text.endswith('万'):
        multiplier = 10000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        digits = re.findall(r'\d+', text)
        return int(digits[0]) if digits else 0


def _extract_bili_search_video(item):
    aid = str(item.get('aid') or item.get('id') or '').strip()
    bvid = str(item.get('bvid') or '').strip()
    if not aid and not bvid:
        return None
    title = _normalize_bili_title(item.get('title') or item.get('typename') or '')
    author = str(item.get('author') or item.get('mid') or 'B站用户').strip()[:80]
    reply_count = _parse_bili_count(item.get('review') or item.get('reply') or item.get('comment') or 0)
    play_count = _parse_bili_count(item.get('play') or 0)
    heat = reply_count or _parse_bili_count(item.get('video_review') or 0) or play_count
    return {
        'aid': aid,
        'bvid': bvid,
        'title': title or bvid or aid,
        'author': author or 'B站用户',
        'publish_time': _parse_bili_time(item.get('pubdate') or item.get('senddate') or ''),
        'reply_count': reply_count,
        'play_count': play_count,
        'like_count': _parse_bili_count(item.get('like') or 0),
        'heat': heat,
    }


def _parse_bili_time(value):
    if value in (None, ''):
        return datetime.now().strftime('%Y-%m-%d %H:%M')
    try:
        return datetime.fromtimestamp(int(value)).strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError, OSError):
        pass
    text = str(value or '').strip()
    if re.match(r'\d{4}-\d{1,2}-\d{1,2}', text):
        try:
            return datetime.strptime(text[:10], '%Y-%m-%d').strftime('%Y-%m-%d %H:%M')
        except ValueError:
            return text
    return text or datetime.now().strftime('%Y-%m-%d %H:%M')


def _fetch_bili_video_info(video_id, cookie):
    params = {}
    video_id = str(video_id or '').strip()
    if video_id.lower().startswith('av'):
        params['aid'] = re.sub(r'\D', '', video_id)
    else:
        params['bvid'] = video_id
    resp = requests.get(BILIBILI_VIEW_URL, params=params, headers=_bili_headers(cookie), timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f'B站视频信息接口返回 HTTP {resp.status_code}')
    data = resp.json()
    if data.get('code') != 0:
        raise RuntimeError(data.get('message') or 'B站视频信息接口返回失败')
    info = data.get('data') or {}
    stat = info.get('stat') or {}
    owner = info.get('owner') or {}
    return {
        'aid': str(info.get('aid') or params.get('aid') or '').strip(),
        'bvid': str(info.get('bvid') or params.get('bvid') or '').strip(),
        'title': _normalize_bili_title(info.get('title') or ''),
        'author': str(owner.get('name') or 'B站用户').strip()[:80],
        'publish_time': _parse_bili_time(info.get('pubdate') or ''),
        'reply_count': _safe_int(stat.get('reply')),
        'play_count': _safe_int(stat.get('view')),
        'like_count': _safe_int(stat.get('like')),
        'heat': _safe_int(stat.get('reply')) or _safe_int(stat.get('view')),
    }


def _search_bili_hot_videos(keyword, cookie, max_videos=BILIBILI_HOT_VIDEO_LIMIT):
    videos = []
    seen = set()
    max_pages = 2
    for page in range(1, max_pages + 1):
        resp = requests.get(
            BILIBILI_SEARCH_URL,
            params={
                'search_type': 'video',
                'keyword': keyword,
                'order': 'click',
                'page': page,
            },
            headers=_bili_headers(cookie),
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f'B站搜索接口返回 HTTP {resp.status_code}')
        data = resp.json()
        if data.get('code') != 0:
            raise RuntimeError(data.get('message') or 'B站搜索接口返回失败')
        for item in (data.get('data') or {}).get('result') or []:
            video = _extract_bili_search_video(item)
            if not video:
                continue
            key = video.get('bvid') or video.get('aid')
            if not key or key in seen:
                continue
            seen.add(key)
            videos.append(video)
        if len(videos) >= max_videos:
            break
        time.sleep(random.uniform(0.8, 1.5))

    enriched = []
    for video in sorted(videos, key=_bili_video_sort_key, reverse=True)[:max_videos]:
        try:
            identifier = video.get('bvid') or f"av{video.get('aid')}"
            enriched.append(_fetch_bili_video_info(identifier, cookie))
            time.sleep(random.uniform(0.4, 1.0))
        except Exception:
            enriched.append(video)
    return sorted(enriched, key=_bili_video_sort_key, reverse=True)[:max_videos]


def _bili_video_sort_key(video):
    return (
        _safe_int(video.get('reply_count')),
        _safe_int(video.get('like_count')),
        _safe_int(video.get('play_count')),
        _safe_int(video.get('heat')),
    )


def _sign_bili_wbi_params(params):
    signed = {k: v for k, v in params.items() if v is not None}
    signed['wts'] = int(time.time())
    query = urlencode(sorted((k, str(v)) for k, v in signed.items()))
    signed['w_rid'] = hashlib.md5((query + BILIBILI_WBI_MIXIN_KEY).encode('utf-8')).hexdigest()
    return signed


def _fetch_bili_comment_page(video, cookie, pagination_offset=''):
    oid = str(video.get('aid') or '').strip()
    if not oid:
        raise RuntimeError('B站评论采集缺少视频 aid，无法读取评论')
    pagination_str = json.dumps({'offset': str(pagination_offset or '')}, ensure_ascii=False, separators=(',', ':'))
    params = {
        'mode': 3,
        'oid': oid,
        'pagination_str': pagination_str,
        'plat': 1,
        'seek_rpid': '',
        'type': 1,
        'web_location': 1315875,
    }
    resp = requests.get(
        BILIBILI_REPLY_URL,
        params=_sign_bili_wbi_params(params),
        headers=_bili_headers(cookie),
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f'B站评论接口返回 HTTP {resp.status_code}')
    data = resp.json()
    if data.get('code') != 0:
        raise RuntimeError(data.get('message') or 'B站评论接口返回失败')
    return data.get('data') or {}


def _parse_bili_comment(reply, video):
    content = ((reply.get('content') or {}).get('message') or '').strip()
    clean_content = _clean_weibo_text(content)
    if not clean_content:
        return None
    member = reply.get('member') or {}
    rpid = str(reply.get('rpid') or '').strip()
    if not rpid:
        rpid = f"{video.get('bvid') or video.get('aid')}:{abs(hash(clean_content))}"
    return {
        'weibo_id': f'bili-comment:{rpid}',
        'user_name': str(member.get('uname') or 'B站用户').strip()[:80],
        'content': content,
        'clean_content': clean_content,
        'publish_time': _parse_bili_time(reply.get('ctime') or ''),
        'likes': _safe_int(reply.get('like')),
        'comments': _safe_int(reply.get('rcount')),
        'reposts': 0,
        'data_type': 'comment',
        'parent_note_id': video.get('bvid') or video.get('aid') or '',
        'parent_note_title': video.get('title') or '',
        'parent_note_author': video.get('author') or '',
        'parent_note_heat': video.get('reply_count') or video.get('heat') or 0,
    }


def _extract_bili_comments_for_video(video, cookie, limit):
    comments = []
    seen = set()
    next_offset = ''
    max_pages = max(1, min(BILIBILI_COMMENT_MAX_PAGES_PER_VIDEO, (int(limit or 1) + BILIBILI_COMMENT_PAGE_SIZE - 1) // BILIBILI_COMMENT_PAGE_SIZE + 1))
    for _ in range(max_pages):
        data = _fetch_bili_comment_page(video, cookie, next_offset)
        replies = data.get('replies') or []
        if not replies:
            break
        for raw in replies:
            parsed = _parse_bili_comment(raw, video)
            if not parsed:
                continue
            key = parsed.get('weibo_id') or parsed.get('clean_content')
            if not key or key in seen:
                continue
            comments.append(parsed)
            seen.add(key)
            if len(comments) >= limit:
                return comments
        cursor = data.get('cursor') or {}
        pagination = cursor.get('pagination_reply') or {}
        next_offset = pagination.get('next_offset') or cursor.get('next') or ''
        if not next_offset or str(next_offset) == '0':
            break
        time.sleep(random.uniform(*BILIBILI_REQUEST_DELAY_RANGE))
    return comments


def _crawl_bilibili_hot_comments(task_id, keyword, target_count=500, cookie=''):
    conn = get_conn()
    conn.execute(
        "UPDATE crawl_tasks SET status='running', error_message=? WHERE id=?",
        ('使用B站热门视频评论采集中：先定位热门视频，再采集公开一级评论', task_id)
    )
    conn.commit()

    collected = 0
    seen_ids = set()
    seen_contents = set()

    def progress(message, count=None):
        conn.execute(
            "UPDATE crawl_tasks SET crawled_count=?, error_message=? WHERE id=?",
            (count if count is not None else collected, message[:500], task_id)
        )
        conn.commit()

    try:
        direct_id = _extract_bili_video_id(keyword)
        if direct_id:
            parents = [_fetch_bili_video_info(direct_id, cookie)]
            progress(f'B站评论采集：已识别视频 {parents[0].get("title") or direct_id}，准备读取评论', 0)
        else:
            video_limit = BILIBILI_HOT_VIDEO_LIMIT if target_count >= 50 else max(1, min(BILIBILI_HOT_VIDEO_LIMIT, (target_count + 9) // 10))
            parents = _search_bili_hot_videos(keyword, cookie, max_videos=video_limit)
            parents = [item for item in parents if _safe_int(item.get('reply_count')) > 0 or item.get('aid')]
            progress(f'B站评论采集：已找到 {len(parents)} 条热门视频候选', 0)

        if not parents:
            progress('B站评论采集：未找到可读取评论的热门视频', 0)
            return 0

        for index, parent in enumerate(parents, 1):
            if collected >= target_count:
                break
            remaining = target_count - collected
            slots_left = max(1, len(parents) - index + 1)
            limit = remaining if len(parents) == 1 else max(10, min(remaining, (remaining + slots_left - 1) // slots_left))
            progress(
                f'B站评论采集：正在读取第 {index}/{len(parents)} 条热门视频评论，'
                f'目标本视频 {limit} 条，已采集 {collected}/{target_count} 条'
            )
            try:
                comment_posts = _extract_bili_comments_for_video(parent, cookie, limit)
            except Exception as exc:
                progress(f'B站评论采集：第 {index}/{len(parents)} 条视频评论读取失败：{str(exc)[:120]}', collected)
                time.sleep(random.uniform(*BILIBILI_REQUEST_DELAY_RANGE))
                continue

            inserted = 0
            for post in comment_posts:
                if _insert_mobile_post(conn, task_id, post, seen_ids, seen_contents):
                    inserted += 1
                    collected += 1
                if collected >= target_count:
                    break

            progress(
                f'B站评论采集：第 {index}/{len(parents)} 条视频新增 {inserted} 条评论，'
                f'累计 {collected}/{target_count} 条'
            )
            time.sleep(random.uniform(*BILIBILI_REQUEST_DELAY_RANGE))

        conn.execute(
            "UPDATE crawl_tasks SET crawled_count=?, error_message=? WHERE id=?",
            (collected, f'B站热门视频评论采集完成，已采集 {collected}/{target_count} 条评论。', task_id)
        )
        conn.commit()
    finally:
        try:
            conn.execute(
                "UPDATE crawl_tasks SET crawled_count=? WHERE id=?",
                (conn.execute(
                    "SELECT COUNT(*) as c FROM weibo_posts WHERE task_id=?",
                    (task_id,)
                ).fetchone()['c'], task_id)
            )
            conn.commit()
        finally:
            conn.close()

    return collected

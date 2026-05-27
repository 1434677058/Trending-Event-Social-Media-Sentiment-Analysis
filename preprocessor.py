import re
import jieba
from database import get_conn

STOP_WORDS = set()


def _load_stop_words():
    global STOP_WORDS
    if STOP_WORDS:
        return
    base_words = {
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
        '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着',
        '没有', '看', '好', '自己', '这', '他', '她', '它', '们', '那', '些',
        '什么', '怎么', '如何', '为什么', '哪', '吗', '呢', '吧', '啊', '哦',
        '嗯', '呀', '哈', '嘿', '哎', '唉', '喂', '嘛', '么', '把', '被',
        '让', '给', '从', '向', '对', '以', '但', '而', '或', '如果', '因为',
        '所以', '虽然', '但是', '可以', '这个', '那个', '这些', '那些', '还',
        '又', '再', '已经', '正在', '将', '能', '该', '应该', '可能', '必须',
        '其', '之', '与', '及', '等', '更', '最', '比', '非', '无', '每',
        '各', '某', '该', '本', '此', '其他', '另', '别', '只', '才', '就是',
        '不是', '还是', '已', '曾', '将要', '正', '刚', '才能', '不能',
        '转发微博', '微博', '回复', '哈哈', '哈哈哈', '图片', '视频', '网页链接',
    }
    STOP_WORDS = base_words


def clean_text(text):
    """清洗单条文本"""
    text = text or ''
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'#[^#]+#', '', text)
    text = re.sub(r'@[\w一-鿿]+[:\s]?', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\[[\w]+\]', '', text)
    text = re.sub(r'[^\w一-鿿]+', ' ', text)
    return text.strip()


def segment(text):
    """jieba分词并去停用词"""
    _load_stop_words()
    words = jieba.lcut(text)
    return [w.strip() for w in words if len(w.strip()) > 1 and w.strip() not in STOP_WORDS]


def preprocess_task(task_id):
    """对指定任务的所有微博做预处理"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, content FROM weibo_posts WHERE task_id=? AND (clean_content IS NULL OR clean_content='')",
        (task_id,)
    ).fetchall()

    count = 0
    for row in rows:
        cleaned = clean_text(row['content'])
        if cleaned:
            conn.execute(
                "UPDATE weibo_posts SET clean_content=? WHERE id=?",
                (cleaned, row['id'])
            )
            count += 1

    conn.commit()
    conn.close()
    return count


def deduplicate_task(task_id):
    """去除重复微博"""
    conn = get_conn()
    conn.execute('''
        DELETE FROM weibo_posts WHERE id NOT IN (
            SELECT MIN(id) FROM weibo_posts WHERE task_id=? GROUP BY clean_content
        ) AND task_id=?
    ''', (task_id, task_id))
    affected = conn.total_changes
    conn.commit()
    conn.close()
    return affected

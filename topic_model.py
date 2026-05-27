import json
import re

from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

from database import get_conn
from preprocessor import segment


TOPIC_RULES = [
    ('性别平等与女性议题', {'女权', '女性', '女生', '男生', '男性', '平等', '性别', '父权', '厌女', '女性主义', '权益'}),
    ('网络舆论与立场表达', {'网络', '评论', '转发', '弹幕', '支持', '标签', '对立', '表达', '观点', '污名化'}),
    ('技术与模型能力', {'模型', '算法', '训练', '生成', '大模型', '数据', '算力', '识别', '预测', '智能', '系统'}),
    ('产业应用与效率提升', {'应用', '企业', '效率', '工具', '办公', '客服', '运营', '生产', '业务', '落地', '项目'}),
    ('职业转型与技能学习', {'转行', '编程', '指南', '入门', '未来', '职业', '岗位', '就业', '学习', '能力', '失业'}),
    ('教育学习与人才培养', {'教育', '学习', '学生', '教师', '课程', '论文', '作业', '训练营', '高校', '课堂'}),
    ('医疗健康与公共服务', {'医疗', '医生', '诊断', '病历', '政务', '交通', '城市', '公共', '服务', '治理'}),
    ('内容创作与媒体传播', {'生成', '内容', '视频', '剪辑', '字幕', '直播', '写作', '创作', '新闻', '传播'}),
    ('安全合规与伦理风险', {'隐私', '安全', '合规', '版权', '伦理', '风险', '审核', '授权', '公平', '监管'}),
    ('就业岗位与社会影响', {'就业', '岗位', '招聘', '工作', '职业', '社会', '影响', '替代', '能力'}),
]

TOPIC_WEAK_WORDS = {
    '他们', '她们', '我们', '你们', '大家', '有人',
    '这个', '那个', '这种', '这样', '这些', '那些',
    '很多', '一些', '一个', '一种', '一切',
    '不是', '就是', '可以', '觉得', '真的', '只有', '没有',
    '因为', '所以', '如果', '还是', '已经', '什么', '怎么',
    '希望', '起来', '作为', '正常', '完全',
    '评论', '转发', '视频', '弹幕',
    '中国', '树根',
}


def run_lda(task_id, num_topics=5):
    """对指定任务执行 LDA 主题挖掘（sklearn 实现）。"""
    conn = get_conn()

    conn.execute("DELETE FROM topic_results WHERE task_id=?", (task_id,))

    rows = conn.execute(
        "SELECT clean_content FROM weibo_posts WHERE task_id=? AND clean_content IS NOT NULL AND clean_content!=''",
        (task_id,)
    ).fetchall()

    if not rows:
        conn.commit()
        conn.close()
        return []

    source_docs = []
    texts = []
    for row in rows:
        raw_text = row['clean_content']
        tokens = segment(raw_text)
        if len(tokens) >= 2:
            source_docs.append({'text': raw_text, 'tokens': tokens})
            texts.append(' '.join(tokens))

    if len(texts) < num_topics:
        conn.commit()
        conn.close()
        return []

    vectorizer = CountVectorizer(max_df=0.8, min_df=2, max_features=5000)
    try:
        doc_term = vectorizer.fit_transform(texts)
    except ValueError as exc:
        conn.commit()
        conn.close()
        raise ValueError('有效词汇不足，无法生成主题') from exc

    if doc_term.shape[1] == 0:
        conn.commit()
        conn.close()
        return []

    feature_names = vectorizer.get_feature_names_out()

    lda = LatentDirichletAllocation(
        n_components=num_topics,
        max_iter=20,
        random_state=42,
    )
    doc_topic = lda.fit_transform(doc_term)

    results = []
    used_topic_names = set()
    for i, topic_dist in enumerate(lda.components_):
        weight_indices = topic_dist.argsort()[-8:][::-1]
        raw_indices = topic_dist.argsort()[-24:][::-1]
        raw_keywords = [feature_names[idx] for idx in raw_indices]
        keywords = _refine_topic_keywords(raw_keywords, limit=6)
        weight = round(float(topic_dist[weight_indices].sum() / topic_dist.sum()), 4)
        topic_name = _unique_topic_name(_infer_topic_name(keywords, i + 1), keywords, used_topic_names)
        used_topic_names.add(topic_name)
        explanation = _build_topic_explanation(keywords)
        representative_docs = _representative_docs(source_docs, doc_topic, i)

        conn.execute(
            '''INSERT INTO topic_results
               (task_id, topic_num, topic_name, keywords, weight, explanation, representative_docs)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (
                task_id,
                i + 1,
                topic_name,
                json.dumps(keywords, ensure_ascii=False),
                weight,
                explanation,
                json.dumps(representative_docs, ensure_ascii=False),
            )
        )
        results.append({
            'topic_num': i + 1,
            'topic_name': topic_name,
            'keywords': keywords,
            'weight': weight,
            'explanation': explanation,
            'representative_docs': representative_docs,
        })

    conn.commit()
    conn.close()
    return results


def get_topic_results(task_id):
    """获取已保存的主题结果。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM topic_results WHERE task_id=? ORDER BY topic_num",
        (task_id,)
    ).fetchall()
    conn.close()

    return [{
        'topic_num': r['topic_num'],
        'topic_name': r['topic_name'],
        'keywords': json.loads(r['keywords']),
        'weight': r['weight'],
        'explanation': r['explanation'] or _build_topic_explanation(json.loads(r['keywords'])),
        'representative_docs': json.loads(r['representative_docs'] or '[]'),
    } for r in rows]


def _infer_topic_name(keywords, topic_num):
    keyword_set = set(keywords)
    best_name = ''
    best_score = 0
    for name, vocab in TOPIC_RULES:
        score = len(keyword_set & vocab)
        if score > best_score:
            best_name = name
            best_score = score
    if best_name and best_score >= 1:
        return best_name
    return _keyword_topic_name(keywords, topic_num)


def _is_informative_topic_word(word):
    text = str(word or '').strip()
    if not text:
        return False
    if text in TOPIC_WEAK_WORDS:
        return False
    if text.isdigit() or text.lower() in {'ai', 'no'}:
        return False
    if len(text) < 2:
        return False
    if re.fullmatch(r'[a-zA-Z]+', text):
        return False
    return True


def _refine_topic_keywords(raw_keywords, limit=6):
    refined = []
    seen = set()

    for kw in raw_keywords:
        text = str(kw or '').strip()
        if not text or text in seen:
            continue
        if _is_informative_topic_word(text):
            refined.append(text)
            seen.add(text)
        if len(refined) >= limit:
            return refined

    for kw in raw_keywords:
        text = str(kw or '').strip()
        if not text or text in seen or len(text) < 2:
            continue
        refined.append(text)
        seen.add(text)
        if len(refined) >= limit:
            break

    return refined[:limit]


def _keyword_topic_name(keywords, topic_num):
    useful = [kw for kw in keywords if _is_informative_topic_word(kw)]
    if len(useful) >= 2:
        return f'{useful[0]}与{useful[1]}议题'
    if useful:
        return f'{useful[0]}议题'
    return f'主题{topic_num}'


def _unique_topic_name(topic_name, keywords, used_names):
    if topic_name not in used_names:
        return topic_name
    useful = [kw for kw in keywords if _is_informative_topic_word(kw)]
    for kw in useful:
        candidate = f'{topic_name}：{kw}'
        if candidate not in used_names:
            return candidate
    index = 2
    while f'{topic_name} {index}' in used_names:
        index += 1
    return f'{topic_name} {index}'


def _build_topic_explanation(keywords):
    shown = '、'.join(keywords[:4])
    if not shown:
        return '该主题由 LDA 根据词语共现关系自动归纳。'
    return f'该主题围绕“{shown}”等高关联词展开，反映了相关文本中的集中讨论方向。'


def _representative_docs(source_docs, doc_topic, topic_index, limit=2):
    ranked = sorted(
        enumerate(doc_topic[:, topic_index]),
        key=lambda item: item[1],
        reverse=True,
    )
    docs = []
    seen = set()
    for doc_index, score in ranked:
        text = _shorten_text(source_docs[doc_index]['text'])
        if not text or text in seen:
            continue
        docs.append({
            'text': text,
            'score': round(float(score), 4),
        })
        seen.add(text)
        if len(docs) >= limit:
            break
    return docs


def _shorten_text(text, limit=90):
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    if len(text) <= limit:
        return text
    return text[:limit] + '...'

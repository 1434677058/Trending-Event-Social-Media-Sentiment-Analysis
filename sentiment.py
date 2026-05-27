from snownlp import SnowNLP
from database import get_conn


def analyze_sentiment(task_id):
    """对指定任务的微博进行SnowNLP情感分析"""
    conn = get_conn()

    conn.execute("DELETE FROM sentiment_results WHERE task_id=?", (task_id,))

    rows = conn.execute(
        "SELECT id, clean_content FROM weibo_posts WHERE task_id=? AND clean_content IS NOT NULL AND clean_content!=''",
        (task_id,)
    ).fetchall()

    results = []
    for row in rows:
        try:
            s = SnowNLP(row['clean_content'])
            score = round(s.sentiments, 4)
        except Exception:
            score = 0.5

        if score >= 0.6:
            label = 'positive'
        elif score <= 0.4:
            label = 'negative'
        else:
            label = 'neutral'

        results.append((row['id'], task_id, score, label))

    conn.executemany(
        "INSERT INTO sentiment_results (post_id, task_id, score, label) VALUES (?, ?, ?, ?)",
        results
    )
    conn.commit()
    conn.close()
    return len(results)


def get_sentiment_stats(task_id):
    """获取情感统计"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT label, COUNT(*) as cnt FROM sentiment_results WHERE task_id=? GROUP BY label",
        (task_id,)
    ).fetchall()
    conn.close()

    stats = {'positive': 0, 'neutral': 0, 'negative': 0}
    for row in rows:
        stats[row['label']] = row['cnt']
    total = sum(stats.values())
    return {
        'positive': stats['positive'],
        'neutral': stats['neutral'],
        'negative': stats['negative'],
        'total': total,
        'positive_pct': round(stats['positive'] / total * 100, 1) if total else 0,
        'neutral_pct': round(stats['neutral'] / total * 100, 1) if total else 0,
        'negative_pct': round(stats['negative'] / total * 100, 1) if total else 0,
    }


def get_score_distribution(task_id):
    """获取情感得分分布（0.0-1.0分10个区间）"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT score FROM sentiment_results WHERE task_id=?",
        (task_id,)
    ).fetchall()
    conn.close()

    bins = [0] * 11
    for row in rows:
        idx = min(int(row['score'] * 10), 10)
        bins[idx] += 1
    return bins

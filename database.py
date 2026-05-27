import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'sentiment.db')


def get_conn():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _ensure_column(conn, table, column, definition):
    columns = {row['name'] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def update_task_status(task_id, status, crawled_count=None, error_message=None):
    conn = get_conn()
    fields = ["status=?"]
    params = [status]

    if crawled_count is not None:
        fields.append("crawled_count=?")
        params.append(crawled_count)
    if error_message is not None:
        fields.append("error_message=?")
        params.append(error_message)
    if status in {'done', 'failed'}:
        fields.append("completed_at=datetime('now','localtime')")

    params.append(task_id)
    conn.execute(f"UPDATE crawl_tasks SET {', '.join(fields)} WHERE id=?", params)
    conn.commit()
    conn.close()


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS crawl_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT NOT NULL,
        start_date TEXT,
        end_date TEXT,
        source TEXT DEFAULT 'bilibili',
        target_count INTEGER DEFAULT 500,
        crawled_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        error_message TEXT,
        completed_at TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS weibo_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        weibo_id TEXT,
        user_name TEXT,
        content TEXT,
        clean_content TEXT,
        publish_time TEXT,
        likes INTEGER DEFAULT 0,
        comments INTEGER DEFAULT 0,
        reposts INTEGER DEFAULT 0,
        FOREIGN KEY (task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS sentiment_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        task_id INTEGER NOT NULL,
        score REAL,
        label TEXT,
        analyzed_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (post_id) REFERENCES weibo_posts(id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS topic_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        topic_num INTEGER,
        topic_name TEXT,
        keywords TEXT,
        weight REAL,
        analyzed_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE
    )''')

    _ensure_column(conn, 'crawl_tasks', 'error_message', 'TEXT')
    _ensure_column(conn, 'crawl_tasks', 'completed_at', 'TEXT')
    _ensure_column(conn, 'crawl_tasks', 'source', "TEXT DEFAULT 'bilibili'")
    _ensure_column(conn, 'weibo_posts', 'data_type', "TEXT DEFAULT 'post'")
    _ensure_column(conn, 'weibo_posts', 'parent_note_id', 'TEXT')
    _ensure_column(conn, 'weibo_posts', 'parent_note_title', 'TEXT')
    _ensure_column(conn, 'weibo_posts', 'parent_note_author', 'TEXT')
    _ensure_column(conn, 'weibo_posts', 'parent_note_heat', 'INTEGER DEFAULT 0')
    _ensure_column(conn, 'topic_results', 'explanation', 'TEXT')
    _ensure_column(conn, 'topic_results', 'representative_docs', 'TEXT')
    conn.execute("UPDATE crawl_tasks SET source='import' WHERE (source IS NULL OR source='' OR source='weibo') AND COALESCE(start_date, '')='' AND COALESCE(end_date, '')=''")
    conn.execute("UPDATE crawl_tasks SET source='bilibili' WHERE source IS NULL OR source='' OR source='weibo'")
    c.execute("CREATE INDEX IF NOT EXISTS idx_crawl_tasks_status ON crawl_tasks(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_weibo_posts_task_id ON weibo_posts(task_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_weibo_posts_weibo_id ON weibo_posts(task_id, weibo_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_weibo_posts_publish_time ON weibo_posts(task_id, publish_time)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_weibo_posts_data_type ON weibo_posts(task_id, data_type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_results_task_id ON sentiment_results(task_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_topic_results_task_id ON topic_results(task_id)")

    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print("数据库初始化完成:", DB_PATH)

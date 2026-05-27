PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS crawl_tasks (
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
);

CREATE TABLE IF NOT EXISTS weibo_posts (
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
    data_type TEXT DEFAULT 'post',
    parent_note_id TEXT,
    parent_note_title TEXT,
    parent_note_author TEXT,
    parent_note_heat INTEGER DEFAULT 0,
    FOREIGN KEY (task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sentiment_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    score REAL,
    label TEXT,
    analyzed_at TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (post_id) REFERENCES weibo_posts(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS topic_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    topic_num INTEGER,
    topic_name TEXT,
    keywords TEXT,
    weight REAL,
    analyzed_at TEXT DEFAULT (datetime('now','localtime')),
    explanation TEXT,
    representative_docs TEXT,
    FOREIGN KEY (task_id) REFERENCES crawl_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_crawl_tasks_status
    ON crawl_tasks(status);

CREATE INDEX IF NOT EXISTS idx_weibo_posts_task_id
    ON weibo_posts(task_id);

CREATE INDEX IF NOT EXISTS idx_weibo_posts_weibo_id
    ON weibo_posts(task_id, weibo_id);

CREATE INDEX IF NOT EXISTS idx_weibo_posts_publish_time
    ON weibo_posts(task_id, publish_time);

CREATE INDEX IF NOT EXISTS idx_weibo_posts_data_type
    ON weibo_posts(task_id, data_type);

CREATE INDEX IF NOT EXISTS idx_sentiment_results_task_id
    ON sentiment_results(task_id);

CREATE INDEX IF NOT EXISTS idx_topic_results_task_id
    ON topic_results(task_id);

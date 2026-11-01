import sqlite3
from datetime import datetime
from Pymatsci.SurfAgent.config import DATABASE_DIR
import gradio as gr
import json

DB_PATH = DATABASE_DIR.joinpath('gradio.db')

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT NOT NULL PRIMARY KEY,
                user_id TEXT NOT NULL, 
                created_at TIMESTAMP NOT NULL
            )
            ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                structure_id TEXT,
                msg_type TEXT NOT NULL, -- text / image
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (session_id) REFERENCES conversations(session_id),
                FOREIGN KEY (session_id) REFERENCES gradio(session_id)
            )
            ''')

def load_user_history(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
           SELECT session_id FROM conversations WHERE user_id = ?;
        ''', (user_id,))
        rows = cursor.fetchall()
    history_dict = {}
    for session_id in rows:
        history_dict[session_id] = load_session_history(session_id)
    return history_dict

# 读取会话历史，组装chatbot messages
def load_session_history(session_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT role, msg_type, content, metadata FROM chat_messages
            WHERE session_id = ? ORDER BY id ASC
        ''', (session_id,))
        rows = cursor.fetchall()
    history = []
    for role, typ, cnt, metadata in rows:
        info = {"role": role}
        if metadata is not None:
            info.update({'metadata': json.loads(metadata)})
        if typ == "text":
            info.update({"content": cnt})
        else:
            type2gradio = {'html': gr.HTML, 'image': gr.Image}
            info.update({"content": type2gradio[typ](**json.loads(cnt))})
        history.append(info)
    return history

def get_last_structure_id(session_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT structure_id FROM chat_messages
            WHERE session_id = ? ORDER BY id DESC
        ''', (session_id,))
        row = cursor.fetchone()
    return row[0]

def load_session_by_user_id(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT session_id FROM conversations WHERE user_id = ?;
        ''', (user_id,))
        rows = cursor.fetchall()
  
    session_dict = {}
    for idx, row in enumerate(rows):
        session_id = row[0]
        session_dict.update({session_id: f"对话 {idx+1}"}) 
    session_dict = dict(reversed(session_dict.items()))
    return session_dict

def insert_msg(user_id, session_id, structure_id, msg_type, role, content, metadata=None):
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO chat_messages (session_id, structure_id, msg_type, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, structure_id, msg_type, role, content, metadata, now))
        conn.execute('''
                INSERT OR IGNORE INTO conversations (session_id, user_id, created_at)
                VALUES (?, ?, ?)
            ''', (session_id, user_id, now))

def insert_gradio(session_id, formula, structure_id, structre_html, structure_json):
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            INSERT INTO gradio (session_id, formula, structure_id, structre_html, structure_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, formula, structure_id, structre_html, structure_json, now))
          
            
def delete_session_by_session_id(session_id):
    """
    根据 session_id 删除整个会话：先删消息，再删会话记录
    :param session_id: 会话唯一id
    """
    with sqlite3.connect(DB_PATH) as conn:
        # 外键关联，先删除该会话下所有聊天消息
        conn.execute('DELETE FROM chat_messages WHERE session_id = ?', (session_id,))
        # 删除会话主记录
        conn.execute('DELETE FROM conversations WHERE session_id = ?', (session_id,))

        conn.execute('DELETE FROM gradio WHERE session_id = ?', (session_id,))

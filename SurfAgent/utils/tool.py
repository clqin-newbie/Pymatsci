import json
import html
from jobflow import SETTINGS, JobStore
from maggma.stores import JSONStore
from Pymatsci.SurfAgent.config import DATABASE_DIR
import base64
from pathlib import Path
from urllib.parse import quote


def download2chatbox(paths: list[str]):
    links = []
    for item in paths:
        p = Path(item if isinstance(item, dict) else item)
        links.append(
            f'<a href="/download/{quote(str(p))}" '
            'target="_blank" '
            'style="display:inline-block;margin-right:12px;">'
            f'📥{p.name}</a>'
        )
    return f'<div style="margin-top:4px;">{" ".join(links)}</div>'

def json2chatbox(data):
    """json转化为chatbox可插入的"""
    json_text = json.dumps(data, indent=2, ensure_ascii=False)
    response = f"""
<details>
<summary>可用信息</summary>
<pre><code>{html.escape(json_text)}</code></pre>
</details>
"""
    return response


def merge_same_key(items: list[dict]) -> dict:
    result = {}
    for item in items:
        for k, v in item.items():
            if k not in result:
                result[k] = []
            # 把当前值追加到结果列表
            result[k].extend(v)
    return result


# 数据库搜索




def query_calcs(task_label: str, structure_id: str, properties: list=None):
    """
    根据提供的参数搜索DFT计算的结果

     Args:
        task_label: 计算任务的标识
        structure_id: 结构的唯一标识
        properties: 需要搜索的一些结果
    """
    store = SETTINGS.JOB_STORE
    store.connect()
    result = store.query_one(
        {"output.task_label": task_label, 'metadata.structure_id': structure_id},
        properties,
        load=True,  # DOS stored in the data store, so we need to explicitly load it
    )
    return result

def get_store():
    docs_store = JSONStore(
        paths=str(DATABASE_DIR.joinpath('docs.json')),
        read_only=False,
    )
    data_store = JSONStore(
        paths=str(DATABASE_DIR.joinpath('data.json')),
        read_only=False,
    )
    job_store = JobStore(docs_store, additional_stores={"data": data_store})
    job_store.connect()
    return job_store, docs_store

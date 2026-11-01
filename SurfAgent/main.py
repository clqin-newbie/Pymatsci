from gradio import ChatMessage
import gradio as gr
from jobflow import SETTINGS
from rich import print as rprint
from Pymatsci.SurfAgent.graph import get_agent_app
from langchain.messages import AIMessage, ToolMessage
from pymatgen.core.structure import Structure, Lattice
from Pymatsci.SurfAgent.ui.get_struc_plot import make_crystal_html
import pandas as pd 
from pathlib import Path
import json
import uvicorn
from Pymatsci.SurfAgent.utils.database import *
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from Pymatsci.SurfAgent.utils.tool import json2chatbox, merge_same_key, get_store
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from Pymatsci.SurfAgent.config import ROOT_DIR
import uuid
server = FastAPI()

def agent_chat(message, history, system, structure_id, mode, session_id, user_id):
    # 用户消息入历史
    text = message['text']
    cif_files = message['files']
    message = text

    config = {"configurable": {"thread_id": session_id}}
    # 根据mode选择是否插入summary
    if mode == 'stateless':
        job_store, docs_store = get_store()
        summary = job_store.query_one({'structure_id': structure_id})
        if summary is not None:
            message += f"\n可用的信息{str(summary)}"

    if len(cif_files) != 0:
        message += '\n上传的结构' + str({'filepath': cif_files})

    history.append(ChatMessage(role="user", content=text)) # 发送消息
    insert_msg(user_id, session_id, structure_id, "text", "user", text)
    yield history, gr.skip(), gr.skip(), gr.skip(), gr.skip()
    app = get_agent_app()
    for chunk in app.stream(
        {
        "messages": [("human", message)], 
        'structural_system': system,
        'mode': mode
        }, 
        stream_mode="updates",
        config=config
    ):
        
        for node_name, node_outputs in chunk.items():
            print("*" * 100)
            print(node_name)
            rprint(node_outputs)
            if isinstance(node_outputs, list):
                node_outputs = merge_same_key(node_outputs)
            for k, v in node_outputs.items():
                if k == "messages":
                    for output in v:
                        if isinstance(output, AIMessage):
                            content = "*"*10+f"\n{output.content}"
                            history.append(ChatMessage(role="assistant", content=content))
                            insert_msg(user_id, session_id, structure_id, "text", "assistant", content)
                            yield history, gr.skip(), gr.skip(), gr.skip(), gr.skip()
                            for tool_call in output.tool_calls:
                                metadata = {
                                    "title": f"🛠️ 调用{tool_call['name']}",
                                    "status": "pending",
                                    "log": f"参数：{tool_call['args']}"
                                }
                                history.append(ChatMessage(role="assistant", content='', metadata=metadata))
                                insert_msg(user_id, session_id, structure_id, "text", "assistant", '', json.dumps(metadata))
                                yield history, gr.skip(), gr.skip(), gr.skip(), gr.skip()
                        elif isinstance(output, ToolMessage):
                            info = output.artifact

                            if info['gradio'][1].get('value', None):
                                structure_id = info['gradio'][1].get('value')

                            metadata = {
                                        "title": f"🛠️ {output.name}已经完成",
                                        "status": "done"
                                    }
                            history.append(ChatMessage(role="assistant", content='', metadata=metadata))  
                            insert_msg(user_id, session_id, structure_id, "text", "assistant", '', json.dumps(metadata))
                            # history.append(ChatMessage(role="assistant", content="*"*60+f"\n{output.content}"))
                            type2gradio = {'html': gr.HTML, 'image': gr.Image}
                            
                            for k, v in info['chatbox'].items():
                                k = k.split('-')[0]
                                if k == 'text':
                                    history += [ChatMessage(role="assistant", content=v)]
                                    insert_msg(user_id, session_id, structure_id, k, "assistant", v)
                                else:
                                    history += [ChatMessage(role="assistant", content=type2gradio[k](**v))]
                                    insert_msg(user_id, session_id, structure_id, k, "assistant", json.dumps(v))
                            gradio_rst = [gr.update(**v) for v in info['gradio']]    
                            yield history, *gradio_rst
                      

def get_structure_gr(request: gr.Request):
    structure_id = request.query_params.get("structure_id")
    if structure_id is None:
        viewer = f"""<div style="width: 600px;height: 500px;display: block;"></div>"""
        return viewer
    # 获取当前文件的路径
    current_file_path = Path(__file__).resolve()

    # 获取当前文件所在的目录
    current_dir = current_file_path.parent

    struct = Structure.from_file(current_dir.joinpath(f"data/{structure_id}.cif") )

    viewer = make_crystal_html(struct)
    
    return viewer

# 清空专用函数
def clear_input_gr():
    print(1)
    return {"text":"", "files":[]}

def load_sessions_gr(user_id, session_id):
    session_dict = load_session_by_user_id(user_id)
    session_list = [[idx] for idx in session_dict.values()]
    history = load_session_history(session_id=session_id)
    return gr.update(samples=session_list), history

def load_history_by_session_id_gr(user_id, evt: gr.SelectData):
    session_dict = load_session_by_user_id(user_id)
    session_list = list(session_dict.keys())
    session_id = session_list[evt.index]
    history = load_session_history(session_id=session_id)

    structure_id = get_last_structure_id(session_id)
    print(structure_id)
    job_store, docs_store = get_store()
    summary = job_store.query_one({'structure_id': structure_id})
    if summary is None:
        return history, session_id, gr.update(value=None), gr.update(value=None), gr.update(value=None), gr.update(value=None)
    filepath = summary['filepath']
    structure = Structure.from_file(filepath)
    structure_text = make_crystal_html(structure)
    formula = structure.composition.formula
    return history, session_id, gr.update(value=formula), gr.update(value=structure_id), gr.update(value=structure_text), gr.update(value=summary)

def new_sesiion_gr():
    session_id = str(uuid.uuid4())
    return {"text":"", "files":[]}, [], session_id, gr.update(value=None), gr.update(value=None), gr.update(value=None), gr.update(value=None)

def delete_sesiion_gr(user_id, session_id):
    delete_session_by_session_id(session_id) # 删除
    session_dict = load_session_by_user_id(user_id)
    session_list = [[idx] for idx in session_dict.values()]
    return gr.update(samples=session_list), *new_sesiion_gr()



with gr.Blocks() as demo:
   
    session_id = gr.State(str(uuid.uuid4()))
    with gr.Sidebar(position="left", open=True): 
       
        gr.Button(value="DFT Agent", icon="./figures/apple.svg", size='lg')
        # gr.Markdown('# ')
        system = gr.Radio(choices=['bulk', 'surface'], value='bulk', label='Structural system')
        mode = gr.Radio(choices=['stateless', 'stateful'], value='stateful', label='Working mode')
        
        new_chat_button = gr.Button(
                        'New chat',
                        variant="primary",
                        size="md",
                        icon="./figures/message.svg",
                        # scale=0,
                    )
        chat_history_dataset = gr.Dataset(
            components=['text'],
            show_label=False,
            layout="table",
            type="index",
            label='最近'
        )
        delete_chat_button = gr.Button(
            'Delete chat',
            variant="primary",
            size="md",
            icon="./figures/delete.svg",
            # scale=0,
        )
        user_id = gr.Button('clqin', icon="./figures/user.svg") # user_id
    
    # group_consecutive_messages=True同角色同一气泡
    chatbot = gr.Chatbot(height=1200, line_breaks=True, 
                        avatar_images=("./figures/user.svg", "./figures/agent.svg"), buttons=[]
                         )
    msg = gr.MultimodalTextbox(
        interactive=True,
        file_count="single",
        sources=["upload"], # ["upload","microphone"]开启麦克风
        placeholder="只允许上传cif文件",
        show_label=False,
        file_types=['.cif']
    )
    
    
    with gr.Sidebar(position="right", width=600):  
        
        gr.Markdown('# Crystal Structure')
        formula_text = gr.Textbox('ID', label='Formula')
        structure_id_text = gr.Textbox('ID', label='Structure ID')
        structre_html = gr.HTML()
        gr.Markdown('# Summary')
        structure_json = gr.JSON(label='Information', max_height=600)

    chat_history_dataset.select(load_history_by_session_id_gr, inputs=[user_id], outputs=[chatbot, session_id, formula_text, structure_id_text, structre_html, structure_json])
    demo.load(
        load_sessions_gr,
        inputs=[user_id, session_id],
        outputs=[chat_history_dataset, chatbot]
    )
    new_chat_button.click(
        fn=new_sesiion_gr,
        outputs=[msg, chatbot, session_id, formula_text, structure_id_text, structre_html, structure_json]
    )
    delete_chat_button.click(
        delete_sesiion_gr, 
        inputs=[user_id, session_id], 
        outputs=[chat_history_dataset, msg, chatbot, session_id, formula_text, structure_id_text, structre_html, structure_json]
    )
    msg.submit(
        agent_chat, 
        [msg, chatbot, system, structure_id_text, mode, session_id, user_id], 
        [chatbot, formula_text, structure_id_text, structre_html, structure_json]
    ).then(
        load_sessions_gr, inputs=[user_id, session_id], outputs=[chat_history_dataset, chatbot]
        ).then(clear_input_gr, outputs=msg)

    # chatbot.change(insert_gradio_gr, inputs=[session_id, formula_text, structure_id_text, structre_html, structure_json])
    # demo.load(
    #     get_structure,
    #     inputs=None,
    #     outputs=unrelaxed_html
    # )

# 文件下载   
@server.get("/download/{filename:path}")
def download_file(filename: str):
    # 替换为你实际存放文件的目录
    base_dir = ROOT_DIR.resolve()
    file_path = (base_dir / filename).resolve()

    # 防止通过 ../ 访问目录之外的文件
    if not file_path.is_relative_to(base_dir):
        raise HTTPException(status_code=403, detail="Forbidden")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )

 # html文件加载
server.mount(
    "/viewer",
    StaticFiles(directory=str(ROOT_DIR), html=True),
    name="viewer",
)
    
if __name__ == "__main__":
    
    init_db() # gradio的记录数据初始化
    # 再挂载 Gradio
    fast_app = gr.mount_gradio_app(server, demo, path="/")
    uvicorn.run(fast_app, host="127.0.0.1", port=7860)

 


import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from rich import print as rprint
from Pymatsci.SurfAgent.tools.calculation import *
from Pymatsci.SurfAgent.tools.get_structure import *

from langchain_core.messages import AnyMessage
import sqlite3
from langgraph.graph import StateGraph, MessagesState, START, END
from pymatgen.core.structure import Structure
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Annotated, List, Dict, Literal
import operator
from Pymatsci.SurfAgent.config import DATABASE_DIR
# 从.env文件中加载环境变量
load_dotenv(override=True)
# 从环境变量读取配置
ALI_API_KEY = os.getenv("QWEN_API_KEY")

model = ChatDeepSeek(
        model='deepseek-flash', 
        api_key=os.getenv("deepseek-api"), 
        base_url='https://api.deepseek.com', 
        extra_body={"thinking": {"type": "disabled"}}
        )
struct_tools = [search_materials_project, get_struc_from_path]
calcs_tools=[get_relax, get_scf, get_dos]
bulk_tools = [get_hkl_surface, get_possible_hkl]
surface_tools = []
common_tools = struct_tools + calcs_tools
tools = common_tools + bulk_tools

class GraphState(MessagesState):
    structural_system: Literal['bulk', 'surface'] 
    mode: Literal['stateless', 'stateful']
  
    

tool_node = ToolNode(tools)

def should_continue(state: GraphState):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

def call_model(state: GraphState) -> GraphState:
    messages = state["messages"]
    system = state["structural_system"]
    mode = state['mode']
    print(messages)
    print("*" * 100)
    if mode == 'stateless':
        messages = messages[-1:] # 只取最后一条数据
    if system == 'surface':
        tools = common_tools + surface_tools
        model_with_tools = model.bind_tools(tools)
    else:
        tools = common_tools + bulk_tools
        model_with_tools = model.bind_tools(tools)
    print(messages)
    response = model_with_tools.invoke(messages)
    return {"messages": [response]}


workflow = StateGraph(GraphState)

# 定义两个节点，以便循环调用
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, ["tools", END])
workflow.add_edge("tools", "agent")

def get_agent_app():

    db_path = DATABASE_DIR.joinpath("langraph.db")
    conn = sqlite3.connect(database=str(db_path), check_same_thread=False)
    sqlite_db = SqliteSaver(conn=conn)
    app = workflow.compile(checkpointer=sqlite_db)
    return app


if __name__ == "__main__":
    # result = app.invoke({"messages": [("human", "获取NaCl结构")]})
    # rprint(result)
    from Pymatsci.SurfAgent.tools.calculation import main_file
    print(main_file)
    # for chunk in app.stream({"messages": [("human", "获取NaCl结构")]}, stream_mode="updates"):
    #     # chunk 格式 {节点名: 返回的state更新字典}
    #     for node_name, node_output in chunk.items():
    #         rprint(node_output)
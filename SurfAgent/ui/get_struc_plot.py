import gradio as gr
from pymatgen.core import Structure, Lattice
import threading
import dash
from dash import html
import crystal_toolkit.components as ctc
import json
import multiprocessing
import time
import random
from aseview import MolecularViewer
from pathlib import Path
from pymatgen.io.ase import AseAtomsAdaptor
from Pymatsci.SurfAgent.config import ROOT_DIR

def make_crystal_html(struct):
    """生成晶体并保存独立查看器 HTML。"""
    atoms = AseAtomsAdaptor.get_atoms(struct)
    # 普通晶体结构使用 MolecularViewer
    viewer = MolecularViewer(
        atoms,
        style="glossy",
        show_cell=True,
    )
  
    filename ='index.html'
    HTML_FILE = ROOT_DIR.joinpath(filename)
    # 保存完整 HTML，而不是直接嵌入 gr.HTML
    viewer.save_html(HTML_FILE)

    # 防止浏览器复用缓存
    url = f"/viewer/{filename}?v={time.time_ns()}"

    return f"""
    <iframe
        src="{url}"
        style="width:100%; height:400px; border:0;"
        loading="eager">
    </iframe>
    """

#  @gr.render(inputs=[tab_names_state])
#         def render_tabs(tab_names):
#             if tab_names is None:
#                 return
#             store = SETTINGS.JOB_STORE
#             store.connect()
# with gr.Tabs(selected=tab_names[-1]['type']):
#                 for name in tab_names:
#                     ty = name['type']
#                     calcs = name['calcs']                       
#                     with gr.Tab(ty, id=ty):
#                         fina_rst = {}
#                         for idx, calc in enumerate(calcs):
#                             result = query_calcs(**calc)
#                             fina_rst[f'{idx+1}-{calc['task_label']}'] = result
#                         gr.JSON(fina_rst, label='Information', max_height=400)
def get_plot(structure):
   
    dash_app = dash.Dash(__name__)
    port = random.randint(1, 10000)
    structure_component = ctc.StructureMoleculeComponent(
        struct_or_mol=structure,
        id="structure_viewer",
    )

    dash_layout = html.Div([
        structure_component.layout()
    ])

    ctc.register_crystal_toolkit(
        app=dash_app,
        layout=dash_layout,
    )

    viewer = f"""
    <div style="
        width: 600px;
        height: 500px;
        display: block;
    ">
        <iframe
            src="http://127.0.0.1:{port}/"
            style="
                width: 100%;
                height: 100%;
                border: none;
                display: block;
            ">
        </iframe>
    </div>
    """

    def run_dash():
        dash_app.run(
                host="127.0.0.1",
                port=port,
                debug=False
            )
    
    p = multiprocessing.Process(target=run_dash, daemon=False)
    p.start()
    time.sleep(2)
    return viewer



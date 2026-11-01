from langchain.tools import tool, InjectedToolCallId
from typing import TypedDict, Annotated
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolRuntime
from atomate2.vasp.flows.core import RelaxBandStructureMaker
from atomate2.vasp.sets.core import StaticSetGenerator, RelaxSetGenerator, NonSCFSetGenerator
from atomate2.vasp.flows.core import BandStructureMaker
from atomate2.vasp.jobs.core import StaticMaker, RelaxMaker, NonSCFMaker
from jobflow import run_locally
from pymatgen.core import Structure
from rich import print as rprint
import uuid
from atomate2.vasp.jobs.base import get_vasp_task_document
from jobflow import SETTINGS
from Pymatsci.SurfAgent.utils.tool import json2chatbox, download2chatbox
from Pymatsci.SurfAgent.ui.get_struc_plot import make_crystal_html
from pymatgen.electronic_structure.plotter import DosPlotter, BSPlotter
from pymatgen.electronic_structure.dos import CompleteDos
from pymatgen.electronic_structure.bandstructure import BandStructureSymmLine
from atomate2.vasp.powerups import update_user_incar_settings
from Pymatsci.SurfAgent.config import ROOT_DIR
from Pymatsci.SurfAgent.utils.structure import init_structure
from Pymatsci.SurfAgent.utils.tool import query_calcs, get_store
from Pymatsci.SurfAgent.utils.run_dpdispatcher import run_vasp_dpdispatcher



def get_calclulatio():
    pass


@tool(parse_docstring=True)
def get_relax(runtime: ToolRuntime, filepath: str, structure_id: str):
    """
    对提供的晶体进行弛豫计算

    Args:
        filepath: 结构文件的文件路径
        structure_id: 结构的唯一标识
    """

    struct = Structure.from_file(filepath)
    tool_call_id = runtime.tool_call_id
    my_custom_set = RelaxSetGenerator(user_incar_settings={"ENCUT": 200, 'ISPIN': 1})
    maker = RelaxMaker(input_set_generator=my_custom_set)
    job = maker.make(struct)
    metadata = {"structure_id": structure_id, "calc_type": 'relax', "task_id": str(uuid.uuid4())}
    job.update_metadata(metadata)
    job_uuid = job.uuid
    job_store, doc_store = get_store()

    STRUCTURE_DIR = ROOT_DIR.joinpath(structure_id).joinpath('structure')
    JOBFLOW_DIR = ROOT_DIR.joinpath(structure_id).joinpath('jobflow')
    STRUCTURE_DIR.mkdir(exist_ok=True, parents=True)
    JOBFLOW_DIR.mkdir(exist_ok=True, parents=True)


    # run_locally(job, create_folders=True, store=job_store, root_dir=JOBFLOW_DIR) # jobflow
    # 写入输入文件
    input_set_generator = maker.input_set_generator
    input_set_generator.user_incar_settings["ENCUT"] = 200 # 更新
    input_set_generator.user_incar_settings["ISPIN"] = 1
    vasp_input_set = input_set_generator.get_input_set(struct)
    vasp_input_set.write_input(JOBFLOW_DIR)
    run_vasp_dpdispatcher(structure_id)# dpdispatcher
    task_doc = get_vasp_task_document(JOBFLOW_DIR, **maker.task_document_kwargs)
    task_doc.task_label = maker.name
    task_doc = task_doc.model_dump()
    calc = {'uuid': job_uuid, 'output': task_doc, "metadata": metadata}
    doc_store.update(calc)
    #  遍历所有任务
    
    filepath = STRUCTURE_DIR.joinpath(f"{structure_id}-relaxed.cif")
    p = ['output.output.'+i for i in ["energy", "energy_per_atom", 'volume', 'density', 'symmetry', 'structure']]
    p += ['output.'+i for i in ["state", "dir_name", 'task_type']]
    p += ['metadata']
    calc_info = job_store.query_one({"uuid": job_uuid}, properties=p)
    [calc_info.pop(i, None) for i in ['_id', 'index', 'uuid']]
    
    structure = Structure.from_dict(calc_info['output']['output'].pop('structure'))
    
    filepath = STRUCTURE_DIR.joinpath(f"relaxed.cif")
    structure.to(filepath)
    calc_info.update({'filepath': str(filepath)})
    summary = job_store.query_one({'structure_id': structure_id})
    summary['calculations'].append(calc_info)
    doc_store.update(summary)
    summary.pop('_id')
    
    artifact = {
          'chatbox': {'text-1': f"# Structure ID: {structure_id}\n", 'text-2': json2chatbox(calc_info),
                      'html': {'value': make_crystal_html(structure)}, 'text-3': download2chatbox([calc_info['filepath']]) 
                  },
          "gradio": [
              {}, {}, {},
              {"value": summary}
              ]
          }
    return Command(
                update={
                    "messages": [ToolMessage(f"结构优化已经完成。\n可用的信息{str(calc_info)}", artifact=artifact, tool_call_id=tool_call_id)]
                }
            )

@tool(parse_docstring=True)
def get_scf(runtime: ToolRuntime, filepath: str, structure_id: str):
    """
    对提供的晶体进行静态计算

    Args:
        filepath: 结构文件的文件路径
        structure_id: 结构的唯一标识
    """
    struct = Structure.from_file(filepath)
    tool_call_id = runtime.tool_call_id
    my_custom_set = StaticSetGenerator(user_incar_settings={"ENCUT": 200, 'ISPIN': 1})
    maker = StaticMaker(input_set_generator=my_custom_set)
    job = maker.make(struct)
    metadata = {"structure_id": structure_id, "calc_type": 'static', "task_id": str(uuid.uuid4())}
    job.update_metadata(metadata)
    job_uuid = job.uuid
    job_store, doc_store = get_store()

    JOBFLOW_DIR = ROOT_DIR.joinpath(structure_id).joinpath('jobflow')
    JOBFLOW_DIR.mkdir(exist_ok=True, parents=True)


    # run_locally(job, create_folders=True, store=job_store, root_dir=JOBFLOW_DIR)
    #  遍历所有任务
    vasp_input_set = maker.input_set_generator.get_input_set(struct)
    vasp_input_set.write_input(JOBFLOW_DIR)
    run_vasp_dpdispatcher(structure_id)# dpdispatcher
    task_doc = get_vasp_task_document(JOBFLOW_DIR, **maker.task_document_kwargs)
    task_doc.task_label = maker.name
    task_doc = task_doc.model_dump()
    calc = {'uuid': job_uuid, 'output': task_doc, "metadata": metadata}
    doc_store.update(calc)


    p = ['output.output.'+i for i in ["energy", "energy_per_atom"]]
    p += ['output.'+i for i in ["state", "dir_name", 'task_type']]
    p += ['metadata']
    calc_info = job_store.query_one({"uuid": job_uuid}, properties=p)
    [calc_info.pop(i, None) for i in ['_id', 'index', 'uuid']]
    
    summary = job_store.query_one({'structure_id': structure_id})
    summary['calculations'].append(calc_info)
    doc_store.update(summary)
    summary.pop('_id')
    artifact = {
            'chatbox': {'text-1': f"# Structure ID: {structure_id}\n", 'text-2': json2chatbox(calc_info)},
            "gradio": [
                {}, {}, {},
                {"value": summary}
                ]
            }
    return Command(
                update={
                    "messages": [ToolMessage(f"静态计算已经完成。\n可用的信息{str(calc_info)}", artifact=artifact, tool_call_id=tool_call_id)],
                }
            )

@tool(parse_docstring=True)
def get_dos(runtime: ToolRuntime, filepath: str, structure_id: str):
    """
    对提供的晶体进行dos计算

    Args:
        filepath: 结构文件的文件路径
        structure_id: 结构的唯一标识
    """

    struct = Structure.from_file(filepath)
    tool_call_id = runtime.tool_call_id
    flow_maker = BandStructureMaker(bandstructure_type='uniform')
    job = flow_maker.make(struct)
    job = update_user_incar_settings(job, {"ENCUT": 200, 'ISPIN': 1})
    metadata = {"structure_id": structure_id, "calc_type": 'dos', "task_id": str(uuid.uuid4())}
    job.update_metadata(metadata)
    job_uuid = job[-1].uuid
    job_store, doc_store = get_store()
    JOBFLOW_DIR = ROOT_DIR.joinpath(structure_id).joinpath('jobflow')
    JOBFLOW_DIR.mkdir(exist_ok=True, parents=True)
    
    run_locally(job, create_folders=True, store=job_store, root_dir=JOBFLOW_DIR)

    for maker in [flow_maker.static_maker, flow_maker.bs_maker]:
    #  遍历所有任务
        vasp_input_set = maker.input_set_generator.get_input_set(struct)
        vasp_input_set.write_input(JOBFLOW_DIR)
        if maker.name == 'non-scf':
            run_vasp_dpdispatcher(structure_id, add_forward_files=["CHGCAR"]) 
            label = maker.name + ' uniform'
            maker.task_document_kwargs.setdefault("parse_dos", True)
        else:
            run_vasp_dpdispatcher(structure_id, add_backward_files=["CHGCAR"])
            label = maker.name
        
    #     task_doc = get_vasp_task_document(JOBFLOW_DIR, **maker.task_document_kwargs)
    #     task_doc.task_label = label
    #     task_doc = task_doc.model_dump()
    # calc = {'uuid': job_uuid, 'output': task_doc, "metadata": metadata}
    # doc_store.update(calc)


    p = ['output.'+i for i in ["state", "dir_name", 'task_type', 'vasp_objects.dos']]
    p += ['metadata']
    calc_info = job_store.query_one({"uuid": job_uuid}, properties=p, load=True)
    [calc_info.pop(i, None) for i in ['_id', 'index', 'uuid']]
   
    vasp_objects = calc_info['output'].pop('vasp_objects')
    

    summary = job_store.query_one({'structure_id': structure_id})
    summary['calculations'].append(calc_info)
    doc_store.update(summary)
    summary.pop('_id')
   
    dos = CompleteDos.from_dict(vasp_objects['dos'])
    dos_plotter = DosPlotter()
    FIGURES_DIR = ROOT_DIR.joinpath(structure_id).joinpath('figures')
    FIGURES_DIR.mkdir(exist_ok=True, parents=True)
    dos_plotter.add_dos_dict(dos.get_element_dos())
    jpg_path = FIGURES_DIR.joinpath('./dos.jpg')
    pdf_path = FIGURES_DIR.joinpath('./dos.pdf')
    dos_plotter.save_plot(jpg_path, ylim=(0, 10))
    dos_plotter.save_plot(pdf_path, ylim=(0, 10))
    
    artifact = {
            'chatbox': {
                'text-1': f"# Structure ID: {structure_id}\n", 'image': {'value': str(jpg_path)},
                'html-1': {'value': download2chatbox([jpg_path, pdf_path])}
            },
            "gradio": [
                {}, {}, {},
                {"value": summary}
                ]
            }
    return Command(
                update={
                    "messages": [ToolMessage(f"静态计算已经完成。\n可用的信息{str(calc_info)}", artifact=artifact, tool_call_id=tool_call_id)],
                }
            )

@tool(parse_docstring=True)
def get_band(runtime: ToolRuntime):
    """
    对提供的晶体进行能带计算
    """
    state = runtime.state
    struct = state['structure']
    return f"{struct}结构正在进行能带计算"


from langchain.tools import tool, InjectedToolCallId
from typing import TypedDict, Annotated, Dict, Any, Optional
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolRuntime
from mp_api.client import MPRester
from pymatgen.core.structure import Structure
import os
import gradio as gr
from rich import print as rprint
from typing import Literal
import traceback
from dotenv import load_dotenv
from pymatgen.core.structure import Structure
from pymatgen.core.surface import SlabGenerator, generate_all_slabs, get_symmetrically_distinct_miller_indices

from pymatgen.core.lattice import Lattice
import uuid
from Pymatsci.SurfAgent.config import ROOT_DIR
from jobflow import job, run_locally, JobStore
from emmet.core.tasks import StructureMetadata
from Pymatsci.SurfAgent.utils.tool import get_store
from Pymatsci.SurfAgent.ui.get_struc_plot import make_crystal_html
from Pymatsci.SurfAgent.utils.tool import json2chatbox, download2chatbox
load_dotenv(override=True)
matpro_api = os.getenv("mp-api")
# def get_wulff

@tool(parse_docstring=True)
def get_possible_hkl(runtime: ToolRuntime, filepath: str, structure_id: str, max_miller_index: int=1):
    """
    根据提供的最大米勒指数获取搜友可能的米勒指数
    
    Args:
        filepath: 固体结构的文件路径
        structure_id: 固体结构的唯一标识
        max_miller_index: 最大米勒指数
    """
    tool_call_id = runtime.tool_call_id
    structure = Structure.from_file(filepath)
    miller_indcies = get_symmetrically_distinct_miller_indices(structure, max_miller_index)
    job_store, doc_store = get_store()
    summary = job_store.query_one({'structure_id': structure_id})
    info = {'max_miller_index': max_miller_index, "possible_indcies": miller_indcies}
    summary['possible_miller_indcies'].append(info)
    doc_store.update(summary)
    summary.pop('_id')
    artifact = {
        'chatbox': {"text": f"# Structure ID: {structure_id}\n{json2chatbox(info)}"},
        "gradio": [
            {}, {}, {},{"value": summary}
            ]
        }
    return Command(
                update={
                    "messages": [ToolMessage(f"表面结构均已经得到\n可用的信息{str(miller_indcies)}", tool_call_id=tool_call_id, artifact=artifact)]
                }
            )

@tool(parse_docstring=True)
def get_hkl_surface(
    runtime: ToolRuntime, filepath: str, structure_id: str, miller_index: list[int]=[1, 0, 0],
    min_slab_size: float=5, min_vacuum_size: float=15, terminations: bool=True
    ):
    """
    根据提供的米勒指数创建表面结构
    
    Args:
        filepath: 固体结构的文件路径
        structure_id: 固体结构的唯一标识
        miller_index: Miller index of the plane parallel to the surface
        min_slab_size: 最小的表面平板厚度
        min_vacuum_size: 最小的真空层厚度
        terminations: 是否考虑所有的表面终端
    """

    tool_call_id = runtime.tool_call_id
    structure = Structure.from_file(filepath)
    job_store, doc_store = get_store()
    summary = job_store.query_one({'structure_id': structure_id})
    
    slab_generator = SlabGenerator(
        structure,
        miller_index,
        min_slab_size,
        min_vacuum_size,
        primitive=False,
        center_slab=True,
    )
    if terminations:
        surfs = slab_generator.get_slabs()
    else:
        surfs = [slab_generator.get_slab()]
    for idx, surf in enumerate(surfs):
        info = init_slab(surf)
        info.update({'composition': surf.composition.as_dict(), 'miller_index': surf.miller_index, 
                    "surface_area": surf.surface_area, 'bulk_structure_id': structure_id, "termination_id": idx+1}) 
        doc_store.update(info)
        summary['surfaces'].append(info)

    doc_store.update(summary)
    summary.pop('_id')
    chatbox = {'text': f"# Structure ID: {structure_id}\n{json2chatbox(summary["surfaces"])}"}
    for idx, (surf, info) in enumerate(zip(surfs, summary["surfaces"])):
        chatbox.update({f'text-{idx}': f"## {str(info['miller_index'])}-{str(info['termination_id'])} (Structure ID: {info['structure_id']})", f'html-{idx}': {"value": make_crystal_html(surf)}})
    artifact = {
        'chatbox': chatbox,
        "gradio": [
            {}, {}, {},{"value": summary}]
        }
    return Command(
                update={
                    "messages": [ToolMessage(f"表面结构均已经得到\n可用的信息{summary['surfaces']}", tool_call_id=tool_call_id, artifact=artifact)]
                }
            )

def init_slab(structure):
    info = {'uuid': str(uuid.uuid4()), "structure_id": str(uuid.uuid4()), 
            "calculations": []
            }
    dir = ROOT_DIR.joinpath(info['structure_id']).joinpath('structure')
    dir.mkdir(exist_ok=True, parents=True)

    filename = f"unrelaxed.cif"
    filepath = dir.joinpath(filename)
    structure.to(filepath)
    info.update({'filepath': str(filepath)})
    return info

def init_bulk(structure, keys=['composition', 'volume', 'density', 'symmetry']):
    info = {'uuid': str(uuid.uuid4()), "structure_id": str(uuid.uuid4()), 
            "calculations": [], 'surfaces': [], 'possible_miller_indcies': []
            }
    dir = ROOT_DIR.joinpath(info['structure_id']).joinpath('structure')
    dir.mkdir(exist_ok=True, parents=True)

    filename = f"unrelaxed.cif"
    filepath = dir.joinpath(filename)
    structure.to(filepath)
    info.update({'filepath': str(filepath)})
    _, doc_store = get_store()
    docs = StructureMetadata.from_structure(structure).model_dump()
    info.update({i: docs[i] for i in keys}) 
    doc_store.update(info)
    return info

@tool(parse_docstring=True)
def get_struc_from_id(runtime: ToolRuntime, filepath: str):
    """
    根据提供的晶体文件路径读取晶体结构
    
    Args:
        filepath: 文件路径
    """
    tool_call_id = runtime.tool_call_id
    structure = Structure.from_file(filepath)
    info = init_bulk(structure)
    artifact = {'text': "初始结构已经获得", "json": info, 'html': 5}
    return Command(
                update={
                    "messages": [ToolMessage(f"初始结构已获得。\n可用的信息{str(info)}", artifact=artifact, tool_call_id=tool_call_id)]
                }
            )

@tool(parse_docstring=True)
def get_struc_from_path(runtime: ToolRuntime, filepath: str):
    """
    根据给定的晶体文件路径获取晶体结构，当可用的信息只有filepath无structure_id时才调用
    
    Args:
        filepath: 给定的文件路径
    """
    tool_call_id = runtime.tool_call_id
    structure = Structure.from_file(filepath)
    rst = init_bulk(structure)
    artifact = {
        'chatbox': {"text-": f"\n# Structure ID: {rst['structure_id']}", "text-2": json2chatbox(rst), 
            'html': {"value": make_crystal_html(structure)}, "text-3": download2chatbox([rst['filepath']])},
        "gradio": [
            {'value': structure.composition.formula}, {'value': rst['structure_id']}, {'value': make_crystal_html(structure)},
            {"value": rst}
            ]
        }
    return Command(
                update={
                    "messages": [ToolMessage(f"初始结构已获得。\n可用的信息{str(rst)}", artifact=artifact, tool_call_id=tool_call_id)]
                }
            )

@tool(parse_docstring=True)
def search_materials_project(
    runtime: ToolRuntime,
    search_criteria: Dict[str, Any],
    limit: int = 10
) -> Dict[str, Any]:
    """
    从Materials Project数据库中根据条件搜索材料
    
    Args:
        search_criteria: 搜索条件字典，支持以下键值：\
            - material_id: str, 材料ID，例如 "mp-1234" \
            - formula: str, 化学式，例如 "TiO2" \
            - elements: List[str], 元素列表，例如 ["Ti", "O"] \
            - exclude_elements: List[str], 排除的元素列表 \
            - band_gap: Tuple[float, float], 带隙范围 (min, max)，例如 (1.0, 3.0) \
            - energy_above_hull: Tuple[float, float], 形成能范围 (min, max) \
            - num_sites: Tuple[int, int], 原子数范围 (min, max) \
            - spacegroup_number: int, 空间群编号 \
            - crystal_system: str, 晶系, "Triclinic", "Monoclinic", "Orthorhombic", "Tetragonal", "Trigonal", "Hexagonal", "Cubic"中的一个 \
            - is_gap_direct: bool, 是否为直接带隙
        limit: 返回结果的最大数量
    """
    
    try:
        # 构建搜索条件
        search_params = {}
        
        # 化学式搜索
        if "formula" in search_criteria:
            search_params["formula"] = search_criteria["formula"]
        
        # 元素组成搜索
        if "elements" in search_criteria:
            elements = search_criteria["elements"]
            if isinstance(elements, list):
                search_params["elements"] = elements
        
        # 排除元素
        if "exclude_elements" in search_criteria:
            exclude_elements = search_criteria["exclude_elements"]
            if isinstance(exclude_elements, list):
                search_params["exclude_elements"] = exclude_elements
        
        # 带隙范围
        if "band_gap" in search_criteria:
            band_gap_range = search_criteria["band_gap"]
            if isinstance(band_gap_range, (tuple, list)) and len(band_gap_range) == 2:
                min_bg, max_bg = band_gap_range
                search_params["band_gap"] = (min_bg, max_bg)
            elif isinstance(band_gap_range, (int, float)):
                # 单值视为下限
                search_params["band_gap"] = (band_gap_range, None)
        
        # 形成能范围
        if "energy_above_hull" in search_criteria:
            energy_range = search_criteria["energy_above_hull"]
            if isinstance(energy_range,  (tuple, list)) and len(energy_range) == 2:
                search_params["energy_above_hull"] = tuple(energy_range)
        
        # 原子数范围
        if "num_sites" in search_criteria:
            nsites_range = search_criteria["num_sites"]
            if isinstance(nsites_range, (tuple, list)) and len(nsites_range) == 2:
                search_params["num_sites"] = tuple(nsites_range)
        
        # 空间群编号
        if "spacegroup_number" in search_criteria:
            search_params["spacegroup_number"] = search_criteria["spacegroup_number"]
        
        # 晶系
        if "crystal_system" in search_criteria:
            search_params["crystal_system"] = search_criteria["crystal_system"]
        
        # 直接带隙
        if "is_gap_direct" in search_criteria:
            search_params["is_gap_direct"] = search_criteria["is_gap_direct"]
        
        search_params["num_chunks"] = 1
        search_params["chunk_size"] = limit
        # 执行搜索
        try:
            with MPRester(matpro_api) as mpr:
                materials_data = mpr.materials.summary.search(
                    **search_params
                )
        except Exception as query_error:
            return {
                "success": False,
                "error": f"搜索Materials Project时出错: {str(query_error)}\n{traceback.format_exc()}",
                "materials": [],
                "count": 0,
                "search_criteria": search_criteria
            }
        # 限制结果数量
        if isinstance(materials_data, list):
            materials_data = materials_data[:limit]
        else:
            materials_data = [materials_data]
        
        if not materials_data:
            return {
                "success": False,
                "error": "未找到符合条件的材料",
                "materials": [],
                "count": 0,
                "search_criteria": search_criteria
            }

        # 处理搜索结果
        tool_call_id = runtime.tool_call_id
        material_data = materials_data[0]
        # try:
        structure: Structure = material_data.structure
        rst = init_bulk(structure)
        artifact = {
                'chatbox': {"text-": f"\n# Structure ID: {rst['structure_id']}", "text-2": json2chatbox(rst), 
                        'html': {"value": make_crystal_html(structure)}, "text-3": download2chatbox([rst['filepath']])},
                "gradio": [
                {'value': structure.composition.formula}, {'value': rst['structure_id']}, {'value': make_crystal_html(structure)},
                {"value": rst}
                ]             
            }
            
        # except Exception as material_error:
        #     print(f"处理材料 {material_data.material_id} 时出错: {str(material_error)}")
            
        return Command(
                        update={
                            "messages": [ToolMessage(f"初始结构已获得。\n可用的信息{str(rst)}", artifact=artifact, tool_call_id=tool_call_id)]
                        }
                    )
    except Exception as e:
        return {
            "success": False,
            "error": f"搜索Materials Project时出错: {str(e)}\n{traceback.format_exc()}",
            "materials": [],
            "search_criteria": search_criteria
        }


if __name__ == "__main__":
    # from rich import print as rprint
    # from langchain_core.utils.function_calling import convert_to_openai_tool
    # rprint(convert_to_openai_tool(search_materials_project))
    structure = Structure(Lattice.cubic(5), ['B', 'C'], [[0, 0, 0], [0.5, 0.5, 0.5]])
    print(structure.lattice.abc)
    print(structure.lattice.angles)
 

    print(structure.volume)
    print(structure.as_dict())
    # print(structure.get_angle())
    # print(structure)
    # surfs = generate_all_slabs(structure, max_index=2, min_slab_size=10, min_vacuum_size=10)
    # for s in surfs:
    #     print(s.miller_index)
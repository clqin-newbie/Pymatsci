from pathlib import Path
import sys



# 明确指定当前工作目录
ROOT_DIR = Path(sys.argv[0]).parent
ROOT_DIR.mkdir(exist_ok=True, parents=True)

# 数据库
DATABASE_DIR = ROOT_DIR.joinpath('database')
DATABASE_DIR.mkdir(exist_ok=True, parents=True)

#  dpdispatcher
machine_dict = {
    "batch_type": "Shell",
    "context_type": "Local",
    "local_root": str(ROOT_DIR),
    "remote_root": "/home/clqin/work/atomate2/DPDispatcher/remote_root"
}
resources_dict = {
    "cpu_per_node" : 10,
    "gpu_per_node" : 1,
    "group_size" : 1,
    "module_list" : ["vasp"],
    "source_list": [],
    "envs" : {},
    "prepend_script" : []					
}

      




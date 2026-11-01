from dpdispatcher import Machine, Resources, Submission, Task
from Pymatsci.SurfAgent.config import ROOT_DIR
from rich import print as rprint
from atomate2.vasp.jobs.base import get_vasp_task_document
from Pymatsci.SurfAgent.config import machine_dict, resources_dict
from pathlib import Path




def run_vasp_dpdispatcher(
        structure_id, 
        work_dir='jobflow', 
        command='mpirun -np 4 vasp_std', 
        add_forward_files=[], 
        add_backward_files=[]
    ):
    machine = Machine.load_from_dict(machine_dict)
    resources = Resources.load_from_dict(resources_dict)
    forward_files = ["INCAR", 'POSCAR', 'POTCAR', 'KPOINTS'] + add_forward_files
    backward_files = ["vasprun.xml", 'OUTCAR', 'CONTCAR'] + add_backward_files
    task1 = Task(
        command=command,
        task_work_path=work_dir,
        forward_files=forward_files,
        backward_files=backward_files,
        outlog="vasp.log",
    )
    task_list = [task1]

    submission = Submission(
        work_base=structure_id,
        machine=machine,
        resources=resources,
        task_list=task_list,
        backward_common_files=[],
    )
    submission.run_submission()
    
# print(task.keys())

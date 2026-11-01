from pymatgen.core import Structure, Lattice
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
import uuid
from pathlib import Path
def get_symmetry_info(struct: Structure, symprec=0.01, angle_tolerance=5):
    """获取结构的对称性"""
    sga = SpacegroupAnalyzer(struct, symprec=symprec, angle_tolerance=angle_tolerance)
    sym_dict = {
        "spacegroup_symbol": sga.get_space_group_symbol(),
        "spacegroup_number": sga.get_space_group_number(),
        "crystal_system": sga.get_crystal_system(),
        "point_group": sga.get_point_group_symbol(),
        # "symmetry_operations": sym_ops_list,
        "symprec": symprec,
        "angle_tolerance": angle_tolerance
    }
    return sym_dict

def get_structure_info(struct: Structure):
    """获取结构信息"""
    symmetry = get_symmetry_info(struct)
    info = struct.as_dict()
    info['formula'] = struct.composition.formula
    for i in ['charge', 'properties', 'sites', "@module", "@class"]:
        info.pop(i)
    info['symmetry'] = symmetry
    return info

def init_structure(struct: Structure, file_path: Path, file_type='unrelaxed'):
    info = get_structure_info(struct)
    info['structure_id'] = str(uuid.uuid4())
    file_path.mkdir(exist_ok=True)
    filename = f"{info['structure_id']}-{file_type}.cif"
    filepath = file_path.joinpath(filename)
    struct.to(filename=filepath, fmt="cif")
    info.update({"filepath": str(filepath)})
    return info

"""Convert a URDF to a single self-contained .usda.

Runs Isaac Lab's UrdfConverter, which writes a layered asset, into a scratch folder and flattens the result.

    isaaclab -p /workspace/learnings/tools/urdf_to_usda.py --out /workspace/learnings/assets/urdf_build/a0509_ag95_from_urdf.usda
    isaaclab -p /workspace/learnings/tools/urdf_to_usda.py --mimic --out .../a0509_ag95_from_urdf_mimic.usda

Pass --mimic to keep the gripper's mimic joints. Despite its name, convert_mimic_joints_to_normal_joints is passed to the
importer's set_parse_mimic, so the default (False) turns the followers into ordinary joints.
"""

import argparse
import contextlib

from isaaclab.app import launch_simulation
from isaaclab.sim import SimulationCfg

parser = argparse.ArgumentParser(description="Convert a URDF to a single .usda.")
parser.add_argument("--urdf", default="/workspace/learnings/assets/urdf_build/a0509_ag95.urdf")
parser.add_argument("--out", required=True, help="Output .usda path (inside the container).")
parser.add_argument("--mimic", action="store_true", help="Keep <mimic> joints (PhysxMimicJointAPI).")
parser.add_argument("--instanceable", action="store_true", help="Keep instanceable meshes (needs the prototypes after flattening).")
args = parser.parse_args()
kit = contextlib.ExitStack()
kit.enter_context(launch_simulation(SimulationCfg()))  # Kit provides pxr and the URDF importer

from pxr import Usd  # noqa: E402

from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg  # noqa: E402

scratch = f"/workspace/learnings/outputs/urdf_conversion_v3_{'mimic' if args.mimic else 'default'}"
cfg = UrdfConverterCfg(
    asset_path=args.urdf,
    usd_dir=scratch,
    usd_file_name="robot.usd",
    force_usd_conversion=True,
    make_instanceable=args.instanceable,
    fix_base=True,  # creates root_joint, as in the composed asset
    merge_fixed_joints=False,  # keeps grasp_link
    convert_mimic_joints_to_normal_joints=args.mimic,
    joint_drive=UrdfConverterCfg.JointDriveCfg(gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=100.0, damping=1.0)),
)
usd_path = UrdfConverter(cfg).usd_path
print(f"[urdf_to_usda] layered converter output: {usd_path}")

stage = Usd.Stage.Open(usd_path)
layer = stage.Flatten()
layer.Export(args.out)

flat = Usd.Stage.Open(args.out)
root = flat.GetRootLayer()
deps = sorted(set(root.GetCompositionAssetDependencies()) | set(root.GetExternalReferences()))
mimic = sum(1 for p in flat.TraverseAll() if any(s.startswith("PhysxMimicJointAPI") for s in p.GetAppliedSchemas()))
joints = sum(1 for p in flat.TraverseAll() if p.GetTypeName().endswith("Joint"))
print(f"[urdf_to_usda] wrote {args.out}")
print(f"[urdf_to_usda] external dependencies left in the file: {deps or 'none'} | prims: {len(list(flat.TraverseAll()))} | joints: {joints} | mimic joints: {mimic}")
kit.close()

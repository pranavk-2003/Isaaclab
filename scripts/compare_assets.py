"""Compare the composed robot (from the reference USDs) with the one built from Doosan's URDF.

    isaaclab -p /workspace/learnings/scripts/compare_assets.py

Joints and bodies are matched by name.
"""

import argparse
import contextlib

from isaaclab.app import launch_simulation
from isaaclab.sim import SimulationCfg

parser = argparse.ArgumentParser(description="Compare the composed robot with the one built from the URDF.")
parser.add_argument("--b", default="/workspace/learnings/assets/urdf_build/a0509_ag95_from_urdf_mimic.usda",
                    help="The URDF-built asset (a single .usda from tools/urdf_to_usda.py).")
args = parser.parse_args()
kit = contextlib.ExitStack()
kit.enter_context(launch_simulation(SimulationCfg()))  # Kit provides pxr and the URDF importer

from pxr import Gf, Usd, UsdGeom, UsdPhysics  # noqa: E402

A_NAME, A_PATH = "composed", "/workspace/learnings/assets/a0509_ag95/a0509_ag95.usda"
B_NAME, B_PATH = "urdf", args.b


def describe(path: str) -> dict:
    stage = Usd.Stage.Open(path)
    prims = list(Usd.PrimRange(stage.GetPseudoRoot(), Usd.TraverseInstanceProxies()))
    out = {"stage": stage, "joints": {}, "bodies": {}, "roots": [], "mimic": {}, "approx": {}}
    out["mpu"] = UsdGeom.GetStageMetersPerUnit(stage)
    out["up"] = UsdGeom.GetStageUpAxis(stage)
    out["default"] = str(stage.GetDefaultPrim().GetPath()) if stage.GetDefaultPrim() else None
    for p in prims:
        if p.HasAPI(UsdPhysics.ArticulationRootAPI):
            out["roots"].append((str(p.GetPath()), p.GetTypeName()))
        if p.HasAPI(UsdPhysics.CollisionAPI):
            mesh = UsdPhysics.MeshCollisionAPI(p)
            approx = mesh.GetApproximationAttr().Get() if p.HasAPI(UsdPhysics.MeshCollisionAPI) else "(no mesh API)"
            out["approx"][str(approx)] = out["approx"].get(str(approx), 0) + 1
        if p.HasAPI(UsdPhysics.RigidBodyAPI):
            mass = UsdPhysics.MassAPI(p).GetMassAttr().Get() if p.HasAPI(UsdPhysics.MassAPI) else None
            out["bodies"][p.GetName()] = mass
        if p.IsA(UsdPhysics.Joint):
            j = UsdPhysics.Joint(p)
            b0 = [t.name for t in j.GetBody0Rel().GetTargets()]
            b1 = [t.name for t in j.GetBody1Rel().GetTargets()]
            info = {"type": p.GetTypeName(), "body0": b0[0] if b0 else "WORLD", "body1": b1[0] if b1 else "WORLD",
                    "pos0": tuple(round(v, 5) for v in j.GetLocalPos0Attr().Get()),
                    "pos1": tuple(round(v, 5) for v in j.GetLocalPos1Attr().Get())}
            if p.IsA(UsdPhysics.RevoluteJoint):
                rj = UsdPhysics.RevoluteJoint(p)
                info["axis"] = str(rj.GetAxisAttr().Get())
                info["limits_deg"] = (round(rj.GetLowerLimitAttr().Get(), 3), round(rj.GetUpperLimitAttr().Get(), 3))
                drive = UsdPhysics.DriveAPI.Get(p, "angular")
                if drive:
                    g = lambda a: a.Get() if a and a.HasAuthoredValue() else None  # noqa: E731
                    info["drive"] = tuple(g(a) for a in (drive.GetStiffnessAttr(), drive.GetDampingAttr(), drive.GetMaxForceAttr()))
            for schema in p.GetAppliedSchemas():
                if schema.startswith("PhysxMimicJointAPI"):
                    axis = schema.split(":")[1]
                    ref = p.GetRelationship(f"physxMimicJoint:{axis}:referenceJoint").GetTargets()
                    gear = p.GetAttribute(f"physxMimicJoint:{axis}:gearing").Get()
                    off = p.GetAttribute(f"physxMimicJoint:{axis}:offset").Get()
                    info["mimic"] = (ref[0].name if ref else None, gear, off)
                elif schema == "NewtonMimicAPI":  # written by the 3.0 URDF importer; PhysX reads it too, with default coefficients
                    ref = p.GetRelationship("newton:mimicJoint").GetTargets()
                    info["mimic"] = (ref[0].name if ref else None, "newton schema", None)
            out["joints"][p.GetName()] = info
    return out


A, B = describe(A_PATH), describe(B_PATH)
rule = "-" * 100


def section(title):
    print(f"\nCOMPARE {rule}\nCOMPARE {title}")


section("1. stage metadata and articulation roots")
for name, d in ((A_NAME, A), (B_NAME, B)):
    print(f"COMPARE {name:8} metersPerUnit={d['mpu']} up={d['up']} defaultPrim={d['default']} | articulation roots: {d['roots']}")

section("2. counts")
for name, d in ((A_NAME, A), (B_NAME, B)):
    kinds = {}
    for j in d["joints"].values():
        kinds[j["type"]] = kinds.get(j["type"], 0) + 1
    total = sum(m for m in d["bodies"].values() if m)
    print(f"COMPARE {name:8} rigid bodies={len(d['bodies'])} joints={len(d['joints'])} {kinds} | summed body mass={total:.3f} kg"
          f" | bodies with no/zero mass: {[b for b, m in d['bodies'].items() if not m]}")
    print(f"COMPARE {'':8} collision approximations: {d['approx']}")

section("3. joints that exist in only one asset (matched by name)")
only_a, only_b = sorted(set(A["joints"]) - set(B["joints"])), sorted(set(B["joints"]) - set(A["joints"]))
print(f"COMPARE only in {A_NAME}: {only_a}")
print(f"COMPARE only in {B_NAME}: {only_b}")
print(f"COMPARE bodies only in {A_NAME}: {sorted(set(A['bodies']) - set(B['bodies']))}")
print(f"COMPARE bodies only in {B_NAME}: {sorted(set(B['bodies']) - set(A['bodies']))}")

section("4. common joints: axis, limits (as authored, degrees), drive (stiffness, damping, maxForce), mimic (ref, gearing, offset)")
print(f"COMPARE {'joint':<28} {'':8} {'type':<22} {'axis':<5} {'limits [deg]':<22} {'drive':<28} mimic")
for jn in sorted(set(A["joints"]) & set(B["joints"])):
    for name, d in ((A_NAME, A), (B_NAME, B)):
        j = d["joints"][jn]
        print(f"COMPARE {jn if name == A_NAME else '':<28} {name:<8} {j['type']:<22} {j.get('axis', ''):<5} {j.get('limits_deg', '')!s:<22} {j.get('drive', '')!s:<28} {j.get('mimic', '')}")

section("5. where the gripper is attached (the joint whose body0 is link_6): local frame in link_6's space")
for name, d in ((A_NAME, A), (B_NAME, B)):
    for jn, j in d["joints"].items():
        if j["body0"] == "link_6":
            print(f"COMPARE {name:8} joint {jn}: link_6 -> {j['body1']}  pos0={j['pos0']}  pos1={j['pos1']}")

section("6. do the two assets agree on the arm geometry? world position of each link at the start pose (m)")
def world(d, body):
    cands = [p for p in Usd.PrimRange(d["stage"].GetPseudoRoot(), Usd.TraverseInstanceProxies()) if p.GetName() == body and p.HasAPI(UsdPhysics.RigidBodyAPI)]
    return UsdGeom.Xformable(cands[0]).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).ExtractTranslation() if cands else None
for body in ["link_1", "link_2", "link_3", "link_4", "link_5", "link_6", "ag95_base_link"]:
    pa, pb = world(A, body), world(B, body)
    gap = (pa - pb).GetLength() if pa is not None and pb is not None else float("nan")
    fmt = lambda v: tuple(round(x, 4) for x in v) if v is not None else None  # noqa: E731
    print(f"COMPARE {body:<15} {A_NAME} {fmt(pa)}   {B_NAME} {fmt(pb)}   difference {gap * 1000:.2f} mm")

kit.close()

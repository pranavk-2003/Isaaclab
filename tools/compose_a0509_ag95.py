"""Compose the A0509 arm and the AG95 gripper into one USD stage, then validate it.

Both source assets are referenced, not copied; this layer only adds overrides on top of them.

    isaaclab -p /workspace/learnings/tools/compose_a0509_ag95.py
    isaaclab -p /workspace/learnings/tools/compose_a0509_ag95.py --skip-fix
    isaaclab -p /workspace/learnings/tools/compose_a0509_ag95.py --validate-only <file.usda>

Set PYTHONUNBUFFERED=1 when piping the output.
"""

import argparse

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--skip-fix", action="store_true", help="Leave the dangling World_joint unrepaired.")
parser.add_argument("--validate-only", type=str, default=None, help="Skip composing; just validate this USD file.")
args = parser.parse_args()

# pxr can only be imported once Kit is running.
import contextlib

from isaaclab.app import launch_simulation
from isaaclab.sim import SimulationCfg

kit = contextlib.ExitStack()
kit.enter_context(launch_simulation(SimulationCfg()))  # Kit provides pxr and the URDF importer

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade  # noqa: E402

ASSETS = "/workspace/learnings/assets"
OUT = f"{ASSETS}/a0509_ag95/a0509_ag95.usda"
OUT_UNFIXED = f"{ASSETS}/a0509_ag95/a0509_ag95_unfixed.usda"

# Relative to the output layer, so the file works on the host and in the container.
ARM_FILE, ARM_PRIM = "../a0509/a0509.usda", "/World/a0509"
GRIPPER_FILE, GRIPPER_PRIM = "../ag95/ag95.usda", "/World/ag95"

ROBOT = "/Robot"
ARM = f"{ROBOT}/a0509"
GRIPPER = f"{ROBOT}/ag95"
FLANGE_LINK = f"{ARM}/link_6"  # the arm's last moving link; its +Z axis is the flange normal
LEFTOVER_JOINT = f"{GRIPPER}/World_joint"
PAD_MATERIAL = f"{ROBOT}/PhysicsMaterials/pad_rubber"
PAD_FRICTION = 1.0  # rubber on a smooth object; the real pad's value is unknown


def joint_frame(pos, rot) -> Gf.Matrix4d:
    """A joint's local frame (localPosN / localRotN) as a 4x4 matrix.

    pxr uses ROW vectors, so a frame expressed in a body's space becomes a world frame by multiplying on the
    RIGHT by that body's local-to-world matrix:   frame_world = frame * body_world
    """
    m = Gf.Matrix4d(1.0)
    m.SetRotate(Gf.Quatd(rot.GetReal(), Gf.Vec3d(rot.GetImaginary())))  # clears the translation, so set it after
    m.SetTranslateOnly(Gf.Vec3d(pos))
    return m


def place_gripper_on_flange(stage: Usd.Stage) -> None:
    """Set the gripper's authored pose to match World_joint's frames.

    PhysX snaps joint frames together at start, but the file stores body poses separately. Without this the gripper is
    drawn 1.055 m from the flange until the simulation starts.

        frame1 * W_gripper = frame0 * W_link6  =>  W_gripper = frame1^-1 * frame0 * W_link6
    """
    joint = UsdPhysics.Joint(stage.GetPrimAtPath(LEFTOVER_JOINT))
    flange_world = UsdGeom.Xformable(stage.GetPrimAtPath(FLANGE_LINK)).ComputeLocalToWorldTransform(
        Usd.TimeCode.Default()
    )
    frame0 = joint_frame(joint.GetLocalPos0Attr().Get(), joint.GetLocalRot0Attr().Get())  # in link_6's space
    frame1 = joint_frame(joint.GetLocalPos1Attr().Get(), joint.GetLocalRot1Attr().Get())  # in ag95/base's space
    gripper_world = frame1.GetInverse() * frame0 * flange_world

    # ag95/base sits at the origin of /Robot/ag95 and /Robot is identity, so one matrix op on /Robot/ag95 sets the pose.
    xform = UsdGeom.Xformable(stage.GetPrimAtPath(GRIPPER))
    xform.ClearXformOpOrder()
    xform.AddTransformOp().Set(gripper_world)


def bind_pad_friction(stage: Usd.Stage) -> None:
    """Bind a physics material to the finger pads.

    The source asset binds them to a material prim that is not in this file, so PhysX falls back to default friction.
    The binding uses the "physics" purpose on each pad body and is inherited by its colliders.
    """
    material = UsdShade.Material.Define(stage, PAD_MATERIAL)
    api = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    api.CreateStaticFrictionAttr(PAD_FRICTION)
    api.CreateDynamicFrictionAttr(PAD_FRICTION)
    api.CreateRestitutionAttr(0.0)
    for side in ("left", "right"):
        pad = stage.GetPrimAtPath(f"{GRIPPER}/{side}_finger_pad")
        pad.GetRelationship("material:binding").SetTargets([])  # remove the stale binding
        UsdShade.MaterialBindingAPI(pad).Bind(material, UsdShade.Tokens.weakerThanDescendants, "physics")


def compose(out_path: str, fix_dangling_joint: bool) -> None:
    """Author the combined stage and save it to `out_path`."""
    stage = Usd.Stage.CreateNew(out_path)

    # Stage metadata is not inherited through references. The sources claim cm, but their geometry is in metres.
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    # Isaac Lab spawns the default prim, so the arm and gripper both live under it.
    robot = UsdGeom.Xform.Define(stage, ROBOT)
    stage.SetDefaultPrim(robot.GetPrim())

    # Explicit prim paths: both sources have defaultPrim=/World, which would nest everything one level too deep.
    stage.DefinePrim(ARM, "Xform").GetReferences().AddReference(ARM_FILE, ARM_PRIM)
    stage.DefinePrim(GRIPPER, "Xform").GetReferences().AddReference(GRIPPER_FILE, GRIPPER_PRIM)

    if fix_dangling_joint:
        # World_joint's body0 points at a link_6 from the scene ag95.usda was exported from. PhysX treats a missing body
        # as the world, which would weld the gripper in place. Keep the joint's offset and re-target body0.
        joint = UsdPhysics.Joint(stage.GetPrimAtPath(LEFTOVER_JOINT))
        joint.GetBody0Rel().SetTargets([Sdf.Path(FLANGE_LINK)])
        place_gripper_on_flange(stage)

    bind_pad_friction(stage)

    stage.GetRootLayer().Save()
    print(f"[compose] saved {out_path}  (dangling joint fixed: {fix_dangling_joint})")


def _is_joint(prim) -> bool:
    return prim.IsA(UsdPhysics.Joint)


def validate(path: str) -> bool:
    """Check the composed stage; prints one line per check."""
    stage = Usd.Stage.Open(path)
    failures = 0

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if passed else 1
        print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))

    def warn(msg: str) -> None:
        print(f"[WARN] {msg}")

    prims = list(stage.Traverse())
    joints = [p for p in prims if _is_joint(p)]
    bodies = [p for p in prims if p.HasAPI(UsdPhysics.RigidBodyAPI)]

    # 1. stage metadata
    default_prim = stage.GetDefaultPrim()
    check("default prim is /Robot", bool(default_prim) and str(default_prim.GetPath()) == ROBOT)
    check("metersPerUnit == 1.0", UsdGeom.GetStageMetersPerUnit(stage) == 1.0, str(UsdGeom.GetStageMetersPerUnit(stage)))
    check("up axis == Z", UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z)

    # 2. joint bodies exist; only root_joint may have an empty body0 (a joint to the world).
    bad = []
    for j in joints:
        jt = UsdPhysics.Joint(j)
        b0, b1 = jt.GetBody0Rel().GetTargets(), jt.GetBody1Rel().GetTargets()
        is_root_joint = j.HasAPI(UsdPhysics.ArticulationRootAPI)
        for label, targets in (("body0", b0), ("body1", b1)):
            if not targets and not (is_root_joint and label == "body0"):
                bad.append(f"{j.GetPath()} {label}=<empty>")
            for t in targets:
                tp = stage.GetPrimAtPath(t)
                if not tp:
                    bad.append(f"{j.GetPath()} {label}->{t} (missing prim)")
                elif not tp.HasAPI(UsdPhysics.RigidBodyAPI):
                    bad.append(f"{j.GetPath()} {label}->{t} (not a rigid body)")
    check("all joint bodies resolve to rigid bodies", not bad, "; ".join(bad[:3]) + (" ..." if len(bad) > 3 else ""))

    # 3. exactly one articulation root, as Isaac Lab requires
    roots = [str(p.GetPath()) for p in prims if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
    check("exactly one articulation root", roots == [f"{ARM}/root_joint"], str(roots))

    # 4. joint counts
    def n_revolute(prefix: str) -> int:
        return sum(1 for j in joints if j.IsA(UsdPhysics.RevoluteJoint) and str(j.GetPath()).startswith(prefix))

    check("6 revolute joints in the arm", n_revolute(ARM) == 6, str(n_revolute(ARM)))
    check("6 revolute joints in the gripper (1 driven + 5 mimic)", n_revolute(GRIPPER) == 6, str(n_revolute(GRIPPER)))

    # 5. mimic joints
    mimics = [p for p in prims if any(s.startswith("PhysxMimicJointAPI") for s in p.GetAppliedSchemas())]
    unresolved = []
    for p in mimics:
        for rel in p.GetRelationships():
            if rel.GetName().startswith("physxMimicJoint:") and rel.GetName().endswith(":referenceJoint"):
                for t in rel.GetTargets():
                    if not stage.GetPrimAtPath(t):
                        unresolved.append(f"{p.GetName()}->{t}")
    check("5 mimic joints", len(mimics) == 5, str(len(mimics)))
    check("every mimic referenceJoint resolves", not unresolved, "; ".join(unresolved[:3]))

    # 6. all bodies form one connected tree (union-find over joints), i.e. the gripper is attached to the arm.
    parent = {str(b.GetPath()): str(b.GetPath()) for b in bodies}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for j in joints:
        jt = UsdPhysics.Joint(j)
        b0, b1 = jt.GetBody0Rel().GetTargets(), jt.GetBody1Rel().GetTargets()
        if b0 and b1 and str(b0[0]) in parent and str(b1[0]) in parent:
            parent[find(str(b0[0]))] = find(str(b1[0]))
    groups: dict[str, list[str]] = {}
    for b in parent:
        groups.setdefault(find(b), []).append(b.rsplit("/", 1)[-1])
    check(
        "all rigid bodies form one connected tree",
        len(groups) == 1,
        f"{len(bodies)} bodies in {len(groups)} group(s)" + ("" if len(groups) == 1 else f": {[sorted(g)[:3] for g in groups.values()]}"),
    )

    # 7. authored body poses agree with joint frames (rotation is checked for fixed joints only).
    def body_world(path):
        return UsdGeom.Xformable(stage.GetPrimAtPath(path)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())

    worst_gap, worst_joint, worst_angle = 0.0, "", 0.0
    for j in joints:
        jt = UsdPhysics.Joint(j)
        b0, b1 = jt.GetBody0Rel().GetTargets(), jt.GetBody1Rel().GetTargets()
        if not (b0 and b1 and stage.GetPrimAtPath(b0[0]) and stage.GetPrimAtPath(b1[0])):
            continue  # joints to the world, or with missing bodies, are reported by check 2
        f0 = joint_frame(jt.GetLocalPos0Attr().Get(), jt.GetLocalRot0Attr().Get()) * body_world(b0[0])
        f1 = joint_frame(jt.GetLocalPos1Attr().Get(), jt.GetLocalRot1Attr().Get()) * body_world(b1[0])
        gap = (f0.ExtractTranslation() - f1.ExtractTranslation()).GetLength()
        if gap > worst_gap:
            worst_gap, worst_joint = gap, str(j.GetPath())
        if j.IsA(UsdPhysics.FixedJoint):
            worst_angle = max(worst_angle, (f0 * f1.GetInverse()).ExtractRotation().GetAngle())  # degrees
    check(
        "authored poses agree with joint frames (PhysX has nothing to snap)",
        worst_gap < 1e-3 and worst_angle < 0.1,
        f"worst position gap {worst_gap * 1000:.3f} mm at {worst_joint or '-'}; worst fixed-joint rotation gap {worst_angle:.3f} deg",
    )

    # 8. finger pad colliders resolve to a physics material with grip friction.
    pad_problems, pad_found = [], []
    for side in ("left", "right"):
        pad = stage.GetPrimAtPath(f"{GRIPPER}/{side}_finger_pad")
        colliders = [c for c in Usd.PrimRange(pad, Usd.TraverseInstanceProxies()) if c.HasAPI(UsdPhysics.CollisionAPI)]
        pad_found.append(f"{side}: {len(colliders)} collider(s)")
        if not colliders:
            pad_problems.append(f"{side}: no collider found")
        for c in colliders:
            mat = UsdShade.MaterialBindingAPI(c).ComputeBoundMaterial("physics")[0]
            mu = UsdPhysics.MaterialAPI(mat.GetPrim()).GetStaticFrictionAttr().Get() if mat.GetPrim().IsValid() else None
            if mu is None or mu < 0.8:
                pad_problems.append(f"{c.GetPath()} friction={mu}")
    check("finger pad colliders bind a physics material with friction >= 0.8", not pad_problems,
          "; ".join(pad_problems[:2]) or ", ".join(pad_found))

    # 9. informational
    for b in bodies:
        m = UsdPhysics.MassAPI(b).GetMassAttr().Get()
        if m is not None and m < 1e-4:
            warn(f"{b.GetPath()} has mass {m:g} kg (tiny masses can destabilise the solver; watch for jitter)")
    driven = stage.GetPrimAtPath(f"{GRIPPER}/joints/left_outer_knuckle_joint")
    if driven:
        j = UsdPhysics.RevoluteJoint(driven)
        print(
            f"[INFO] gripper driven joint left_outer_knuckle_joint limits (USD, degrees): "
            f"{j.GetLowerLimitAttr().Get()} .. {j.GetUpperLimitAttr().Get()}"
        )
    arm_limits = {}
    for j in joints:
        if j.IsA(UsdPhysics.RevoluteJoint) and str(j.GetPath()).startswith(ARM):
            rj = UsdPhysics.RevoluteJoint(j)
            arm_limits[j.GetName()] = (rj.GetLowerLimitAttr().Get(), rj.GetUpperLimitAttr().Get())
    print(f"[INFO] arm joint limits (USD, degrees): {arm_limits}")

    print(f"RESULT: {'PASS' if failures == 0 else 'FAIL'} ({failures} failing check(s)) for {path}")
    return failures == 0


if args.validate_only:
    validate(args.validate_only)
else:
    out = OUT if not args.skip_fix else OUT_UNFIXED
    compose(out, fix_dangling_joint=not args.skip_fix)
    validate(out)

kit.close()

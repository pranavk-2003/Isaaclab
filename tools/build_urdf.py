"""Merge Doosan's A0509 URDF with the expanded AG95 xacro into a0509_ag95.urdf.

    ./isaaclab.sh -p /workspace/learnings/tools/build_urdf.py
"""

import os
import xml.etree.ElementTree as ET
from collections import Counter

ROOT = "/workspace/learnings"
ARM_URDF = f"{ROOT}/third_party/doosan-robot2/dsr_description2/urdf/a0509.urdf"
GRIPPER_URDF = f"{ROOT}/assets/urdf_build/ag95.urdf"  # expanded tools/ag95_top.xacro
OUT = f"{ROOT}/assets/urdf_build/a0509_ag95.urdf"
PACKAGES = {  # package:// name -> local path
    "dsr_description2": f"{ROOT}/third_party/doosan-robot2/dsr_description2",
    "dh_ag95_description": f"{ROOT}/third_party/dh_ag95_gripper_ros2/dh_ag95_description",
}

arm = ET.parse(ARM_URDF).getroot()
gripper = ET.parse(GRIPPER_URDF).getroot()

# Keep only links and joints; the <gazebo> blocks hold SDF loop closures that URDF cannot express.
gripper_parts = [child for child in gripper if child.tag in ("link", "joint")]

# Drop the gripper's empty placeholder link_6 so the arm's link_6 becomes the parent.
placeholders = [p for p in gripper_parts if p.tag == "link" and p.get("name") == "link_6" and len(list(p)) == 0]
assert len(placeholders) == 1, f"expected exactly one empty placeholder link_6, found {len(placeholders)}"
gripper_parts.remove(placeholders[0])
real_link6 = [c for c in arm if c.tag == "link" and c.get("name") == "link_6"]
assert len(real_link6) == 1 and len(list(real_link6[0])) > 0, "the arm's link_6 should exist and have content"

for part in gripper_parts:
    arm.append(part)

# Isaac Sim's importer cannot resolve package:// paths, so make them absolute.
n_meshes = 0
for mesh in arm.iter("mesh"):
    name = mesh.get("filename")
    assert name.startswith("package://"), f"unexpected mesh path: {name}"
    package, rest = name[len("package://"):].split("/", 1)
    path = os.path.join(PACKAGES[package], rest)
    assert os.path.isfile(path), f"mesh file not found: {path}"
    mesh.set("filename", path)
    n_meshes += 1

arm.set("name", "a0509_ag95")
tree = ET.ElementTree(arm)
ET.indent(tree)
tree.write(OUT, xml_declaration=True, encoding="utf-8")

links = [c.get("name") for c in arm if c.tag == "link"]
joints = [c for c in arm if c.tag == "joint"]
n_mimic = len(list(arm.iter("mimic")))
duplicates = [name for name, count in Counter(links).items() if count > 1]
children = {j.find("child").get("link") for j in joints}
dangling = [j.get("name") for j in joints if j.find("parent").get("link") not in links or j.find("child").get("link") not in links]
roots = [name for name in links if name not in children]

print(f"[build_urdf] wrote {OUT}")
print(f"[build_urdf] {len(links)} links, {len(joints)} joints, {n_mimic} mimic tags, {n_meshes} mesh references rewritten")
print(f"[build_urdf] duplicate link names: {duplicates or 'none'} | joints with a missing link: {dangling or 'none'} | root link(s): {roots}")
# 18 joints = 7 arm (6 revolute + base fixed) + 11 gripper (the xacro's 13 minus the 2 <gazebo> loop closures).
ok = len(links) == 19 and len(joints) == 18 and n_mimic == 5 and not duplicates and not dangling and roots == ["base_link"]
print(f"GATE 1.6b URDF merge: {'PASS' if ok else 'FAIL'} (need 19 links, 18 joints, 5 mimic, no duplicates, single root base_link)")

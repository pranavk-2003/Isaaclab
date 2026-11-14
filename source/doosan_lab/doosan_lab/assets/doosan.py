"""Articulation configs for the Doosan A0509 arm with the DH Robotics AG95 gripper.

The USD is built by tools/compose_a0509_ag95.py. Import only after the simulation app has started.
"""

import math
from pathlib import Path

from isaaclab_physx.sim.schemas import PhysxArticulationCfg, PhysxRigidBodyCfg

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets.articulation import ArticulationCfg

REPO_ROOT = Path(__file__).resolve().parents[4]
A0509_AG95_USD = str(REPO_ROOT / "assets" / "a0509_ag95" / "a0509_ag95.usda")

DOOSAN_A0509_AG95_CFG = ArticulationCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path=A0509_AG95_USD,
        activate_contact_sensors=True,
        rigid_props=PhysxRigidBodyCfg(
            # The real controller compensates the arm's weight, so the links ignore gravity.
            disable_gravity=True,
            max_depenetration_velocity=5.0,
        ),
        articulation_props=PhysxArticulationCfg(
            enabled_self_collisions=False,
            solver_position_iteration_count=32,  # the gripper's mimic linkage needs many iterations
            solver_velocity_iteration_count=1,
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, 0.0, 0.0),
        joint_pos={
            # All zeros points the arm straight up; joint_3 and joint_5 at 90 deg point the flange down.
            "joint_1": 0.0,
            "joint_2": 0.0,
            "joint_3": math.pi / 2,
            "joint_4": 0.0,
            "joint_5": math.pi / 2,
            "joint_6": 0.0,
            # Gripper open.
            "left_outer_knuckle_joint": 0.0,
            ".*_inner_knuckle_joint": 0.0,
            ".*_finger_joint": 0.0,
            "right_outer_knuckle_joint": 0.0,
        },
    ),
    actuators={
        # Effort and velocity limits from the A0509 URDF.
        "shoulder": ImplicitActuatorCfg(
            joint_names_expr=["joint_[1-2]"],
            joint_effort_limit=194.0,
            joint_velocity_limit=math.pi,
            stiffness=800.0,
            damping=80.0,
        ),
        "elbow": ImplicitActuatorCfg(
            joint_names_expr=["joint_3"],
            joint_effort_limit=163.0,
            joint_velocity_limit=math.pi,
            stiffness=600.0,
            damping=60.0,
        ),
        "wrist": ImplicitActuatorCfg(
            joint_names_expr=["joint_[4-6]"],
            joint_effort_limit=50.0,
            joint_velocity_limit=2 * math.pi,
            stiffness=200.0,
            damping=20.0,
        ),
        # The only driven gripper joint (0..0.93 rad); the other five follow it as PhysX mimic joints.
        "gripper_drive": ImplicitActuatorCfg(
            joint_names_expr=["left_outer_knuckle_joint"],
            # ~100 N of grip at 9.5 N per N m (scripts/measure_gripper.py); the real AG95 grips 45-160 N.
            joint_effort_limit=10.5,
            joint_velocity_limit=2.1,
            stiffness=300.0,
            damping=5.0,
        ),
        "gripper_passive": ImplicitActuatorCfg(
            joint_names_expr=[".*_inner_knuckle_joint", ".*_finger_joint", "right_outer_knuckle_joint"],
            joint_effort_limit=50.0,
            # Followers need zero gains and no real velocity cap, or they fight the mimic constraint and the linkage explodes.
            joint_velocity_limit=100.0,
            stiffness=0.0,
            damping=0.0,
        ),
    },
)
"""Doosan A0509 + AG95, implicit PD actuators, gravity-compensated links."""

DOOSAN_A0509_AG95_HIGH_PD_CFG = DOOSAN_A0509_AG95_CFG.copy()
DOOSAN_A0509_AG95_HIGH_PD_CFG.actuators["shoulder"].stiffness = 1500.0
DOOSAN_A0509_AG95_HIGH_PD_CFG.actuators["shoulder"].damping = 150.0
DOOSAN_A0509_AG95_HIGH_PD_CFG.actuators["elbow"].stiffness = 1200.0
DOOSAN_A0509_AG95_HIGH_PD_CFG.actuators["elbow"].damping = 120.0
DOOSAN_A0509_AG95_HIGH_PD_CFG.actuators["wrist"].stiffness = 400.0
DOOSAN_A0509_AG95_HIGH_PD_CFG.actuators["wrist"].damping = 40.0
"""Stiffer arm gains, for tasks that track end-effector targets through differential IK."""

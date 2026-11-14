"""Reach task for the Doosan A0509 + AG95, adapted from Isaac Lab's UR10 reach config (see DECISIONS.md D13)."""

import math

from isaaclab_physx.physics import PhysxCfg

import isaaclab.envs.mdp as mdp
from isaaclab.managers import RewardTermCfg as RewTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.utils import configclass
from isaaclab.visualizers import VisualizerCfg

from isaaclab_tasks.core.reach.reach_env_cfg import ReachEnvCfg, ReachPhysicsCfg

from doosan_lab.assets.doosan import DOOSAN_A0509_AG95_CFG

ARM_JOINTS = ["joint_[1-6]"]  # arm only; the gripper is not part of the action
EE_BODY = "ag95_base_link"  # the fingertip point (grasp_link) is 0.19 m further along +Z


def arm_joints() -> SceneEntityCfg:
    """A fresh SceneEntityCfg per term: Isaac Lab resolves it in place, so sharing one across terms fails."""
    return SceneEntityCfg("robot", joint_names=ARM_JOINTS)


@configclass
class A0509ReachPhysicsCfg(ReachPhysicsCfg):
    """The gripper's mimic joints were validated on PhysX, so it is the default; `physics=newton_mjwarp` still selects Newton."""

    default: PhysxCfg = PhysxCfg(bounce_threshold_velocity=0.2)


@configclass
class A0509ReachEnvCfg(ReachEnvCfg):
    def __post_init__(self):
        super().__post_init__()

        # Pin the MDP to the 2.3.2 definition the reach baseline was measured on (DECISIONS D16).
        self.sim.physics = A0509ReachPhysicsCfg()
        self.terminations.success = None
        self.rewards.success = None
        self.rewards.action_magnitude = None
        self.rewards.end_effector_position_tracking_fine_grained = RewTerm(
            func=mdp.position_command_error_tanh,
            weight=0.1,
            params={"asset_cfg": SceneEntityCfg("robot", body_names=[EE_BODY]), "std": 0.1, "command_name": "ee_pose"},
        )

        self.scene.robot = DOOSAN_A0509_AG95_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")

        # The template table starts 5 cm in front of the robot and is sized for a Franka mount; the A0509's wider base
        # plate hung over its edge. Put the base 25 cm in from the near edge and keep the far edge past the farthest target.
        self.scene.table.spawn.size = (1.1, 1.3, 1.0)
        self.scene.table.init_state.pos = (0.30, 0.0, -0.5)

        # 30 Hz policy as in the template; 120 Hz physics, the rate the gripper was validated at.
        self.sim.dt = 1.0 / 120.0
        self.decimation = 4
        self.sim.render_interval = self.decimation

        # Arm joints only: the UR10 config's ".*" would include the gripper.
        self.actions.arm_action = mdp.JointPositionActionCfg(
            asset_name="robot", joint_names=ARM_JOINTS, scale=0.5, use_default_offset=True
        )
        self.observations.policy.joint_pos.params["asset_cfg"] = arm_joints()
        self.observations.policy.joint_vel.params["asset_cfg"] = arm_joints()
        self.rewards.joint_vel.params["asset_cfg"] = arm_joints()

        # Reset by offset: the template scales the default pose, which leaves joints that default to 0 unrandomized.
        self.events.reset_robot_joints.func = mdp.reset_joints_by_offset
        self.events.reset_robot_joints.params = {
            "position_range": (-0.3, 0.3),  # rad around the default pose
            "velocity_range": (0.0, 0.0),
            "asset_cfg": arm_joints(),
        }

        self.commands.ee_pose.body_name = EE_BODY
        for term in (
            self.rewards.end_effector_position_tracking,
            self.rewards.end_effector_position_tracking_fine_grained,
            self.rewards.end_effector_orientation_tracking,
        ):
            term.params["asset_cfg"].body_names = [EE_BODY]

        # Target ranges for ag95_base_link, in the robot base frame.
        r = self.commands.ee_pose.ranges
        r.pos_x = (0.35, 0.60)
        r.pos_y = (-0.20, 0.20)
        r.pos_z = (0.25, 0.50)  # keeps the fingertips above the table
        # Gripper pointing down (roll=pi, pitch=0). Yaw spans 180 deg around the start yaw, since the gripper is symmetric.
        r.roll = (math.pi, math.pi)
        r.pitch = (0.0, 0.0)
        r.yaw = (math.pi / 2, 3 * math.pi / 2)


@configclass
class A0509ReachEnvCfg_PLAY(A0509ReachEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.observations.policy.enable_corruption = False
        self.sim.default_visualizer_cfg = VisualizerCfg(eye=(1.6, -1.4, 1.0), lookat=(0.4, 0.0, 0.3))

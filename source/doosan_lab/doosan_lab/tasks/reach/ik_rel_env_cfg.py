"""Reach task with relative end-effector pose actions, adapted from Isaac Lab's Franka IK-Rel reach config."""

from isaaclab.controllers.differential_ik_cfg import DifferentialIKControllerCfg
from isaaclab.envs.mdp.actions.actions_cfg import DifferentialInverseKinematicsActionCfg
from isaaclab.utils import configclass

from doosan_lab.assets.doosan import DOOSAN_A0509_AG95_HIGH_PD_CFG

from .reach_env_cfg import ARM_JOINTS, EE_BODY, A0509ReachEnvCfg


@configclass
class A0509ReachIKRelEnvCfg(A0509ReachEnvCfg):
    def __post_init__(self):
        super().__post_init__()

        # Stiffer gains so the joints track the IK targets closely.
        self.scene.robot = DOOSAN_A0509_AG95_HIGH_PD_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")

        # No body_offset: the controlled point is EE_BODY, the same body the reward and the target use.
        self.actions.arm_action = DifferentialInverseKinematicsActionCfg(
            asset_name="robot",
            joint_names=ARM_JOINTS,
            body_name=EE_BODY,
            controller=DifferentialIKControllerCfg(command_type="pose", use_relative_mode=True, ik_method="dls"),
            scale=0.5,
        )


@configclass
class A0509ReachIKRelEnvCfg_PLAY(A0509ReachIKRelEnvCfg):
    def __post_init__(self):
        super().__post_init__()
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.observations.policy.enable_corruption = False

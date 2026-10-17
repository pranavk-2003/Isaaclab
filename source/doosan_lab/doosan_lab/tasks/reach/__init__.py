"""Reach: move the A0509 + AG95 gripper to a random target pose."""

import gymnasium as gym

from . import agents

gym.register(
    id="Doosan-Reach-A0509-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.reach_env_cfg:A0509ReachEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:A0509ReachPPORunnerCfg",
    },
)

gym.register(
    id="Doosan-Reach-A0509-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.reach_env_cfg:A0509ReachEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:A0509ReachPPORunnerCfg",
    },
)

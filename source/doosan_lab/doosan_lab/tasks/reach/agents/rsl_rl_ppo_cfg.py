"""PPO settings for the reach task, copied from Isaac Lab's UR10 reach agent."""

from isaaclab.utils import configclass

from isaaclab_rl.rsl_rl import RslRlMLPModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg


@configclass
class A0509ReachPPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 1500
    save_interval = 50
    experiment_name = "reach_a0509"
    run_name = ""
    actor = RslRlMLPModelCfg(
        hidden_dims=[64, 64],
        activation="elu",
        obs_normalization=False,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[64, 64],
        activation="elu",
        obs_normalization=False,
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.01,
        num_learning_epochs=8,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )


@configclass
class A0509ReachIKRelPPORunnerCfg(A0509ReachPPORunnerCfg):
    experiment_name = "reach_a0509_ik_rel"
    # Random exploration through IK makes the arm thrash (joint speeds of hundreds of rad/s); without observation
    # normalization PPO diverged to NaN within about 20 iterations. The joint-position run does not need it.
    actor = RslRlMLPModelCfg(
        hidden_dims=[64, 64],
        activation="elu",
        obs_normalization=True,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
    )
    critic = RslRlMLPModelCfg(hidden_dims=[64, 64], activation="elu", obs_normalization=True)

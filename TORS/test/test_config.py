from manager.config import AgentConfig
from serde import from_dict


def test_agent_config():
    example_config = {
        "class": "planner.greedy_planner.GreedyPlanner",
        "seed": 42,
        "verbose": 1,

        "planner.greedy_planner.GreedyPlanner": {
            "epsilon": 0.5
        }
    }
    new_agent_config = from_dict(AgentConfig, example_config)

    assert new_agent_config.agent_specific_config.epsilon == 0.5
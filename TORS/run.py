from manager.manager import Manager
from manager.config import EpisodeConfig, AgentConfig
import time
import argparse
from serde.json import from_json


def initialize_manager(episode, agent, verbose=0):
    with open(episode, "r") as episode_config_file:
        episode_config_serde = from_json(EpisodeConfig, episode_config_file.read())
    with open(agent, "r") as agent_config_file:
        agent_config_serde = from_json(AgentConfig, agent_config_file.read())

    manager = Manager(episode_config_serde, agent_config_serde)

    return manager


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--agent",
        help="Path to the agent configuration file (default=agent.json)",
        required=False,
        default="agent.json",
    )
    parser.add_argument(
        "-e",
        "--episode",
        help="Path to the episode configuration file (default=episode.json)",
        required=False,
        default="episode.json",
    )
    parser.add_argument(
        "-t",
        "--train",
        action="store_true",
        help="Train the agent (default=evaluate)",
        required=False,
    )
    parser.add_argument(
        "-r",
        "--result-path",
        help="Path at which to save the result json (default=result.json)",
        default="result.json",
    )
    parser.add_argument(
        "-n",
        "--number-trains",
        help="Number of trains to tell the manager to use. This option is only "
        "respected when a scenario generator is used.",
        default=1,
        type=int,
    )
    args = parser.parse_args()
    start = time.time()
    manager = initialize_manager(args.episode, args.agent)

    if args.train:
        raise NotImplementedError("Not yet implemented")
    else:
        failed = manager.run(
            n_trains=args.number_trains, result_save_path=args.result_path
        )
        print(f"Scenario failed: {failed}")
    print("Total running time: {}".format(time.time() - start))

    # print("\n***** Summary Metrics *****")
    # pprint.pprint(metrics)

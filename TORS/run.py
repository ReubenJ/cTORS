from manager.manager import Manager
from manager.config import EpisodeConfig, AgentConfig
import time
import argparse
from serde.json import from_json
import time
import logging
from rich.logging import RichHandler

FORMAT = "%(message)s"
logging.basicConfig(
    level=logging.DEBUG, format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True)]
)

logger = logging.getLogger(__name__)

def initialize_manager(episode, agent, seed, epsilon, verbose=0):
    with open(episode, "r") as episode_config_file:
        episode_config = from_json(EpisodeConfig, episode_config_file.read())
    with open(agent, "r") as agent_config_file:
        agent_config = from_json(AgentConfig, agent_config_file.read())
    agent_config.seed = seed
    agent_config.agent_specific["epsilon"] = epsilon

    manager = Manager(episode_config, agent_config)

    return manager

def main(args):
    global logger
    start = time.time()
    manager = initialize_manager(args.episode, args.agent, args.seed, args.epsilon)

    if args.train:
        raise NotImplementedError("Not yet implemented")
    else:
        failed = manager.run(
            n_trains=args.number_trains, result_save_path=args.result_path
        )
        logger.info(f"Scenario failed: {failed}")
    # print(f"Success rate: {0/100}")
    logger.info("Total running time: {}".format(time.time() - start))


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
    parser.add_argument(
        "-s",
        "--seed",
        help="Seed for the random number generator",
        default=0,
        type=int,
    )
    parser.add_argument(
        "--epsilon",
        help="Epsilon value for the epsilon-greedy policy",
        default=0.5,
        type=float,
    )
    args = parser.parse_args()
    main(args)

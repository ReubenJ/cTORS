from run import main as run_main
from pathlib import Path
from argparse import Namespace


class MainArgs(Namespace):
    agent = "agent.json"
    episode = "episode.json"
    train = False
    result_path = "result.json"
    number_trains = 100
    seed = 0
    epsilon = 0.1


def test_run_main_shouldnt_choose_invalid_action():
    """With the 'Larger' test instance, the agent is currently chooing an invalid action.

    This test ensures that the agent is not choosing an invalid action.
    """
    args = MainArgs(seed=7)
    run_main(args)


def test_run_main(tmp_path: Path, caplog):
    """With the 'Larger' test instance, the agent is currently chooing an invalid action.

    This test ensures that the agent is not choosing an invalid action.
    """
    caplog.set_level("DEBUG")
    args = MainArgs(
        agent="test/resources/larger_instance/agent.json",
        episode="test/resources/larger_instance/episode.json",
        result_path=str(tmp_path / "result.json"),
        seed=3,
        epsilon=1,
    )
    run_main(args)

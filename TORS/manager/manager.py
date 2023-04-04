from typing import Callable
from pyTORS import ScenarioFailedError, Scenario
from manager.simulator import Simulator
from planner.planner import Planner
import importlib
from time import time, perf_counter
from contextlib import contextmanager
import logging
from typing import Optional
from typing_extensions import Self
import functools
from manager.config import AgentConfig, EpisodeConfig

from typing import Optional
from pathlib import Path


def time_in_planner(func):
    @functools.wraps(func)
    def wrapper_time_in_planner(self: Self, *args, **kwargs):
        start = perf_counter()
        ret = func(self, *args, **kwargs)
        self.sol_runtime += start - perf_counter()
        return ret

    return wrapper_time_in_planner


class Manager:
    def __init__(self, episode_config: EpisodeConfig, agent_config: AgentConfig):
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        self.episode_config = episode_config
        self.agent_config = agent_config
        self.simulator = Simulator(episode_config)
        self.sol_runtime = 0
        self.planner = self.get_planner()
        self.print_episode_info()
        self.print_agent_info()

    def print_episode_info(self):
        self.logger.info("### Episode info ###")
        self.logger.info("Data folder: {}".format(self.episode_config.data_folder))
        self.logger.info("Scenario(s): {}".format(self.episode_config.scenario))
        self.logger.info("Number of runs: {}".format(self.episode_config.n_runs))
        self.logger.info(
            "Maximum number of trains: {}".format(self.episode_config.max_trains)
        )

    def print_agent_info(self):
        self.print("M> ### Agent info ###")
        planner_class = self.agent_config.agent_class
        self.print("M> Agent class: {}".format(planner_class))
        # if planner_class in self.agent_config:
        #     config = self.agent_config[planner_class]
        #     for key, val in config.items():
        #         self.print("M> \t{}: {}".format(key, val))

    @time_in_planner
    def initialize_planner(self):
        self.logger.debug("Initializing planner")
        engine, location = self.simulator.get_engine(), self.simulator.get_location()
        with timeout(self, 10):
            self.planner.initialize(engine, location)

    @time_in_planner
    def reset_planner(self):
        self.logger.debug("Resetting planner")
        with timeout(self, 10):
            self.planner.reset()

    @time_in_planner
    def get_planner_action(self, state):
        self.logger.debug("Getting state from planner")
        with timeout(self):
            return self.planner.get_action(state)

    @time_in_planner
    def report_planner_result(self, result):
        self.logger.debug("Reporting result back to planner")
        with timeout(self, 10):
            self.planner.report_result(result)

    def lack_of_action_not_valid(self, state):
        valid_actions = self.simulator.get_engine().get_valid_actions(state)
        if len(valid_actions) != 0:
            return True
        return False

    def apply_action(self, state, action):
        if action is None:
            if self.lack_of_action_not_valid(state):
                raise ScenarioFailedError(
                    "The planner returned no action, but valid actions are still available."
                )
            else:
                return False
        elif action is not None:
            self.simulator.apply_action(action)
            return True

    def run(
        self,
        n_trains=2,
        result_save_path: Optional[Path] = None,
    ):
        failure = False

        self.simulator.start()

        self.initialize_planner()

        self.simulator.generate_scenario(n_trains)

        planning_time_left = self.get_remaining_planning_time()
        if planning_time_left < 0 and planning_time_left != -1:
            return self.simulator.get_result(), True

        # Close running engine, generate new scenario
        self.simulator.reset()

        self.reset_planner()

        # Main simulation loop
        while True:
            state = self.simulator.get_state()
            if not self.simulator.is_active():  # If scenario not failed or ended
                break

            # Step simulation and handle possible/expected exceptions
            try:
                action = self.get_planner_action(state)
                should_continue = self.apply_action(state, action)

                if not should_continue:
                    break

            except TimeoutError:
                self.logger.info("Timeout reached.")
                failure = True
                break
            except ScenarioFailedError as e:
                self.logger.info(e)
                failure = True
                break

        if not failure and self.simulator.engine is not None:
            state_still_active = self.simulator.engine.is_state_active(
                self.simulator.state
            )
            if state_still_active:
                failure = True
                self.logger.debug("State is still active.")

        result = self.simulator.get_result()
        self.report_planner_result(result)

        if result_save_path:
            result.serialize_to_file(self.simulator.engine, result_save_path)

        return failure

    def print(self, m):
        if self.episode_config.verbose >= 1:
            print(m)

    def get_planner(self) -> Planner:
        planner_str = self.agent_config.agent_class
        planner_lst = planner_str.split(".")
        _module = importlib.import_module(".".join(planner_lst[:-1]))
        _class = getattr(_module, planner_lst[-1])
        # if planner_str in self.agent_config:
        # config = self.agent_config[planner_str]
        # else:
        config = AgentConfig()
        # self.agent_config["time_limit"] = self.episode_config.time_limit
        planner = _class(self.agent_config, config)
        return planner

    # Get the remaining time left for the planner (in seconds)
    def get_remaining_planning_time(self) -> float:
        time_limit = self.episode_config.time_limit
        if time_limit == -1:
            return -1
        return float(time_limit) - self.sol_runtime


def time_function(f: Callable):
    """Execute a function and return the amount of time it took."""
    start = time()
    f()
    return time() - start


# Code for time out #######################################################################
# From https://www.jujens.eu/posts/en/2018/Jun/02/python-timeout-function/
# From https://stackoverflow.com/questions/492519/timeout-on-a-function-call/494273#494273
# Note, only works on UNIX
try:
    import signal

    def raise_timeout(signum, frame):
        raise TimeoutError

    @contextmanager
    def timeout(manager, minimum=None):
        time = manager.get_remaining_planning_time()
        if time != -1 and not minimum is None and time < minimum:
            time = minimum
        if time != -1 and time <= 0:
            raise TimeoutError()
        if time != -1:
            # Register a function to raise a TimeoutError on the signal.
            signal.signal(signal.SIGALRM, raise_timeout)
            # Schedule the signal to be sent after ``time``.
            signal.alarm(int(time + 2))  # add some extra time
        timeout_error = False
        try:
            yield
        except TimeoutError:
            timeout_error = True
        finally:
            # Unregister the signal so it won't be triggered
            # if the timeout is not reached.
            if time != -1:
                signal.signal(signal.SIGALRM, signal.SIG_IGN)
            if timeout_error:
                raise TimeoutError()

except:  # If the package signal cannot be imported

    @contextmanager
    def timeout(manager, minimum=None):
        if manager.get_remaining_planning_time() != -1:
            raise NotImplementedError("Time out is only supported on UNIX systems")
        yield


# End code for time out ###################################################################

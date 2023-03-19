from planner.planner import Planner
from pyTORS import Action, SimpleAction, State, POSPlan, Scenario
from typing import Optional, Union


class SimulatedAnnealingPlan:
    _pos_plan: POSPlan

    def __init__(self, scenario: Scenario) -> None:
        self._pos_plan = self.search(scenario)
        raise NotImplementedError()

    @property
    def get_pos_plan(self):
        return self._pos_plan

    def get_action(self, state: State) -> Action:
        raise NotImplementedError()

    def search(self, scenario: Scenario, threshold=1e-5) -> POSPlan:
        # Perform simulated annealing
        raise NotImplementedError()


class SimulatedAnnealingPlanner(Planner):
    plan: SimulatedAnnealingPlan

    def __init__(self, config):
        super().__init__(config)
        self.reset()

    def get_action(self, state: State) -> Optional[Union[Action, SimpleAction]]:
        if not self.plan:
            self.plan = SimulatedAnnealingPlan(self._engine.get_scenario())
        return self.plan.get_action(state)

    def reset(self):
        super().reset(self)
        self.plan = None

    def close(self):
        pass

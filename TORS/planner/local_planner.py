from dataclasses import dataclass
import networkx as nx
from networkx.algorithms import bipartite
from typing import Optional, Union, Type
import random
import itertools
import math

from proto_gen.PartialOrderSchedule_pb2 import PartialOrderSchedule

from pyTORS import (
    State,
    Action,
    SimpleAction,
    Location,
    Incoming,
    Outgoing,
    ScenarioFailedError,
    Train,
    ShuntingUnit,
    POSPlan,
    POSAction
)

from manager.config import AgentConfig
from planner.planner import Planner


class LocalPlanner(Planner):
    def __init__(self, config: AgentConfig, local_config):
        super().__init__(config)
        self._plan = None

    def get_action(self, state: State) -> Optional[Union[Action, SimpleAction]]:
        if self._plan is None:
            self.plan = Plan(state, self.location, self.random)

        return None

    def reset(self):
        pass

    def close(self):
        pass


@dataclass(eq=True, frozen=True)
class _TrainInShuntUnit:
    train: Train
    shunt_id: int
    train_index: int
    in_or_out: Union[Type[Incoming], Type[Outgoing]]


def _create_outgoing_from_matching(
    matching: dict[_TrainInShuntUnit, _TrainInShuntUnit],
    outgoing_shunt_units: list[Outgoing],
) -> list[Outgoing]:
    outgoing_by_id = {outgoing.id: outgoing for outgoing in outgoing_shunt_units}
    matched_outgoing_shunt_units = {outgoing: {} for outgoing in outgoing_shunt_units}
    for in_match, out_match in matching.items():
        if in_match.train.id != -1:
            existing_shunt_unit = matched_outgoing_shunt_units[
                outgoing_by_id[out_match.shunt_id]
            ]
            existing_shunt_unit[out_match.train_index] = in_match.train

    constructed_matched_outgoing_shunt_units = []  # TODO: change name
    # create an `Outgoing` shunting unit from each of the matched_outgoing_shunting_units
    for outgoing, train_units in matched_outgoing_shunt_units.items():
        # create a ShuntingUnit from the trains in train_units by turning train_units into a list
        matched_shunting_unit = ShuntingUnit(
            outgoing.id, [train_units[i] for i in sorted(train_units.keys())]
        )

        constructed_matched_outgoing_shunt_units.append(
            Outgoing(
                outgoing.id,
                matched_shunting_unit,
                outgoing.parking_track,
                outgoing.side_track,
                outgoing.time,
                outgoing.instanding,
                outgoing.standing_index,
            )
        )

    return constructed_matched_outgoing_shunt_units


def _initial_matching_objective(
    matching: dict[_TrainInShuntUnit, _TrainInShuntUnit],
    incoming_shunt_units: list[Incoming],
    outgoing_shunt_units: list[Outgoing],
):
    """
    Calculate the objective value for a matching.

    This consists of the number of decouples and couples that are required and
    the number of train units that cannot depart on time.
    """
    n_decoupling_actions_required = 0
    n_coupling_actions_required = 0

    map_incoming_to_outgoing_units: dict[_TrainInShuntUnit, _TrainInShuntUnit] = {
        incoming: outgoing
        for incoming, outgoing in matching.items()
        if incoming.in_or_out == Incoming
    }

    # get the number of unique shunt ids that all train units in each incoming shunt unit are assigned to
    # this is the number of decoupling actions that will be required
    for shunt_id in [incoming.id for incoming in incoming_shunt_units]:
        outgoing_shunt_ids_for_this_shunt_id = map(
            lambda x: x[1].shunt_id,
            filter(
                lambda x: x[0].shunt_id == shunt_id,
                map_incoming_to_outgoing_units.items(),
            ),
        )
        n_decoupling_actions_required += (
            len(set(outgoing_shunt_ids_for_this_shunt_id)) - 1
        )

    # outgoing units usually have a train id of -1
    # TODO: outgoing units might have a train id specified
    map_outgoing_to_incoming_units = {
        outgoing: incoming
        for outgoing, incoming in matching.items()
        if outgoing.in_or_out == Outgoing
    }

    for shunt_id in [outgoing.id for outgoing in outgoing_shunt_units]:
        incoming_shunt_ids_for_this_shunt_id = map(
            lambda x: x[1].shunt_id,
            filter(
                lambda x: x[0].shunt_id == shunt_id,
                map_outgoing_to_incoming_units.items(),
            ),
        )
        n_coupling_actions_required += (
            len(set(incoming_shunt_ids_for_this_shunt_id)) - 1
        )

    # Create map of incoming shunting units by id
    incoming_by_id = {incoming.id: incoming for incoming in incoming_shunt_units}
    outgoing_by_id = {outgoing.id: outgoing for outgoing in outgoing_shunt_units}

    num_train_units_not_departing_on_time = 0

    # Get the number of train units that cannot depart on time
    for incoming, outgoing in map_incoming_to_outgoing_units.items():
        if (
            incoming_by_id[incoming.shunt_id].time
            > outgoing_by_id[outgoing.shunt_id].time
        ):
            num_train_units_not_departing_on_time += 1

    penalty = (
        n_coupling_actions_required
        + n_decoupling_actions_required
        + num_train_units_not_departing_on_time
    )

    return penalty


def _randomly_swap_equal_train_units(
    matching: dict[_TrainInShuntUnit, _TrainInShuntUnit],
    random: random.Random,
    chance: float,
) -> dict[_TrainInShuntUnit, _TrainInShuntUnit]:
    """
    Randomly swap train units in a matching if they have the same train type and compatible ids.

    Both outgoing IDs must be -1 for the swap to occur.
    """
    match_in_to_out: dict[_TrainInShuntUnit, _TrainInShuntUnit] = {
        incoming: outgoing
        for incoming, outgoing in matching.items()
        if incoming.in_or_out == Incoming
    }

    # randomly swap incoming trains who have the same train type
    # and the same outgoing shunt id
    for incoming, incoming2 in itertools.combinations(match_in_to_out, 2):
        outgoing = match_in_to_out[incoming]
        outgoing2 = match_in_to_out[incoming2]
        if (
            incoming.train.get_type() == incoming2.train.get_type()
            # Only swap if neither of the outgoing IDs are set (meaning they are -1)
            and (outgoing.train.get_id() == -1 and outgoing2.train.get_id() == -1)
            and random.random() < chance  # swap with a certain chance
        ):
            # swap the incoming trains' matching outgoing trains
            matching[incoming], matching[incoming2] = (
                matching[incoming2],
                matching[incoming],
            )
            # also swap the outgoing trains' matching incoming trains
            matching[outgoing], matching[outgoing2] = (
                matching[outgoing2],
                matching[outgoing],
            )

    return matching


def _initial_simulated_annealing(
    matching: dict[_TrainInShuntUnit, _TrainInShuntUnit],
    incoming_shunt_units: list[Incoming],
    outgoing_shunt_units: list[Outgoing],
    random: random.Random,
    max_iterations: int,
    initial_temperature: float,
    cooling_rate: float,
    swap_chance: float,
) -> dict[_TrainInShuntUnit, _TrainInShuntUnit]:
    """
    Perform simulated annealing on a matching.

    This is done by randomly swapping train units in the matching and accepting
    the swap if it improves the objective value.
    """
    current_matching = matching
    current_objective = _initial_matching_objective(
        current_matching, incoming_shunt_units, outgoing_shunt_units
    )

    temperature = initial_temperature

    for _ in range(max_iterations):
        # randomly swap train units in the matching
        new_matching = _randomly_swap_equal_train_units(
            current_matching, random, swap_chance
        )
        new_objective = _initial_matching_objective(
            new_matching, incoming_shunt_units, outgoing_shunt_units
        )

        # if the new matching is better, accept it
        if new_objective < current_objective:
            current_matching = new_matching
            current_objective = new_objective
        # otherwise, accept it with a certain probability
        else:
            if random.random() < 1 - math.exp(
                (current_objective - new_objective) / temperature
            ):
                current_matching = new_matching
                current_objective = new_objective

        temperature *= 1 - cooling_rate

    return current_matching


def _initial_matching(
    incoming_shunt_units: list[Incoming],
    outgoing_shunt_units: list[Outgoing],
    random: random.Random,
) -> nx.DiGraph:
    incoming_train_units: list[_TrainInShuntUnit] = [
        _TrainInShuntUnit(train, incoming.id, i, Incoming)
        for incoming in incoming_shunt_units
        for i, train in enumerate(incoming.shunting_unit.trains)
    ]
    outgoing_train_units: list[_TrainInShuntUnit] = [
        _TrainInShuntUnit(train, outgoing.id, i, Outgoing)
        for outgoing in outgoing_shunt_units
        for i, train in enumerate(outgoing.shunting_unit.trains)
    ]

    matching_graph = nx.DiGraph()

    matching_graph.add_nodes_from(incoming_train_units, bipartite=0)
    matching_graph.add_nodes_from(outgoing_train_units, bipartite=0)

    for incoming_train in incoming_train_units:
        for outgoing_train in outgoing_train_units:
            if incoming_train.train.type == outgoing_train.train.type:
                matching_graph.add_edge(incoming_train, outgoing_train)

    matching = bipartite.hopcroft_karp_matching(
        matching_graph, top_nodes=incoming_train_units
    )

    return matching


class Plan:
    def __init__(self, state: State, location: Location, random: random.Random) -> None:
        self.location = location
        self.incoming = state.incoming_trains
        self.outgoing = state.outgoing_trains
        self.random = random
        self.solution = self.construct_initial_solution()

    def construct_initial_solution(self):
        # Matching incoming and outgoing train units
        try:
            matching = _initial_matching(self.incoming, self.outgoing, self.random)
        except nx.exception.AmbiguousSolution:
            raise ScenarioFailedError("No initial matching found")

        # Simulated annealing to reduce the number of composition changes
        matching = _initial_simulated_annealing(
            matching,
            self.incoming,
            self.outgoing,
            random,
            1000,
            100,
            0.01,
            0.5,
        )

        concrete_outgoing = _create_outgoing_from_matching(matching, self.outgoing)

        # 
        # parking = PartialOrderSchedule()

        plan = PartialOrderSchedule()
        print(plan)

        

from manager.config import AgentConfig

from planner.planner import Planner
from pyTORS import (
    BeginMoveAction,
    EndMoveAction,
    MoveAction,
    ArriveAction,
    ExitAction,
    ServiceAction,
    WaitAction,
    SetbackAction,
    SplitAction,
    CombineAction,
    TrackPartType,
    State,
    Location,
    ShuntingUnit,
    Train,
    Incoming,
    Outgoing,
    Engine,
    Action,
    Track,
    Task,
)
import random
from typing import List, Tuple, Type, Optional
import logging
from contextlib import redirect_stdout
from io import StringIO

class GreedyPlanner(Planner):
    def __init__(self, config: AgentConfig, greedy_config: dict):
        super(GreedyPlanner, self).__init__(config)
        self.epsilon = greedy_config["epsilon"]
        self.existing_plan = greedy_config.get("existing_plan")
        self.reset()

    def get_action(self, state: State) -> Optional[Action]:
        if self.plan is None:
            self.logger.debug("Plan is not yet initialized, initializing...")
            self.plan = Plan(state, self.get_location(), self.random, self.epsilon, self.existing_plan)
        
        with redirect_stdout(StringIO()) as temp_io:
            state.print_state_info()
        self.logger.debug("\n" + temp_io.getvalue())
        self.logger.debug("Getting actions")
        actions = self.get_valid_actions(state)
        self.logger.debug(f"{actions=}")
        
        if len(actions) == 0:
            return None
        return self.plan.get_action(state, actions)

    def reset(self):
        Planner.reset(self)
        self.plan = None

    def close(self):
        pass


class Plan:
    def __init__(self, state: State, location: Location, random: random.Random, epsilon, existing_plan):
        self.random = random
        self.epsilon = epsilon
        self.location = location
        self.existing_plan = existing_plan
        self.existing_index = 0
        self.existing_failed = False
        self.incoming = state.incoming_trains
        self.outgoing = state.outgoing_trains
        self.trains = {}
        available_trains = []
        for inc in self.incoming:
            for tr in inc.shunting_unit.trains:
                self.trains[tr] = TrainState(tr, inc, location)
                available_trains.append(tr)
        for out in self.outgoing:
            for tr in out.shunting_unit.trains:
                train = (
                    self.find_match(available_trains, tr)
                    if tr not in self.trains
                    else tr
                )
                available_trains.remove(train)
                self.trains[train].update_outgoing(out, tr)
        for train, train_state in self.trains.items():
            train_state.set_same_shunting_unit()
        for train in self.trains:
            self.location.calc_shortest_paths(train.type)
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def find_match(self, trains: List[Train], train: Train):
        for t in trains:
            if t.type == train.type:
                return t
        return None
    
    def _match_action(self, action_a: dict, action_b: Action) -> bool:
        self.logger.debug("Checking if actions match, action_b: %s", action_b)
        # Step 1: wait actions should already be filtered out
        if isinstance(action_b, WaitAction):
            self.logger.exception("Wait actions should already be filtered out")
        # Step 2: check if the train ids match
        ids_a = [int(train_id) for train_id in action_a.get("trainUnitIds")]
        ids_b = [x.get_id() for x in action_b.shunting_unit.trains]
        self.logger.debug("ids_a: %s, ids_b: %s", ids_a, ids_b)
        if ids_a != ids_b:
            return False
        
        # Step 3: check if the actions match
        if (task := action_a.get("task")) is not None:
            predefined = task["type"]["predefined"]
            self.logger.debug("predefined: %s", predefined)
            self.logger.debug("action_b: %s", action_b)
            if isinstance(action_b, ExitAction) and predefined == "Exit":
                return True
            elif isinstance(action_b, CombineAction) and predefined == "Combine":
                return True
            elif isinstance(action_b, SplitAction) and predefined == "Split":
                return True
            elif isinstance(action_b, ServiceAction) and predefined == "Service":
                return True
            elif isinstance(action_b, SetbackAction) and predefined == "Walking":
                return True
            elif isinstance(action_b, ArriveAction) and predefined == "Arrive":
                return True
            elif isinstance(action_b, BeginMoveAction) and predefined == "BeginMove":
                return True
            elif isinstance(action_b, EndMoveAction) and predefined == "EndMove":
                return True
        if isinstance(action_b, MoveAction) and (move := action_a.get("movement")) is not None:
            """
            example of a movement action:
            {
                "trainUnitIds": [
                    "2422"
                ],
                "minimumDuration": "90",
                "movement": {
                    "fromSide": "A",
                    "path": [
                        "3",
                        "7",
                        "1"
                    ],
                    "toSide": "B"
                }
            },

            In order to compare, we need to compare the path array with the tracks array
            of the MoveAction object.
            """
            tracks_a = move["path"]
            # get array of track ids from action_b
            tracks_b = [x.id for x in action_b.tracks]
            self.logger.debug("tracks_a: %s, tracks_b: %s", tracks_a, tracks_b)

            if tracks_a == tracks_b:
                return True

        return False
    
    def _apply_existing_plan(self, actions: List[Action]) -> Optional[Action]:
        action_to_find = self.existing_plan[self.existing_index]
        self.logger.debug("Action to find: %s", action_to_find)

        waitactions = list(filter(lambda x: isinstance(x, WaitAction), actions))
        non_waitactions = list(filter(lambda x: not isinstance(x, WaitAction), actions))
        matching_actions = list(filter(lambda x: self._match_action(action_to_find, x), non_waitactions))

        self.logger.debug("Found %s matching actions: %s", len(matching_actions), matching_actions)
        self.logger.debug("Wait actions: %s", waitactions)

        if len(matching_actions) == 0:
            if len(waitactions) > 0:
                self.logger.info("No matching actions found, waiting instead.")
                return waitactions[0]
            else:
                self.logger.warning("Failed to execute next step in plan, "
                                    "reverting to normal greedy policy.")
                self.existing_failed = True
        else:
            if len(matching_actions) > 1:
                self.logger.info("More than one matching action: %s, "
                        "choosing the first one.", matching_actions)
                
            self.existing_index += 1

            self.logger.info("Executing next step in plan: %s", matching_actions[0])

            return matching_actions[0]
        return None

    def get_action(self, state: State, actions: List[Action]):
        for su in state.shunting_units:
            prev = state.get_position(su)
            pos = state.get_previous(su)
            for tr in su.trains:
                serv = state.get_tasks_for_train(tr)
                self.trains[tr].update_current_state(prev, pos, serv, su)
        
        # Apply existing plan, if specified
        if self.existing_plan is not None and self.existing_index < len(self.existing_plan) and not self.existing_failed:
            next_action_from_existing_plan = self._apply_existing_plan(actions)
            if next_action_from_existing_plan is not None:
                index_of_chosen_action = actions.index(next_action_from_existing_plan)
                self.logger.debug(f"{index_of_chosen_action=}")
                return next_action_from_existing_plan

        # Otherwise continue with greedy plan
        action_priority = sum(
            [
                train_state.get_action_priority(state, actions)
                for train_state in self.trains.values()
            ],
            [],
        )
        action_priority = sorted(action_priority, key=lambda ap: ap[0], reverse=True)
        self.logger.debug(action_priority)

        # If there is an arrival or exit action, take it
        for ap in action_priority:
            if isinstance(ap[1], (ArriveAction, ExitAction)):
                self.logger.info("Action is a %s action, taking it.", ap[1].__class__.__name__)
                chosen_action = ap[1]
                index_of_chosen_action = actions.index(chosen_action)
                self.logger
                return chosen_action

        epsilon_choice = self.random.random()

        if action_priority[0][0] == 0 or epsilon_choice < self.epsilon:
            chosen_action = self.random.choice(actions)
            return chosen_action
        index_of_chosen_action = actions.index(action_priority[0][1])
        self.logger.debug(f"{index_of_chosen_action=}")
        return action_priority[0][1]


class TrainState:
    def __init__(self, train: Train, incoming: Incoming, location: Location):
        self.train = train
        self.location = location
        self.incoming = incoming
        self.begin_track = incoming.parking_track
        self.begin_side_track = incoming.side_track
        self.in_su = incoming.shunting_unit
        self.arrival_time = incoming.time
        self.outgoing = None
        self.service_track = None
        self.end_track = None
        self.end_side_track = None
        self.end_su = None
        self.departure_time = None
        self.same_shunting_unit = True
        self.logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

    def update_outgoing(self, outgoing: Outgoing, train_match: Train):
        self.outgoing = outgoing
        self.train_match = train_match
        self.end_track = outgoing.parking_track
        self.end_side_track = outgoing.side_track
        self.out_su = outgoing.shunting_unit
        self.departure_time = outgoing.time

    def update_current_state(
        self, previous: Track, position: Track, tasks: List[Task], su: ShuntingUnit
    ):
        self.in_su = su
        self.begin_track = position
        self.begin_side_track = previous
        if len(tasks) == 0:
            self.service_track = None
        else:
            task = tasks[0]
            for f in self.location.facilities:
                if f.executes_task(task):
                    self.service_track = f.tracks[0]
                    break
        self.set_same_shunting_unit()

    def set_same_shunting_unit(self):
        self.same_shunting_unit = self.in_su.matches_shunting_unit(self.out_su)

    def get_action_priority(self, state: State, actions: List[Action]) -> List[Tuple[int, Action]]:
        su = self.in_su
        priority = [(0, actions[0])]
        if state.time == self.arrival_time:
            TrainState.add_action_if_found(actions, priority, 100, ArriveAction, su)
        if self.same_shunting_unit:
            if state.time >= self.arrival_time and su in state.shunting_units:
                prev = state.get_previous(su)
                pos = state.get_position(su)
                moving = state.is_moving(su)
                if not self.service_track is None and pos == self.service_track:
                    if moving:
                        TrainState.add_action_if_found(
                            actions, priority, 5, EndMoveAction, su
                        )
                    else:
                        TrainState.add_action_if_found(
                            actions, priority, 20, ServiceAction, su
                        )
                if (
                    pos == self.end_track
                    and self.end_side_track in pos.get_next_track_parts(prev)
                ):
                    self.logger.debug(
                        "On end track facing the correct direction.\n"
                        "Unit should leave at %s, and the time is currently %s.\n"
                        "The unit is moving: %s"
                        % (self.departure_time, state.time, moving),
                    )
                    if moving:
                        TrainState.add_action_if_found(
                            actions, priority, 5, EndMoveAction, su
                        )
                    else:
                        TrainState.add_action_if_found(
                            actions, priority, 100, ExitAction, su
                        )
                else:
                    if not moving:
                        TrainState.add_action_if_found(
                            actions, priority, 5, BeginMoveAction, su
                        )
                    else:
                        if not self.service_track is None:
                            side_track1 = self.service_track.neighbors[0]
                            side_track2 = self.service_track.neighbors[1]
                            path1 = self.location.get_shortest_path(
                                self.train.type,
                                prev,
                                pos,
                                side_track1,
                                self.service_track,
                            )
                            path2 = self.location.get_shortest_path(
                                self.train.type,
                                prev,
                                pos,
                                side_track2,
                                self.service_track,
                            )
                            if path1.length > path2.length:
                                path = path2
                            else:
                                path = path1
                        else:
                            side_track = self.end_track.get_next_track_parts(
                                self.end_side_track
                            )[0]
                            path = self.location.get_shortest_path(
                                self.train.type, prev, pos, side_track, self.end_track
                            )
                        nextTrack = None
                        nextTrackPrev = pos
                        for track in path.route[1:]:
                            if track.type == TrackPartType.RAILROAD:
                                nextTrack = track
                                break
                            nextTrackPrev = track
                        if not nextTrack is None:
                            if nextTrack == nextTrackPrev:
                                TrainState.add_action_if_found(
                                    actions, priority, 20, SetbackAction, su
                                )
                            else:
                                TrainState.add_action_if_found(
                                    actions,
                                    priority,
                                    20,
                                    MoveAction,
                                    su,
                                    track=nextTrack,
                                    prev=nextTrackPrev,
                                )

                TrainState.add_action_if_found(actions, priority, 1, WaitAction, su)
        else:
            TrainState.add_action_if_found(actions, priority, 10, SplitAction, su)
            TrainState.add_action_if_found(
                actions, priority, 10, CombineAction, self.out_su
            )
        return priority

    @staticmethod
    def add_action_if_found(
        actions: List[Action],
        priority_list: List[Tuple[int, Action]],
        priority: int,
        action_type: Type[Action],
        su: ShuntingUnit,
        track: Track = None,
        prev: Track = None,
    ):
        action = TrainState.find_action(actions, action_type, su, track, prev)
        if action:
            priority_list.append((priority, action))

    @staticmethod
    def find_action(
        actions: List[Action],
        action_type: Type[Action],
        su: ShuntingUnit,
        track: Track = None,
        prev: Track = None,
    ):
        return next(
            (
                a
                for a in actions
                if isinstance(a, action_type)
                and (
                    a.shunting_unit == su
                    or (
                        action_type == CombineAction
                        and a.shunting_unit.matches_shunting_unit(su)
                    )
                )
                and (track is None or a.destination_track == track)
                and (prev is None or a.previous_track == prev)
            ),
            None,
        )

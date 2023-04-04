import json
import os
import importlib
from dataclasses import dataclass
from serde import deserialize, field, Strict
from pathlib import Path
from typing import Union


def _valid_class(value):
    """Check if value is a valid class before deserializing"""
    try:
        planner_lst = value.split(".")
        _module = importlib.import_module(".".join(planner_lst[:-1]))
        getattr(_module, planner_lst[-1])
    except:
        raise Exception("Cannot find file or class: {}".format(value))
    return value


def _valid_data_folder(value: str) -> Path:
    """Check if data folder `value` exists"""
    data_folder = Path(value)
    if not data_folder.exists():
        raise FileNotFoundError("Path {} does not exist".format(data_folder))
    if not data_folder.is_dir():
        raise ValueError("The 'data folder' configuration value should be a folder.")
    return data_folder


@deserialize(type_check=Strict)
@dataclass
class ScenarioGeneratorConfig:
    generator_class: str = field(deserializer=_valid_class, rename="class")
    n_workers: int = 0
    n_disturbances: int = 0
    match_outgoing_trains: bool = False


@deserialize(type_check=Strict)
@dataclass
class EpisodeConfig:
    scenario: Path
    generator: ScenarioGeneratorConfig
    data_folder: Path = field(rename="data folder", deserializer=_valid_data_folder)
    verbose: Union[bool, int] = True
    n_runs: int = 1
    max_trains: int = 1
    time_limit: int = -1


@deserialize(type_check=Strict)
@dataclass
class AgentConfig:
    seed: int = 42
    verbose: Union[bool, int] = True
    agent_class: str = field(
        rename="class",
        deserializer=_valid_class,
        default="planner.random_planner.RandomPlanner",
    )
    time_limit: int = -1

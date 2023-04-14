import random

from hypothesis import given, strategies as st

from pyTORS import Incoming, Outgoing, ShuntingUnit, Train, Task, Track

from planner.local_planner import LocalPlanner, Plan, _initial_matching


@given(
    st.lists(
        st.builds(
            Incoming,
            st.integers(0, 100),
            st.builds(ShuntingUnit, st.integers(0, 100), st.lists(st.builds(Train))),
            st.builds(Track),
            st.builds(Track),
            st.integers(0, 100),
            st.booleans(),
            st.integers(0, 100),
            st.dictionaries(st.builds(Train), st.builds(Task), min_size=1, max_size=10),
        )
    ),
    st.lists(st.builds(Outgoing)),
)
def test_initial_matching(incoming, outgoing):
    _initial_matching(incoming, outgoing, random.random())

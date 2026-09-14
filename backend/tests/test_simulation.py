"""Full autoplay games without HTTP."""

from game_engine.engine import GameEngine
from simulation.policy import run_autoplay
import random


def test_autoplay_finishes_a_game():
    engine = GameEngine(seed=3)
    summary = run_autoplay(engine, 6, random.Random(100))
    assert summary["over"] is True
    assert engine.is_over()
    assert summary["scores"][1]["total"] >= 0
    assert summary["scores"][2]["total"] >= 0

"""Transparent, deterministic traffic and signal simulation rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DIRECTIONS = ("North", "East", "South", "West")


@dataclass(frozen=True)
class Road:
    direction: str
    vehicle_count: int
    queue_length: int
    waiting_seconds: int

    @property
    def density(self) -> float:
        return min(1.0, self.queue_length / 24)


def severity(queue_length: int) -> str:
    if queue_length >= 20:
        return "Critical"
    if queue_length >= 13:
        return "High"
    if queue_length >= 6:
        return "Medium"
    return "Low"


def green_duration(road: Road, minimum: int, maximum: int) -> int:
    """Allocate a bounded green interval using queue, wait, and congestion."""
    score = (
        road.queue_length * 1.7
        + min(road.waiting_seconds, 120) * 0.12
        + min(road.vehicle_count, 50) * 0.25
        + road.density * 3
    )
    duration = round(minimum + score)
    return max(minimum, min(maximum, duration))


def choose_next_direction(
    roads: list[Road],
    current: str,
    last_served: dict[str, int],
    now: int,
) -> str:
    """Choose the most urgent waiting approach, with a starvation-prevention bonus."""
    candidates = [road for road in roads if road.direction != current]
    if not candidates:
        return current

    def priority(road: Road) -> tuple[float, int]:
        age = now - last_served.get(road.direction, 0)
        return (road.queue_length * 2 + road.waiting_seconds * 0.1 + age * 0.04, -DIRECTIONS.index(road.direction))

    return max(candidates, key=priority).direction


def build_intersection(name: str, queues: dict[str, int], waits: dict[str, int], counts: dict[str, int],
                       phase_direction: str, phase: str, remaining: int, emergency: dict[str, Any] | None = None) -> dict[str, Any]:
    roads = []
    for direction in DIRECTIONS:
        queue = queues[direction]
        roads.append({
            "direction": direction,
            "vehicle_count": counts[direction],
            "queue_length": queue,
            "waiting_seconds": waits[direction],
            "density": round(min(1.0, queue / 24), 2),
            "congestion": severity(queue),
            "signal": "green" if direction == phase_direction and phase == "green" else (
                "yellow" if direction == phase_direction and phase == "yellow" else "red"
            ),
        })
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "roads": roads,
        "phase_direction": phase_direction,
        "phase": phase,
        "remaining_seconds": remaining,
        "emergency": emergency,
    }


def optimize_fixed_vs_adaptive(queues: list[int]) -> dict[str, int]:
    """Illustrative comparison derived from this simulation's queue samples."""
    if not queues:
        return {"fixed_average_wait_seconds": 0, "adaptive_average_wait_seconds": 0, "improvement_percent": 0}
    average = sum(queues) / len(queues)
    fixed = round(18 + average * 2.4)
    adaptive = round(12 + average * 1.35)
    return {
        "fixed_average_wait_seconds": fixed,
        "adaptive_average_wait_seconds": adaptive,
        "improvement_percent": round(max(0, (fixed - adaptive) / max(fixed, 1) * 100)),
    }

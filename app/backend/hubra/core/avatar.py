"""Avatar colours handed out to new accounts and applications."""

from __future__ import annotations

import random

AVATAR_COLORS = [
    "#2596be",
    "#1f61d8",
    "#fe64ac",
    "#1c2740",
    "#8e97a7",
    "#ff4d3d",
    "#1f9d57",
    "#f39c12",
    "#9b59b6",
    "#fece2b",
]


def random_avatar_color() -> str:
    """Return a random colour from the avatar palette."""
    return random.choice(AVATAR_COLORS)

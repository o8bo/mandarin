"""Shared hit testing; no toolkit or native API imports."""
import math


def sector_at(x, y, count, size=420):
    dx, dy = x - size / 2, y - size / 2
    if count <= 0 or not 69 <= math.hypot(dx, dy) <= size / 2 - 13:
        return -1
    angle = (math.atan2(dy, dx) + math.pi / 2 + math.pi / count) % math.tau
    return int(angle / (math.tau / count)) % count

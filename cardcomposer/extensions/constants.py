from operator import add, mul, sub, truediv, getitem
from os import path

from .methods import Methods


class Constants:
    CALCULATIONS_LOOKUP = {
        "+": add,
        "*": mul,
        "-": sub,
        "/": truediv,
        "round": round,
        "sum": sum,
        "min": min,
        "max": max,
        "getitem": getitem,
        "getattr": getattr,
        "str.format": str.format,
        "path.join": path.join,
        "if": Methods.calc_if,
        "contains": (lambda container, val: val in container)
    }

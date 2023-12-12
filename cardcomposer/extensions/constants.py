from operator import add, mul, sub, truediv, getitem
from os import path


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
        "if": (lambda is_true, true_val, false_val=None: true_val if is_true else false_val),
        "contains": (lambda container, val: val in container)
    }

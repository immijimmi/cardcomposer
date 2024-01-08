from operator import add, mul, sub, truediv, getitem, eq, gt
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
        "dict_get": (lambda target_dict, key, default=None: target_dict.get(key, default)),
        "getattr": getattr,
        "str.format": str.format,
        "path.join": path.join,
        "if": Methods.calc_if,
        "contains": (lambda container, val: val in container),
        "not": (lambda val: not val),
        "eq": eq,
        "gt": gt
    }

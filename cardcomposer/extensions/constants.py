from operator import add, mul, sub, truediv, getitem, eq, gt, ge, lt, le, ne
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
        "dict.get": (lambda target_dict, key, default=None: target_dict.get(key, default)),
        "getattr": getattr,
        "str.format": str.format,
        "path.join": path.join,
        "if": Methods.calc_if,
        "contains": (lambda container, val: val in container),
        "not": (lambda val: not val),
        "eq": eq,
        "ne": ne,
        "gt": gt,
        "ge": ge,
        "lt": lt,
        "le": le,
        "int": int,
        "float": float,
        "str": str,
        "and": (lambda a, b: a and b),
        "or": (lambda a, b: a or b),
        "all": all,
        "any": any,
        "is": (lambda a, b: a is b)
    }

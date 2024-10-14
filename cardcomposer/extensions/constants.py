from operator import add, mul, sub, floordiv, truediv, pow, mod, getitem, eq, gt, ge, lt, le, ne
from os import path
from json import dumps, loads

from .methods import Methods


class Constants:
    ARITHMETIC_ORDER = (("**",), ("*", "/", "//", "%"), ("+", "-"))

    CALCULATIONS_LOOKUP = {
        "+": add,
        "*": mul,
        "-": sub,
        "/": truediv,
        "//": floordiv,
        "**": pow,
        "%": mod,
        "round": round,
        "sum": sum,
        "min": min,
        "max": max,
        "getitem": getitem,
        "getattr": getattr,
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
        "str.format": str.format,
        "dict": dict,
        "dict.get": dict.get,
        "and": Methods.calc_ands,
        "or": Methods.calc_ors,
        "all": all,
        "any": any,
        "is": (lambda a, b: a is b),
        "is_not": (lambda a, b: a is not b),
        "json.dumps": dumps,
        "json.loads": loads
    }

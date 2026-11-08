from operator import (
    add, mul, sub, floordiv, truediv, pow, mod, getitem, eq, gt, ge, lt, le, ne, contains, not_, is_, is_not
)
from os import path
from json import dumps, loads

from .methods import Methods


class Constants:
    ARITHMETIC_ORDER = (
        {"[]"},
        {"**"}, {"*", "/", "//", "%"}, {"+", "-"},
        {
            "==", "!=", ">", ">=", "<", "<=", "is", "is not",
            "contains", "in", "not in",
            "and", "or"
        }
    )

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
        "[]": getitem,  # Alias. To slice using `getitem`, a `slice` object must be passed in
        "getattr": getattr,
        ".": getattr,  # Alias. Note that `getattr` does not respect name mangling as `.` does
        "path.join": path.join,
        "if": Methods.calc_if,
        "contains": contains,
        "in": (lambda a, b: a in b),  # Inverse operand order to `contains`
        "not_in": (lambda a, b: a not in b),
        "not in": (lambda a, b: a not in b),  # Alias
        "not": not_,
        "==": eq,
        "eq": eq,  # Alias
        "!=": ne,
        "ne": ne,  # Alias
        ">": gt,
        "gt": gt,  # Alias
        ">=": ge,
        "ge": ge,  # Alias
        "<": lt,
        "lt": lt,  # Alias
        "<=": le,
        "le": le,  # Alias
        "int": int,
        "float": float,
        "str": str,
        "str.title": str.title,
        "str.format": str.format,
        "dict": dict,
        "dict.get": dict.get,
        "and": Methods.calc_ands,
        "or": Methods.calc_ors,
        "all": all,
        "any": any,
        "is": is_,
        "is_not": is_not,
        "is not": is_not,  # Alias
        "json.dumps": dumps,
        "json.loads": loads,
        "reversed": reversed,
        "inverted_dict": Methods.calc_inverted_dict,
        "slice": slice
    }

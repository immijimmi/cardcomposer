from operator import add, mul, sub, truediv, getitem


class Constants:
    DEFERRED_TYPE_KEY = "deferred"

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
        "getattr": getattr
    }

from operator import add, mul, sub, truediv, itemgetter


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
        "getitem": itemgetter,
        "getattr": getattr
    }

from enum import Enum


class StepKey(str, Enum):
    """
    Keys that have a common usage in all steps
    """

    TYPE = "type"
    PRIORITY = "priority"


class DeferredValue(str, Enum):
    CACHED = "cached"
    CALCULATION = "calc"
    CARD_DIMENSION = "card_dim"
    SEEDED_RANDOM = "seeded"

    # PIL-specific values
    IMAGE = "image"

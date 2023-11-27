from enum import Enum


class StepKey(str, Enum):
    """
    Keys that have a common usage in all steps
    """

    TYPE = "type"
    PRIORITY = "priority"


class DeferredValue(str, Enum):
    SELF = "self"
    CALCULATION = "calc"
    SEEDED_RANDOM = "seeded"

    # Shortcut values
    CACHED = "cached"
    CARD_DIMENSION = "card_dim"
    WORKING_IMAGE = "working_image"

    # PIL-specific values
    IMAGE = "image"
    FONT = "font"
    TEXT_LENGTH = "text_length"
    TEXT_BBOX = "text_bbox"

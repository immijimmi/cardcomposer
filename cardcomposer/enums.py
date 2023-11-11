from enum import Enum


class StepKey(str, Enum):
    """
    Keys that are common to all steps
    """

    TYPE = "type"
    PRIORITY = "priority"

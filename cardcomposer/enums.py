from enum import Enum


class StepKey(str, Enum):
    """
    Keys that have a common usage in all steps
    """

    TYPE = "type"
    PRIORITY = "priority"


class DeferredValue(str, Enum):
    SAVED = "saved"
    CALCULATION = "calculation"

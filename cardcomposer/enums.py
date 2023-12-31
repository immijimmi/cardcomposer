from enum import Enum


class ConfigKey(str, Enum):
    LOG_ALL = "log_all"


class GenericKey(str, Enum):
    """
    Keys that have a common usage in all step data and deferred values
    """

    DO_LOG = "do_log"


class DeferredKey(str, Enum):
    """
    Keys that have a common usage in all deferred values
    """

    DEFERRED = "deferred"


class StepKey(str, Enum):
    """
    Keys that have a common usage in all steps
    """

    TYPE = "type"
    PRIORITY = "priority"
    DO_STEP = "do_step"

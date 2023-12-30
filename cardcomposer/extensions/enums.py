from enum import Enum


class DeferredValue(str, Enum):
    SELF = "self"
    CALCULATION = "calc"
    SEEDED_RANDOM = "seeded"

    # Meta
    MAPPED = "mapped"

    # Shortcut values
    CONFIG = "config",
    CACHED = "cached",
    CARD_DIMENSION = "card_dim"
    WORKING_IMAGE = "working_image"

    # PIL-specific values
    IMAGE_FROM_FILE = "image_from_file"
    BLANK_IMAGE = "blank_image"
    IMAGE_FROM_TEMPLATE = "image_from_template"
    FONT = "font"
    TEXT_LENGTH = "text_length"
    TEXT_BBOX = "text_bbox"

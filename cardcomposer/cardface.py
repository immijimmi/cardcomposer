from objectextensions import Extendable
from PIL import Image, ImageFont, ImageDraw

from typing import Optional, Callable, Any, Sequence, Iterable
import logging
import random

from .methods import Methods
from .enums import StepKey, DeferredValue
from .constants import Constants


class CardFace(Extendable):
    def __init__(
            self, label: Optional[str] = None,
            templates: Sequence["CardFace"] = (), size: Optional[tuple[int, int]] = None,
            steps: Sequence[dict[str]] = (), is_template: bool = False,
            logger=None
    ):
        super().__init__()

        self.step_handlers: dict[str, Callable[[Image.Image, dict[str], "CardFace"], Image.Image]] = {}
        """
        The cache can be used to store pieces of re-usable data, typically referencing various aspects of the card face
        (e.g. the coords of a specific point location on the card). They can be added by specific steps, and may be
        read during any subsequent steps once added
        """
        self.cache: dict[str] = {}
        # Stores a reference to the image being generated during `.generate()`
        self.working_image: Optional[Image.Image] = None

        self.label = label
        self.templates = tuple(templates)
        self.steps = tuple(steps)
        self.is_template = is_template

        self._logger = logger or logging.root

        self.size: Optional[tuple[int, int]] = None
        if size:
            self.size = tuple(size)
        else:
            for template in self.templates:  # Go through templates in order, to search for a size value to use
                if template.size:
                    self.size = tuple(template.size)
                    break

        self.cumulative_templates = (
            *(sub_template for template in templates for sub_template in template.cumulative_templates),
            *self.templates
        )
        self.cumulative_steps = (
            *(step for template in templates for step in template.cumulative_steps),
            *self.steps
        )

        # Validating templates, to prevent a template being passed in at multiple points and duplicating its steps
        cumulative_templates_labels = set()
        for template in self.cumulative_templates:
            if template.label in cumulative_templates_labels:
                raise ValueError(
                    f"two templates with the same label ({template.label})"
                    f" passed to {type(self).__name__} object."
                    f" {type(self).__name__} object label: {self.label}"
                )
            cumulative_templates_labels.add(template.label)

    @property
    def logger(self):
        return self._logger

    def generate(self) -> Image.Image:
        if not self.size:
            raise ValueError(f"unable to generate image from {type(self).__name__} (no size set)")

        self.cache.clear()
        self.logger.debug(f"{type(self).__name__} cache cleared.")

        self.logger.info(f"Generating new {type(self).__name__} image (label='{self.label}')...")
        self.working_image = Image.new("RGBA", self.size)

        # Sorting steps
        steps_sort_keys: list[dict[str, Any]] = []
        for step_index, step in enumerate(self.cumulative_steps):
            # Optional params
            """
            Step priority is used as a primary sorting key for steps, with
            the initial ordering of the steps used as the secondary key.
            Any comparable set of values (numbers or not) are valid.
            If provided priorities are not comparable, priority will not be used at all
            """
            step_priority = step.get(StepKey.PRIORITY, None)

            steps_sort_keys.append({"step": step, "index": step_index, "priority": step_priority})

        try:
            steps_sort_keys.sort(key=lambda step_keys: (step_keys["priority"], step_keys["index"]))
            self.logger.info(f"Sorted {type(self).__name__} steps.")
        except TypeError:  # Unable to sort by priority
            self.logger.debug(f"Unable to sort {type(self).__name__} steps by priority.")
            steps_sort_keys.sort(key=lambda step_keys: step_keys["index"])

        ordered_steps = tuple(step_keys["step"] for step_keys in steps_sort_keys)
        # Executing steps
        for step in ordered_steps:
            # Required params
            step_type: str = step[StepKey.TYPE]
            self.logger.debug(f"Processing {type(self).__name__} step: {step_type}")

            step_handler = self.step_handlers[step_type]
            self.working_image = step_handler(self.working_image, step, self)

        result = self.working_image
        self.working_image = None

        self.logger.info(f"{type(self).__name__} image successfully generated.")
        return result

    def resolve_deferred_value(self, value):
        """
        This method should be invoked liberally by step handlers, to decode any values provided in their step data.

        Responsible for processing any deferred values into a usable form. If the provided data is not a deferred value,
        it will simply be returned as-is.

        Recursively converts sub-values within any dict, list or tuple
        """

        # To ensure the provided value is not edited in place within this method, a copy is made
        # Necessary to ensure due to the recursive nature of this method
        working_value = Methods.try_copy(value)

        # Resolve deferred value types in a loop until the remaining value is not a deferred value
        while deferred_value := self._deferred_value_type(working_value):
            if deferred_value == DeferredValue.SELF:
                working_value = self

            elif deferred_value == DeferredValue.CALCULATION:
                working_value = self._resolve_calculation(working_value)

            elif deferred_value == DeferredValue.SEEDED_RANDOM:
                # Required params
                seed = self.resolve_deferred_value(working_value["seed"])

                # Optional params
                n: int = self.resolve_deferred_value(working_value.get("n", 0))

                random.seed(seed)
                for prior_roll in range(n):
                    random.random()

                working_value = random.random()

            elif deferred_value == DeferredValue.CACHED:
                # Required params
                cache_key = self.resolve_deferred_value(working_value["key"])

                try:
                    working_value = self.cache[cache_key]
                except KeyError:
                    if "default" not in working_value:
                        raise KeyError(f"no value found in cache and no default provided for key: {cache_key}")

                    working_value = working_value["default"]

            elif deferred_value == DeferredValue.CARD_DIMENSION:
                # Required params
                dimension: str = self.resolve_deferred_value(working_value["dimension"])

                if dimension == "width":
                    working_value = self.size[0]
                elif dimension == "height":
                    working_value = self.size[1]
                else:
                    raise ValueError(f"invalid dimension name received: {dimension}")

            elif deferred_value == DeferredValue.WORKING_IMAGE:
                working_value = self.working_image

            elif deferred_value == DeferredValue.IMAGE_FROM_FILE:
                # Required params
                src: str = self.resolve_deferred_value(working_value["src"])

                working_value = Image.open(src)

            elif deferred_value == DeferredValue.BLANK_IMAGE:
                # Required params
                size: tuple[float, float] = self.resolve_deferred_value(working_value["size"])

                working_value = Image.new("RGBA", Methods.ensure_ints(size))

            elif deferred_value == DeferredValue.FONT:
                # Required params
                src: str = self.resolve_deferred_value(working_value["src"])

                # Optional params
                font_type: str = self.resolve_deferred_value(working_value.get("type", "truetype"))
                size: Optional[int] = self.resolve_deferred_value(working_value.get("size", None))
                index: Optional[int] = self.resolve_deferred_value(working_value.get("index", None))
                encoding: Optional[str] = self.resolve_deferred_value(working_value.get("encoding", None))

                font_optional_kwargs = {
                    key: value for key, value in {
                        "size": size,
                        "index": index,
                        "encoding": encoding
                    }.items() if value is not None
                }

                if font_type == "truetype":
                    working_value = ImageFont.truetype(font=src, **font_optional_kwargs)
                elif font_type == "bitmap":
                    """
                    kwargs are purposefully provided here despite not being expected,
                    since for a bitmap font they should be empty anyway
                    """
                    working_value = ImageFont.load(src, **font_optional_kwargs)
                else:
                    raise ValueError(f"invalid font type: {font_type}")

            elif deferred_value == DeferredValue.TEXT_LENGTH:
                # Required params
                text: str = self.resolve_deferred_value(working_value["text"])
                font: ImageFont = self.resolve_deferred_value(working_value["font"])

                # Optional params
                text_layer: Optional[Image.Image] = self.resolve_deferred_value(working_value.get("text_layer", None))
                direction: Optional[str] = self.resolve_deferred_value(working_value.get("direction", None))
                features: Optional[Sequence[str]] = self.resolve_deferred_value(working_value.get("features", None))
                language: Optional[str] = self.resolve_deferred_value(working_value.get("language", None))
                embedded_color: Optional[bool] = self.resolve_deferred_value(working_value.get("embedded_color", None))

                textlength_optional_kwargs = {
                    key: value for key, value in {
                        "direction": direction,
                        "features": features,
                        "language": language,
                        "embedded_color": embedded_color
                    }.items() if value is not None
                }

                text_layer = Image.new("RGBA", self.working_image.size) if (text_layer is None) else text_layer
                draw = ImageDraw.Draw(text_layer)
                working_value = draw.textlength(text=text, font=font, **textlength_optional_kwargs)

            elif deferred_value == DeferredValue.TEXT_BBOX:
                # Required params
                position: tuple[float, float] = self.resolve_deferred_value(working_value["position"])
                text: str = self.resolve_deferred_value(working_value["text"])
                font: ImageFont = self.resolve_deferred_value(working_value["font"])

                # Optional params
                text_layer: Optional[Image.Image] = self.resolve_deferred_value(working_value.get("text_layer", None))
                anchor: Optional[str] = self.resolve_deferred_value(working_value.get("anchor", None))
                spacing: Optional[float] = self.resolve_deferred_value(working_value.get("spacing", None))
                align: Optional[str] = self.resolve_deferred_value(working_value.get("align", None))
                direction: Optional[str] = self.resolve_deferred_value(working_value.get("direction", None))
                features: Optional[Sequence[str]] = self.resolve_deferred_value(working_value.get("features", None))
                language: Optional[str] = self.resolve_deferred_value(working_value.get("language", None))
                stroke_width: Optional[int] = self.resolve_deferred_value(working_value.get("stroke_width", None))
                embedded_color: Optional[bool] = self.resolve_deferred_value(working_value.get("language", None))

                textbbox_optional_kwargs = {
                    key: value for key, value in {
                        "anchor": anchor,
                        "spacing": spacing,
                        "align": align,
                        "direction": direction,
                        "features": features,
                        "language": language,
                        "stroke_width": stroke_width,
                        "embedded_color": embedded_color
                    }.items() if value is not None
                }

                text_layer = Image.new("RGBA", self.working_image.size) if (text_layer is None) else text_layer
                draw = ImageDraw.Draw(text_layer)
                # Floats are accepted here for xy
                working_value = draw.textbbox(xy=position, text=text, font=font, **textbbox_optional_kwargs)

            else:
                raise NotImplementedError(f"no case implemented to handle deferred value type: {deferred_value}")

        # Recursive conversion
        if type(working_value) in (tuple, list):
            old_working_value = working_value
            working_value = []
            for item in old_working_value:
                working_value.append(self.resolve_deferred_value(item))
            if type(old_working_value) is tuple:
                working_value = tuple(working_value)
        elif type(working_value) is dict:
            for key, item in working_value.items():
                working_value[key] = self.resolve_deferred_value(item)

        return working_value

    def _resolve_calculation(self, calculation: dict[str]):
        """
        Invokes a single calculation from a limited list of options, passing in the provided arguments.
        The provided arguments may themselves be any valid deferred value
        (further calculations, references to cached values etc.), and are not limited to representing
        numbers - any types which are valid parameters for the calculation will equally suffice
        """

        # Required params
        operands: Iterable = self.resolve_deferred_value(calculation["args"])
        operation_key: str = self.resolve_deferred_value(calculation["op"])

        # Optional params
        do_log: bool = self.resolve_deferred_value(calculation.get("do_log", False))

        operands = tuple(operands)
        operation = Constants.CALCULATIONS_LOOKUP[operation_key]
        result = operation(*operands)

        if do_log:
            self.logger.info(f"Performing calculation step: {operation}{operands} -> {result}")

        return result

    @staticmethod
    def _deferred_value_type(value) -> Optional[str]:
        """
        If the provided value represents any of a selection of special types which must be further processed
        to yield usable values, returns the specific type represented.
        The return value of this method will be truthy only if a deferred value is detected
        """

        if type(value) is not dict:
            return
        if Constants.DEFERRED_TYPE_KEY not in value:
            return
        if (value_type := value[Constants.DEFERRED_TYPE_KEY]) not in DeferredValue:
            raise TypeError(f"unrecognised type when evaluating deferred value: {value_type}")
        return value_type

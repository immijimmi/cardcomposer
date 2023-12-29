from objectextensions import Extendable
from PIL import Image

from typing import Optional, Callable, Any, Sequence
import logging

from .methods import Methods
from .enums import StepKey
from .constants import Constants


class CardFace(Extendable):
    def __init__(
            self, label: Optional[str] = None,
            templates_labels: Sequence[str] = (), steps: Sequence[dict[str]] = (),
            size: Optional[tuple[int, int]] = None,
            is_template: bool = False, templates_pool: dict[str, "CardFace"] = {},
            logger=None
    ):
        super().__init__()

        self.step_handlers: dict[str, Callable[[Image.Image, dict[str], "CardFace"], Image.Image]] = {}
        self.deferred_value_resolvers: dict[str, Callable[[dict[str], "CardFace"], Any]] = {}

        """
        The cache can be used to store pieces of re-usable data, typically referencing various aspects of the card face
        (e.g. the coords of a specific point location on the card). They can be added by specific steps, and read during
        any subsequent steps once added
        """
        self.cache: dict[str] = {}
        # Stores a reference to the image being generated during `.generate()`
        self.working_image: Optional[Image.Image] = None

        self.label = label
        self.templates_labels = tuple(templates_labels)
        self.steps = tuple(steps)
        self.is_template = is_template
        self.templates_pool = templates_pool
        self.logger = logger or logging.root

        self._size: Optional[tuple[int, int]] = tuple(size) if size else None

        # Add to templates pool, if this object is a template
        if self.is_template:
            if self.label in self.templates_pool:
                raise ValueError(
                    f"unable to add {type(self).__name__} to templates pool"
                    f" (a template with the same label already exists): {self.label}"
                )
            self.templates_pool[self.label] = self

    @property
    def templates(self) -> tuple["CardFace"]:
        return tuple(self.templates_pool[template_label] for template_label in self.templates_labels)

    @property
    def cumulative_templates(self) -> tuple["CardFace"]:
        result = []

        for template in self.templates:
            for sub_template in template.cumulative_templates:
                result.append(sub_template)
            result.append(template)

        # Validating templates, to prevent a template being passed in at multiple points and duplicating its steps
        cumulative_templates_labels = set()
        for template in result:
            if template.label in cumulative_templates_labels:
                raise ValueError(
                    f"two templates with the same label ({template.label})"
                    f" passed to {type(self).__name__} object."
                    f" {type(self).__name__} object label: {self.label}"
                )
            cumulative_templates_labels.add(template.label)

        return tuple(result)

    @property
    def cumulative_steps(self) -> tuple[dict[str]]:
        return tuple((
            *(step for template in self.templates for step in template.cumulative_steps),
            *self.steps
        ))

    @property
    def size(self) -> Optional[tuple[int, int]]:
        if self._size is None:
            # Go through templates from latest to earliest, to search for a size value to use
            for template in reversed(self.templates):
                if template.size is not None:
                    return template.size
        return self._size

    def generate(self) -> Image.Image:
        if not self.size:
            raise ValueError(f"unable to generate image from {type(self).__name__} (no size set)")

        self.logger.debug(f"Generating new {type(self).__name__} image (label='{self.label}')...")
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
            self.logger.debug(f"Sorted {type(self).__name__} steps.")
        except TypeError:  # Unable to sort by priority
            self.logger.debug(f"Unable to sort {type(self).__name__} steps by priority.")
            steps_sort_keys.sort(key=lambda step_keys: step_keys["index"])

        ordered_steps = tuple(step_keys["step"] for step_keys in steps_sort_keys)
        # Executing steps
        for step in ordered_steps:
            # Required params
            step_type: str = step[StepKey.TYPE]

            # Optional params
            do_log: bool = step.get("do_log", False)

            if do_log:
                self.logger.info(f"Processing {type(self).__name__} step: {step_type}")

            step_handler = self.step_handlers[step_type]
            self.working_image = step_handler(self.working_image, step, self)

        result = self.working_image
        self.working_image = None

        self.cache.clear()
        self.logger.debug(f"{type(self).__name__} cache cleared.")

        self.logger.info(f"{type(self).__name__} image (label='{self.label}') successfully generated.")
        return result

    def resolve_deferred_value(self, value):
        """
        This method should be invoked liberally by step handlers and deferred value resolvers,
        to decode any nested values provided in the data they are given.

        Responsible for processing any deferred values into a usable form. If the provided data is not a deferred value,
        it will simply be returned as-is.

        Recursively converts sub-values within any dict, list or tuple that a deferred value may be resolved into
        """

        # To ensure the provided value is not edited in place within this method, a copy is made
        # Necessary to ensure due to the recursive nature of this method
        working_value = Methods.try_copy(value)

        # Determining whether to log the resolved value
        deferred_value_type = self.deferred_value_type(working_value)
        if deferred_value_type:
            # Optional params
            do_log: bool = self.resolve_deferred_value(value.get("do_log", False))

            log_deferred_value_type = deferred_value_type
        else:
            do_log = False

        # Resolve deferred value types in a loop until the remaining value is not a deferred value
        while deferred_value_type := self.deferred_value_type(working_value):
            if deferred_value_type in self.deferred_value_resolvers:
                working_value = self.deferred_value_resolvers[deferred_value_type](working_value, self)
            else:
                raise NotImplementedError(f"no resolver found to handle deferred value type: {deferred_value_type}")

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

        # Logging
        if do_log:
            self.logger.info(f"Resolved deferred value (type='{log_deferred_value_type}'): {working_value}")

        return working_value

    @staticmethod
    def deferred_value_type(value) -> Optional[str]:
        """
        If the provided value represents any of a selection of special types which must be further processed
        to yield usable values, returns the specific type represented.
        The return value of this method will be truthy only if a deferred value is detected
        """

        if type(value) is not dict:
            return
        if Constants.DEFERRED_TYPE_KEY not in value:
            return
        return value[Constants.DEFERRED_TYPE_KEY]

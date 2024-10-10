from objectextensions import Extendable
from PIL import Image

from typing import Optional, Callable, Any, Union, Iterable
from datetime import datetime
import logging

from .methods import Methods
from .constants import Constants
from .enums import ConfigKey, GenericKey, DeferredKey, StepKey
from .types import Deferred, Step, CardFaceLabel


class CardFace(Extendable):
    STEP_HANDLERS: dict[str, Callable[[Image.Image, dict[str], "CardFace"], Image.Image]] = {}
    DEFERRED_VALUE_RESOLVERS: dict[str, Callable[[Deferred, "CardFace"], Any]] = {}

    def __init__(
            self,
            label: Union[Deferred, CardFaceLabel] = None,
            templates_labels: Union[Deferred, Iterable[CardFaceLabel]] = (),
            steps: Iterable[Step] = (),
            size: Union[Deferred, Optional[tuple[int, int]]] = None,
            is_template: Union[Deferred, bool] = True,
            templates_pool: Union[Deferred, dict[CardFaceLabel, "CardFace"]] = {},
            global_cache: dict = {},
            do_skip_generation: Union[Deferred, bool] = False,
            config: Union[Deferred, Optional[dict[str]]] = None,
            logger=None
    ):
        super().__init__()

        """
        The cache can be used to store pieces of re-usable data, typically referencing various aspects of the card face
        (e.g. the coords of a specific point location on the card). They can be added by specific steps, and read during
        any subsequent steps once added
        """
        self.cache: dict = {}
        # Tracks the image being generated during `.generate()`
        self.working_image: Optional[Image.Image] = None
        # Tracks the parent CardFace responsible for invoking `.generate()` on this object, if any
        self.parent: Optional["CardFace"] = None

        self.label: CardFaceLabel = self.resolve_deferred_value(label)
        self.templates_labels: tuple[CardFaceLabel, ...] = tuple(self.resolve_deferred_value(templates_labels))
        # Deferred values in steps should not be resolved until generation
        self.steps: tuple[Step, ...] = tuple(steps)
        self.is_template: bool = self.resolve_deferred_value(is_template)
        # Deferred values in the global cache should not be resolved until generation
        self.global_cache: dict = global_cache if global_cache is not None else {}
        self.do_skip_generation: bool = self.resolve_deferred_value(do_skip_generation)
        self.logger = logger or logging.root

        self.templates_pool: dict[CardFaceLabel, "CardFace"]
        if self.deferred_value_type(templates_pool):
            self.templates_pool = self.resolve_deferred_value(templates_pool)
        else:
            # Done this way to prevent the object identity of the templates pool from changing if it isn't deferred
            self.templates_pool = templates_pool

        self.config: dict[str]
        if config is not None:
            self.config = self.resolve_deferred_value(config)
        else:
            self.config = {}

        self._size: Optional[tuple[int, int]] = tuple(size) if (size := self.resolve_deferred_value(size)) else None

        # Add to templates pool, if this object is a template
        if self.is_template:
            if self.label in self.templates_pool:
                raise ValueError(
                    f"unable to add {type(self).__name__} to templates pool"
                    f" (a template with the same label already exists): {self.label}"
                )
            self.templates_pool[self.label] = self

    @property
    def templates(self) -> tuple["CardFace", ...]:
        return tuple(self.templates_pool[template_label] for template_label in self.templates_labels)

    @property
    def cumulative_templates(self) -> tuple["CardFace", ...]:
        result = []
        cumulative_templates_labels = set()
        for template in self.templates:
            for sub_template in template.cumulative_templates:
                if sub_template.label not in cumulative_templates_labels:  # Not a duplicate template
                    result.append(sub_template)
                    cumulative_templates_labels.add(sub_template.label)

            if template.label not in cumulative_templates_labels:  # Not a duplicate template
                result.append(template)
                cumulative_templates_labels.add(template.label)

        return tuple(result)

    @property
    def cumulative_steps(self) -> tuple[Step, ...]:
        return tuple((
            *(step for template in self.cumulative_templates for step in template.steps),
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

    def generate(self, parent: Optional["CardFace"] = None) -> Optional[Image.Image]:
        if self.do_skip_generation:
            self.logger.debug(f"Generation for {type(self).__name__} (label='{self.label}') skipped.")
            return None

        if not self.size:
            self.logger.warning(
                f"Unable to generate image from {type(self).__name__} (label='{self.label}'); No size set."
            )
            return None

        self.cache.clear()
        self.cache.update(self.global_cache)
        self.logger.debug(f"{type(self).__name__} cache reset (pre-generation).")

        gen_start = datetime.now()

        self.logger.debug(f"Generating new {type(self).__name__} image (label='{self.label}')...")
        self.parent = parent
        self.working_image = Image.new("RGBA", self.size)

        # Sorting steps
        steps_sort_keys: list[dict[str]] = []
        for step_index, step in enumerate(self.cumulative_steps):
            # Optional params
            """
            Step priority is used as a primary sorting key for steps, with
            the initial ordering of the steps used as the secondary key.
            Any comparable set of values (numbers or not) are valid.
            If provided priorities are not comparable, priority will not be used at all
            """
            step_priority = self.resolve_deferred_value(step.get(StepKey.PRIORITY, None))

            steps_sort_keys.append({"step": step, "index": step_index, "priority": step_priority})

        try:
            steps_sort_keys.sort(key=lambda step_keys: (step_keys["priority"], step_keys["index"]))
            self.logger.debug(f"Sorted {type(self).__name__} steps.")
        except TypeError:  # Unable to sort by priority
            self.logger.warning(f"Unable to sort {type(self).__name__} steps by priority.")
            steps_sort_keys.sort(key=lambda step_keys: step_keys["index"])

        ordered_steps = tuple(step_sort_keys["step"] for step_sort_keys in steps_sort_keys)
        # Executing steps
        steps_completed = 0
        do_log_all: bool = self.config.get(ConfigKey.DO_LOG_ALL, False)
        for step in ordered_steps:
            # Required params
            step_type: str = self.resolve_deferred_value(step[StepKey.TYPE])

            # Optional params
            do_step: bool = self.resolve_deferred_value(step.get(StepKey.DO_STEP, True))
            do_log_step: bool = self.resolve_deferred_value(step.get(GenericKey.DO_LOG, False))

            if not do_step:
                continue
            if do_log_step or do_log_all:
                step_start = datetime.now()

                step_priority = self.resolve_deferred_value(step.get(StepKey.PRIORITY, None))
                self.logger.info(f"Processing {type(self).__name__} step: {step_type} (priority={step_priority})")

            step_handler = self.STEP_HANDLERS[step_type]
            try:
                self.working_image = step_handler(self.working_image, step, self)
                steps_completed += 1

                if do_log_step or do_log_all:
                    step_end = datetime.now()
                    self.logger.info(f"Step completed in {round((step_end - step_start).total_seconds(), 2)}s.")
            # This indicates that any further processing should cease
            except StopIteration:
                break
            # This indicates that any further processing should cease, and nothing be returned
            except NotImplementedError:
                steps_completed = None
                break

        generated_image = self.working_image
        self.working_image = None
        self.parent = None

        gen_end = datetime.now()

        self.cache.clear()
        self.logger.debug(f"{type(self).__name__} cache cleared (post-generation).")

        if steps_completed is None:
            self.logger.debug(f"Generation for {type(self).__name__} (label='{self.label}') cancelled.")
            return None  # No image is returned if no processing was completed

        self.logger.info(
            f"{type(self).__name__} image (label='{self.label}') successfully generated"
            f"{'' if parent is None else ' by parent'}"
            f" in {round((gen_end - gen_start).total_seconds(), 2)}s."
        )
        return generated_image

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
        value = Methods.try_copy(value)

        # Determining whether to log the resolved value
        deferred_value_type = self.deferred_value_type(value)
        if deferred_value_type:
            # Optional params
            do_log: bool = self.resolve_deferred_value(value.get(GenericKey.DO_LOG, False))

            log_deferred_value_type = deferred_value_type
        else:
            do_log = False

        # Resolve deferred value types in a loop until the remaining value is not a deferred value
        loops = 0
        while deferred_value_type := self.deferred_value_type(value):
            loops += 1
            if loops > Constants.DEFERRED_VALUE_RESOLVER_MAX_LOOPS:
                raise RecursionError(f"unable to resolve deferred value (max. loops exceeded): {value}")

            deferred_value_resolver = self.DEFERRED_VALUE_RESOLVERS[deferred_value_type]
            value = deferred_value_resolver(value, self)

        # Recursive conversion
        if type(value) in (tuple, list):
            old_value = value
            value = []
            for item in old_value:
                value.append(self.resolve_deferred_value(item))
            if type(old_value) is tuple:
                value = tuple(value)
        elif type(value) is dict:
            for entry_key, entry_value in value.items():
                value[entry_key] = self.resolve_deferred_value(entry_value)

        # Logging
        if do_log:
            self.logger.info(f"Resolved deferred value (type='{log_deferred_value_type}'): {value}")

        return value

    @staticmethod
    def deferred_value_type(value) -> Optional[str]:
        """
        If the provided value represents any of a selection of special types which must be further processed
        to yield usable values, returns the specific type represented.
        The return value of this method will be truthy only if a deferred value is detected
        """

        if type(value) is not dict:
            return
        if DeferredKey.DEFERRED not in value:
            return
        return value[DeferredKey.DEFERRED]

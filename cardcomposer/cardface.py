from PIL import Image, ImageOps, ImageDraw

from typing import Optional, Callable, Union, Any
from os import path
from pathlib import Path

from .methods import Methods
from .enums import StepKey, DeferredValue
from .constants import Constants


class CardFace:
    def __init__(
            self, label: Optional[str] = None,
            template: Optional["CardFace"] = None, size: Optional[tuple[int, int]] = None,
            steps: tuple[dict[str], ...] = ()
    ):
        self.step_handlers: dict[str, Callable[[Image.Image, dict[str], "CardFace"], Image.Image]] = {
            "paste_image": self._step_paste_image,
            "write_to_cache": self._step_write_to_cache,
            "save": self._step_save
        }
        """
        The cache can be used to store pieces of re-usable data, typically referencing various aspects of the card face
        (e.g. the coords of a specific point location on the card). They can be added by specific steps, and may be
        read during any subsequent steps once added
        """
        self.cache: dict[str] = {}

        self.label = label
        self.template = template

        self.size: tuple[int, int]
        self.steps: tuple[dict[str], ...]
        if template:
            if size:
                self.size = size
            else:
                self.size = template.size

            self.steps = (*template.steps, *steps)
        else:
            if not size:
                raise ValueError(
                    f"no template and no size provided for initialisation of {CardFace.__name__} object."
                    " At least one must be provided"
                )

            self.size = (*size,)
            self.steps = (*steps,)

    def generate(self) -> Image.Image:
        self.cache.clear()

        image = Image.new("RGBA", self.size)

        # Sorting steps
        steps_sort_keys: list[dict[str, Any]] = []
        for step_index, step in enumerate(self.steps):
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
        except TypeError:  # Unable to sort by priority
            steps_sort_keys.sort(key=lambda step_keys: step_keys["index"])

        ordered_steps = tuple(step_keys["step"] for step_keys in steps_sort_keys)
        # Executing steps
        for step in ordered_steps:
            # Required params
            step_type: str = step[StepKey.TYPE]

            step_handler = self.step_handlers[step_type]
            image = step_handler(image, step, self)

        return image

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

        # Resolve deferred values in a loop until the remaining value is not a deferred value
        while deferred_value := self._deferred_value_type(working_value):
            if deferred_value == DeferredValue.CACHED:
                cache_key = self.resolve_deferred_value(working_value["key"])
                working_value = self.cache[cache_key]
            elif deferred_value == DeferredValue.CALCULATION:
                working_value = self._resolve_calculation(working_value)
            elif deferred_value == DeferredValue.CARD_DIMENSION:
                dimension = self.resolve_deferred_value(working_value["dimension"])
                if dimension == "width":
                    working_value = self.size[0]
                elif dimension == "height":
                    working_value = self.size[1]
                else:
                    raise ValueError(f"invalid dimension name received: {dimension}")
            else:
                raise NotImplementedError(f"no case implemented to handle deferred value type: {deferred_value}")

        # Recursive conversion
        if type(working_value) in (list, tuple):
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
        Invokes a single calculation from a limited list of options, passing in the provided operands.
        The provided operands may themselves be any valid deferred value
        (further calculations, references to cached values etc.), and are not limited to representing
        numbers - any types which are valid parameters for the calculation will equally suffice
        """

        # Required params
        operands: tuple = self.resolve_deferred_value(calculation["operands"])
        operation_key: str = self.resolve_deferred_value(calculation["operation"])

        operation = Constants.CALCULATIONS_LOOKUP[operation_key]
        return operation(*operands)

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

    @staticmethod
    def _step_write_to_cache(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Required params
        key = card_face.resolve_deferred_value(step["key"])
        value = step["value"]  # Value to be stored should remain deferred until needed

        # Will not be used, is simply executed to ensure that a valid value has been provided
        card_face.resolve_deferred_value(value)

        card_face.cache[key] = value
        return image

    @staticmethod
    def _step_paste_image(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Required params
        src: str = card_face.resolve_deferred_value(step["src"])
        position: tuple[int, int] = Methods.round_all(
            card_face.resolve_deferred_value(step["position"])
        )

        # Optional params
        crop: Optional[tuple[int, int, int, int]] = Methods.round_all(
            card_face.resolve_deferred_value(step.get("crop", None))
        )
        scale: Optional[tuple[Union[float, bool], Union[float, bool]]] = (
            card_face.resolve_deferred_value(step.get("scale", None))
        )
        resize_to: Optional[tuple[Union[int, bool], Union[int, bool]]] = (
            card_face.resolve_deferred_value(step.get("resize_to", None))
        )

        compatibility_layer = Image.new("RGBA", image.size)
        embed_image = Image.open(src)

        if crop:
            embed_image = embed_image.crop(crop)
        if scale:
            if (type(scale[0]) is bool) and (type(scale[1]) is bool):
                pass  # No numeric value to scale image with has been provided
            else:
                if scale[0] is False:
                    scaled_width = embed_image.size[0]
                elif scale[0] is True:
                    scaled_width = embed_image.size[0] * scale[1]
                else:
                    scaled_width = embed_image.size[0] * scale[0]

                if scale[1] is False:
                    scaled_height = embed_image.size[1]
                elif scale[1] is True:
                    scaled_height = embed_image.size[1] * scale[0]
                else:
                    scaled_height = embed_image.size[1] * scale[1]

                new_embed_image_size = Methods.round_all((scaled_width, scaled_height))
                # Resampling.LANCZOS is the highest quality but lowest performance (most time-consuming) option
                embed_image = embed_image.resize(new_embed_image_size, resample=Image.Resampling.LANCZOS)
        if resize_to:
            if (type(resize_to[0]) is bool) and (type(resize_to[1]) is bool):
                pass  # No numeric value to scale image with has been provided
            else:
                if resize_to[0] is False:
                    resized_width = embed_image.size[0]
                elif resize_to[0] is True:
                    resized_width = embed_image.size[0] * (resize_to[1]/embed_image.size[1])
                else:
                    resized_width = resize_to[0]

                if resize_to[1] is False:
                    resized_height = embed_image.size[1]
                elif resize_to[1] is True:
                    resized_height = embed_image.size[1] * (resize_to[0]/embed_image.size[0])
                else:
                    resized_height = resize_to[1]

                new_embed_image_size = Methods.round_all((resized_width, resized_height))
                # Resampling.LANCZOS is the highest quality but lowest performance (most time-consuming) option
                embed_image = embed_image.resize(new_embed_image_size, resample=Image.Resampling.LANCZOS)

        paste_box = (
            position[0],
            position[1],
            position[0] + embed_image.size[0],
            position[1] + embed_image.size[1]
        )
        compatibility_layer.paste(embed_image, paste_box)

        image = Image.alpha_composite(image, compatibility_layer)
        return image

    @staticmethod
    def _step_save(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Optional params
        file_path: str = card_face.resolve_deferred_value(step.get("path", "Cards"))
        filename: str = card_face.resolve_deferred_value(step.get("filename", card_face.label or "card"))
        extension: str = card_face.resolve_deferred_value(step.get("extension", ".tif"))

        full_path = path.join(file_path, filename + extension)

        Path(file_path).mkdir(parents=True, exist_ok=True)
        image.save(full_path)

        return image

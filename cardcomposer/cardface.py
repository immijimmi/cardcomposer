from PIL import Image, ImageFont, ImageDraw

from typing import Optional, Callable, Union, Any, Sequence, Iterable
from os import path
from pathlib import Path
from logging import info, debug
import random

from .methods import Methods
from .enums import StepKey, DeferredValue
from .constants import Constants


class CardFace:
    def __init__(
            self, label: Optional[str] = None,
            templates: Sequence["CardFace"] = (), size: Optional[tuple[int, int]] = None,
            steps: Sequence[dict[str]] = (), is_template: bool = False
    ):
        self.step_handlers: dict[str, Callable[[Image.Image, dict[str], "CardFace"], Image.Image]] = {
            "paste_image": self._step_paste_image,
            "write_to_cache": self._step_write_to_cache,
            "save": self._step_save,
            "write_text": self._step_write_text
        }
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

    def generate(self) -> Image.Image:
        if not self.size:
            raise ValueError(f"unable to generate image from {type(self).__name__} (no size set)")

        self.cache.clear()
        debug(f"{type(self).__name__} cache cleared.")

        info(f"Generating new {type(self).__name__} image (label='{self.label}')...")
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
            info(f"Sorted {type(self).__name__} steps.")
        except TypeError:  # Unable to sort by priority
            debug(f"Unable to sort {type(self).__name__} steps by priority.")
            steps_sort_keys.sort(key=lambda step_keys: step_keys["index"])

        ordered_steps = tuple(step_keys["step"] for step_keys in steps_sort_keys)
        # Executing steps
        for step in ordered_steps:
            # Required params
            step_type: str = step[StepKey.TYPE]
            debug(f"Processing {type(self).__name__} step: {step_type}")

            step_handler = self.step_handlers[step_type]
            self.working_image = step_handler(self.working_image, step, self)

        result = self.working_image
        self.working_image = None

        info(f"{type(self).__name__} image successfully generated.")
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
            info(f"Performing calculation step: {operation}{operands} -> {result}")

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

    @staticmethod
    def _step_write_to_cache(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Optional params
        entries: dict[str] = step["entries"]  # Values to be stored should remain deferred until needed
        mode: str = card_face.resolve_deferred_value(step.get("mode", "add"))
        is_lazy: bool = card_face.resolve_deferred_value(step.get("is_lazy", True))
        do_log: bool = card_face.resolve_deferred_value(step.get("do_log", False))

        for key, value in entries.items():
            if not is_lazy:  # Resolve value now rather than waiting until it is needed
                value = card_face.resolve_deferred_value(value)

            if mode == "add":
                if key in card_face.cache:
                    raise ValueError(f"key already exists in {type(card_face).__name__} cache: {key}")
            elif mode == "update":
                if key not in card_face.cache:
                    raise KeyError(f"key not found in {type(card_face).__name__} cache: {key}")
            elif mode == "add_or_update":
                pass
            else:
                raise ValueError(f"unrecognised write mode: {mode}")

            if do_log:
                info(f"Writing to cache (mode={mode}, is_lazy={is_lazy}): {{{key}: {value}}}")

            card_face.cache[key] = value

        return image

    @staticmethod
    def _step_paste_image(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Required params
        embed_image: Image.Image = card_face.resolve_deferred_value(step["image"])
        position: tuple[float, float] = card_face.resolve_deferred_value(step["position"])

        embed_image = Methods.manipulate_image(
            embed_image,
            **Methods.unpack_manipulate_image_kwargs(step, card_face)
        )

        paste_box = (
            position[0],
            position[1],
            position[0] + embed_image.size[0],
            position[1] + embed_image.size[1]
        )

        compatibility_layer = Image.new("RGBA", image.size)
        compatibility_layer.paste(embed_image, Methods.ensure_ints(paste_box))

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

    @staticmethod
    def _step_write_text(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Required params
        position: tuple[float, float] = card_face.resolve_deferred_value(step["position"])
        text: str = card_face.resolve_deferred_value(step["text"])
        fill = Methods.coalesce_list_to_tuple(
            card_face.resolve_deferred_value(step["fill"])
        )
        font: ImageFont = card_face.resolve_deferred_value(step["font"])

        # Optional params
        text_layer: Optional[Image.Image] = card_face.resolve_deferred_value(step.get("text_layer", None))
        layer_position: Union[tuple[float, float], True] = card_face.resolve_deferred_value(
            step.get("layer_position", (0, 0))
        )
        anchor: Optional[str] = card_face.resolve_deferred_value(step.get("anchor", None))
        spacing: Optional[float] = card_face.resolve_deferred_value(step.get("spacing", None))
        align: Optional[str] = card_face.resolve_deferred_value(step.get("align", None))
        direction: Optional[str] = card_face.resolve_deferred_value(step.get("direction", None))
        features: Optional[Sequence[str]] = card_face.resolve_deferred_value(step.get("features", None))
        language: Optional[str] = card_face.resolve_deferred_value(step.get("language", None))
        stroke_width: Optional[int] = card_face.resolve_deferred_value(step.get("stroke_width", None))
        stroke_fill = card_face.resolve_deferred_value(step.get("stroke_fill", None))
        embedded_color: Optional[bool] = card_face.resolve_deferred_value(step.get("language", None))

        draw_text_optional_kwargs = {
            key: value for key, value in {
                "anchor": anchor,
                "spacing": spacing,
                "align": align,
                "direction": direction,
                "features": features,
                "language": language,
                "stroke_width": stroke_width,
                "stroke_fill": stroke_fill,
                "embedded_color": embedded_color
            }.items() if value is not None
        }

        text_layer = Image.new("RGBA", image.size) if (text_layer is None) else text_layer
        draw = ImageDraw.Draw(text_layer)
        # Floats are accepted here for xy
        draw.text(xy=position, text=text, fill=fill, font=font, **draw_text_optional_kwargs)

        text_layer = Methods.manipulate_image(
            text_layer,
            **Methods.unpack_manipulate_image_kwargs(step, card_face)
        )

        layer_position = tuple(position) if (layer_position is True) else layer_position
        paste_box = (
            layer_position[0],
            layer_position[1],
            layer_position[0] + text_layer.size[0],
            layer_position[1] + text_layer.size[1]
        )

        compatibility_layer = Image.new("RGBA", image.size)
        compatibility_layer.paste(text_layer, Methods.ensure_ints(paste_box))

        image = Image.alpha_composite(image, compatibility_layer)
        return image

from PIL import Image, ImageOps, ImageDraw

from typing import Optional, Callable, Union, Literal


class CardFace:
    def __init__(
            self, label: Optional[str] = None,
            template: Optional["CardFace"] = None, size: Optional[tuple[int, int]] = None,
            steps: tuple[dict[str], ...] = ()
    ):
        self.step_handlers: dict[str, Callable[[Image.Image, dict[str], "CardFace"], Image.Image]] = {
            "image": self._step_image,
            "save_value": self._step_save_value
        }
        """
        Saved values are pieces of re-usable data referencing various aspects of the card face,
        e.g. the coords of a specific point location on the card. They can be added by specific steps, and may be
        read during any subsequent steps once added
        """
        self.saved_values: dict[str] = {}

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

    def generate_image(self) -> Image.Image:
        self.saved_values.clear()

        image = Image.new("RGBA", self.size)

        for step in self.steps:
            step_type: str = step["type"]
            step_handler = self.step_handlers[step_type]
            image = step_handler(image, step, self)

        return image

    def decode_step_value(self, step_value):
        """
        Returns the provided step value with saved values substituted in where they are referenced,
        and relative amounts changed into absolute ones.
        If the provided data needs no converting, it will be returned as-is.

        Recursively converts sub-values within any dict, list or tuple
        """

        working_value = step_value

        while (
                (is_saved := self._is_saved_value(working_value)) or
                (is_relative := self._is_relative_amount(working_value))
        ):
            if is_saved:
                working_value = self.saved_values[working_value["key"]]
            elif is_relative:
                working_value = self._convert_relative_amount(working_value)

        if type(working_value) in (list, tuple):
            for index, item in enumerate(working_value):
                working_value[index] = self.decode_step_value(item)
        elif type(working_value) is dict:
            for key, item in working_value.items():
                working_value[key] = self.decode_step_value(item)

        return working_value

    def _convert_relative_amount(self, amount: dict[str]) -> Union[int, float]:
        """
        Returns the provided amount converted into absolute units (pixels), so it can be used directly.
        Requires a target amount which this amount is relative to,
        which may also be relative or reference a saved value
        """

        type AmountOperand = Union[Literal["width", "height"], Union[int, float]]

        # Required params
        target: AmountOperand = self.decode_step_value(amount["target"])

        # Optional params
        multiplier: AmountOperand = self.decode_step_value(amount.get("multiplier", 1))
        offset: AmountOperand = self.decode_step_value(amount.get("offset", 0))
        round_to: Union[None, int] = self.decode_step_value(amount.get("round_to", None))

        # Operands may also include references to the card face's height or width, these must be resolved
        operands = [target, multiplier, offset]
        for index, operand in enumerate(operands):
            if operand == "width":
                operands[index] = self.size[0]
            elif operand == "height":
                operands[index] = self.size[1]
        target, multiplier, offset = operands

        # Applying calculations
        result = (target * multiplier) + offset
        if round_to is not None:
            result = round(result, round_to)
        if round_to == 0:
            result = int(result)

        return result

    @staticmethod
    def _is_saved_value(value) -> bool:
        if type(value) is not dict:
            return False
        if "type" not in value:
            return False
        if value["type"] != "saved":
            return False
        return True

    @staticmethod
    def _is_relative_amount(value) -> bool:
        if type(value) is not dict:
            return False
        if "type" not in value:
            return False
        if value["type"] != "relative":
            return False
        return True

    @staticmethod
    def _step_save_value(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Required params
        key: str = step["key"]
        value = step["value"]

        # Will not be used, is simply executed to ensure that a valid value has been provided
        card_face.decode_step_value(value)

        card_face.saved_values[key] = value
        return image

    @staticmethod
    def _step_image(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Required params
        src: str = step["src"]
        position: tuple[int, int] = card_face.decode_step_value(step["position"])

        # Optional params
        crop: Optional[tuple[int, int, int, int]] = card_face.decode_step_value(step.get("crop", None))
        scale: Optional[float] = card_face.decode_step_value(step.get("scale", None))

        compatibility_layer = Image.new("RGBA", image.size)
        embed_image = Image.open(src)

        if crop:
            embed_image = embed_image.crop(crop)
        if scale:
            scaled_embed_image_size = tuple(round(dimension * scale) for dimension in embed_image.size)
            embed_image = ImageOps.contain(embed_image, scaled_embed_image_size)

        paste_box = (
            position[0],
            position[1],
            position[0] + embed_image.size[0],
            position[1] + embed_image.size[1]
        )
        compatibility_layer.paste(embed_image, paste_box)

        image = Image.alpha_composite(image, compatibility_layer)
        return image

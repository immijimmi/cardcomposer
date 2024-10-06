from objectextensions import Extension
from PIL import Image, ImageFont, ImageDraw

from typing import Iterable, Optional, Sequence, Union, Literal
from numbers import Number
from collections.abc import Collection
import random

from ..cardface import CardFace
from ..types import Deferred, CardFaceLabel, ArithmeticOperator
from ..methods import Methods as CardFaceMethods
from ..enums import GenericKey, DeferredKey
from .constants import Constants
from .enums import DeferredValue


class PresetValues(Extension):
    @staticmethod
    def can_extend(target_cls):
        return issubclass(target_cls, CardFace)

    @staticmethod
    def extend(target_cls):
        deferred_value_resolvers = {
            DeferredValue.SELF: PresetValues.__resolve_self,
            DeferredValue.LABEL: PresetValues.__resolve_label,
            DeferredValue.CONFIG: PresetValues.__resolve_config,
            DeferredValue.CACHED: PresetValues.__resolve_cached,
            DeferredValue.STANDARD_CALCULATION: PresetValues.__resolve_standard_calculation,
            DeferredValue.ARITHMETIC_EQUATION: PresetValues.__resolve_arithmetic_equation,
            DeferredValue.SEEDED_RANDOM: PresetValues.__resolve_seeded_random,
            DeferredValue.MAPPED: PresetValues.__resolve_mapped,
            DeferredValue.CARD_DIMENSION: PresetValues.__resolve_card_dimension,
            DeferredValue.WORKING_IMAGE: PresetValues.__resolve_working_image,
            DeferredValue.PARENT: PresetValues.__resolve_parent,
            DeferredValue.IMAGE_FROM_FILE: PresetValues.__resolve_image_from_file,
            DeferredValue.BLANK_IMAGE: PresetValues.__resolve_blank_image,
            DeferredValue.IMAGE_FROM_TEMPLATE: PresetValues.__resolve_image_from_template,
            DeferredValue.FONT: PresetValues.__resolve_font,
            DeferredValue.TEXT_LENGTH: PresetValues.__resolve_text_length,
            DeferredValue.TEXT_BBOX: PresetValues.__resolve_text_bbox
        }

        # To prevent mutating the dict on the base class
        target_cls.DEFERRED_VALUE_RESOLVERS = {**target_cls.DEFERRED_VALUE_RESOLVERS}

        for resolver_key, resolver in deferred_value_resolvers.items():
            if resolver_key in target_cls.DEFERRED_VALUE_RESOLVERS:
                raise ValueError(f"a deferred value resolver already exists under the provided key: {resolver_key}")
            target_cls.DEFERRED_VALUE_RESOLVERS[resolver_key] = resolver

    @staticmethod
    def __resolve_self(value: Deferred, card_face: CardFace) -> CardFace:
        return card_face

    @staticmethod
    def __resolve_label(value: Deferred, card_face: CardFace) -> CardFaceLabel:
        return card_face.label

    @staticmethod
    def __resolve_config(value: Deferred, card_face: CardFace) -> dict[str]:
        return card_face.config

    @staticmethod
    def __resolve_cached(value: Deferred, card_face: CardFace):
        # Required params
        cache_key = card_face.resolve_deferred_value(value["key"])

        try:
            return card_face.cache[cache_key]
        except KeyError:
            if "default" not in value:
                raise KeyError(
                    f"no value found in {type(card_face).__name__} cache (label={card_face.label}) and no default provided for key: {cache_key}"
                )

            return value["default"]

    @staticmethod
    def __resolve_standard_calculation(value: Deferred, card_face: CardFace):
        """
        Invokes a single calculation from a limited list of options, passing in the provided arguments.
        The provided arguments may themselves be any valid deferred value
        (further calculations, references to cached values etc.), and are not limited to representing
        numbers - any types which are valid parameters for the calculation will equally suffice
        """

        # Required params
        operation_key: str = card_face.resolve_deferred_value(value["op"])
        operands: Iterable = card_face.resolve_deferred_value(value["args"])

        # Optional params
        do_log: bool = card_face.resolve_deferred_value(value.get(GenericKey.DO_LOG, False))

        operation = Constants.CALCULATIONS_LOOKUP[operation_key]
        operands = tuple(operands)

        try:
            result = operation(*operands)
            if do_log:
                card_face.logger.info(f"Calculated value: {operation.__name__}{operands} -> {result}")
        except:
            if "default" not in value:
                raise KeyError(
                    f"unable to perform calculation, and no default value provided: {operation.__name__}{operands}"
                )

            result = value["default"]
            if do_log:
                card_face.logger.info(
                    f"Calculation failed, using default value ({value["default"]}): {operation.__name__}{operands}"
                )

        return result

    @staticmethod
    def __resolve_arithmetic_equation(value: Deferred, card_face: CardFace):
        # Required params
        args: Iterable[Union[Deferred, list, float, ArithmeticOperator]] = (
            card_face.resolve_deferred_value(value["args"])
        )

        args = list(args)

        depth_indexes = []
        while True:
            working_args = args
            for depth_index in depth_indexes:
                working_args = working_args[depth_index]

            # Check for sub-lists to resolve
            do_reset = False
            for operand_index in range(len(working_args)):
                operand = card_face.resolve_deferred_value(working_args[operand_index])
                working_args[operand_index] = operand

                if type(operand) is list:
                    # This must be resolved before the current depth, so set new depth and go to next loop
                    depth_indexes.append(operand_index)
                    do_reset = True
                    break
            if do_reset:
                continue

            # Resolve all arithmetic calculations in current working args list
            for arithmetic_op_group in Constants.ARITHMETIC_ORDER:
                while True:
                    first_group_op = None
                    first_group_op_index = None
                    for arithmetic_op in arithmetic_op_group:
                        if arithmetic_op in working_args:
                            first_op_index = working_args.index(arithmetic_op)
                            if (first_group_op_index is None) or (first_op_index < first_group_op_index):
                                first_group_op = arithmetic_op
                                first_group_op_index = first_op_index

                    if first_group_op is None:
                        break

                    if (first_group_op_index < 1) or (first_group_op_index >= (len(working_args) - 1)):
                        raise ValueError(
                            f"unable to parse arithmetic calculation"
                            f" (each operator must have an operand on either side): {working_args}"
                        )

                    operands = working_args[first_group_op_index-1], working_args[first_group_op_index+1]
                    for operand in operands:
                        if not isinstance(operand, Number):
                            raise ValueError(f"invalid operand for arithmetic calculation: {operand}")

                    arithmetic_result = Constants.CALCULATIONS_LOOKUP[first_group_op](*operands)
                    working_args = [
                        *working_args[:first_group_op_index-1],
                        arithmetic_result,
                        *working_args[first_group_op_index+2:]
                    ]

            if len(working_args) > 1:
                raise ValueError(f"unable to parse remaining arguments in arithmetic calculation: {working_args}")

            if len(depth_indexes) > 0:  # `working_args` is a sub-list
                depth_last_index = depth_indexes.pop()
                working_args_container = args
                for depth_index in depth_indexes:
                    working_args_container = working_args_container[depth_index]

                working_args_container[depth_last_index] = working_args[0]
            else:  # This is not a sub-list, so the value in `working_args` is the final result
                return working_args[0]

    @staticmethod
    def __resolve_seeded_random(value: Deferred, card_face: CardFace) -> float:
        # Required params
        seed = card_face.resolve_deferred_value(value["seed"])

        # Optional params
        n: int = card_face.resolve_deferred_value(value.get("n", 1))
        is_int: bool = card_face.resolve_deferred_value(value.get("is_int", False))
        mult: float = card_face.resolve_deferred_value(value.get("mult", 1))

        random.seed(seed)
        for prior_roll in range(n-1):
            random.random()

        result = mult * random.random()
        if is_int:
            result = round(result)

        return result

    @staticmethod
    def __resolve_mapped(value: Deferred, card_face: CardFace) -> list[Collection]:
        # Required params
        map_to: Collection = card_face.resolve_deferred_value(value["map_to"])
        key = card_face.resolve_deferred_value(value["key"])
        values: Iterable = card_face.resolve_deferred_value(value["values"])

        # Optional params
        map_deferred_type: Optional[str] = card_face.resolve_deferred_value(value.get("map_deferred_type", None))

        result = []
        for value_to_map in values:
            copied_map_target = CardFaceMethods.try_copy(map_to)
            copied_map_target[key] = value_to_map

            if map_deferred_type is not None:
                copied_map_target[DeferredKey.DEFERRED] = map_deferred_type

            result.append(copied_map_target)

        return result

    @staticmethod
    def __resolve_card_dimension(value: Deferred, card_face: CardFace) -> int:
        # Required params
        dimension: str = card_face.resolve_deferred_value(value["dim"])

        if dimension == "width":
            return card_face.size[0]
        elif dimension == "height":
            return card_face.size[1]
        else:
            raise ValueError(f"invalid dimension name received: {dimension}")

    @staticmethod
    def __resolve_working_image(value: Deferred, card_face: CardFace) -> Image.Image:
        image = CardFaceMethods.manipulate_image(
            card_face.working_image,
            **CardFaceMethods.unpack_manipulate_image_kwargs(value, card_face)
        )

        return image

    @staticmethod
    def __resolve_parent(value: Deferred, card_face: CardFace) -> Optional[CardFace]:
        return card_face.parent

    @staticmethod
    def __resolve_image_from_file(value: Deferred, card_face: CardFace) -> Image.Image:
        # Required params
        src: str = card_face.resolve_deferred_value(value["src"])

        image = Image.open(src)
        image = CardFaceMethods.manipulate_image(
            image,
            **CardFaceMethods.unpack_manipulate_image_kwargs(value, card_face)
        )

        return image

    @staticmethod
    def __resolve_blank_image(value: Deferred, card_face: CardFace) -> Image.Image:
        # Required params
        size: tuple[float, float] = card_face.resolve_deferred_value(value["size"])

        return Image.new("RGBA", CardFaceMethods.ensure_ints(size))

    @staticmethod
    def __resolve_image_from_template(value: Deferred, card_face: CardFace) -> Optional[Image.Image]:
        # Required params
        label: CardFaceLabel = card_face.resolve_deferred_value(value["label"])

        image = card_face.templates_pool[label].generate(parent=card_face)
        image = CardFaceMethods.manipulate_image(
            image,
            **CardFaceMethods.unpack_manipulate_image_kwargs(value, card_face)
        )

        return image

    @staticmethod
    def __resolve_font(value: Deferred, card_face: CardFace) -> ImageFont:
        # Required params
        src: str = card_face.resolve_deferred_value(value["src"])

        # Optional params
        font_type: str = card_face.resolve_deferred_value(value.get("type", "truetype"))
        size: Optional[int] = card_face.resolve_deferred_value(value.get("size", None))
        index: Optional[int] = card_face.resolve_deferred_value(value.get("index", None))
        encoding: Optional[str] = card_face.resolve_deferred_value(value.get("encoding", None))

        font_optional_kwargs = {
            key: value for key, value in {
                "size": size,
                "index": index,
                "encoding": encoding
            }.items() if value is not None
        }

        if font_type == "truetype":
            return ImageFont.truetype(font=src, **font_optional_kwargs)
        elif font_type == "bitmap":
            """
            kwargs are purposefully provided here despite not being expected,
            since for a bitmap font they should be empty anyway
            """
            return ImageFont.load(src, **font_optional_kwargs)
        else:
            raise ValueError(f"invalid font type: {font_type}")

    @staticmethod
    def __resolve_text_length(value: Deferred, card_face: CardFace) -> float:
        # Required params
        text: str = card_face.resolve_deferred_value(value["text"])
        font: ImageFont = card_face.resolve_deferred_value(value["font"])

        # Optional params
        direction: Optional[str] = card_face.resolve_deferred_value(value.get("direction", None))
        features: Optional[Sequence[str]] = card_face.resolve_deferred_value(value.get("features", None))
        language: Optional[str] = card_face.resolve_deferred_value(value.get("language", None))
        embedded_color: Optional[bool] = card_face.resolve_deferred_value(value.get("embedded_color", None))

        textlength_optional_kwargs = {
            key: value for key, value in {
                "direction": direction,
                "features": features,
                "language": language,
                "embedded_color": embedded_color
            }.items() if value is not None
        }

        textlength_layer = Image.new("RGB", (0, 0))
        draw = ImageDraw.Draw(textlength_layer)
        return draw.textlength(text=text, font=font, **textlength_optional_kwargs)

    @staticmethod
    def __resolve_text_bbox(value: Deferred, card_face: CardFace) -> tuple[int, int, int, int]:
        # Required params
        text: str = card_face.resolve_deferred_value(value["text"])
        font: ImageFont = card_face.resolve_deferred_value(value["font"])

        # Optional params
        position: tuple[float, float] = card_face.resolve_deferred_value(value.get("position", (0, 0)))
        anchor: Optional[str] = card_face.resolve_deferred_value(value.get("anchor", None))
        spacing: Optional[float] = card_face.resolve_deferred_value(value.get("spacing", None))
        align: Optional[str] = card_face.resolve_deferred_value(value.get("align", None))
        direction: Optional[str] = card_face.resolve_deferred_value(value.get("direction", None))
        features: Optional[Sequence[str]] = card_face.resolve_deferred_value(value.get("features", None))
        language: Optional[str] = card_face.resolve_deferred_value(value.get("language", None))
        stroke_width: Optional[int] = card_face.resolve_deferred_value(value.get("stroke_width", None))
        embedded_color: Optional[bool] = card_face.resolve_deferred_value(value.get("language", None))

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

        bbox_layer = Image.new("RGB", (0, 0))
        draw = ImageDraw.Draw(bbox_layer)
        # Floats are accepted here for xy
        return draw.textbbox(xy=position, text=text, font=font, **textbbox_optional_kwargs)

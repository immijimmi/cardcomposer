from objectextensions import Extension
from PIL import Image, ImageFont, ImageDraw

from typing import Iterable, Optional, Sequence
import random

from ..cardface import CardFace
from ..constants import Constants as CardFaceConstants
from ..methods import Methods as CardFaceMethods
from .enums import DeferredValue


class PresetValues(Extension):
    @staticmethod
    def can_extend(target_cls):
        return issubclass(target_cls, CardFace)

    @staticmethod
    def extend(target_cls):
        Extension._wrap(target_cls, "__init__", PresetValues.__wrap_init)

    @staticmethod
    def __wrap_init(self, *args, **kwargs):
        yield

        deferred_value_resolvers = {
            DeferredValue.SELF: PresetValues.__resolve_self,
            DeferredValue.CACHED: PresetValues.__resolve_cached,
            DeferredValue.CALCULATION: PresetValues.__resolve_calculation,
            DeferredValue.SEEDED_RANDOM: PresetValues.__resolve_seeded_random,
            DeferredValue.CARD_DIMENSION: PresetValues.__resolve_card_dimension,
            DeferredValue.WORKING_IMAGE: PresetValues.__resolve_working_image,
            DeferredValue.IMAGE_FROM_FILE: PresetValues.__resolve_image_from_file,
            DeferredValue.BLANK_IMAGE: PresetValues.__resolve_blank_image,
            DeferredValue.FONT: PresetValues.__resolve_font,
            DeferredValue.TEXT_LENGTH: PresetValues.__resolve_text_length,
            DeferredValue.TEXT_BBOX: PresetValues.__resolve_text_bbox
        }

        for value_type, value_resolver in deferred_value_resolvers.items():
            if value_type in self.deferred_value_resolvers:
                raise ValueError(f"multiple resolvers provided for deferred value type: {value_type}")

            self.deferred_value_resolvers[value_type] = value_resolver

    @staticmethod
    def __resolve_self(value: dict[str], card_face: "CardFace"):
        return card_face

    @staticmethod
    def __resolve_cached(value: dict[str], card_face: "CardFace"):
        # Required params
        cache_key = card_face.resolve_deferred_value(value["key"])

        try:
            return card_face.cache[cache_key]
        except KeyError:
            if "default" not in value:
                raise KeyError(f"no value found in cache and no default provided for key: {cache_key}")

            return value["default"]

    @staticmethod
    def __resolve_calculation(value: dict[str], card_face: "CardFace"):
        """
        Invokes a single calculation from a limited list of options, passing in the provided arguments.
        The provided arguments may themselves be any valid deferred value
        (further calculations, references to cached values etc.), and are not limited to representing
        numbers - any types which are valid parameters for the calculation will equally suffice
        """

        # Required params
        operands: Iterable = card_face.resolve_deferred_value(value["args"])
        operation_key: str = card_face.resolve_deferred_value(value["op"])

        # Optional params
        do_log: bool = card_face.resolve_deferred_value(value.get("do_log", False))

        operands = tuple(operands)
        operation = CardFaceConstants.CALCULATIONS_LOOKUP[operation_key]
        result = operation(*operands)

        if do_log:
            card_face.logger.info(f"Performing calculation step: {operation.__name__}{operands} -> {result}")

        return result

    @staticmethod
    def __resolve_seeded_random(value: dict[str], card_face: "CardFace"):
        # Required params
        seed = card_face.resolve_deferred_value(value["seed"])

        # Optional params
        n: int = card_face.resolve_deferred_value(value.get("n", 0))

        random.seed(seed)
        for prior_roll in range(n):
            random.random()

        return random.random()

    @staticmethod
    def __resolve_card_dimension(value: dict[str], card_face: "CardFace"):
        # Required params
        dimension: str = card_face.resolve_deferred_value(value["dimension"])

        if dimension == "width":
            return card_face.size[0]
        elif dimension == "height":
            return card_face.size[1]
        else:
            raise ValueError(f"invalid dimension name received: {dimension}")

    @staticmethod
    def __resolve_working_image(value: dict[str], card_face: "CardFace"):
        return card_face.working_image

    @staticmethod
    def __resolve_image_from_file(value: dict[str], card_face: "CardFace"):
        # Required params
        src: str = card_face.resolve_deferred_value(value["src"])

        return Image.open(src)

    @staticmethod
    def __resolve_blank_image(value: dict[str], card_face: "CardFace"):
        # Required params
        size: tuple[float, float] = card_face.resolve_deferred_value(value["size"])

        return Image.new("RGBA", CardFaceMethods.ensure_ints(size))

    @staticmethod
    def __resolve_font(value: dict[str], card_face: "CardFace"):
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
    def __resolve_text_length(value: dict[str], card_face: "CardFace"):
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
    def __resolve_text_bbox(value: dict[str], card_face: "CardFace"):
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

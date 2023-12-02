from objectextensions import Extension
from PIL import Image, ImageFont, ImageDraw

from typing import Optional, Union, Sequence
from os import path
from pathlib import Path

from ..cardface import CardFace
from ..methods import Methods as CardFaceMethods


class PresetSteps(Extension):
    @staticmethod
    def can_extend(target_cls):
        return issubclass(target_cls, CardFace)

    @staticmethod
    def extend(target_cls):
        Extension._wrap(target_cls, "__init__", PresetSteps.__wrap_init)

    @staticmethod
    def __wrap_init(self, *args, **kwargs):
        yield

        step_handlers = {
            "paste_image": PresetSteps.__step_paste_image,
            "write_to_cache": PresetSteps.__step_write_to_cache,
            "save": PresetSteps.__step_save,
            "write_text": PresetSteps.__step_write_text
        }

        for step_name, step_handler in step_handlers.items():
            if step_name in self.step_handlers:
                raise ValueError(f"multiple step handlers provided under the same key: {step_name}")

            self.step_handlers[step_name] = step_handler

    @staticmethod
    def __step_write_to_cache(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Optional params
        entries: Optional[dict] = step.get(
            "entries", None
        )  # Values to be stored should remain deferred until needed
        mode: str = card_face.resolve_deferred_value(step.get("mode", "add"))
        is_lazy: bool = card_face.resolve_deferred_value(step.get("is_lazy", True))
        do_log: bool = card_face.resolve_deferred_value(step.get("do_log", False))

        if entries is not None:
            if ("key" in step) or ("value" in step):
                raise ValueError(
                    f"writing to cache requires either ('key' and 'value') or ('entries') in its parameters; not both"
                )
        else:
            # Required params
            key = card_face.resolve_deferred_value(step["key"])
            value = step["value"]  # Value to be stored should remain deferred until needed

            entries = {key: value}

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
                card_face.logger.info(f"Writing to cache (mode='{mode}', is_lazy={is_lazy}): {{{key}: {value}}}")

            card_face.cache[key] = value

        return image

    @staticmethod
    def __step_paste_image(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Required params
        embed_image: Image.Image = card_face.resolve_deferred_value(step["image"])
        position: tuple[float, float] = card_face.resolve_deferred_value(step["position"])

        embed_image = CardFaceMethods.manipulate_image(
            embed_image,
            **CardFaceMethods.unpack_manipulate_image_kwargs(step, card_face)
        )

        paste_box = (
            position[0],
            position[1],
            position[0] + embed_image.size[0],
            position[1] + embed_image.size[1]
        )

        compatibility_layer = Image.new("RGBA", image.size)
        compatibility_layer.paste(embed_image, CardFaceMethods.ensure_ints(paste_box))

        image = Image.alpha_composite(image, compatibility_layer)
        return image

    @staticmethod
    def __step_save(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Optional params
        file_path: str = card_face.resolve_deferred_value(step.get("path", "Cards"))
        filename: str = card_face.resolve_deferred_value(step.get("filename", card_face.label or "card"))
        extension: str = card_face.resolve_deferred_value(step.get("extension", ".tif"))

        full_path = path.join(file_path, filename + extension)

        Path(file_path).mkdir(parents=True, exist_ok=True)
        image.save(full_path)

        return image

    @staticmethod
    def __step_write_text(image: Image.Image, step: dict[str], card_face: "CardFace") -> Image.Image:
        # Required params
        position: tuple[float, float] = card_face.resolve_deferred_value(step["position"])
        text: str = card_face.resolve_deferred_value(step["text"])
        fill = CardFaceMethods.coalesce_list_to_tuple(
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

        text_layer = CardFaceMethods.manipulate_image(
            text_layer,
            **CardFaceMethods.unpack_manipulate_image_kwargs(step, card_face)
        )

        layer_position = tuple(position) if (layer_position is True) else layer_position
        paste_box = (
            layer_position[0],
            layer_position[1],
            layer_position[0] + text_layer.size[0],
            layer_position[1] + text_layer.size[1]
        )

        compatibility_layer = Image.new("RGBA", image.size)
        compatibility_layer.paste(text_layer, CardFaceMethods.ensure_ints(paste_box))

        image = Image.alpha_composite(image, compatibility_layer)
        return image

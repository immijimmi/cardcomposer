from objectextensions import Extension
from PIL import Image, ImageFont, ImageDraw

from typing import Optional, Sequence, Union, Any
from os import path
from pathlib import Path

from ..cardface import CardFace
from ..types import Deferred, Step
from ..methods import Methods as CardFaceMethods
from ..enums import GenericKey
from .methods import Methods


class PresetSteps(Extension):
    @staticmethod
    def can_extend(target_cls):
        return issubclass(target_cls, CardFace)

    @staticmethod
    def extend(target_cls):
        step_handlers = {
            "paste_image": PresetSteps.__step_paste_image,
            "write_to_cache": PresetSteps.__step_write_to_cache,
            "save": PresetSteps.__step_save,
            "write_text": PresetSteps.__step_write_text,
            "stop": PresetSteps.__step_stop,
            "cancel": PresetSteps.__step_cancel
        }

        # To prevent mutating the dict on the base class
        target_cls.STEP_HANDLERS = {**target_cls.STEP_HANDLERS}

        for handler_key, handler in step_handlers.items():
            if handler_key in target_cls.STEP_HANDLERS:
                raise ValueError(f"a step handler already exists under the provided key: {handler_key}")
            target_cls.STEP_HANDLERS[handler_key] = handler

    @staticmethod
    def __step_write_to_cache(image: Image.Image, step: Step, card_face: "CardFace") -> Image.Image:
        # Optional params
        entries: Optional[dict] = step.get(
            "entries", None
        )  # Values to be stored should remain deferred until needed
        mode: str = card_face.resolve_deferred_value(step.get("mode", "add"))
        is_lazy: bool = card_face.resolve_deferred_value(step.get("is_lazy", True))
        is_global: bool = card_face.resolve_deferred_value(step.get("is_global", False))
        do_log: bool = card_face.resolve_deferred_value(step.get(GenericKey.DO_LOG, False))

        if entries is not None:
            if ("key" in step) or ("value" in step):
                raise ValueError(
                    f"writing to cache requires either ('key' and 'value') or ('entries') in its parameters; not both"
                )
        else:
            # Required params
            key = card_face.resolve_deferred_value(step["key"])
            value: Union[Deferred, Any] = step["value"]  # Value to be stored should remain deferred until needed

            entries = {key: value}

        for key, value in entries.items():
            if mode == "add":
                if key in card_face.cache:
                    raise ValueError(f"key already exists in {type(card_face).__name__} cache (mode='{mode}'): {key}")
                if is_global and (key in card_face.global_cache):
                    raise ValueError(f"key already exists in {type(card_face).__name__} global cache (mode='{mode}'): {key}")
            elif mode == "update":
                if key not in card_face.cache:
                    raise KeyError(f"key not found in {type(card_face).__name__} cache (mode='{mode}'): {key}")
                if is_global and (key not in card_face.global_cache):
                    raise KeyError(f"key not found in {type(card_face).__name__} global cache (mode='{mode}'): {key}")
            elif mode == "add_or_update":
                pass
            elif mode == "add_or_skip":
                if key in card_face.cache:
                    if do_log:
                        card_face.logger.info(
                            f"Skipping entry - key already exists in {type(card_face).__name__} cache (mode='{mode}'): {key}"
                        )
                    continue
                if is_global and (key in card_face.global_cache):
                    if do_log:
                        card_face.logger.info(
                            f"Skipping entry - key already exists in {type(card_face).__name__} global cache (mode='{mode}'): {key}"
                        )
                    continue
            else:
                raise ValueError(f"unrecognised write mode: {mode}")

            if not is_lazy:  # Resolve value now rather than waiting until it is needed
                value = card_face.resolve_deferred_value(value)

            if do_log:
                card_face.logger.info(
                    f"Writing to cache (mode='{mode}', is_lazy={is_lazy}, is_global={is_global}): {{{key}: {value}}}"
                )

            card_face.cache[key] = value
            if is_global:
                card_face.global_cache[key] = value

        return image

    @staticmethod
    def __step_paste_image(image: Image.Image, step: Step, card_face: "CardFace") -> Image.Image:
        # Required params
        embed_image: Image.Image = card_face.resolve_deferred_value(step["image"])
        position: tuple[float, float] = card_face.resolve_deferred_value(step["position"])

        # Optional params
        is_position_centre: Optional[bool] = card_face.resolve_deferred_value(step.get("is_position_centre", False))

        embed_image = CardFaceMethods.manipulate_image(
            embed_image,
            **CardFaceMethods.unpack_manipulate_image_kwargs(step, card_face)
        )

        if is_position_centre:
            position = Methods.reposition_centre_to_topleft(position, embed_image)
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
    def __step_save(image: Image.Image, step: Step, card_face: "CardFace") -> Image.Image:
        """
        Replaces/overwrites an existing file at the save location if there is one
        """

        # Optional params
        file_path: str = card_face.resolve_deferred_value(step.get("path", "Cards"))
        filename: str = card_face.resolve_deferred_value(step.get("filename", card_face.label or "card"))
        extension: str = card_face.resolve_deferred_value(step.get("extension", ".tif"))
        data: Optional[Union[Image.Image, str]] = card_face.resolve_deferred_value(step.get("data", None))

        filename = Methods.sanitise_filename(filename)
        full_path = path.join(file_path, filename + extension)

        Path(file_path).mkdir(parents=True, exist_ok=True)

        if data is None:
            image.save(full_path)
        elif issubclass(type(data), Image.Image):
            data.save(full_path)
        else:
            with open(full_path, "w") as file:
                file.write(data)

        card_face.logger.info(
            f"{type(card_face).__name__} image (label='{card_face.label}') saved to file: {filename + extension}"
        )

        return image

    @staticmethod
    def __step_write_text(image: Image.Image, step: Step, card_face: "CardFace") -> Image.Image:
        # Required params
        position: tuple[float, float] = card_face.resolve_deferred_value(step["position"])
        text: str = card_face.resolve_deferred_value(step["text"])
        fill = CardFaceMethods.coalesce_list_to_tuple(
            card_face.resolve_deferred_value(step["fill"])
        )
        font: ImageFont = card_face.resolve_deferred_value(step["font"])

        # Optional params
        is_position_centre: Optional[bool] = card_face.resolve_deferred_value(step.get("is_position_centre", None))
        anchor: Optional[str] = card_face.resolve_deferred_value(step.get("anchor", None))
        spacing: Optional[float] = card_face.resolve_deferred_value(step.get("spacing", None))
        align: Optional[str] = card_face.resolve_deferred_value(step.get("align", None))
        direction: Optional[str] = card_face.resolve_deferred_value(step.get("direction", None))
        features: Optional[Sequence[str]] = card_face.resolve_deferred_value(step.get("features", None))
        language: Optional[str] = card_face.resolve_deferred_value(step.get("language", None))
        stroke_width: Optional[int] = card_face.resolve_deferred_value(step.get("stroke_width", None))
        stroke_fill = card_face.resolve_deferred_value(step.get("stroke_fill", None))
        embedded_color: Optional[bool] = card_face.resolve_deferred_value(step.get("language", None))

        stroke_width = CardFaceMethods.ensure_int(stroke_width)

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
        text_bbox_optional_kwargs = {
            key: value for key, value in draw_text_optional_kwargs.items()
            if key not in ["stroke_fill"]
        }  # `ImageDraw.textbbox()` does not support all kwargs that `ImageDraw.text()` does

        bbox_layer = Image.new("RGB", (0, 0))
        draw = ImageDraw.Draw(bbox_layer)
        bbox = draw.textbbox(xy=(0, 0), text=text, font=font, **text_bbox_optional_kwargs)

        text_dimensions = (bbox[2] - bbox[0], bbox[3] - bbox[1])
        adjusted_text_position = (-bbox[0], -bbox[1])

        text_layer = Image.new("RGBA", text_dimensions)
        draw = ImageDraw.Draw(text_layer)
        draw.text(adjusted_text_position, text=text, fill=fill, font=font, **draw_text_optional_kwargs)

        text_layer = CardFaceMethods.manipulate_image(
            text_layer,
            **CardFaceMethods.unpack_manipulate_image_kwargs(step, card_face)
        )

        if is_position_centre:
            position = Methods.reposition_centre_to_topleft(position, text_layer)
        paste_box = (
            position[0],
            position[1],
            position[0] + text_layer.size[0],
            position[1] + text_layer.size[1]
        )

        compatibility_layer = Image.new("RGBA", image.size)
        compatibility_layer.paste(text_layer, CardFaceMethods.ensure_ints(paste_box))

        image = Image.alpha_composite(image, compatibility_layer)
        return image

    @staticmethod
    def __step_stop(image: Image.Image, step: Step, card_face: "CardFace") -> Image.Image:
        raise StopIteration

    @staticmethod
    def __step_cancel(image: Image.Image, step: Step, card_face: "CardFace") -> Image.Image:
        raise NotImplementedError

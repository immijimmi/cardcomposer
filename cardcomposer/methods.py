from PIL import Image

from typing import Any, Union, Optional, Iterable
from copy import deepcopy


class Methods:
    @staticmethod
    def try_copy(item: Any) -> Any:
        """
        A failsafe deepcopy wrapper
        """

        try:
            return deepcopy(item)
        except:
            return item

    @staticmethod
    def ensure_ints(numbers: Union[tuple[Union[float, int], ...], Any]) -> Union[tuple[int, ...], Any]:
        """
        Used to ensure a number sequence contains only integers, in cases where:
        - Integer values are a requirement
        - Losing float precision is acceptable

        Should be invoked as late as possible to minimise loss of precision.
        If the provided data is not a tuple or list of only numbers, it will be returned as-is
        """

        if type(numbers) not in (tuple, list):
            return numbers

        for number in numbers:
            if type(number) not in (float, int):
                return numbers

        return tuple(round(number) for number in numbers)

    @staticmethod
    def coalesce_list_to_tuple(value):
        if type(value) is list:
            return tuple(value)

        return value

    @staticmethod
    def unpack_manipulate_image_kwargs(data: dict[str], card_face: "CardFace") -> dict[str]:
        """
        Unpacks and resolves only the kwargs used in `.manipulate_image()` from the provided data
        """

        crop: Optional[tuple[float, float, float, float]] = card_face.resolve_deferred_value(data.get("crop", None))
        scale: Optional[tuple[Union[float, bool], Union[float, bool]]] = (
            card_face.resolve_deferred_value(data.get("scale", None))
        )
        resize_to: Optional[tuple[Union[float, bool], Union[float, bool]]] = (
            card_face.resolve_deferred_value(data.get("resize_to", None))
        )
        limits: Optional[Iterable[dict[str]]] = (
            card_face.resolve_deferred_value(data.get("limits", None))
        )
        opacity: Optional[float] = (
            card_face.resolve_deferred_value(data.get("opacity", None))
        )

        return {
            "crop": crop,
            "scale": scale,
            "resize_to": resize_to,
            "limits": limits,
            "opacity": opacity
        }

    @staticmethod
    def manipulate_image(
            image: Image.Image,
            crop: Optional[tuple[float, float, float, float]] = None,
            scale: Optional[tuple[Union[float, bool], Union[float, bool]]] = None,
            resize_to: Optional[tuple[Union[float, bool], Union[float, bool]]] = None,
            limits: Optional[Iterable[dict[str]]] = None,
            opacity: Optional[float] = None
    ) -> Image.Image:
        if crop:
            image = image.crop(Methods.ensure_ints(crop))

        if scale:
            if (type(scale[0]) is bool) and (type(scale[1]) is bool):
                pass  # No numeric value to scale image with has been provided
            else:
                if scale[0] is False:
                    scaled_width = image.size[0]
                elif scale[0] is True:
                    scaled_width = image.size[0] * scale[1]
                else:
                    scaled_width = image.size[0] * scale[0]

                if scale[1] is False:
                    scaled_height = image.size[1]
                elif scale[1] is True:
                    scaled_height = image.size[1] * scale[0]
                else:
                    scaled_height = image.size[1] * scale[1]

                new_image_size = (scaled_width, scaled_height)
                # Resampling.LANCZOS is the highest quality but lowest performance (most time-consuming) option
                image = image.resize(Methods.ensure_ints(new_image_size), resample=Image.Resampling.LANCZOS)

        if resize_to:
            if (type(resize_to[0]) is bool) and (type(resize_to[1]) is bool):
                pass  # No numeric value to scale image with has been provided
            else:
                if resize_to[0] is False:
                    resized_width = image.size[0]
                elif resize_to[0] is True:
                    try:
                        resized_width = image.size[0] * (resize_to[1] / image.size[1])
                    except ZeroDivisionError:  # Edge case where the image being resized is 0px tall/wide
                        resized_width = resize_to[0]
                else:
                    resized_width = resize_to[0]

                if resize_to[1] is False:
                    resized_height = image.size[1]
                elif resize_to[1] is True:
                    try:
                        resized_height = image.size[1] * (resize_to[0] / image.size[0])
                    except ZeroDivisionError:  # Edge case where the image being resized is 0px tall/wide
                        resized_width = resize_to[0]
                else:
                    resized_height = resize_to[1]

                new_image_size = (resized_width, resized_height)
                # Resampling.LANCZOS is the highest quality but lowest performance (most time-consuming) option
                image = image.resize(Methods.ensure_ints(new_image_size), resample=Image.Resampling.LANCZOS)

        if limits:
            for limit in limits:
                limit_type: str = limit["type"]
                limit_dimension: str = limit["dimension"]
                limit_value: float = limit["value"]
                do_maintain_proportions: bool = limit["do_maintain_proportions"]

                limited_dim_index = {"width": 0, "height": 1}[limit_dimension]
                limited_dim_value = image.size[limited_dim_index]

                limit_func = {"min": min, "max": max}[limit_type]
                if limit_func(limited_dim_value, limit_value) == limit_value:  # Dimension is within the provided limit
                    continue

                other_dim_index = int(not limited_dim_index)
                other_dim_value = image.size[other_dim_index]
                if do_maintain_proportions:
                    try:
                        other_dim_resized_value = other_dim_value * (limit_value / limited_dim_value)
                    except ZeroDivisionError:  # Edge case where the image being resized is 0px tall/wide
                        other_dim_resized_value = other_dim_value
                else:
                    other_dim_resized_value = other_dim_value

                new_image_size = [None, None]
                new_image_size[limited_dim_index] = limit_value
                new_image_size[other_dim_index] = other_dim_resized_value

                # Resampling.LANCZOS is the highest quality but lowest performance (most time-consuming) option
                image = image.resize(Methods.ensure_ints(tuple(new_image_size)), resample=Image.Resampling.LANCZOS)

        if opacity is not None:
            opacity_layer = Image.new("RGBA", image.size)
            image = Image.blend(opacity_layer, image, alpha=opacity)

        return image

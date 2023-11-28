from PIL import Image

from typing import Any, Union, Optional
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
    def manipulate_image(
            image: Image.Image,
            crop: Optional[tuple[int, int, int, int]] = None,
            scale: Optional[tuple[Union[float, bool], Union[float, bool]]] = None,
            resize_to: Optional[tuple[Union[int, bool], Union[int, bool]]] = None,
            opacity: Optional[float] = None
    ) -> Image.Image:
        if crop:
            image = image.crop(crop)

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

                new_image_size = Methods.ensure_ints((scaled_width, scaled_height))
                # Resampling.LANCZOS is the highest quality but lowest performance (most time-consuming) option
                image = image.resize(new_image_size, resample=Image.Resampling.LANCZOS)

        if resize_to:
            if (type(resize_to[0]) is bool) and (type(resize_to[1]) is bool):
                pass  # No numeric value to scale image with has been provided
            else:
                if resize_to[0] is False:
                    resized_width = image.size[0]
                elif resize_to[0] is True:
                    resized_width = image.size[0] * (resize_to[1]/image.size[1])
                else:
                    resized_width = resize_to[0]

                if resize_to[1] is False:
                    resized_height = image.size[1]
                elif resize_to[1] is True:
                    resized_height = image.size[1] * (resize_to[0]/image.size[0])
                else:
                    resized_height = resize_to[1]

                new_image_size = Methods.ensure_ints((resized_width, resized_height))
                # Resampling.LANCZOS is the highest quality but lowest performance (most time-consuming) option
                image = image.resize(new_image_size, resample=Image.Resampling.LANCZOS)

        if opacity is not None:
            opacity_layer = Image.new(mode="RGBA", size=image.size)
            image = Image.blend(opacity_layer, image, alpha=opacity)

        return image

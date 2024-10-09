from PIL import Image

import re


class Methods:
    @staticmethod
    def reposition_centre_to_topleft(position: tuple[float, float], image: Image.Image) -> tuple[float, float]:
        """
        Takes a position representing the centre of the provided image, and returns a position representing
        the top-left of that image
        """

        return (
            position[0] - (image.size[0]/2),
            position[1] - (image.size[1]/2)
        )

    @staticmethod
    def calc_if(is_truthy, true_value=None, false_value=None):
        if is_truthy:
            return (True if true_value is None else true_value)
        else:
            return (False if false_value is None else false_value)

    @staticmethod
    def calc_ands(*conditions):
        if len(conditions) < 2:
            raise ValueError(f"expected 2 or more arguments for 'and' operation, got {len(conditions)}")

        for condition in conditions:
            if not condition:
                return condition

        return condition

    @staticmethod
    def calc_ors(*conditions):
        if len(conditions) < 2:
            raise ValueError(f"expected 2 or more arguments for 'and' operation, got {len(conditions)}")

        for condition in conditions:
            if condition:
                return condition

        return condition

    @staticmethod
    def sanitise_filename(filename: str) -> str:
        pattern = re.compile(
            "|".join(
                (r"\\", "/", ":", r"\*", r"\?", "\"", "<", ">", r"\|")
            )
        )

        return pattern.sub("", filename)

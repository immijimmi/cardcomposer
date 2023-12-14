from PIL import Image


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

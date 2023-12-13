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

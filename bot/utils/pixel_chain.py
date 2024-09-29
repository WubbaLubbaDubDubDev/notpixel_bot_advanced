import random
from PIL import Image
from ..utils.image_simplifier import ImageSimplifier
from ..utils.pixel_mapper import PixelMapper
from ..config.palette import hex_palette


class PixelChain:
    def __init__(self, image_path, start_x, start_y,  canvas_width, canvas_height):
        self.image = Image.open(image_path)
        self.start_x = start_x
        self.start_y = start_y
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.ImageCoordinatesCalculator = PixelMapper((canvas_width, canvas_height))
        self.ImageSimplifier = ImageSimplifier(hex_palette)
        self.all_pixels = self._get_all_pixels()
        self.unused_pixels = self.all_pixels

    def _get_all_pixels(self):
        simplified_image = self.ImageSimplifier.simplify_image(self.image)
        pixels_list = self.ImageCoordinatesCalculator.calculate_pixel_coordinates(simplified_image, self.start_x,
                                                                                  self.start_y)
        return pixels_list

    def get_pixel(self):
        if len(self.unused_pixels) == 0:
            self.unused_pixels = self.all_pixels
        pixel = random.choice(self.unused_pixels)
        self.unused_pixels.remove(pixel)
        return pixel

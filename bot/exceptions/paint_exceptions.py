class PaintError(Exception):
    """Custom exception for errors during the painting process."""

    def __init__(self, message, *args):
        super().__init__(message, *args)

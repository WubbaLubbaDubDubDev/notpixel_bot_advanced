class ProxyError(Exception):
    """Base exception for proxy-related errors."""

    def __init__(self, message: str):
        super().__init__(message)


class InvalidProxyError(ProxyError):
    """Exception raised when the proxy is invalid."""

    def __init__(self, proxy: str):
        message = (
            f"Invalid proxy: {proxy} | Please check your proxy settings!"
        )
        super().__init__(message)

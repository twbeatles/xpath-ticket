"""XPath Explorer package."""

__all__ = ["XPathExplorer", "main"]


def __getattr__(name):
    if name == "XPathExplorer":
        from xpath_explorer.main_window import XPathExplorer

        return XPathExplorer
    if name == "main":
        from xpath_explorer.main_window import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

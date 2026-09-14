"""Host-neutral MCP transports; importing Actions must not initialize Ads Read."""
from importlib import import_module

__all__ = ["AdsReadMcpFacade", "UnknownAdsReadToolError"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(name)
    value=getattr(import_module(".facade",__name__),name)
    globals()[name]=value
    return value

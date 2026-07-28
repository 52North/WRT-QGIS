def classFactory(iface):
    from .plugin import WRTPlugin

    return WRTPlugin(iface)

EXTENSION_VERSION = "0.4.2"

from . import user_profiles, properties, connected_transforms, viewport_overlay, operators, ui


def register():
    print(f"[Curve Profile Creator] loaded v{EXTENSION_VERSION}")
    user_profiles.register()
    properties.register()
    connected_transforms.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    viewport_overlay.shutdown()
    connected_transforms.unregister()
    properties.unregister()
    user_profiles.unregister()

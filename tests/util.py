#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""utils used by tests"""


from soundconverter.util.settings import settings


DEFAULT_SETTINGS = settings.copy()


def reset_settings():
    """Reset the global settings to their initial state."""
    global settings
    # convert to list otherwise del won't work
    for key in list(settings.keys()):
        if key in DEFAULT_SETTINGS:
            settings[key] = DEFAULT_SETTINGS[key]
        else:
            del settings[key]
    # batch tests assume that recursive is off by default:
    assert (("recursive" not in settings) or (not settings["recursive"]))

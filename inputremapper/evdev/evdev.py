import evdev


class Evdev:
    # A Wrapper for evdev for improved testability, easily allowing all sorts of crazy
    # mocks independent of how evdev is imported, and allowing tiny fixes if something
    # in evdev goes wrong. Eventually everything should follow the DI pattern, for even
    # better testability by allowing to swap the whole Evdev class out with a mock
    # class.

    @staticmethod
    def list_devices(*args, **kwargs):
        return evdev.list_devices(*args, **kwargs)

    @staticmethod
    def input_device_factory(*args, **kwargs):
        return evdev.InputDevice(*args, **kwargs)

    @staticmethod
    def uinput_factory(*args, **kwargs):
        return evdev.UInput(*args, **kwargs)

    @staticmethod
    def input_event_factory(*args, **kwargs):
        return evdev.InputEvent(*args, **kwargs)

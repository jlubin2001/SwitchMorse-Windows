# SwitchMorse - USB HID key names for build_map.py (runs on the PC only).
# Stands in for adafruit_hid.keycode / consumer_control_code, so morse_map.py
# can be written exactly like an AeroMorse map. Values are the USB HID Usage
# Table codes, the same numbers adafruit_hid uses.


class Keycode:
    A = 0x04
    B = 0x05
    C = 0x06
    D = 0x07
    E = 0x08
    F = 0x09
    G = 0x0A
    H = 0x0B
    I = 0x0C
    J = 0x0D
    K = 0x0E
    L = 0x0F
    M = 0x10
    N = 0x11
    O = 0x12
    P = 0x13
    Q = 0x14
    R = 0x15
    S = 0x16
    T = 0x17
    U = 0x18
    V = 0x19
    W = 0x1A
    X = 0x1B
    Y = 0x1C
    Z = 0x1D
    ONE = 0x1E
    TWO = 0x1F
    THREE = 0x20
    FOUR = 0x21
    FIVE = 0x22
    SIX = 0x23
    SEVEN = 0x24
    EIGHT = 0x25
    NINE = 0x26
    ZERO = 0x27
    ENTER = RETURN = 0x28
    ESCAPE = 0x29
    BACKSPACE = 0x2A
    TAB = 0x2B
    SPACE = SPACEBAR = 0x2C
    MINUS = 0x2D
    EQUALS = 0x2E
    LEFT_BRACKET = 0x2F
    RIGHT_BRACKET = 0x30
    BACKSLASH = 0x31
    POUND = 0x32
    SEMICOLON = 0x33
    QUOTE = 0x34
    GRAVE_ACCENT = 0x35
    COMMA = 0x36
    PERIOD = 0x37
    FORWARD_SLASH = 0x38
    CAPS_LOCK = 0x39
    F1 = 0x3A
    F2 = 0x3B
    F3 = 0x3C
    F4 = 0x3D
    F5 = 0x3E
    F6 = 0x3F
    F7 = 0x40
    F8 = 0x41
    F9 = 0x42
    F10 = 0x43
    F11 = 0x44
    F12 = 0x45
    PRINT_SCREEN = 0x46
    SCROLL_LOCK = 0x47
    PAUSE = 0x48
    INSERT = 0x49
    HOME = 0x4A
    PAGE_UP = 0x4B
    DELETE = 0x4C
    END = 0x4D
    PAGE_DOWN = 0x4E
    RIGHT_ARROW = 0x4F
    LEFT_ARROW = 0x50
    DOWN_ARROW = 0x51
    UP_ARROW = 0x52
    KEYPAD_NUMLOCK = 0x53
    KEYPAD_FORWARD_SLASH = 0x54
    KEYPAD_ASTERISK = 0x55
    KEYPAD_MINUS = 0x56
    KEYPAD_PLUS = 0x57
    KEYPAD_ENTER = 0x58
    KEYPAD_ONE = 0x59
    KEYPAD_TWO = 0x5A
    KEYPAD_THREE = 0x5B
    KEYPAD_FOUR = 0x5C
    KEYPAD_FIVE = 0x5D
    KEYPAD_SIX = 0x5E
    KEYPAD_SEVEN = 0x5F
    KEYPAD_EIGHT = 0x60
    KEYPAD_NINE = 0x61
    KEYPAD_ZERO = 0x62
    KEYPAD_PERIOD = 0x63
    KEYPAD_BACKSLASH = 0x64
    APPLICATION = 0x65
    POWER = 0x66
    KEYPAD_EQUALS = 0x67
    F13 = 0x68
    F14 = 0x69
    F15 = 0x6A
    F16 = 0x6B
    F17 = 0x6C
    F18 = 0x6D
    F19 = 0x6E
    F20 = 0x6F
    F21 = 0x70
    F22 = 0x71
    F23 = 0x72
    F24 = 0x73
    LEFT_CONTROL = CONTROL = 0xE0
    LEFT_SHIFT = SHIFT = 0xE1
    LEFT_ALT = ALT = OPTION = 0xE2
    LEFT_GUI = GUI = WINDOWS = COMMAND = 0xE3
    RIGHT_CONTROL = 0xE4
    RIGHT_SHIFT = 0xE5
    RIGHT_ALT = 0xE6
    RIGHT_GUI = 0xE7


class ConsumerControlCode:
    RECORD = 0xB2
    FAST_FORWARD = 0xB3
    REWIND = 0xB4
    SCAN_NEXT_TRACK = 0xB5
    SCAN_PREVIOUS_TRACK = 0xB6
    STOP = 0xB7
    EJECT = 0xB8
    PLAY_PAUSE = 0xCD
    MUTE = 0xE2
    VOLUME_DECREMENT = 0xEA
    VOLUME_INCREMENT = 0xE9
    BRIGHTNESS_DECREMENT = 0x70
    BRIGHTNESS_INCREMENT = 0x6F
    AL_EMAIL_READER = 0x18A
    AL_CALCULATOR = 0x192
    AL_LOCAL_MACHINE_BROWSER = 0x194
    AL_INTERNET_BROWSER = 0x196


# Display names for keys, for the action line in the feedback window.
KEY_LABELS = {}
for _n, _v in vars(Keycode).items():
    if not _n.startswith("_") and _v not in KEY_LABELS:
        KEY_LABELS[_v] = _n.replace("_", " ").title()
KEY_LABELS.update({
    0x28: "Enter", 0x29: "Esc", 0x2A: "Backspace", 0x2C: "Space",
    0x4B: "Page Up", 0x4E: "Page Down", 0x4F: "Right", 0x50: "Left",
    0x51: "Down", 0x52: "Up", 0x53: "Num Lock", 0x65: "Menu",
    0x46: "Print Screen", 0x48: "Pause Key",
})
MOD_LABELS = ("Ctrl", "Shift", "Alt", "Win", "RCtrl", "RShift", "RAlt", "RWin")

# US keyboard: character -> (needs Shift, keycode)
US_CHARS = {}
for _i, _c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    US_CHARS[_c] = (False, 0x04 + _i)
    US_CHARS[_c.upper()] = (True, 0x04 + _i)
for _i, _c in enumerate("1234567890"):
    US_CHARS[_c] = (False, 0x1E + _i)
for _i, _c in enumerate("!@#$%^&*()"):
    US_CHARS[_c] = (True, 0x1E + _i)
for _plain, _shifted, _code in (
        ("-", "_", 0x2D), ("=", "+", 0x2E), ("[", "{", 0x2F), ("]", "}", 0x30),
        ("\\", "|", 0x31), (";", ":", 0x33), ("'", '"', 0x34), ("`", "~", 0x35),
        (",", "<", 0x36), (".", ">", 0x37), ("/", "?", 0x38)):
    US_CHARS[_plain] = (False, _code)
    US_CHARS[_shifted] = (True, _code)
US_CHARS[" "] = (False, 0x2C)
US_CHARS["\n"] = (False, 0x28)
US_CHARS["\t"] = (False, 0x2B)

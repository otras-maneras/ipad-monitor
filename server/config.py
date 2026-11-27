"""iPad Monitor — utilidades para iPad Mini 1 (iOS 9)."""

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765

IPAD_WIDTH = 1024
IPAD_HEIGHT = 768

JPEG_QUALITY = 52
TARGET_FPS = 12

DEFAULT_CAPTURE = {
    "monitor": 1,
    "left": 0,
    "top": 0,
    "width": IPAD_WIDTH,
    "height": IPAD_HEIGHT,
    "target_width": IPAD_WIDTH,
    "target_height": IPAD_HEIGHT,
    "full_monitor": False,
    "fit_mode": "fill",
}

QUALITY_PRESETS = {
    "ultra": {
        "jpeg_quality": 30,
        "target_fps": 12,
        "resize_method": "nearest",
        "jpeg_subsample": 2,
    },
    "turbo": {
        "jpeg_quality": 38,
        "target_fps": 16,
        "resize_method": "nearest",
        "jpeg_subsample": 2,
    },
    "balanced": {
        "jpeg_quality": 52,
        "target_fps": 12,
        "resize_method": "bilinear",
        "jpeg_subsample": 2,
    },
    "quality": {
        "jpeg_quality": 68,
        "target_fps": 10,
        "resize_method": "bilinear",
        "jpeg_subsample": 1,
    },
}

DEFAULT_PRESET = "ultra"

CONFIG = {
    "languages": ['en', 'de'],
    "screen_region": (50, 400, 500, 600),
    "scale_factor": 3,
    "y_merge_threshold": 18,
    "confidence_threshold": 0.8,
    "text_threshold": 0.6,

    # HSV bounds for chat text highlights (OpenCV HSV)
    # "team" (blue) and "all" (orange) chat colors in Overwatch
    "team_hsv_lower": [90, 140, 140],
    "team_hsv_upper": [110, 255, 255],
    "all_hsv_lower": [8, 160, 160],
    "all_hsv_upper": [18, 255, 255],

    "capture_interval": 2.0,
    "max_remembered": 2000,
}

IGNORED_SENDERS = {"team", "match"}
DEBUG_LEVEL = 2

LOG_FILE = "chat_log.csv"
SNAP_DIR = "debug_snaps"
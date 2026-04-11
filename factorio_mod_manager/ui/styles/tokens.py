"""Color and spacing tokens for the dark theme. Source of truth for dark_theme.qss."""

# Surface colors
BG_PRIMARY = "#0e0e0e"
BG_PANEL = "#1a1a1a"
BG_ROW_ALT = "#141414"
BG_INPUT = "#1a1a1a"
BG_INPUT_READONLY = "#111111"

# Text colors
FG_PRIMARY = "#e0e0e0"
FG_SECONDARY = "#b0b0b0"
FG_DISABLED = "#555555"

# Accent colors
ACCENT = "#0078d4"
ACCENT_HOVER = "#1084d7"
ACCENT_PRESSED = "#005fa3"
ACCENT_DISABLED_BG = "#1a2a3a"

# Semantic colors
SUCCESS = "#4ec952"
ERROR = "#d13438"
WARNING = "#ffad00"

# Notification overlay backgrounds
NOTIF_BG_SUCCESS = "#2d5016"
NOTIF_BG_ERROR = "#3a0f0f"
NOTIF_BG_WARNING = "#3a2f1a"
NOTIF_BG_INFO = "#1a2a3a"

# Border colors
BORDER_DEFAULT = "#3a3a3a"
BORDER_FOCUS = "#0078d4"
BORDER_READONLY = "#222222"
BORDER_HOVER = "#0078d4"

# Button hover/pressed states
BTN_HOVER_BG = "#2a2a2a"
BTN_PRESSED_BG = "#0a0a0a"
BTN_DESTR_BG = "#3a0f0f"
BTN_DESTR_HOVER_BG = "#4a1515"
BTN_DESTR_PRESSED_BG = "#2a0a0a"

# Table
TABLE_SELECTED_BG = "#1e3a1e"
TABLE_HEADER_BG = "#0e0e0e"

# Spacing (integer pixel values — for use in setContentsMargins / setSpacing)
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24

# Fixed dimensions
STATUS_BAR_HEIGHT = 28
NOTIF_MAX_WIDTH = 420

# Log line colors
LOG_INFO = "#0078d4"
LOG_DEBUG = "#b0b0b0"
LOG_WARNING = "#ffad00"
LOG_ERROR = "#d13438"
LOG_SUCCESS = "#4ec952"

# -- Phase 2 shell layout tokens -----------------------------
SPACING_2XL = 48      # Section breaks (UI-SPEC.md)
SPACING_3XL = 64      # Page-level top/bottom rhythm (UI-SPEC.md)
NAV_RAIL_WIDTH = 200  # Left navigation rail fixed width
SIDE_PANEL_WIDTH = 320  # Contextual side panel fixed width
PAGE_HEADER_HEIGHT = 48  # Per-page header zone height

# -- Phase 3 light theme tokens ----------------------------------
LIGHT_BG_PRIMARY = "#f5f5f5"
LIGHT_BG_PANEL = "#e8e8e8"
LIGHT_BG_INPUT = "#ffffff"
LIGHT_BG_INPUT_READONLY = "#eeeeee"
LIGHT_BG_ROW_ALT = "#efefef"
LIGHT_FG_PRIMARY = "#1a1a1a"
LIGHT_FG_SECONDARY = "#555555"
LIGHT_FG_DISABLED = "#aaaaaa"
LIGHT_ACCENT = "#0078d4"
LIGHT_ACCENT_HOVER = "#1084d7"
LIGHT_ACCENT_PRESSED = "#005fa3"
LIGHT_ACCENT_DISABLED_BG = "#cce0f5"
LIGHT_SUCCESS = "#107c10"
LIGHT_ERROR = "#d13438"
LIGHT_WARNING = "#ca5010"
LIGHT_BORDER_DEFAULT = "#d0d0d0"
LIGHT_BORDER_FOCUS = "#0078d4"
LIGHT_BORDER_HOVER = "#0078d4"
LIGHT_BORDER_READONLY = "#e0e0e0"
LIGHT_BTN_HOVER_BG = "#e0e0e0"
LIGHT_BTN_PRESSED_BG = "#d0d0d0"
LIGHT_BTN_DESTR_BG = "#fde7e9"
LIGHT_BTN_DESTR_HOVER_BG = "#f8c9cc"
LIGHT_BTN_DESTR_PRESSED_BG = "#f0b0b4"
LIGHT_TABLE_SELECTED_BG = "#cce0f5"
LIGHT_TABLE_HEADER_BG = "#f0f0f0"
LIGHT_NOTIF_BG_SUCCESS = "#dff6dd"
LIGHT_NOTIF_BG_ERROR = "#fde7e9"
LIGHT_NOTIF_BG_WARNING = "#fff4ce"
LIGHT_NOTIF_BG_INFO = "#cce0f5"

# -- Phase 4 queue tokens ----------------------------------------
QUEUE_DRAWER_WIDTH = 360       # Right-edge queue drawer fixed width
QUEUE_BADGE_SIZE = 28          # Header badge button fixed width/height
QUEUE_CARD_RADIUS = 4          # Queue item card border radius
QUEUE_CHIP_RADIUS = 10         # State chip border radius

# Queue badge colors
QUEUE_BADGE_BG = "#1a1a1a"
QUEUE_BADGE_ACTIVE_BG = "#0078d4"
QUEUE_BADGE_FAILED_DOT = "#d13438"

# State chip colors (dark)
QUEUE_CHIP_QUEUED_BG = "#1a2a3a"
QUEUE_CHIP_RUNNING_BG = "#1a2a3a"
QUEUE_CHIP_PAUSED_BG = "#3a2f1a"
QUEUE_CHIP_COMPLETED_BG = "#1e2e1e"
QUEUE_CHIP_FAILED_BG = "#3a0f0f"
QUEUE_CHIP_CANCELED_BG = "#222222"

# Light theme equivalents
LIGHT_QUEUE_BADGE_BG = "#f0f0f0"
LIGHT_QUEUE_BADGE_ACTIVE_BG = "#0078d4"
LIGHT_QUEUE_CHIP_QUEUED_BG = "#cce0f5"
LIGHT_QUEUE_CHIP_RUNNING_BG = "#cce0f5"
LIGHT_QUEUE_CHIP_PAUSED_BG = "#fff4ce"
LIGHT_QUEUE_CHIP_COMPLETED_BG = "#dff6dd"
LIGHT_QUEUE_CHIP_FAILED_BG = "#fde7e9"
LIGHT_QUEUE_CHIP_CANCELED_BG = "#e8e8e8"

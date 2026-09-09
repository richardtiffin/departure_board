import pygame
from datetime import datetime
import time
import logging
import requests
import sys
import json
from json import JSONDecodeError

# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    filename="departure_boardmk2.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# ============================================================
# Configuration
# ============================================================

CONFIG_PATH = "configmk3.json"

TOC_NAMES = {
    "GW": "GWR",
    "AW": "Transport for Wales",
    "XC": "CrossCountry",
    "EM": "East Midlands Railway",
    "GR": "GNER",
    "LE": "Greater Anglia",
    "LM": "London Northwestern Railway",
    "SE": "Southeastern",
    "SN": "Southern",
    "SW": "South Western Railway",
    "TL": "Thameslink",
    "VT": "Avanti West Coast",
    "GC": "Grand Central",
    "HT": "Hull Trains",
    "LD": "Lumo",
    "CC": "c2c",
    "GX": "Gatwick Express",
    "TP": "TransPennine Express",
    "SR": "ScotRail",
    "NT": "Northern"
}

SAMPLE_CONFIG = {
    "API_URL": "http://192.168.0.146:8085/departures",

    "SELECT_STATIONS": [
        "BGN",
        "CDF",
        "NCL",
        "MAN"
    ],

    "STATIONS": {
        "BGN": {
            "NAME": "Bridgend",
            "PLATFORMS": [0, 1, 2, 3, 4, 6, 7, 8],
            "LATITUDE": 51.5069,
            "LONGITUDE": -3.5753,
            "TIPLOC": "BRGEND"
        }
    },

    "STATION_ROTATE_INTERVAL": 100,
    "SCREEN_ROTATE_INTERVAL": 20,
    "UPDATE_INTERVAL": 60,

    "TEST_MODE": False,
    "ROTATE_DISPLAY": False,

    "SCROLL_SPEED": 9,
    "SCROLL_GAP": 200,

    "CLOCK_FONT_SIZE": 40,
    "PLATFORM_FONT_SIZE": 40,
    "STATION_FONT_SIZE": 50,
    "TRAIN_FONT_SIZE": 30,
    "STATUS_FONT_SIZE": 20,

    "WINDOW_WIDTH": 2560,
    "WINDOW_HEIGHT": 1440,

    "FULLSCREEN": True,

    "NSERVICE": 28,
    "TRAINSPERSCREEN": 7
}


try:
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

except FileNotFoundError:
    logging.error("configmk2.json not found. Creating sample file and exiting.")

    with open("config.sample.json", "w") as sample:
        json.dump(SAMPLE_CONFIG, sample, indent=4)

    print("configmk2.json not found. Sample created.")
    sys.exit(1)

except JSONDecodeError as e:
    logging.error(f"configmk2.json JSON error: {e}")
    sys.exit(1)


# ============================================================
# Configuration values
# ============================================================

API_URL = config.get(
    "API_URL",
    "http://192.168.0.146:8085/departures"
)

SELECT_STATIONS = config.get("SELECT_STATIONS")
ALL_STATIONS = config.get("STATIONS", {})

STATION_ROTATE_INTERVAL = config.get(
    "STATION_ROTATE_INTERVAL",
    60
)

SCREEN_ROTATE_INTERVAL = config.get(
    "SCREEN_ROTATE_INTERVAL",
    20
)

UPDATE_INTERVAL = config.get(
    "UPDATE_INTERVAL",
    60
)

TEST_MODE = config.get(
    "TEST_MODE",
    False
)

ROTATE_DISPLAY = config.get(
    "ROTATE_DISPLAY",
    False
)

SCROLL_SPEED = config.get(
    "SCROLL_SPEED",
    14
)

SCROLL_GAP = config.get(
    "SCROLL_GAP",
    200
)

CLOCK_FONT_SIZE = config.get(
    "CLOCK_FONT_SIZE",
    148
)

STATION_FONT_SIZE = config.get(
    "STATION_FONT_SIZE",
    80
)

PLATFORM_FONT_SIZE = config.get(
    "PLATFORM_FONT_SIZE",
    72
)

TRAIN_FONT_SIZE = config.get(
    "TRAIN_FONT_SIZE",
    56
)

STATUS_FONT_SIZE = config.get(
    "STATUS_FONT_SIZE",
    50
)

WINDOW_WIDTH = config.get(
    "WINDOW_WIDTH",
    800
)

WINDOW_HEIGHT = config.get(
    "WINDOW_HEIGHT",
    480
)

FULLSCREEN = config.get(
    "FULLSCREEN",
    False
)

NSERVICE = config.get(
    "NSERVICE",
    6
)

TRAINSPERSCREEN = config.get(
    "TRAINSPERSCREEN",
    10
)


# Only use the stations selected in the configuration.
if SELECT_STATIONS:
    STATIONS = {
        code: ALL_STATIONS[code]
        for code in SELECT_STATIONS
        if code in ALL_STATIONS
    }
else:
    STATIONS = ALL_STATIONS


if not STATIONS:
    logging.error("No stations configured.")
    print("No stations configured in SELECT_STATIONS/STATIONS.")
    sys.exit(1)


logging.info(f"Rail departure API: {API_URL}")
logging.info(f"Configured stations: {list(STATIONS.keys())}")


# ============================================================
# Pygame setup
# ============================================================

pygame.mixer.pre_init(0, 0, 0, 0)
pygame.init()
pygame.mixer.quit()

if FULLSCREEN:
    screen = pygame.display.set_mode(
        (0, 0),
        pygame.FULLSCREEN
    )
else:
    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT)
    )

WINDOW_WIDTH, WINDOW_HEIGHT = screen.get_size()

BLACK = (0, 0, 0)
ORANGE = (255, 165, 0)
RED = (255, 0, 0)


# ============================================================
# Fonts
# ============================================================

font_path = "fonts/bus-stop.ttf"

try:
    clock_font = pygame.font.Font(
        font_path,
        CLOCK_FONT_SIZE
    )

    station_font = pygame.font.Font(
        font_path,
        STATION_FONT_SIZE
    )

    platform_font = pygame.font.Font(
        font_path,
        PLATFORM_FONT_SIZE
    )

    train_font = pygame.font.Font(
        font_path,
        TRAIN_FONT_SIZE
    )

    status_font = pygame.font.Font(
        font_path,
        STATUS_FONT_SIZE
    )

except Exception:
    logging.warning(
        "Could not load bus-stop font. Using system fonts."
    )

    clock_font = pygame.font.SysFont(
        None,
        CLOCK_FONT_SIZE
    )

    station_font = pygame.font.SysFont(
        None,
        STATION_FONT_SIZE
    )

    platform_font = pygame.font.SysFont(
        None,
        PLATFORM_FONT_SIZE
    )

    train_font = pygame.font.SysFont(
        None,
        TRAIN_FONT_SIZE
    )

    status_font = pygame.font.SysFont(
        None,
        STATUS_FONT_SIZE
    )


# ============================================================
# Scrolling text
# ============================================================

class ScrollingText:

    def __init__(
        self,
        y_pos,
        text,
        label_surface,
        x_margin=10,
        gap=SCROLL_GAP
    ):

        self.text = text

        rendered_text = train_font.render(
            self.text,
            True,
            ORANGE
        )

        self.text_width = rendered_text.get_width()

        self.surface = pygame.Surface(
            (
                self.text_width,
                train_font.get_height()
            ),
            pygame.SRCALPHA
        )

        self.surface.blit(
            rendered_text,
            (0, 0)
        )

        self.y_pos = y_pos

        self.x_start = (
            label_surface.get_width()
            + x_margin
        )

        self.x_pos = self.x_start

        self.speed = SCROLL_SPEED
        self.gap = gap

        self.clip_width = (
            WINDOW_WIDTH
            - self.x_start
            - 20
        )

    def update(self):

        self.x_pos -= self.speed

        if (
            self.x_pos
            < self.x_start
            - self.text_width
            - self.gap
        ):

            self.x_pos += (
                self.text_width
                + self.gap
            )

    def draw(
        self,
        surface,
        clip_rect=None
    ):

        if clip_rect:
            surface.set_clip(clip_rect)

        surface.blit(
            self.surface,
            (
                self.x_pos,
                self.y_pos
            )
        )

        surface.blit(
            self.surface,
            (
                self.x_pos
                + self.text_width
                + self.gap,
                self.y_pos
            )
        )

        surface.set_clip(None)


# ============================================================
# API helpers
# ============================================================

def format_time(value):
    """
    Convert an API time value into HH:MM.

    Handles:
        HH:MM
        HH:MM:SS
        None
        empty strings
    """

    if not value:
        return ""

    value = str(value).strip()

    if len(value) >= 5:
        return value[:5]

    return value


def parse_time_to_seconds(value):
    """
    Convert HH:MM or HH:MM:SS into seconds after midnight.

    Returns None if the value cannot be parsed.
    """

    if not value:
        return None

    try:
        parts = str(value).split(":")

        hour = int(parts[0])
        minute = int(parts[1])

        second = (
            int(parts[2])
            if len(parts) > 2
            else 0
        )

        return (
            hour * 3600
            + minute * 60
            + second
        )

    except (ValueError, TypeError, IndexError):
        return None


def get_service_status(service):
    """
    Determine the display status from the API's
    timetable and realtime departure information.

    The timetable remains the displayed scheduled time.
    Darwin realtime is shown as the expected/actual status.
    """

    # --------------------------------------------------------
    # Check for explicit cancellation information.
    # --------------------------------------------------------

    if service.get("cancelled") is True:
        return "Cancelled", True

    if service.get("is_cancelled") is True:
        return "Cancelled", True

    status_value = service.get("status")

    if isinstance(status_value, str):
        if status_value.lower() == "cancelled":
            return "Cancelled", True

    departure = service.get("departure") or {}

    if departure.get("cancelled") is True:
        return "Cancelled", True

    # --------------------------------------------------------
    # Timetable and realtime departure
    # --------------------------------------------------------

    timetable = departure.get("public")
    realtime = departure.get("realtime")

    if not realtime:
        return "On time", False

    timetable_seconds = parse_time_to_seconds(timetable)
    realtime_seconds = parse_time_to_seconds(realtime)

    if (
        timetable_seconds is None
        or realtime_seconds is None
    ):
        return "On time", False

    if timetable_seconds == realtime_seconds:
        return "On time", False

    # --------------------------------------------------------
    # Darwin gives us an actual/estimated departure.
    # Preserve the scheduled time in the main time column
    # and show the realtime time in the status column.
    # --------------------------------------------------------

    realtime_display = format_time(realtime)

    basis = (
        departure.get("realtime_basis")
        or ""
    ).lower()

    if basis == "actual":
        return f"Dep {realtime_display}", False

    return f"Exp {realtime_display}", True


def get_calling_point_name(point):
    """
    Get the human-readable station name from the API.

    Convert timetable names from ALL CAPS to normal
    capitalised station names for the display.
    """

    name = (
        point.get("name")
        or point.get("station")
        or point.get("locationName")
        or point.get("crs")
        or point.get("tiploc")
        or "Unknown"
    )

    name = str(name).strip()

    # Only alter names which are entirely uppercase.
    # This avoids damaging names which already contain
    # intentional mixed case.
    if name.isupper():
        name = name.title()

    return name


def get_calling_point_time(point):
    """
    Get the TIMETABLED time for a calling point.

    Deliberately does NOT use Darwin realtime here.

    The timetable defines the calling points and their
    scheduled times. Realtime is only used for the current
    departure status.
    """

    arrival = point.get("arrival") or {}
    departure = point.get("departure") or {}

    timetable_departure = departure.get("public")

    if timetable_departure:
        return format_time(timetable_departure)

    timetable_arrival = arrival.get("timetable")

    if timetable_arrival:
        return format_time(timetable_arrival)

    return ""


def find_station_call(service, station_code):
    """
    Find the calling point corresponding to the station
    requested from the API.
    """

    calling_points = service.get("calling_points") or []

    station_code = station_code.upper()

    for point in calling_points:

        point_crs = str(
            point.get("crs") or ""
        ).upper()

        if point_crs == station_code:
            return point

    return None


def build_calling_at(service, station_code):
    """
    Build the 'Calling at:' text.

    Only timetable calling points after the current station
    are included.

    Realtime updates from Redis/Darwin are deliberately not
    used to create or remove calling points.
    """

    calling_points = service.get(
        "calling_points"
    ) or []

    if not calling_points:
        return ""

    station_code = station_code.upper()

    current_index = None

    for index, point in enumerate(calling_points):

        point_crs = str(
            point.get("crs") or ""
        ).upper()

        if point_crs == station_code:
            current_index = index
            break

    if current_index is None:
        return ""

    subsequent_points = calling_points[
        current_index + 1:
    ]

    result = []

    for point in subsequent_points:

        name = get_calling_point_name(point)

        timetable_time = get_calling_point_time(
            point
        )

        if timetable_time:
            result.append(
                f"{name} ({timetable_time})"
            )
        else:
            result.append(name)

    return ", ".join(result)


# ============================================================
# Fetch departures from FastAPI
# ============================================================

def fetch_departures(
    station_code,
    current_screen_index
):
    """
    Fetch departures from the FastAPI rail API.

    The API is responsible for finding the correct services
    for the requested station/date. The display only handles
    pagination of the returned list.

    Returns a list of tuples compatible with the existing
    display renderer.
    """

    if TEST_MODE:
        logging.info(
            f"TEST_MODE enabled - no API request for {station_code}"
        )
        return []

    try:

        params = {
            "crs": station_code,
            "limit": NSERVICE
        }

        logging.info(
            f"Requesting departures: "
            f"{API_URL} "
            f"crs={station_code} "
            f"limit={NSERVICE}"
        )

        response = requests.get(
            API_URL,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            logging.error(
                f"Unexpected API response for "
                f"{station_code}: {type(data)}"
            )
            return []

        # ----------------------------------------------------
        # API already returns the correct services for the
        # requested station. We only paginate them for the
        # physical display.
        # ----------------------------------------------------

        start = (
            current_screen_index
            * TRAINSPERSCREEN
        )

        end = (
            start
            + TRAINSPERSCREEN
        )

        page_services = data[start:end]

        services = []

        for service in page_services:

            departure = service.get(
                "departure"
            ) or {}

            departure_time = format_time(
                departure.get("public")
            )

            destination = (
                service.get("destination")
                or "Unknown"
            )

            if destination.isupper():
                destination = destination.title()


            # ------------------------------------------------
            # Prefer the platform supplied at the station
            # level by the API.
            # ------------------------------------------------

            platform = (
                service.get("platform")
                or "N/A"
            )

            # ------------------------------------------------
            # If the top-level platform is missing, look at
            # the requested station's calling point.
            # ------------------------------------------------

            if platform == "N/A":

                station_call = find_station_call(
                    service,
                    station_code
                )

                if station_call:
                    platform = (
                        station_call.get("platform")
                        or "N/A"
                    )

            platform = str(platform)

            # ------------------------------------------------
            # Operator / TOC
            # ------------------------------------------------

            toc = (
                service.get("toc")
                or ""
            ).upper()

            operator = TOC_NAMES.get(
                toc,
                toc
            )

            # ------------------------------------------------
            # Status based on timetable vs Darwin realtime.
            # ------------------------------------------------

            status, status_alert = get_service_status(
                service
            )

            # ------------------------------------------------
            # Timetable-authoritative calling points.
            # ------------------------------------------------

            calling_at = build_calling_at(
                service,
                station_code
            )

            services.append(
                (
                    departure_time,
                    destination,
                    platform,
                    calling_at,
                    status,
                    operator,
                    status_alert
                )
            )

        logging.info(
            f"API returned {len(data)} departures "
            f"for {station_code}; "
            f"displaying {len(services)} "
            f"on page {current_screen_index + 1}"
        )

        return services

    except requests.exceptions.RequestException as e:

        logging.error(
            f"API request failed for "
            f"{station_code}: {e}"
        )

        print(
            f"API ERROR for {station_code}: {e}"
        )

        return []

    except ValueError as e:

        logging.error(
            f"Invalid JSON from API for "
            f"{station_code}: {e}"
        )

        print(
            f"API JSON ERROR for {station_code}: {e}"
        )

        return []

    except Exception as e:

        logging.exception(
            f"Unexpected API error for "
            f"{station_code}: {e}"
        )

        print(
            f"API ERROR for {station_code}: {e}"
        )

        return []


# ============================================================
# Display renderer
# ============================================================

def update_display_multi_platform_with_calling_at(
    departures,
    static_text,
    scrolling_texts
):

    static_text.clear()
    scrolling_texts.clear()

    y_pos = (
        station_font.get_height()
        + 50
    )

    if not departures:
        return False

    for dep in departures:

        (
            departure_time,
            destination,
            platform,
            calling_at,
            status,
            operator,
            status_alert
        ) = dep

        line_y = y_pos

        # ----------------------------------------------------
        # Column positions
        # ----------------------------------------------------

        x_time = 10
        x_dest = 200
        x_plat = 700
        x_op = 860

        # ----------------------------------------------------
        # Departure time
        # ----------------------------------------------------

        static_text.append(
            (
                train_font.render(
                    departure_time,
                    True,
                    ORANGE
                ),
                (
                    x_time,
                    line_y
                )
            )
        )

        # ----------------------------------------------------
        # Destination
        # ----------------------------------------------------

        static_text.append(
            (
                train_font.render(
                    destination,
                    True,
                    ORANGE
                ),
                (
                    x_dest,
                    line_y
                )
            )
        )

        # ----------------------------------------------------
        # Platform
        # ----------------------------------------------------

        platform_text = f"Plat {platform}"

        static_text.append(
            (
                train_font.render(
                    platform_text,
                    True,
                    ORANGE
                ),
                (
                    x_plat,
                    line_y
                )
            )
        )

        # ----------------------------------------------------
        # Operator / TOC
        # ----------------------------------------------------

        if operator:

            operator_text = f"({operator})"

            static_text.append(
                (
                    train_font.render(
                        operator_text,
                        True,
                        ORANGE
                    ),
                    (
                        x_op,
                        line_y
                    )
                )
            )

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        status_colour = (
            RED
            if status_alert
            else ORANGE
        )

        status_surface = status_font.render(
            status,
            True,
            status_colour
        )

        status_x = (
            WINDOW_WIDTH
            - status_surface.get_width()
            - 30
        )

        status_y = (
            line_y
            + (
                train_font.get_height()
                - status_surface.get_height()
            ) // 2
        )

        static_text.append(
            (
                status_surface,
                (
                    status_x,
                    status_y
                )
            )
        )

        # ----------------------------------------------------
        # Calling at
        # ----------------------------------------------------

        if calling_at:

            y_pos += (
                train_font.get_height()
                + 5
            )

            label_surface = train_font.render(
                "Calling at:",
                True,
                ORANGE
            )

            static_text.append(
                (
                    "CALLING_AT_LABEL",
                    (
                        20,
                        y_pos
                    ),
                    label_surface
                )
            )

            scrolling_texts.append(
                ScrollingText(
                    y_pos,
                    calling_at,
                    label_surface,
                    x_margin=150,
                    gap=SCROLL_GAP
                )
            )

            y_pos += (
                train_font.get_height()
                + 5
            )

        y_pos += (
            train_font.get_height()
            + status_font.get_height()
            - 40
        )

    y_pos += 10

    return True


# ============================================================
# Weather
# ============================================================

def get_temperature(lat, lon):

    try:

        if lat is None or lon is None:
            return "N/A"

        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}"
            f"&longitude={lon}"
            "&current_weather=true"
        )

        response = requests.get(
            url,
            timeout=5
        )

        response.raise_for_status()

        data = response.json()

        current_weather = data.get(
            "current_weather"
        )

        if (
            current_weather
            and "temperature"
            in current_weather
        ):

            return (
                f"{round(current_weather['temperature'])}°C"
            )

        return "N/A"

    except Exception:

        return "N/A"


# ============================================================
# Main
# ============================================================

def main():

    clock = pygame.time.Clock()

    static_text = []
    scrolling_texts = []

    static_surface = pygame.Surface(
        (
            WINDOW_WIDTH,
            WINDOW_HEIGHT
        )
    ).convert()

    static_surface.fill(BLACK)

    last_update_time = 0
    last_temp_update = 0

    station_codes = list(
        STATIONS.keys()
    )

    station_index = 0
    current_screen_index = 0

    last_station_rotate = time.time()
    last_screen_rotate = time.time()

    departures = {}

    NO_DEPARTURES_COOLDOWN = 60

    allTemp = {
        code: "N/A"
        for code in station_codes
    }

    # --------------------------------------------------------
    # Initial station
    # --------------------------------------------------------

    STATION_CODE = station_codes[
        station_index
    ]

    current_station = STATIONS[
        STATION_CODE
    ]

    current_temp = allTemp.get(
        STATION_CODE,
        "N/A"
    )

    # --------------------------------------------------------
    # Number of display pages.
    #
    # The API supplies NSERVICE services and the display
    # shows TRAINSPERSCREEN services at a time.
    # --------------------------------------------------------

    page_count = max(
        1,
        (
            NSERVICE
            + TRAINSPERSCREEN
            - 1
        )
        // TRAINSPERSCREEN
    )

    running = True

    while running:

        now = time.time()

        # ====================================================
        # Events
        # ====================================================

        for event in pygame.event.get():

            if event.type == pygame.QUIT:

                running = False

            elif (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_ESCAPE
            ):

                running = False

        # ====================================================
        # Temperature update every 10 minutes
        # ====================================================

        if now - last_temp_update >= 600:

            for code in station_codes:

                station_for_temp = STATIONS[
                    code
                ]

                allTemp[code] = get_temperature(
                    station_for_temp.get(
                        "LATITUDE"
                    ),
                    station_for_temp.get(
                        "LONGITUDE"
                    )
                )

            last_temp_update = now

        # ====================================================
        # Rotate station
        # ====================================================

        station_changed = False

        if (
            now - last_station_rotate
            >= STATION_ROTATE_INTERVAL
        ):

            station_index = (
                station_index + 1
            ) % len(station_codes)

            current_screen_index = 0

            last_station_rotate = now

            station_changed = True

        # ====================================================
        # Rotate display page
        # ====================================================

        page_changed = False

        if (
            now - last_screen_rotate
            >= SCREEN_ROTATE_INTERVAL
        ):

            current_screen_index = (
                current_screen_index + 1
            ) % page_count

            last_screen_rotate = now

            page_changed = True

        # ====================================================
        # Fetch departures when required
        # ====================================================

        draw_ready = False

        if (
            station_changed
            or page_changed
            or now - last_update_time
            >= UPDATE_INTERVAL
        ):

            STATION_CODE = station_codes[
                station_index
            ]

            current_station = STATIONS[
                STATION_CODE
            ]

            current_temp = allTemp.get(
                STATION_CODE,
                "N/A"
            )

            if station_changed:

                current_screen_index = 0

            # ------------------------------------------------
            # Try the requested page first, then any other
            # page if it happens to be empty.
            # ------------------------------------------------

            attempts = 0

            start_index = (
                current_screen_index
            )

            while attempts < page_count:

                idx = (
                    start_index
                    + attempts
                ) % page_count

                departures = fetch_departures(
                    STATION_CODE,
                    idx
                )

                success = (
                    update_display_multi_platform_with_calling_at(
                        departures,
                        static_text,
                        scrolling_texts
                    )
                )

                if success:

                    static_surface.fill(
                        BLACK
                    )

                    for item in static_text:

                        if isinstance(
                            item[0],
                            pygame.Surface
                        ):

                            static_surface.blit(
                                item[0],
                                item[1]
                            )

                        elif (
                            isinstance(
                                item[0],
                                str
                            )
                            and item[0]
                            == "CALLING_AT_LABEL"
                        ):

                            static_surface.blit(
                                item[2],
                                item[1]
                            )

                    last_update_time = now

                    draw_ready = True

                    current_screen_index = idx

                    break

                attempts += 1

            # =================================================
            # No departures
            # =================================================

            if not draw_ready:

                logging.info(
                    f"No departures for "
                    f"station {STATION_CODE} "
                    f"on any page. "
                    f"Backing off "
                    f"{NO_DEPARTURES_COOLDOWN}s."
                )

                static_surface.fill(
                    BLACK
                )

                no_dep_text = train_font.render(
                    "No departures",
                    True,
                    ORANGE
                )

                station_name_text = station_font.render(
                    current_station.get(
                        "NAME",
                        ""
                    ),
                    True,
                    ORANGE
                )

                static_surface.blit(
                    station_name_text,
                    (
                        (
                            WINDOW_WIDTH
                            - station_name_text.get_width()
                        ) // 2,
                        40
                    )
                )

                static_surface.blit(
                    no_dep_text,
                    (
                        (
                            WINDOW_WIDTH
                            - no_dep_text.get_width()
                        ) // 2,
                        (
                            WINDOW_HEIGHT
                            // 2
                            - no_dep_text.get_height()
                            // 2
                        )
                    )
                )

                screen.blit(
                    static_surface,
                    (0, 0)
                )

                pygame.display.flip()

                # ------------------------------------------------
                # Move to next station.
                # ------------------------------------------------

                station_index = (
                    station_index + 1
                ) % len(station_codes)

                last_station_rotate = now
                last_update_time = now

                backoff_end = (
                    time.time()
                    + NO_DEPARTURES_COOLDOWN
                )

                while (
                    time.time()
                    < backoff_end
                ):

                    for event in pygame.event.get():

                        if event.type == pygame.QUIT:

                            running = False
                            break

                        if (
                            event.type
                            == pygame.KEYDOWN
                            and event.key
                            == pygame.K_ESCAPE
                        ):

                            running = False
                            break

                    if not running:
                        break

                    current_time = datetime.now().strftime(
                        "%H:%M:%S"
                    )

                    clock_text = clock_font.render(
                        current_time,
                        True,
                        ORANGE
                    )

                    frame_surface = pygame.Surface(
                        (
                            WINDOW_WIDTH,
                            WINDOW_HEIGHT
                        )
                    ).convert()

                    frame_surface.blit(
                        static_surface,
                        (0, 0)
                    )

                    frame_surface.blit(
                        clock_text,
                        (
                            (
                                WINDOW_WIDTH
                                - clock_text.get_width()
                            ) // 2,
                            WINDOW_HEIGHT
                            - clock_text.get_height()
                            - 20
                        )
                    )

                    screen.blit(
                        frame_surface,
                        (0, 0)
                    )

                    pygame.display.flip()

                    clock.tick(1)

        # ====================================================
        # Normal frame
        # ====================================================

        frame_surface = pygame.Surface(
            (
                WINDOW_WIDTH,
                WINDOW_HEIGHT
            )
        ).convert()

        frame_surface.blit(
            static_surface,
            (0, 0)
        )

        # ----------------------------------------------------
        # Scrolling calling points
        # ----------------------------------------------------

        for text in scrolling_texts:

            clip_rect = pygame.Rect(
                text.x_start,
                text.y_pos,
                text.clip_width,
                train_font.get_height()
            )

            text.update()

            text.draw(
                frame_surface,
                clip_rect
            )

        # ====================================================
        # Clock / temperature / station
        # ====================================================

        current_time = datetime.now().strftime(
            "%H:%M:%S"
        )

        clock_text = clock_font.render(
            current_time,
            True,
            ORANGE
        )

        temp_text = train_font.render(
            current_temp,
            True,
            ORANGE
        )

        station_text = station_font.render(
            current_station.get(
                "NAME",
                ""
            ),
            True,
            ORANGE
        )

        clock_x = (
            WINDOW_WIDTH
            - clock_text.get_width()
        ) // 2

        clock_y = (
            WINDOW_HEIGHT
            - clock_text.get_height()
            - 20
        )

        temp_x = (
            clock_x
            + clock_text.get_width()
            + 60
        )

        temp_y = (
            clock_y
            + (
                clock_text.get_height()
                - temp_text.get_height()
            ) // 2
        )

        station_x = (
            WINDOW_WIDTH
            - station_text.get_width()
        ) // 2

        station_y = 20

        # ----------------------------------------------------
        # Background behind clock
        # ----------------------------------------------------

        pygame.draw.rect(
            frame_surface,
            BLACK,
            (
                clock_x - 10,
                clock_y - 10,
                clock_text.get_width()
                + temp_text.get_width()
                + 70,
                clock_text.get_height()
                + 20
            )
        )

        # ----------------------------------------------------
        # Station
        # ----------------------------------------------------

        frame_surface.blit(
            station_text,
            (
                station_x,
                station_y
            )
        )

        # ----------------------------------------------------
        # Clock
        # ----------------------------------------------------

        frame_surface.blit(
            clock_text,
            (
                clock_x,
                clock_y
            )
        )

        # ----------------------------------------------------
        # Temperature
        # ----------------------------------------------------

        frame_surface.blit(
            temp_text,
            (
                temp_x,
                temp_y
            )
        )

        # ----------------------------------------------------
        # Rotate display if configured
        # ----------------------------------------------------

        if ROTATE_DISPLAY:

            frame_surface = pygame.transform.rotate(
                frame_surface,
                180
            )

        screen.blit(
            frame_surface,
            (0, 0)
        )

        pygame.display.flip()

        clock.tick(60)

    pygame.quit()


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()
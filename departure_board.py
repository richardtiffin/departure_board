import pygame
import zeep
from datetime import datetime
import json
import time
import logging
import requests
import sys
from json import JSONDecodeError

# === Setup logging ===
logging.basicConfig(
    filename="departure_board.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# === Load configuration safely ===
CONFIG_PATH = "config.json"
SAMPLE_CONFIG = {
    "API_KEY": "YOUR_API_KEY_HERE",
    "STATION_CODE": "PAD",
    "TARGET_PLATFORMS": [1, 2],
    "TEST_MODE": True,
    "UPDATE_INTERVAL": 30,
    "ROTATE_DISPLAY": False,
    "SCROLL_SPEED": 14,
    "SCROLL_GAP": 200,
    "CLOCK_FONT_SIZE": 148,
    "PLATFORM_FONT_SIZE": 72,
    "TRAIN_FONT_SIZE": 56,
    "STATUS_FONT_SIZE": 50,
    "LATITUDE": 51.5074,
    "LONGITUDE": -0.1278
}

try:
    with open(CONFIG_PATH, "r") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    logging.error("config.json not found. Creating sample file and exiting.")
    with open("config.sample.json", "w") as sample:
        json.dump(SAMPLE_CONFIG, sample, indent=4)
    print("config.json not found. A sample config has been written to config.sample.json. Please copy it to config.json and edit values.")
    sys.exit(1)
except JSONDecodeError as e:
    logging.error(f"config.json JSON error: {e}")
    print(f"config.json contains invalid JSON: {e}")
    sys.exit(1)

API_KEY = config.get("API_KEY")
STATION_CODE = config.get("STATION_CODE")
TARGET_PLATFORMS = [str(p) for p in config.get("TARGET_PLATFORMS", [])]
TEST_MODE = config.get("TEST_MODE", False)
UPDATE_INTERVAL = config.get("UPDATE_INTERVAL", 30)
ROTATE_DISPLAY = config.get("ROTATE_DISPLAY", False)
SCROLL_SPEED = config.get("SCROLL_SPEED", 14)
SCROLL_GAP = config.get("SCROLL_GAP", 200)
CLOCK_FONT_SIZE = config.get("CLOCK_FONT_SIZE", 148)
PLATFORM_FONT_SIZE = config.get("PLATFORM_FONT_SIZE", 72)
TRAIN_FONT_SIZE = config.get("TRAIN_FONT_SIZE", 56)
STATUS_FONT_SIZE = config.get("STATUS_FONT_SIZE", 50)
LATITUDE = config.get("LATITUDE")
LONGITUDE = config.get("LONGITUDE")
PLATFORMS_PER_SCREEN = config.get("PLATFORMS_PER_SCREEN", 4)
SCREEN_ROTATE_INTERVAL = config.get("SCREEN_ROTATE_INTERVAL", 20)


# === Set up SOAP client (defensive) ===
WSDL_URL = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"
soap_client = None
soap_header_value = None
try:
    soap_client = zeep.Client(wsdl=WSDL_URL)
    header = zeep.xsd.Element(
        "{http://thalesgroup.com/RTTI/2013-11-28/Token/types}AccessToken",
        zeep.xsd.ComplexType([zeep.xsd.Element("TokenValue", zeep.xsd.String())]),
    )
    soap_header_value = header(TokenValue=API_KEY)
    logging.info("SOAP client initialised.")
except Exception as e:
    logging.error(f"Failed to initialise SOAP client: {e}")
    if not TEST_MODE:
        logging.warning("Switching to TEST_MODE because SOAP is unavailable.")
        TEST_MODE = True

# === Initialize Pygame ===
pygame.mixer.pre_init(0, 0, 0, 0)
pygame.init()
pygame.mixer.quit()

screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
WINDOW_WIDTH, WINDOW_HEIGHT = screen.get_size()

BLACK = (0, 0, 0)
ORANGE = (255, 165, 0)
PLATFORM_BG_COLOR = (50, 50, 50)

font_path = "fonts/bus-stop.ttf"
try:
    clock_font = pygame.font.Font(font_path, CLOCK_FONT_SIZE)
    platform_font = pygame.font.Font(font_path, PLATFORM_FONT_SIZE)
    train_font = pygame.font.Font(font_path, TRAIN_FONT_SIZE)
    status_font = pygame.font.Font(font_path, STATUS_FONT_SIZE)
except Exception as e:
    logging.warning(f"Failed to load custom font ({font_path}): {e}. Falling back to system fonts.")
    clock_font = pygame.font.SysFont(None, CLOCK_FONT_SIZE)
    platform_font = pygame.font.SysFont(None, PLATFORM_FONT_SIZE)
    train_font = pygame.font.SysFont(None, TRAIN_FONT_SIZE)
    status_font = pygame.font.SysFont(None, STATUS_FONT_SIZE)

# === Scrolling Text class ===
class ScrollingText:
    def __init__(self, y_pos, text, label_surface, x_margin=10, gap=SCROLL_GAP):
        self.text = text
        rendered_text = train_font.render(self.text, True, ORANGE)
        self.text_width = rendered_text.get_width()
        self.surface = pygame.Surface((self.text_width, train_font.get_height()), pygame.SRCALPHA).convert_alpha()
        self.surface.blit(rendered_text, (0, 0))
        self.y_pos = y_pos
        self.x_start = label_surface.get_width() + x_margin
        self.x_pos = self.x_start
        self.speed = SCROLL_SPEED
        self.gap = gap
        self.clip_width = WINDOW_WIDTH - self.x_start - 20

    def update(self):
        self.x_pos -= self.speed
        if self.x_pos < self.x_start - self.text_width - self.gap:
            self.x_pos += self.text_width + self.gap

    def draw(self, surface, clip_rect=None):
        if clip_rect:
            surface.set_clip(clip_rect)
        surface.blit(self.surface, (self.x_pos, self.y_pos))
        surface.blit(self.surface, (self.x_pos + self.text_width + self.gap, self.y_pos))
        surface.set_clip(None)

# === Fetch test departures ===
def fetch_test_data_grouped(target_platforms):
    try:
        with open("test_data.json", "r") as file:
            test_data = json.load(file)
            platform_map = {platform: [] for platform in target_platforms}
            for entry in test_data:
                platform = str(entry.get("platform"))
                if platform in platform_map and len(platform_map[platform]) < 2:
                    platform_map[platform].append(
                        (entry["departure_time"], entry["destination"], entry.get("calling_at", ""), entry.get("status", "On time"))
                    )
            return platform_map
    except Exception as e:
        logging.error(f"Error loading test data: {e}")
        return {p: [] for p in target_platforms}

# === Fetch live departures ===
def fetch_departures():
    if TEST_MODE:
        return fetch_test_data_grouped(TARGET_PLATFORMS)
    if soap_client is None:
        logging.error("SOAP client not available and TEST_MODE is False. Returning empty dataset.")
        return {p: [] for p in TARGET_PLATFORMS}
    try:
        response = soap_client.service.GetDepartureBoard(40, STATION_CODE, _soapheaders=[soap_header_value])
        if not hasattr(response, 'trainServices') or not response.trainServices:
            return {p: [] for p in TARGET_PLATFORMS}
        services_by_platform = {platform: [] for platform in TARGET_PLATFORMS}
        for service in response.trainServices.service:
            platform = str(service.platform)
            if platform in services_by_platform and len(services_by_platform[platform]) < 2:
                destination = service.destination.location[0].locationName
                departure_time = getattr(service, "std", "")
                etd = getattr(service, "etd", "").strip().lower()
                status = "On time" if etd == "on time" else f"Exp {etd}" if ":" in etd or etd.startswith("exp") else "Exp unknown"
                calling_at = ""
                if len(services_by_platform[platform]) == 0:
                    try:
                        details = soap_client.service.GetServiceDetails(service.serviceID, _soapheaders=[soap_header_value])
                        if hasattr(details, 'subsequentCallingPoints') and details.subsequentCallingPoints:
                            point_lists = details.subsequentCallingPoints.callingPointList
                            if isinstance(point_lists, list) and point_lists:
                                points = point_lists[0].callingPoint
                                calling_at = ", ".join(cp.locationName for cp in points if hasattr(cp, "locationName"))
                    except Exception as e:
                        logging.error(f"Failed to extract calling points for {destination}: {e}")
                services_by_platform[platform].append((departure_time, destination, calling_at, status))
        return services_by_platform
    except Exception as e:
        logging.error(f"Error fetching data from SOAP: {str(e)}")
        return {p: [] for p in TARGET_PLATFORMS}

# === Update display surfaces ===
def update_display_multi_platform(departures_by_platform, static_text, scrolling_texts):
    static_text.clear()
    scrolling_texts.clear()
    y_pos = 20
    for platform, departures in departures_by_platform.items():
        # Platform header with background
        header_text = f"Platform {platform}"
        header_surface = platform_font.render(header_text, True, ORANGE)
        header_rect = header_surface.get_rect()
        header_rect.width = WINDOW_WIDTH
        header_rect.height = header_surface.get_height() + 10
        header_bg_surface = pygame.Surface((WINDOW_WIDTH, header_rect.height))
        header_bg_surface.fill(PLATFORM_BG_COLOR)
        header_bg_surface.blit(header_surface, ((WINDOW_WIDTH - header_surface.get_width()) // 2, 5))
        static_text.append((header_bg_surface, (0, y_pos)))
        y_pos += header_rect.height + 5

        for i, (departure_time, destination, calling_at, status) in enumerate(departures):
            line_y = y_pos
            static_text.append((train_font.render(departure_time, True, ORANGE), (20, line_y)))
            if len(destination) > 90:
                scrolling_texts.append(ScrollingText(line_y, destination, train_font.render("", True, ORANGE), x_margin=250))
            else:
                static_text.append((train_font.render(destination, True, ORANGE), (250, line_y)))
            color = (255, 0, 0) if "Exp" in status else ORANGE
            status_surface = status_font.render(status, True, color)
            status_x = WINDOW_WIDTH - status_surface.get_width() - 30
            status_y = line_y + (train_font.get_height() - status_surface.get_height()) // 2
            static_text.append((status_surface, (status_x, status_y)))
            if i == 0 and calling_at:
                y_pos += train_font.get_height() + 10
                label_surface = train_font.render("Calling at: ", True, ORANGE)
                static_text.append(("CALLING_AT_LABEL", (20, y_pos), label_surface))
                scrolling_texts.append(ScrollingText(y_pos, calling_at, label_surface, x_margin=5, gap=SCROLL_GAP))
                y_pos += train_font.get_height() + 5
            y_pos += train_font.get_height() + status_font.get_height() - 40
        y_pos += 10

# === Temperature fetch ===
def get_temperature():
    try:
        if LATITUDE is None or LONGITUDE is None:
            return "N/A"
        url = f"https://api.open-meteo.com/v1/forecast?latitude={LATITUDE}&longitude={LONGITUDE}&current_weather=true"
        response = requests.get(url, timeout=5)
        data = response.json()
        if response.status_code == 200:
            if "current_weather" in data and "temperature" in data["current_weather"]:
                return f"{round(data['current_weather']['temperature'])}°C"
            if "current" in data and "temperature_2m" in data["current"]:
                return f"{round(data['current']['temperature_2m'])}°C"
        return "N/A"
    except Exception as e:
        logging.error(f"Error fetching temperature: {e}")
        return "N/A"
    
def get_paginated_platforms(all_platforms, per_page):
    """Split platform list into pages of fixed size."""
    for i in range(0, len(all_platforms), per_page):
        yield all_platforms[i:i + per_page]

# === Main loop ===
def main():
    clock = pygame.time.Clock()
    scrolling_texts = []
    static_text = []
    static_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT)).convert()
    last_update_time = time.time() - UPDATE_INTERVAL
    last_temp_update = 0
    current_temp = "N/A"
    running = True

    # === Platform screen rotation setup ===
    platform_pages = list(get_paginated_platforms(TARGET_PLATFORMS, PLATFORMS_PER_SCREEN))
    current_page_index = 0
    last_screen_switch = time.time()

    logging.info(f"Display divided into {len(platform_pages)} screens of {PLATFORMS_PER_SCREEN} platforms each.")

    # === Initial data fetch ===
    departures_all = fetch_departures()
    visible_platforms = platform_pages[current_page_index]
    subset = {p: departures_all.get(p, []) for p in visible_platforms}
    update_display_multi_platform(subset, static_text, scrolling_texts)
    static_surface.fill(BLACK)
    for item in static_text:
        if isinstance(item[0], str) and item[0] == "CALLING_AT_LABEL":
            static_surface.blit(item[2], item[1])
        elif isinstance(item[0], pygame.Surface):
            static_surface.blit(item[0], item[1])

    # === Main loop ===
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False

        # === Periodic departure updates ===
        if time.time() - last_update_time >= UPDATE_INTERVAL:
            departures_all = fetch_departures()
            visible_platforms = platform_pages[current_page_index]
            subset = {p: departures_all.get(p, []) for p in visible_platforms}
            update_display_multi_platform(subset, static_text, scrolling_texts)
            static_surface.fill(BLACK)
            for item in static_text:
                if isinstance(item[0], str) and item[0] == "CALLING_AT_LABEL":
                    static_surface.blit(item[2], item[1])
                elif isinstance(item[0], pygame.Surface):
                    static_surface.blit(item[0], item[1])
            last_update_time = time.time()

        # === Switch between platform pages ===
        if time.time() - last_screen_switch >= SCREEN_ROTATE_INTERVAL:
            current_page_index = (current_page_index + 1) % len(platform_pages)
            last_screen_switch = time.time()
            logging.info(f"Switched to platform page {current_page_index + 1}/{len(platform_pages)}")
            visible_platforms = platform_pages[current_page_index]
            subset = {p: departures_all.get(p, []) for p in visible_platforms}
            update_display_multi_platform(subset, static_text, scrolling_texts)
            static_surface.fill(BLACK)
            for item in static_text:
                if isinstance(item[0], str) and item[0] == "CALLING_AT_LABEL":
                    static_surface.blit(item[2], item[1])
                elif isinstance(item[0], pygame.Surface):
                    static_surface.blit(item[0], item[1])

        # === Temperature refresh every 10 min ===
        if time.time() - last_temp_update >= 600:
            current_temp = get_temperature()
            last_temp_update = time.time()

        # === Frame rendering ===
        frame_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT)).convert()
        frame_surface.blit(static_surface, (0, 0))

        for text in scrolling_texts:
            clip_rect = pygame.Rect(text.x_start, text.y_pos, text.clip_width, train_font.get_height())
            text.update()
            text.draw(frame_surface, clip_rect)

        # === Draw clock and temperature ===
        current_time = datetime.now().strftime("%H:%M:%S")
        clock_text = clock_font.render(current_time, True, ORANGE)
        temp_text = train_font.render(current_temp, True, ORANGE)
        clock_x = (WINDOW_WIDTH - clock_text.get_width()) // 2
        clock_y = WINDOW_HEIGHT - clock_text.get_height() - 20
        temp_x = clock_x + clock_text.get_width() + 60
        temp_y = clock_y + (clock_text.get_height() - temp_text.get_height()) // 2

        pygame.draw.rect(frame_surface, BLACK, (
            clock_x - 10, clock_y - 10,
            clock_text.get_width() + temp_text.get_width() + 70,
            clock_text.get_height() + 20
        ))

        frame_surface.blit(clock_text, (clock_x, clock_y))
        frame_surface.blit(temp_text, (temp_x, temp_y))

        if ROTATE_DISPLAY:
            frame_surface = pygame.transform.rotate(frame_surface, 180)

        screen.blit(frame_surface, (0, 0))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()

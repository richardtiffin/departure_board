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
    filename="departure_boardmk2.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# === Load configuration safely ===
CONFIG_PATH = "configmk2.json"
SAMPLE_CONFIG = {
    "API_KEY": "YOUR_API_KEY_HERE",
    "STATIONS": {
        "CARD": {
            "NAME": "Cardiff",
            "PLATFORMS": [0,1,2,3,4,5],
            "LATITUDE": 51.48,
            "LONGITUDE": -3.18
        },
        "NCL": {
            "NAME": "Newcastle",
            "PLATFORMS": [1,2,3,4,5,6],
            "LATITUDE": 54.97,
            "LONGITUDE": -1.62
        }
    },
    "STATION_ROTATE_INTERVAL": 60,
    "PLATFORMS_PER_SCREEN": 4,
    "SCREEN_ROTATE_INTERVAL": 20,
    "UPDATE_INTERVAL": 30,
    "TEST_MODE": True,
    "ROTATE_DISPLAY": False,
    "SCROLL_SPEED": 14,
    "SCROLL_GAP": 200,
    "CLOCK_FONT_SIZE": 148,
    "STATION_FONT_SIZE": 80,
    "PLATFORM_FONT_SIZE": 72,
    "TRAIN_FONT_SIZE": 56,
    "STATUS_FONT_SIZE": 50
}

try:
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
except FileNotFoundError:
    logging.error("config.json not found. Creating sample file and exiting.")
    with open("config.sample.json", "w") as sample:
        json.dump(SAMPLE_CONFIG, sample, indent=4)
    print("config.json not found. Sample created.")
    sys.exit(1)
except JSONDecodeError as e:
    logging.error(f"config.json JSON error: {e}")
    sys.exit(1)

API_KEY = config.get("API_KEY")
STATIONS = config.get("STATIONS", {})
STATION_ROTATE_INTERVAL = config.get("STATION_ROTATE_INTERVAL", 60)
PLATFORMS_PER_SCREEN = config.get("PLATFORMS_PER_SCREEN", 4)
SCREEN_ROTATE_INTERVAL = config.get("SCREEN_ROTATE_INTERVAL", 20)
UPDATE_INTERVAL = config.get("UPDATE_INTERVAL", 30)
TEST_MODE = config.get("TEST_MODE", True)
ROTATE_DISPLAY = config.get("ROTATE_DISPLAY", False)
SCROLL_SPEED = config.get("SCROLL_SPEED", 14)
SCROLL_GAP = config.get("SCROLL_GAP", 200)
CLOCK_FONT_SIZE = config.get("CLOCK_FONT_SIZE", 148)
STATION_FONT_SIZE = config.get("STATION_FONT_SIZE", 80)
PLATFORM_FONT_SIZE = config.get("PLATFORM_FONT_SIZE", 72)
TRAIN_FONT_SIZE = config.get("TRAIN_FONT_SIZE", 56)
STATUS_FONT_SIZE = config.get("STATUS_FONT_SIZE", 50)
WINDOW_WIDTH = config.get("WINDOW_WIDTH", 800)
WINDOW_HEIGHT = config.get("WINDOW_HEIGHT", 480)
FULLSCREEN = config.get("FULLSCREEN", False)

# === Setup SOAP client ===
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
except Exception as e:
    logging.error(f"SOAP client init failed: {e}")
    TEST_MODE = True

# === Service details cache ===
service_details_cache = {}
SERVICE_DETAILS_TTL = 600
last_service_details_cleanup = time.time()

# === Pygame setup ===
pygame.mixer.pre_init(0,0,0,0)
pygame.init()
pygame.mixer.quit()

if FULLSCREEN:
    screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)
else:
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))

WINDOW_WIDTH, WINDOW_HEIGHT = screen.get_size()

BLACK = (0,0,0)
ORANGE = (255,165,0)
PLATFORM_BG_COLOR = (50,50,50)

font_path = "fonts/bus-stop.ttf"
try:
    clock_font = pygame.font.Font(font_path, CLOCK_FONT_SIZE)
    station_font = pygame.font.Font(font_path, STATION_FONT_SIZE)
    platform_font = pygame.font.Font(font_path, PLATFORM_FONT_SIZE)
    train_font = pygame.font.Font(font_path, TRAIN_FONT_SIZE)
    status_font = pygame.font.Font(font_path, STATUS_FONT_SIZE)
except:
    clock_font = pygame.font.SysFont(None, CLOCK_FONT_SIZE)
    station_font = pygame.font.SysFont(None, STATION_FONT_SIZE)
    platform_font = pygame.font.SysFont(None, PLATFORM_FONT_SIZE)
    train_font = pygame.font.SysFont(None, TRAIN_FONT_SIZE)
    status_font = pygame.font.SysFont(None, STATUS_FONT_SIZE)

# === Scrolling Text class ===
class ScrollingText:
    def __init__(self, y_pos, text, label_surface, x_margin=10, gap=SCROLL_GAP):
        self.text = text
        rendered_text = train_font.render(self.text, True, ORANGE)
        self.text_width = rendered_text.get_width()
        self.surface = pygame.Surface((self.text_width, train_font.get_height()), pygame.SRCALPHA)
        self.surface.blit(rendered_text, (0,0))
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

# === Helpers ===
def get_paginated_platforms(platforms, per_page):
    for i in range(0, len(platforms), per_page):
        yield platforms[i:i+per_page]

def fetch_test_data_grouped(target_platforms):
    try:
        with open("test_data.json","r") as f:
            test_data = json.load(f)
            platform_map = {p:[] for p in target_platforms}
            for entry in test_data:
                platform = str(entry.get("platform"))
                if platform in platform_map and len(platform_map[platform])<2:
                    platform_map[platform].append(
                        (entry["departure_time"], entry["destination"], entry.get("calling_at",""), entry.get("status","On time"))
                    )
            return platform_map
    except:
        return {p:[] for p in target_platforms}

def fetch_departures(station_code, target_platforms):
    global last_service_details_cleanup, service_details_cache

    if TEST_MODE or soap_client is None:
        return fetch_test_data_grouped(target_platforms)

    # Cleanup old cache entries periodically
    if time.time() - last_service_details_cleanup > SERVICE_DETAILS_TTL:
        service_details_cache = {}
        last_service_details_cleanup = time.time()

    try:
        response = soap_client.service.GetDepartureBoard(6, station_code, _soapheaders=[soap_header_value])
        if not hasattr(response, 'trainServices') or not response.trainServices:
            return {p:[] for p in target_platforms}
        
        # services_by_platform = {p:[] for p in target_platforms}
        services = []

        for service in response.trainServices.service:
            platform = str(service.platform)
            operator = service.operator
            # if platform not in services_by_platform or len(services_by_platform[platform]) >= 2:
            #     continue

            destination = service.destination.location[0].locationName
            departure_time = getattr(service, "std", "")
            etd = getattr(service, "etd", "").strip().lower()
            status = "On time" if etd=="on time" else f"Exp {etd}" if ":" in etd or etd.startswith("exp") else "Exp unknown"
            calling_at = ""

            service_id = service.serviceID
            # if len(services_by_platform[platform]) == 0:
            if service_id in service_details_cache:
                details = service_details_cache[service_id]
            else:
                try:
                    details = soap_client.service.GetServiceDetails(service_id, _soapheaders=[soap_header_value])
                    service_details_cache[service_id] = details
                    time.sleep(0.2)
                except:
                    details = None

            if details and hasattr(details,'subsequentCallingPoints') and details.subsequentCallingPoints:
                point_lists = details.subsequentCallingPoints.callingPointList
                if isinstance(point_lists,list) and point_lists:
                    points = point_lists[0].callingPoint
                    calling_at = ", ".join(cp.locationName for cp in points if hasattr(cp,"locationName"))

            services.append((departure_time, destination, platform, calling_at, status, operator))

        return services
    except Exception as e:
        logging.exception(f"GetDepartureBoard failed for {station_code}: {e}")
        print("SOAP ERROR:", e)
        return {p:[] for p in target_platforms}

def update_display_multi_platform_with_calling_at(departures, static_text, scrolling_texts, current_targets):
    static_text.clear()
    scrolling_texts.clear()
    y_pos = station_font.get_height() + 50
    
    if not departures:
        print("No departures — skipping screen")
        return False

    # for platform in current_targets:
    #     departures = departures_by_platform.get(platform, [])
    #     if not departures:
    #         continue

        # Platform header
        # header_text = f"Platform {platform}"
        # header_surface = platform_font.render(header_text, True, ORANGE)
        # header_bg_surface = pygame.Surface((WINDOW_WIDTH, header_surface.get_height() + 10))
        # header_bg_surface.fill(PLATFORM_BG_COLOR)
        # header_bg_surface.blit(header_surface, ((WINDOW_WIDTH - header_surface.get_width())//2,5))
        # static_text.append((header_bg_surface,(0,y_pos)))
        # y_pos += header_surface.get_height() + 10

    for dep in departures:
        departure_time, destination, platform, calling_at, status, operator = dep
        line_y = y_pos

        # Column X positions
        x_time = 10
        x_dest = 200
        x_plat = 550
        x_op = 700

        # Draw departure time
        static_text.append(
            (train_font.render(departure_time, True, ORANGE), (x_time, line_y))
        )

        # Draw destination
        static_text.append(
            (train_font.render(destination, True, ORANGE), (x_dest, line_y))
        )

        # Draw platform number
        platformNo = f"Plat {platform}"
        static_text.append(
            (train_font.render(platformNo, True, ORANGE), (x_plat, line_y))
        )

        operatorp = f"({operator})"

        # Draw operator
        static_text.append(
            (train_font.render(operatorp, True, ORANGE), (x_op, line_y))
        )

        color = (255,0,0) if "Exp" in status else ORANGE
        status_surface = status_font.render(status, True, color)
        status_x = WINDOW_WIDTH - status_surface.get_width() -30
        status_y = line_y + (train_font.get_height()-status_surface.get_height())//2
        static_text.append((status_surface,(status_x,status_y)))

        if calling_at:
            y_pos += train_font.get_height() + 5
            label_surface = train_font.render("Calling at:", True, ORANGE)
            static_text.append(("CALLING_AT_LABEL",(20,y_pos),label_surface))
            scrolling_texts.append(ScrollingText(y_pos, calling_at, label_surface, x_margin=150, gap=SCROLL_GAP))
            y_pos += train_font.get_height() + 5

        y_pos += train_font.get_height() + status_font.get_height() - 40
    y_pos += 10

    return True

def get_temperature(lat, lon):
    try:
        if lat is None or lon is None:
            return "N/A"
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        r = requests.get(url, timeout=5)
        data = r.json()
        if "current_weather" in data and "temperature" in data["current_weather"]:
            return f"{round(data['current_weather']['temperature'])}°C"
        return "N/A"
    except:
        return "N/A"

# === Main function ===
def main():
    clock = pygame.time.Clock()
    static_text = []
    scrolling_texts = []
    static_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT)).convert()
    last_update_time = 0
    last_temp_update = 0

    station_codes = list(STATIONS.keys())
    station_index = 0
    current_screen_index = 0
    last_station_rotate = time.time()
    last_screen_rotate = time.time()
    departures = {}
    NO_DEPARTURES_COOLDOWN = 60
    last_successful_fetch = 0
    allTemp = {code: "N/A" for code in station_codes}

    # Initialise first station/page
    STATION_CODE = station_codes[station_index]
    current_station = STATIONS[STATION_CODE]
    current_temp = allTemp.get(STATION_CODE, "N/A")
    all_platforms = [str(p) for p in current_station.get("PLATFORMS", [])]
    platform_pages = list(get_paginated_platforms(all_platforms, PLATFORMS_PER_SCREEN))
    current_targets = platform_pages[0] if platform_pages else []

    running = True
    while running:
        now = time.time()
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False

        # --- Update temperature every 10 min ---
        if now - last_temp_update >= 600:
            for code in station_codes:
                stationForTemp = STATIONS[code]
                allTemp[code] = get_temperature(stationForTemp.get("LATITUDE"), stationForTemp.get("LONGITUDE"))
            last_temp_update = now

        # --- Rotate stations ---
        station_changed = False
        if now - last_station_rotate >= STATION_ROTATE_INTERVAL:
            station_index = (station_index + 1) % len(station_codes)
            current_screen_index = 0
            last_station_rotate = now
            station_changed = True

        # --- Rotate platform pages ---
        page_changed = False
        if len(platform_pages) > 1 and now - last_screen_rotate >= SCREEN_ROTATE_INTERVAL:
            current_screen_index = (current_screen_index + 1) % len(platform_pages)
            last_screen_rotate = now
            page_changed = True

        # --- Fetch departures & update display ---
        if station_changed or page_changed or now - last_update_time >= UPDATE_INTERVAL:
            STATION_CODE = station_codes[station_index]
            current_station = STATIONS[STATION_CODE]
            current_temp = allTemp.get(STATION_CODE, "N/A")

            if station_changed:
                all_platforms = [str(p) for p in current_station.get("PLATFORMS", [])]
                platform_pages = list(get_paginated_platforms(all_platforms, PLATFORMS_PER_SCREEN))
                current_screen_index = 0

            # Safeguard for empty platform_pages
            if not platform_pages:
                station_index = (station_index + 1) % len(station_codes)
                last_station_rotate = now
                continue

            # Keep advancing until we find a page with departures or all pages checked
            page_attempts = 0
            success = False
            while page_attempts < len(platform_pages):
                current_targets = platform_pages[current_screen_index]
                departures = fetch_departures(STATION_CODE, current_targets)

                success = update_display_multi_platform_with_calling_at(
                    departures, static_text, scrolling_texts, current_targets
                )

                if success:
                    # We found a page with departures — render and break
                    static_surface.fill(BLACK)
                    for item in static_text:
                        if isinstance(item[0], pygame.Surface):
                            static_surface.blit(item[0], item[1])
                        elif isinstance(item[0], str) and item[0] == "CALLING_AT_LABEL":
                            static_surface.blit(item[2], item[1])
                    last_update_time = now
                    break
                else:
                    # Advance to the next page immediately
                    current_screen_index = (current_screen_index + 1) % len(platform_pages)
                    page_attempts += 1

            # If all pages were empty, skip to next station — but back off to avoid hammering API
            if not success:
                station_index = (station_index + 1) % len(station_codes)
                last_station_rotate = now
                last_update_time = now  # prevent immediate re-fetch
                time.sleep(NO_DEPARTURES_COOLDOWN)
                continue


        # --- Draw frame ---
        frame_surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT)).convert()
        frame_surface.blit(static_surface, (0,0))
        for text in scrolling_texts:
            clip_rect = pygame.Rect(text.x_start, text.y_pos, text.clip_width, train_font.get_height())
            text.update()
            text.draw(frame_surface, clip_rect)

        # --- Clock, temperature, station ---
        current_time = datetime.now().strftime("%H:%M:%S")
        clock_text = clock_font.render(current_time, True, ORANGE)
        temp_text = train_font.render(current_temp, True, ORANGE)
        station_text = station_font.render(current_station.get("NAME", ""), True, ORANGE)

        clock_x = (WINDOW_WIDTH - clock_text.get_width()) // 2
        clock_y = WINDOW_HEIGHT - clock_text.get_height() - 20
        temp_x = clock_x + clock_text.get_width() + 60
        temp_y = clock_y + (clock_text.get_height() - temp_text.get_height()) // 2
        station_x = (WINDOW_WIDTH - station_text.get_width()) // 2
        station_y = 20

        pygame.draw.rect(frame_surface, BLACK, (
            clock_x-10, clock_y-10,
            clock_text.get_width() + temp_text.get_width() + 70,
            clock_text.get_height() + 20
        ))

        frame_surface.blit(station_text, (station_x, station_y))
        frame_surface.blit(clock_text, (clock_x, clock_y))
        frame_surface.blit(temp_text, (temp_x, temp_y))

        if ROTATE_DISPLAY:
            frame_surface = pygame.transform.rotate(frame_surface, 180)

        screen.blit(frame_surface, (0,0))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()

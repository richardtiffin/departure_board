import json
import signal
from datetime import datetime
from confluent_kafka import Consumer, KafkaException


CONFIG_FILE = "/home/rich/departure_board/configmk2.json"


# ============================================================
# Load configuration
# ============================================================

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

stations = config["STATIONS"]
kafka_config = config["RDM_KAFKA"]


# ============================================================
# Build TIPLOC -> station lookup
# ============================================================

tiploc_to_station = {}

for crs, station in stations.items():

    tiploc = station.get("TIPLOC")

    if tiploc:
        tiploc_to_station[tiploc] = {
            "crs": crs,
            "name": station["NAME"],
            "platforms": station.get("PLATFORMS", []),
        }


# ============================================================
# Kafka configuration
# ============================================================

consumer_config = {
    "bootstrap.servers": kafka_config["BOOTSTRAP_SERVERS"],
    "security.protocol": kafka_config["SECURITY_PROTOCOL"],
    "sasl.mechanisms": kafka_config["SASL_MECHANISM"],
    "sasl.username": kafka_config["USERNAME"],
    "sasl.password": kafka_config["PASSWORD"],
    "group.id": kafka_config["GROUP_ID"],

    # For this diagnostic we start with new messages.
    "auto.offset.reset": "latest",

    # Don't commit anything during the test.
    "enable.auto.commit": False,
}

consumer = Consumer(consumer_config)


# ============================================================
# Train state
#
# One record per RID.
#
# Schedule information provides the baseline.
# TS messages subsequently update the live state.
# ============================================================

trains = {}


def make_train(rid):

    return {
        "rid": rid,

        # Schedule information
        "uid": None,
        "train_id": None,
        "ssd": None,
        "toc": None,

        "origin": None,
        "destination": None,

        "calling_points": [],
        "passing_points": [],

        # Live TS information
        "last_location": None,
        "last_tiploc": None,
        "last_platform": None,
        "last_ts": None,

        # Counts
        "ts_updates": 0,

        # Has a relevant station in the schedule?
        "relevant": False,

        # Have we printed this schedule yet?
        "schedule_printed": False,
    }


def get_train(rid):

    if rid not in trains:
        trains[rid] = make_train(rid)

    return trains[rid]


# ============================================================
# Stop handling
# ============================================================

running = True


def shutdown(signum, frame):

    global running
    running = False


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


# ============================================================
# Helpers
# ============================================================

def locations_as_list(value):

    if value is None:
        return []

    if isinstance(value, dict):
        return [value]

    if isinstance(value, list):
        return value

    return []


def platform_from_location(location):

    plat = location.get("plat")

    if plat is None:
        return None

    if isinstance(plat, (int, float)):
        return str(plat)

    if isinstance(plat, str):
        return plat

    if isinstance(plat, dict):

        if "" in plat:
            return str(plat[""])

        for key in ("platform", "plat", "value"):

            if key in plat:
                return str(plat[key])

    return None


def station_for_tiploc(tiploc):

    return tiploc_to_station.get(tiploc)


def point_time(point, arrival=True):

    if not isinstance(point, dict):
        return "-"

    if arrival:

        return (
            point.get("pta")
            or point.get("wta")
            or "-"
        )

    return (
        point.get("ptd")
        or point.get("wtd")
        or "-"
    )


def point_description(point):

    if not isinstance(point, dict):
        return "?"

    tiploc = point.get("tpl", "?")

    station = station_for_tiploc(tiploc)

    if station:
        return f"{station['name']} [{tiploc}]"

    return tiploc


# ============================================================
# Schedule processing
# ============================================================

def schedule_contains_configured_station(record):

    """
    Return True if OR, IP or DT contains one of our
    configured station TIPLOCs.
    """

    # Origin
    origin = record.get("OR")

    if (
        isinstance(origin, dict)
        and origin.get("tpl") in tiploc_to_station
    ):
        return True

    # Intermediate calling points
    ip = record.get("IP", [])

    if isinstance(ip, dict):
        ip = [ip]

    if isinstance(ip, list):

        for point in ip:

            if (
                isinstance(point, dict)
                and point.get("tpl") in tiploc_to_station
            ):
                return True

    # Destination
    destination = record.get("DT")

    if (
        isinstance(destination, dict)
        and destination.get("tpl") in tiploc_to_station
    ):
        return True

    return False


def process_schedule_record(record):

    if not isinstance(record, dict):
        return None

    rid = record.get("rid")

    if not rid:
        return None

    train = get_train(rid)

    # --------------------------------------------------------
    # Basic information
    # --------------------------------------------------------

    if record.get("uid"):
        train["uid"] = record["uid"]

    if record.get("trainId"):
        train["train_id"] = record["trainId"]

    if record.get("ssd"):
        train["ssd"] = record["ssd"]

    if record.get("toc"):
        train["toc"] = record["toc"]

    # --------------------------------------------------------
    # Origin
    # --------------------------------------------------------

    origin = record.get("OR")

    if isinstance(origin, dict):
        train["origin"] = origin

    # --------------------------------------------------------
    # Calling points
    # --------------------------------------------------------

    ip = record.get("IP", [])

    if isinstance(ip, dict):
        ip = [ip]

    if isinstance(ip, list):
        train["calling_points"] = ip

    # --------------------------------------------------------
    # Passing points
    # --------------------------------------------------------

    pp = record.get("PP", [])

    if isinstance(pp, dict):
        pp = [pp]

    if isinstance(pp, list):
        train["passing_points"] = pp

    # --------------------------------------------------------
    # Destination
    # --------------------------------------------------------

    destination = record.get("DT")

    if isinstance(destination, dict):
        train["destination"] = destination

    # --------------------------------------------------------
    # Is this train relevant to us?
    # --------------------------------------------------------

    if schedule_contains_configured_station(record):

        train["relevant"] = True

    return train


# ============================================================
# Print complete schedule
# ============================================================

def print_schedule(train):

    print()
    print("=" * 90)
    print("RELEVANT TRAIN SCHEDULE")
    print("=" * 90)

    print(f"RID:          {train['rid']}")

    if train["uid"]:
        print(f"UID:          {train['uid']}")

    if train["train_id"]:
        print(f"Train ID:     {train['train_id']}")

    if train["toc"]:
        print(f"TOC:          {train['toc']}")

    if train["ssd"]:
        print(f"Date:         {train['ssd']}")

    print()

    # --------------------------------------------------------
    # Origin
    # --------------------------------------------------------

    if train["origin"]:

        print(
            f"Origin:       "
            f"{point_description(train['origin'])}"
        )

    # --------------------------------------------------------
    # Destination
    # --------------------------------------------------------

    if train["destination"]:

        print(
            f"Destination:  "
            f"{point_description(train['destination'])}"
        )

    print()

    # --------------------------------------------------------
    # Calling points
    # --------------------------------------------------------

    print("CALLING POINTS")
    print("-" * 90)

    points = []

    if train["origin"]:
        points.append(("OR", train["origin"]))

    for point in train["calling_points"]:
        points.append(("IP", point))

    if train["destination"]:
        points.append(("DT", train["destination"]))

    if not points:

        print("  No calling points available")

    else:

        for point_type, point in points:

            if not isinstance(point, dict):
                continue

            tiploc = point.get("tpl", "?")

            station = station_for_tiploc(tiploc)

            if station:
                name = station["name"]
                marker = "  *** OUR STATION ***"
            else:
                name = ""
                marker = ""

            arr = point_time(point, True)
            dep = point_time(point, False)

            if name:

                print(
                    f"  {point_type:<3} "
                    f"{tiploc:<10} "
                    f"{name:<28} "
                    f"arr {arr:<8} "
                    f"dep {dep:<8}"
                    f"{marker}"
                )

            else:

                print(
                    f"  {point_type:<3} "
                    f"{tiploc:<10} "
                    f"arr {arr:<8} "
                    f"dep {dep:<8}"
                )

    print()

    # --------------------------------------------------------
    # Passing points
    # --------------------------------------------------------

    if train["passing_points"]:

        print(
            f"Passing points retained: "
            f"{len(train['passing_points'])}"
        )

    # --------------------------------------------------------
    # Current live state
    # --------------------------------------------------------

    if train["last_location"]:

        location = train["last_location"]

        print()
        print("CURRENT LIVE STATE")
        print("-" * 90)

        print(
            f"Current TIPLOC: {location.get('tpl', '?')}"
        )

        if train["last_platform"]:
            print(
                f"Platform:       {train['last_platform']}"
            )

        arr = location.get("arr")

        if isinstance(arr, dict):
            print(f"Arrival:        {arr}")

        dep = location.get("dep")

        if isinstance(dep, dict):
            print(f"Departure:      {dep}")

        print(
            f"TS updates:     {train['ts_updates']}"
        )

    print("=" * 90)


# ============================================================
# Print live TS update
# ============================================================

def print_ts_update(train, location):

    tiploc = location.get("tpl", "?")

    station = station_for_tiploc(tiploc)

    print()
    print("-" * 90)
    print("LIVE TS UPDATE")
    print("-" * 90)

    print(f"RID:            {train['rid']}")

    if train["uid"]:
        print(f"UID:            {train['uid']}")

    if train["train_id"]:
        print(f"Train ID:       {train['train_id']}")

    print(
        f"Location:       {tiploc}"
    )

    if station:

        print(
            f"Station:        "
            f"{station['name']} ({station['crs']})"
        )

    platform = platform_from_location(location)

    if platform:

        print(
            f"Platform:       {platform}"
        )

    print(
        f"WTA:            {location.get('wta', '-')}"
    )

    print(
        f"WTD:            {location.get('wtd', '-')}"
    )

    print(
        f"PTA:            {location.get('pta', '-')}"
    )

    print(
        f"PTD:            {location.get('ptd', '-')}"
    )

    arr = location.get("arr")

    if isinstance(arr, dict):
        print(f"Arrival:        {arr}")

    dep = location.get("dep")

    if isinstance(dep, dict):
        print(f"Departure:      {dep}")

    print("-" * 90)


# ============================================================
# Configuration display
# ============================================================

print()
print("Configured stations:")
print()

for crs, station in stations.items():

    print(
        f"  {crs:<4} "
        f"{station['NAME']:<25} "
        f"TIPLOC={station.get('TIPLOC', 'NONE')}"
    )

print()
print("Listening for Darwin RDM messages...")
print()
print("Architecture:")
print("  SCHEDULE -> build train timetable")
print("  TS       -> update live train state")
print()
print("Schedules containing configured stations will be displayed.")
print("Calling points will be retained.")
print()
print("Press Ctrl-C to stop.")
print()


# ============================================================
# Subscribe
# ============================================================

consumer.subscribe([kafka_config["TOPIC"]])


# ============================================================
# Counters
# ============================================================

message_count = 0
schedule_count = 0
schedule_record_count = 0
relevant_schedule_count = 0
ts_count = 0
known_train_ts_count = 0
unknown_train_ts_count = 0
station_match_count = 0


# ============================================================
# Main loop
# ============================================================

try:

    while running:

        msg = consumer.poll(1.0)

        if msg is None:
            continue

        if msg.error():

            if msg.error().code() == KafkaException._PARTITION_EOF:
                continue

            print(
                f"Kafka error: {msg.error()}"
            )

            continue

        message_count += 1

        # ----------------------------------------------------
        # Progress report
        # ----------------------------------------------------

        if message_count % 1000 == 0:

            print()
            print(
                f"[Progress] "
                f"Kafka={message_count:,}  "
                f"Schedules={schedule_count:,}  "
                f"Schedule records={schedule_record_count:,}  "
                f"TS={ts_count:,}  "
                f"Known RID TS={known_train_ts_count:,}  "
                f"Relevant trains={relevant_schedule_count:,}  "
                f"Station matches={station_match_count:,}  "
                f"Trains retained={len(trains):,}"
            )

        # ----------------------------------------------------
        # Decode message
        # ----------------------------------------------------

        try:

            value = msg.value()

            if isinstance(value, bytes):
                value = value.decode("utf-8")

            data = json.loads(value)

        except Exception as e:

            print(
                f"Could not decode message: {e}"
            )

            continue

        # ----------------------------------------------------
        # Darwin outer structure
        # ----------------------------------------------------

        ur = data.get("uR")

        if not isinstance(ur, dict):
            continue

        # ====================================================
        # SCHEDULE
        # ====================================================

        schedule = ur.get("schedule")

        if schedule is not None:

            schedule_count += 1

            if isinstance(schedule, dict):
                schedule = [schedule]

            if isinstance(schedule, list):

                schedule_record_count += len(schedule)

                for record in schedule:

                    train = process_schedule_record(record)

                    if train is None:
                        continue

                    if train["relevant"]:

                        relevant_schedule_count += 1

                        # Only print each train's schedule the
                        # first time we encounter it.

                        if not train["schedule_printed"]:

                            train["schedule_printed"] = True

                            print_schedule(train)

        # ====================================================
        # TRAIN SERVICE / TS
        # ====================================================

        ts = ur.get("TS")

        if not isinstance(ts, dict):
            continue

        ts_count += 1

        rid = ts.get("rid")

        if not rid:
            continue

        # ----------------------------------------------------
        # Find or create train
        # ----------------------------------------------------

        train_exists = rid in trains

        train = get_train(rid)

        if train_exists:
            known_train_ts_count += 1
        else:
            unknown_train_ts_count += 1

        # ----------------------------------------------------
        # Update basic TS information
        # ----------------------------------------------------

        if ts.get("uid"):
            train["uid"] = ts["uid"]

        if ts.get("ssd"):
            train["ssd"] = ts["ssd"]

        # ----------------------------------------------------
        # Process locations
        # ----------------------------------------------------

        locations = locations_as_list(
            ts.get("Location")
        )

        for location in locations:

            if not isinstance(location, dict):
                continue

            tiploc = location.get("tpl")

            if not tiploc:
                continue

            # ------------------------------------------------
            # Always update the train's current location.
            #
            # This is important: the TS message doesn't have
            # to be at one of our stations.
            # ------------------------------------------------

            train["last_location"] = location
            train["last_tiploc"] = tiploc
            train["last_platform"] = (
                platform_from_location(location)
            )
            train["last_ts"] = data.get("ts")

            train["ts_updates"] += 1

            # ------------------------------------------------
            # If this is one of our stations, display it.
            # ------------------------------------------------

            station = station_for_tiploc(tiploc)

            if station is not None:

                station_match_count += 1

                print_ts_update(
                    train,
                    location,
                )

                # If the schedule arrived after the TS,
                # print the complete schedule now.

                if (
                    train["relevant"]
                    and not train["schedule_printed"]
                ):

                    train["schedule_printed"] = True

                    print_schedule(train)


except KeyboardInterrupt:

    pass


finally:

    print()
    print("=" * 90)
    print("STOPPING DIAGNOSTIC TEST")
    print("=" * 90)

    print(
        f"Kafka messages:          {message_count:,}"
    )

    print(
        f"Schedule messages:       {schedule_count:,}"
    )

    print(
        f"Schedule records:        {schedule_record_count:,}"
    )

    print(
        f"Relevant schedules:      {relevant_schedule_count:,}"
    )

    print(
        f"TS messages:             {ts_count:,}"
    )

    print(
        f"TS for known RIDs:       {known_train_ts_count:,}"
    )

    print(
        f"TS for unknown RIDs:     {unknown_train_ts_count:,}"
    )

    print(
        f"Station TS matches:      {station_match_count:,}"
    )

    print(
        f"RID records retained:    {len(trains):,}"
    )

    consumer.close()
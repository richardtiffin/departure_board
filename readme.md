# Train Departure Board

A Python-based digital train departure board that displays real-time train information for a specific platform at a railway station. The application uses the National Rail Data Feeds API to fetch live departure information and presents it in a visually appealing digital display format.

## Features

- Real-time train departure information
- Platform-specific display
- Scrolling text for calling points
- Digital clock display
- Configurable display settings
- Support for multiple platforms
- Weather information integration (optional)

## Prerequisites

- Python 3.x
- Pygame
- Zeep (SOAP client for Python)
- National Rail Data Feeds API key

## Installation

1. Clone this repository:
```bash
git clone https://github.com/jennybuni/train-board.git
cd train-board
```

2. Install the required dependencies:
```bash
pip install pygame zeep
```

3. Configure the application:

The `config.json` file allows you to customize various aspects of the display:

- `API_KEY`: Your National Rail Data Feeds API key
- `STATION_CODE`: The station code (e.g., "OXN" for Oxford)
- `TARGET_PLATFORMS`: Array of platform numbers to monitor
- `TEST_MODE`: Enable/disable test mode
- `UPDATE_INTERVAL`: Time between API updates (in seconds)
- `ROTATE_DISPLAY`: Enable/disable display rotation
- `SCROLL_SPEED`: Speed of scrolling text
- `CLOCK_FONT_SIZE`: Size of the clock display
- `TRAIN_FONT_SIZE`: Size of train information text
- `STATUS_FONT_SIZE`: Size of status text
- `LATITUDE`: Latitude for temp
- `LONGITUDE`: Longitude for temp

## Usage

Run the main application:
```bash
python3 departure_board.py
```

The display will show:
- Current time
- Train departures for the specified platform
- Destination and scheduled departure time
- Calling points (scrolling text)
- Service status
- temperature of the location set in the config.json

## Controls

- Press `ESC` to exit the application
- Close the window to quit



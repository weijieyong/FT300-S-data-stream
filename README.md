# FT300-S Data Stream

A Python package for streaming force/torque data from the FT300-S sensor with support for data logging and real-time monitoring.


## Prerequisites

- Docker or uv installed
- FT300-S connected via USB (e.g. `/dev/ttyUSB0`)  

> [!TIP]
> After plugging in your FT300-S, run:
> ```bash
> dmesg | grep -E 'ttyUSB|ttyACM' | tail -n 10
> ```
> to see which `/dev/tty*` device was assigned.


## Installation

### Method 1: Docker container

```bash
# 1. Build image
docker build -t uv-env .

# 2. Run container, mounting only FT300-S device
docker run --rm -it --device /dev/ttyUSB0:/dev/ttyUSB0 uv-env

# 3. Inside container, start streaming
uv run ft300s_stream.py -p /dev/ttyUSB0
```

### Method 2: Local uv install
> [!NOTE]
> **What is uv?**   
> [uv](https://github.com/astral-sh/uv) is a fast Python package and project manager (similar to pip but faster). It automatically handles dependencies and virtual environments for you.

```bash
# 1. Install uv (system or venv)
pip install uv

# 2. Grant USB access (with your device path)
sudo chmod 666 /dev/ttyUSB0

# 3. Run streaming script directly
uv run ft300s_stream.py -p /dev/ttyUSB0
```

## Usage

### Basic streaming
```bash
# Run the script directly
uv run ft300s_stream.py -p /dev/ttyUSB0
```

### With data logging
```bash
# Log to CSV file
uv run ft300s_stream.py -p /dev/ttyUSB0 --csv-output sensor_data.csv

# Log to JSON file  
uv run ft300s_stream.py -p /dev/ttyUSB0 --json-output sensor_data.json

```

## Package Structure

```
ft300s-stream-py/
├── src/ft300s/           # Core package
│   ├── sensor.py         # FT300 sensor interface
│   ├── logger.py         # Data logging utilities
│   └── exceptions.py     # Custom exceptions
├── ft300s_stream.py      # Main application script
├── pyproject.toml        # Package configuration
└── Dockerfile            # Container setup
```

## Features

- **Real-time streaming** at up to 100Hz
- **Data logging** to CSV and JSON formats
- **Error handling** with CRC validation
- **Graceful shutdown** with Ctrl+C
- **Docker support** for containerized deployment
- **Modular design** with reusable components

## Sample Output

```
F: 100Hz | Force: [  -0.08,   -0.12,   -0.02] N | Torque: [-0.000,  0.000,  0.000] Nm
F: 100Hz | Force: [  -0.02,   -0.15,    0.01] N | Torque: [-0.000,  0.000,  0.000] Nm
F: 100Hz | Force: [   0.03,   -0.14,    0.05] N | Torque: [-0.000,  0.000,  0.000] Nm
F: 100Hz | Force: [   0.00,   -0.07,    0.05] N | Torque: [-0.000,  0.000,  0.000] Nm
F: 100Hz | Force: [  -0.04,   -0.04,    0.02] N | Torque: [-0.000,  0.000,  0.000] Nm
F: 100Hz | Force: [  -0.04,   -0.04,   -0.02] N | Torque: [-0.000,  0.000,  0.000] Nm
```

## Sensor Axes

<figure align="center">
  <img src="docs/axis.png" alt="Axis Diagram" width="400" />
  <figcaption><em>FT300-S sensor axis orientation diagram.</em></figcaption>
</figure>


## Credits

- modified from: https://github.com/castetsb/pyFT300/blob/main/pyFT300stream.py
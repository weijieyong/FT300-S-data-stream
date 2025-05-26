
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FT300 Force/Torque Sensor Interface

This module provides a clean interface for communicating with the FT300 sensor
in streaming mode using Python.
"""

import time
import logging
import contextlib
from typing import List, Optional, Tuple
import serial
import minimalmodbus as mm
import libscrc

from ft300s.exceptions import FT300Error, CRCError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@contextlib.contextmanager
def serial_connection(port: str, **kwargs):
    """Context manager for safe serial connections"""
    ser = None
    try:
        ser = serial.Serial(port=port, **kwargs)
        logger.debug(f"Serial connection opened on {port}")
        yield ser
    except Exception as e:
        logger.error(f"Serial connection error on {port}: {e}")
        raise FT300Error(f"Failed to connect to {port}: {e}")
    finally:
        if ser and ser.is_open:
            ser.close()
            logger.debug(f"Serial connection closed on {port}")


class FT300MessageParser:
    """Handles parsing and validation of FT300 serial messages"""

    START_BYTES = bytes([0x20, 0x4E])
    MESSAGE_LENGTH = 16

    @staticmethod
    def format_message(raw_data: bytes) -> bytearray:
        """Format raw serial data into proper message format"""
        data_array = bytearray(raw_data)
        return FT300MessageParser.START_BYTES + data_array[:-2]

    @staticmethod
    def validate_crc(message: bytearray) -> bool:
        """Validate CRC checksum of the message"""
        if len(message) < FT300MessageParser.MESSAGE_LENGTH:
            return False

        received_crc = int.from_bytes(message[14:16], byteorder="little", signed=False)
        calculated_crc = libscrc.modbus(message[0:14])
        return received_crc == calculated_crc

    @staticmethod
    def extract_force_torque(message: bytearray, zero_ref: List[float]) -> List[float]:
        """Extract force and torque values from serial message"""
        if len(message) < FT300MessageParser.MESSAGE_LENGTH:
            raise FT300Error("Message too short")

        force_torque = []

        # Extract force values (Fx, Fy, Fz) - divide by 100
        for i in range(3):
            offset = 2 + i * 2
            raw_value = int.from_bytes(message[offset:offset+2],
                                     byteorder="little", signed=True)
            value = round(raw_value / 100.0 - zero_ref[i], 2)
            force_torque.append(value)

        # Extract torque values (Tx, Ty, Tz) - divide by 1000
        for i in range(3):
            offset = 8 + i * 2
            raw_value = int.from_bytes(message[offset:offset+2],
                                     byteorder="little", signed=True)
            value = round(raw_value / 1000.0 - zero_ref[i + 3], 2)
            force_torque.append(value)

        return force_torque


class FT300Sensor:
    """Main interface for FT300 Force/Torque Sensor"""

    # Serial communication parameters
    DEFAULT_BAUDRATE = 19200
    DEFAULT_BYTESIZE = 8
    DEFAULT_PARITY = "N"
    DEFAULT_STOPBITS = 1
    DEFAULT_TIMEOUT = 1
    DEFAULT_SLAVE_ADDRESS = 9

    # Modbus register for streaming control
    STREAMING_REGISTER = 410
    STREAMING_ENABLE_VALUE = 0x0200

    def __init__(self, port: str, slave_address: int = DEFAULT_SLAVE_ADDRESS):
        """Initialize FT300 sensor interface"""
        self.port = port
        self.slave_address = slave_address
        self.parser = FT300MessageParser()
        self.zero_reference = [0.0] * 6  # [Fx, Fy, Fz, Tx, Ty, Tz]

        # Serial parameters
        self.serial_params = {
            'baudrate': self.DEFAULT_BAUDRATE,
            'bytesize': self.DEFAULT_BYTESIZE,
            'parity': self.DEFAULT_PARITY,
            'stopbits': self.DEFAULT_STOPBITS,
            'timeout': self.DEFAULT_TIMEOUT
        }

    def stop_streaming(self) -> None:
        """Stop the sensor data stream"""
        logger.info("Stopping FT300 data stream...")

        with serial_connection(self.port, **self.serial_params) as ser:
            # Send 50 0xFF bytes to stop streaming
            stop_packet = bytearray([0xFF] * 50)
            ser.write(stop_packet)
            time.sleep(0.1)  # Allow time for the command to take effect

        logger.info("Data stream stopped")

    def start_streaming(self) -> None:
        """Start the sensor data stream using Modbus"""
        logger.info("Starting FT300 data stream...")

        # Configure minimalmodbus
        mm.BAUDRATE = self.serial_params['baudrate']
        mm.BYTESIZE = self.serial_params['bytesize']
        mm.PARITY = self.serial_params['parity']
        mm.STOPBITS = self.serial_params['stopbits']
        mm.TIMEOUT = self.serial_params['timeout']

        # Create Modbus instrument
        instrument = mm.Instrument(self.port, slaveaddress=self.slave_address)
        instrument.close_port_after_each_call = True

        try:
            # Write to streaming register to enable streaming
            instrument.write_register(self.STREAMING_REGISTER, self.STREAMING_ENABLE_VALUE)
            time.sleep(0.1)  # Allow time for the command to take effect
            logger.info("Data stream started")
        except Exception as e:
            raise FT300Error(f"Failed to start streaming: {e}")
        finally:
            del instrument

    def calibrate_zero_reference(self, ser: serial.Serial) -> None:
        """Calibrate the zero reference using current sensor readings"""
        logger.info("Calibrating zero reference...")

        # Discard first (potentially incomplete) message
        ser.read_until(self.parser.START_BYTES)

        # Read calibration message
        raw_data = ser.read_until(self.parser.START_BYTES)
        message = self.parser.format_message(raw_data)

        if not self.parser.validate_crc(message):
            raise CRCError("CRC validation failed during calibration")

        # Extract values without zero reference (use zeros)
        zero_ref = [0.0] * 6
        self.zero_reference = self.parser.extract_force_torque(message, zero_ref)

        logger.info(f"Zero reference calibrated: {self.zero_reference}")

    def read_force_torque(self, ser: serial.Serial) -> List[float]:
        """Read a single force/torque measurement"""
        raw_data = ser.read_until(self.parser.START_BYTES)
        message = self.parser.format_message(raw_data)

        if not self.parser.validate_crc(message):
            raise CRCError("CRC validation failed")

        return self.parser.extract_force_torque(message, self.zero_reference)

    def initialize(self) -> None:
        """Initialize the sensor for streaming"""
        self.stop_streaming()
        self.start_streaming()


class FT300DataCollector:
    """Handles data collection and frequency calculation"""

    def __init__(self, sensor: FT300Sensor):
        self.sensor = sensor
        self.message_count = 0
        self.start_time = None
        self.last_frequency = 0

    def start_collection(self) -> None:
        """Start data collection timing"""
        self.message_count = 0
        self.start_time = time.time()
        logger.info("Data collection started")

    def collect_data(self, ser: serial.Serial) -> Tuple[List[float], int]:
        """Collect a single data point and return force/torque values and frequency"""
        if self.start_time is None:
            raise FT300Error("Data collection not started")

        force_torque = self.sensor.read_force_torque(ser)

        # Update statistics
        self.message_count += 1
        elapsed_time = time.time() - self.start_time

        if elapsed_time > 0:
            self.last_frequency = round(self.message_count / elapsed_time)

        return force_torque, self.last_frequency

    def reset_statistics(self) -> None:
        """Reset collection statistics"""
        self.message_count = 0
        self.start_time = time.time()


class FT300StreamReader:
    """High-level interface for streaming FT300 data"""

    def __init__(self, port: str, slave_address: int = FT300Sensor.DEFAULT_SLAVE_ADDRESS):
        self.sensor = FT300Sensor(port, slave_address)
        self.collector = FT300DataCollector(self.sensor)
        self._running = False

    def start(self, calibrate: bool = True) -> None:
        """Start the streaming session"""
        logger.info(f"Starting FT300 stream reader on {self.sensor.port}")

        # Initialize sensor
        self.sensor.initialize()

        # Open serial connection for streaming
        self._serial_connection = serial_connection(
            self.sensor.port, **self.sensor.serial_params
        )
        self._ser = self._serial_connection.__enter__()

        # Calibrate zero reference if requested
        if calibrate:
            self.sensor.calibrate_zero_reference(self._ser)

        # Start data collection
        self.collector.start_collection()
        self._running = True

        logger.info("Stream reader started successfully")

    def read_data(self) -> Tuple[List[float], int]:
        """Read a single data point"""
        if not self._running:
            raise FT300Error("Stream reader not started")

        try:
            return self.collector.collect_data(self._ser)
        except CRCError as e:
            logger.warning(f"CRC error encountered: {e}")
            raise

    def stop(self) -> None:
        """Stop the streaming session"""
        if self._running:
            self._running = False
            if hasattr(self, '_serial_connection'):
                self._serial_connection.__exit__(None, None, None)
            logger.info("Stream reader stopped")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FT300 Force/Torque Sensor Streaming Application

This is the main application script for streaming data from the FT300 sensor.
"""

import argparse
import signal
import sys
import time
import logging
from typing import Optional

from ft300s import FT300StreamReader, FT300Error, CRCError, FT300DataLogger

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FT300Application:
    """Main application class for FT300 streaming"""

    def __init__(self, args):
        self.args = args
        self.stream_reader: Optional[FT300StreamReader] = None
        self.data_logger: Optional[FT300DataLogger] = None
        self.running = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def setup(self) -> None:
        """Setup the application components"""
        logger.info("Setting up FT300 application...")

        # Create stream reader
        self.stream_reader = FT300StreamReader(
            port=self.args.port,
            slave_address=self.args.slave_address
        )

        # Create data logger
        csv_file = self.args.csv_output if self.args.csv_output else None
        json_file = self.args.json_output if self.args.json_output else None

        self.data_logger = FT300DataLogger(
            csv_filename=csv_file,
            json_filename=json_file,
            buffer_size=self.args.buffer_size
        )

        logger.info("Application setup complete")

    def run(self) -> None:
        """Run the main application loop"""
        logger.info("Starting FT300 data streaming...")

        try:
            with self.stream_reader:
                # Start streaming
                self.stream_reader.start(calibrate=not self.args.no_calibration)
                self.running = True

                crc_error_count = 0
                last_stats_time = time.time()

                logger.info("Data streaming started. Press Ctrl+C to stop.")

                while self.running:
                    try:
                        # Read data
                        force_torque, frequency = self.stream_reader.read_data()

                        # Log data
                        self.data_logger.log_data(force_torque, frequency)

                        # Reset CRC error count on successful read
                        crc_error_count = 0

                        # Display data
                        if not self.args.quiet:
                            fx, fy, fz, tx, ty, tz = force_torque
                            print(f"F: {frequency:3d}Hz | "
                                  f"Force: [{fx:7.2f}, {fy:7.2f}, {fz:7.2f}] N | "
                                  f"Torque: [{tx:6.3f}, {ty:6.3f}, {tz:6.3f}] Nm")

                        # Show statistics periodically
                        current_time = time.time()
                        if (self.args.show_stats and
                            current_time - last_stats_time >= self.args.stats_interval):

                            stats = self.data_logger.get_statistics()
                            if stats:
                                logger.info(f"Statistics (last {stats['sample_count']} samples):")
                                for axis in ['fx', 'fy', 'fz', 'tx', 'ty', 'tz']:
                                    if axis in stats:
                                        s = stats[axis]
                                        logger.info(f"  {axis.upper()}: "
                                                   f"mean={s['mean']}, std={s['std']}, "
                                                   f"range=[{s['min']}, {s['max']}]")

                            last_stats_time = current_time

                    except CRCError:
                        crc_error_count += 1
                        if crc_error_count <= self.args.max_crc_errors:
                            logger.warning(f"CRC error #{crc_error_count}, continuing...")
                            continue
                        else:
                            logger.error(f"Too many CRC errors ({crc_error_count}), stopping")
                            break

                    except Exception as e:
                        logger.error(f"Unexpected error during data reading: {e}")
                        if not self.args.continue_on_error:
                            break
                        time.sleep(0.1)  # Brief pause before retry

        except FT300Error as e:
            logger.error(f"FT300 sensor error: {e}")
            return 1
        except Exception as e:
            logger.error(f"Unexpected application error: {e}")
            return 1

        logger.info("Data streaming stopped")
        return 0

    def cleanup(self) -> None:
        """Cleanup resources"""
        logger.info("Cleaning up...")

        if self.data_logger:
            # Show final statistics
            if self.args.show_stats:
                stats = self.data_logger.get_statistics()
                if stats and stats['sample_count'] > 0:
                    logger.info(f"Final statistics ({stats['sample_count']} total samples):")
                    for axis in ['fx', 'fy', 'fz', 'tx', 'ty', 'tz']:
                        if axis in stats:
                            s = stats[axis]
                            logger.info(f"  {axis.upper()}: "
                                       f"mean={s['mean']}, std={s['std']}, "
                                       f"range=[{s['min']}, {s['max']}]")

            self.data_logger.close()

        logger.info("Cleanup complete")


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        description="FT300 Force/Torque Sensor Streaming Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -p /dev/ttyUSB0                    # Basic streaming
  %(prog)s -p COM3 --csv-output data.csv     # Stream with CSV logging
  %(prog)s -p /dev/ttyUSB0 --show-stats      # Stream with statistics
        """
    )

    # Connection settings
    parser.add_argument(
        "-p", "--port",
        default="/dev/ttyUSB0",
        help="Serial port where FT300 is connected (default: /dev/ttyUSB0)"
    )

    parser.add_argument(
        "--slave-address",
        type=int,
        default=9,
        help="Modbus slave address of the FT300 (default: 9)"
    )

    # Output settings
    parser.add_argument(
        "--csv-output",
        help="Save data to CSV file"
    )

    parser.add_argument(
        "--json-output",
        help="Save data to JSON file"
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress real-time data output"
    )

    # Statistics and monitoring
    parser.add_argument(
        "--show-stats",
        action="store_true",
        help="Show periodic statistics"
    )

    parser.add_argument(
        "--stats-interval",
        type=float,
        default=10.0,
        help="Statistics display interval in seconds (default: 10.0)"
    )

    parser.add_argument(
        "--buffer-size",
        type=int,
        default=1000,
        help="Size of the data buffer for statistics (default: 1000)"
    )

    # Error handling
    parser.add_argument(
        "--max-crc-errors",
        type=int,
        default=10,
        help="Maximum consecutive CRC errors before stopping (default: 10)"
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue operation on non-critical errors"
    )

    # Calibration
    parser.add_argument(
        "--no-calibration",
        action="store_true",
        help="Skip zero reference calibration on startup"
    )

    # Debug
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    return parser


def main() -> int:
    """Main entry point"""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create and run application
    app = FT300Application(args)

    try:
        app.setup()
        return app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Application failed: {e}")
        return 1
    finally:
        app.cleanup()


if __name__ == "__main__":
    sys.exit(main())

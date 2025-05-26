#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data logging utilities for FT300 sensor data
"""

import csv
import time
import json
from typing import List, Optional, Dict, Any
from collections import deque
import statistics


class FT300DataLogger:
    """Handles logging of FT300 sensor data to various formats"""

    def __init__(self, csv_filename: Optional[str] = None,
                 json_filename: Optional[str] = None,
                 buffer_size: int = 1000):
        self.csv_filename = csv_filename
        self.json_filename = json_filename
        self.buffer = deque(maxlen=buffer_size)

        # CSV setup
        self.csv_file = None
        self.csv_writer = None
        if csv_filename:
            self._setup_csv()

        # JSON setup
        self.json_data = []

    def _setup_csv(self) -> None:
        """Setup CSV file and writer"""
        self.csv_file = open(self.csv_filename, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)

        # Write header
        header = ['timestamp', 'fx', 'fy', 'fz', 'tx', 'ty', 'tz', 'frequency']
        self.csv_writer.writerow(header)

    def log_data(self, force_torque: List[float], frequency: int) -> None:
        """Log a data point"""
        timestamp = time.time()

        # Add to buffer
        data_point = {
            'timestamp': timestamp,
            'force_torque': force_torque,
            'frequency': frequency
        }
        self.buffer.append(data_point)

        # Write to CSV if enabled
        if self.csv_writer:
            row = [timestamp] + force_torque + [frequency]
            self.csv_writer.writerow(row)
            self.csv_file.flush()  # Ensure data is written

        # Add to JSON data if enabled
        if self.json_filename:
            self.json_data.append(data_point)

    def get_statistics(self) -> Dict[str, Any]:
        """Calculate statistics from buffered data"""
        if not self.buffer:
            return {}

        # Extract force/torque data by axis
        fx_data = [point['force_torque'][0] for point in self.buffer]
        fy_data = [point['force_torque'][1] for point in self.buffer]
        fz_data = [point['force_torque'][2] for point in self.buffer]
        tx_data = [point['force_torque'][3] for point in self.buffer]
        ty_data = [point['force_torque'][4] for point in self.buffer]
        tz_data = [point['force_torque'][5] for point in self.buffer]

        freq_data = [point['frequency'] for point in self.buffer]

        def calc_stats(data: List[float]) -> Dict[str, float]:
            if not data:
                return {}
            return {
                'mean': round(statistics.mean(data), 3),
                'std': round(statistics.stdev(data) if len(data) > 1 else 0, 3),
                'min': round(min(data), 3),
                'max': round(max(data), 3)
            }

        return {
            'fx': calc_stats(fx_data),
            'fy': calc_stats(fy_data),
            'fz': calc_stats(fz_data),
            'tx': calc_stats(tx_data),
            'ty': calc_stats(ty_data),
            'tz': calc_stats(tz_data),
            'frequency': calc_stats(freq_data),
            'sample_count': len(self.buffer)
        }

    def save_json(self) -> None:
        """Save collected data to JSON file"""
        if self.json_filename and self.json_data:
            with open(self.json_filename, 'w') as f:
                json.dump(self.json_data, f, indent=2)

    def close(self) -> None:
        """Close files and clean up"""
        if self.csv_file:
            self.csv_file.close()

        if self.json_filename:
            self.save_json()

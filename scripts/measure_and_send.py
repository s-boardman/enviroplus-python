#!/usr/bin/env python3

import time
import datetime
import sqlite3
import logging
import argparse

# Configure basic logging, will be updated later with argparse
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

try:
    # This import is required to initialize the board
    from enviroplus import gas
except ImportError:
    logging.error("The 'enviroplus-python' library is not installed. Please install it by running: pip3 install enviroplus-python")
    exit()

try:
    # The BME280 sensor for temperature, pressure, and humidity
    from bme280 import BME280
except ImportError:
    logging.error("The 'bme280' library is not installed. Please install it by running: pip3 install enviroplus-python[bme280]")
    exit()

try:
    # The LTR559 sensor for light
    from ltr559 import LTR559
except ImportError:
    logging.error("The 'ltr559' library is not installed. Please install it by running: pip3 install enviroplus-python[ltr559]")
    exit()

try:
    # The PMS5003 sensor for particulate matter
    from pms5003 import PMS5003, ReadTimeoutError
except ImportError:
    logging.error("The 'pms5003' library is not installed. Please install it by running: pip3 install pms5003")
    exit()

# Initialize the sensors
bme280 = BME280()
ltr559 = LTR559()
pms5003_sensor = PMS5003()

def create_database_table(db_file):
    """
    Connects to the SQLite database and creates the 'measurements' table
    if it doesn't already exist.
    """
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS measurements (
                    timestamp DATETIME,
                    temperature REAL,
                    pressure REAL,
                    humidity REAL,
                    light_lux REAL,
                    light_proximity REAL,
                    pm1_0_standard REAL,
                    pm2_5_standard REAL,
                    pm10_standard REAL,
                    pm1_0_env REAL,
                    pm2_5_env REAL,
                    pm10_env REAL,
                    oxidising REAL,
                    reducing REAL,
                    nh3 REAL
                )''')
    conn.commit()
    conn.close()

def get_sensor_data():
    """
    Reads all available data from the Enviro+ sensors.
    Handles potential errors with PMS5003 and gas sensor readings.
    Returns a dictionary of sensor data.
    """
    data = {}

    # BME280 readings
    data['temperature'] = bme280.get_temperature()
    data['pressure'] = bme280.get_pressure()
    data['humidity'] = bme280.get_humidity()

    # LTR559 readings
    data['light_lux'] = ltr559.get_lux()
    data['light_proximity'] = ltr559.get_proximity()
    
    try:
        # PMS5003 particulate matter readings
        pms5003_data = pms5003_sensor.read()
        data['pm1_0_standard'] = pms5003_data.pm_ug_per_m3(1.0, False)
        data['pm2_5_standard'] = pms5003_data.pm_ug_per_m3(2.5, False)
        data['pm10_standard'] = pms5003_data.pm_ug_per_m3(10, False)
        data['pm1_0_env'] = pms5003_data.pm_ug_per_m3(1.0, True)
        data['pm2_5_env'] = pms5003_data.pm_ug_per_m3(2.5, True)
        data['pm10_env'] = pms5003_data.pm_ug_per_m3(None, True)
    except ReadTimeoutError:
        # This can happen if the sensor is not ready
        logging.warning("PMS5003 sensor read timeout. Skipping particulate matter data.")
        data.update({
            'pm1_0_standard': None,
            'pm2_5_standard': None,
            'pm10_standard': None,
            'pm1_0_env': None,
            'pm2_5_env': None,
            'pm10_env': None
        })

    # Gas sensor readings
    gas_data = gas.read_all()
    data['oxidising'] = gas_data.oxidising
    data['reducing'] = gas_data.reducing
    data['nh3'] = gas_data.nh3

    return data

def log_data(data, db_file):
    """
    Inserts a single set of sensor data into the SQLite database.
    """
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO measurements VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (data['timestamp'], data['temperature'], data['pressure'], data['humidity'],
                   data['light_lux'], data['light_proximity'],
                   data['pm1_0_standard'], data['pm2_5_standard'], data['pm10_standard'],
                   data['pm1_0_env'], data['pm2_5_env'], data['pm10_env'],
                   data['oxidising'], data['reducing'], data['nh3']))
        conn.commit()
    except Exception as e:
        logging.error(f"Error logging data: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Mapping for log levels
    LOG_LEVELS = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }
    
    parser = argparse.ArgumentParser(description='Log environmental data from an Enviro+ HAT to an SQLite database.')
    parser.add_argument('--db-file', type=str, default='enviroplus_data.db',
                        help='Specify the name of the database file.')
    parser.add_argument('--log-level', type=str, default='info',
                        choices=list(LOG_LEVELS.keys()),
                        help='Set the logging level (debug, info, warning, error, critical).')
    
    args = parser.parse_args()
    DB_FILE = args.db_file
    
    # Update the logging level based on the argument
    logging.getLogger().setLevel(LOG_LEVELS[args.log_level])
    
    logging.info(f"Starting Enviro+ data logger. Data will be saved to '{DB_FILE}'.")
    
    create_database_table(DB_FILE)

    timestamp = datetime.datetime.now().isoformat()
    
    logging.info(f"Reading sensor data for timestamp: {timestamp}")
    sensor_data = get_sensor_data()
    sensor_data['timestamp'] = timestamp
    
    logging.debug(f"Sensor data read: {sensor_data}")
    
    log_data(sensor_data, DB_FILE)
    
    logging.info("Data logged successfully. Exiting.")

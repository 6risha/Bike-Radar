import os
import redis
import json
import mysql.connector as mysql
from datetime import datetime
from dotenv import load_dotenv


def to_proper_datetime(date_time_str):
    try:
        date_part = date_time_str[:19]
        additional_hour = int(date_time_str[20:])
        date_time_obj = datetime.strptime(date_part, '%m/%d/%Y %H:%M:%S')
        date_time_obj = date_time_obj.replace(hour=additional_hour)
        return date_time_obj
    except ValueError:
        try:
            return datetime.strptime(date_time_str, '%m/%d/%Y %H:%M:%S')
        except ValueError:
            return None


if __name__ == "__main__":
    print("::: Starting the script...")

    load_dotenv()

    INSA_HOST = os.getenv('INSA_HOST')
    INSA_PORT = os.getenv('INSA_PORT')
    INSA_USER = os.getenv('INSA_USER')
    INSA_PASSWORD = os.getenv('INSA_PASSWORD')
    INSA_DB = os.getenv('INSA_DB')

    REDIS_HOST = os.getenv('REDIS_HOST')
    REDIS_PORT = os.getenv('REDIS_PORT')
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

    print("::: Connecting to the MySQL DB...")
    db_connection = mysql.connect(
        host=INSA_HOST,
        port=int(INSA_PORT),
        user=INSA_USER,
        password=INSA_PASSWORD,
        database=INSA_DB
    )
    print("::: Connection to MySQL established successfully.")

    cursor = db_connection.cursor()
    cursor.execute("SELECT * FROM Rides WHERE idRide = (SELECT MAX(idRide) FROM Rides);")
    last_ride_data = cursor.fetchone()

    last_ride_id = last_ride_data[0]
    # last_ride_end = last_ride_data[4]
    last_ride_end = datetime(2024, 6, 8, 12, 0)
    print(last_ride_id, last_ride_end, type(last_ride_end))

    cursor.close()
    db_connection.close()
    print("::: Connection to MySQL closed.")

    input("::: Connection to the DB is closed. Disconnect from VPN, press Enter to continue...")
    print()
    print("::: You have continued the execution of the script.")

    print("::: Connecting to the Redis server...")
    r = redis.Redis(
        host=REDIS_HOST,
        port=int(REDIS_PORT),
        password=REDIS_PASSWORD
    )
    print("::: Connection to Redis established successfully.")

    rides = json.loads(r.get('rides:Rides').decode('utf-8'))
    constant_measurements = json.loads(r.get('rides:ConstantMeasurements').decode('utf-8'))
    crash_measurements = json.loads(r.get('rides:CrashMeasurements').decode('utf-8'))
    car_distance_measurements = json.loads(r.get('rides:CarDistanceMeasurements').decode('utf-8'))

    data_to_upload = []

    for ride in rides:
        timeStart = to_proper_datetime(ride[0])
        timeEnd = to_proper_datetime(ride[1])
        if timeStart is None or timeEnd is None:
            print(f"::: Invalid Ride: {ride}")
            continue

        try:
            username = ride[2]
            if username is None:
                username = 'grisha'
        except IndexError:
            username = 'grisha'

        if timeStart > last_ride_end:
            # 3 - CST meas, 4 - CAR meas, 5 - CRASH meas
            data_to_upload.append([timeStart, timeEnd, username, [], [], []])

    print(f'::: Rides to upload: {len(data_to_upload)}')

    # INDEX 3
    for elem in constant_measurements:
        timestamp = to_proper_datetime(elem[0])

        if timestamp is None:
            print(f"::: Invalid CST value: {elem}")
            continue

        if timestamp < last_ride_end:
            continue

        longitude = float(elem[1])
        latitude = float(elem[2])
        altitude = int(float(elem[3]))
        try:
            luminosity = int(elem[4])
            light_mode = int(elem[5])
        except ValueError:
            print(f"::: Invalid CST value: {elem}")
            continue

        for upload in data_to_upload:
            if upload[0] < timestamp < upload[1]:
                upload[3].append([timestamp, longitude, latitude, altitude, luminosity, light_mode])
                break
    # INDEX 4
    for elem in car_distance_measurements:
        timestamp = to_proper_datetime(elem[0])

        if timestamp is None:
            print(f"::: Invalid CAR value: {elem}")
            continue

        try:
            car_dist = int(elem[1])
        except ValueError:
            print(f"::: Invalid CAR value: {elem}")
            continue

        for upload in data_to_upload:
            if upload[0] < timestamp < upload[1]:
                upload[4].append([timestamp, car_dist])
                break
    # INDEX 5
    for elem in crash_measurements:
        timestamp = to_proper_datetime(elem[0])

        if timestamp is None:
            print(f"::: Invalid CRASH value: {elem}")
            continue

        if timestamp < last_ride_end:
            continue
        try:
            roll = int(elem[1])
            pitch = int(elem[2])
            yaw = int(elem[3])
        except ValueError:
            print(f"::: Invalid CRASH value: {elem}")
            continue

        # Second check
        if abs(roll) > 200 or abs(pitch) > 200 or abs(yaw) > 200:
            continue

        for upload in data_to_upload:
            if upload[0] < timestamp < upload[1]:
                upload[5].append([timestamp, roll, pitch, yaw])
                break

    # print(data_to_upload)

    r.close()

    input("::: Connection to Redis is closed. Connect to VPN, press Enter to continue...")
    print()
    print("::: You have continued the execution of the script.")

    print("::: Reconnecting to the MySQL DB to upload data...")
    db_connection = mysql.connect(
        host=INSA_HOST,
        port=int(INSA_PORT),
        user=INSA_USER,
        password=INSA_PASSWORD,
        database=INSA_DB
    )
    print("::: Reconnected to MySQL successfully.")

    cursor = db_connection.cursor()

    for upload in data_to_upload:
        timeStart, timeEnd, username, const_meas, car_meas, crash_meas = upload
        cursor.execute("SELECT idUser FROM Users WHERE username = %s", ("grisha",))
        user_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO Rides (timeStart, timeEnd, idCyclist, idDevice) VALUES (%s, %s, %s, %s)",
                       (timeStart, timeEnd, user_id, 1))

        cursor.execute("SELECT MAX(idRide) FROM Rides;")
        ride_id = cursor.fetchone()[0]

        for const in const_meas:
            # [datetime.datetime(2024, 6, 6, 15, 28, 52), 4.87435606, 45.78473832, 252, 324, 0]
            cursor.execute(
                "INSERT INTO ConstantMeasurements (timestamp, idRide, longitude, latitude, altitude, luminosity, lightMode) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (const[0], ride_id, const[1], const[2], const[3], const[4], const[5]))

        for car in car_meas:
            cursor.execute("INSERT INTO CarDistanceMeasurements (timestamp, idRide, distanceCar) VALUES (%s, %s, %s)",
                           (car[0], ride_id, car[1]))

        for crash in crash_meas:
            cursor.execute(
                "INSERT INTO CrashMeasurements (timestamp, idRide, roll, pitch, yaw) VALUES (%s, %s, %s, %s, %s)",
                (crash[0], ride_id, crash[1], crash[2], crash[3]))

    db_connection.commit()
    cursor.close()
    db_connection.close()
    print("::: Data uploaded successfully and MySQL connection closed.")
    print("::: Script execution finished.")

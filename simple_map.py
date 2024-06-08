import mysql.connector as mysql
import folium
import os
from dotenv import load_dotenv

load_dotenv()

INSA_HOST = os.getenv('INSA_HOST')
INSA_PORT = os.getenv('INSA_PORT')
INSA_USER = os.getenv('INSA_USER')
INSA_PASSWORD = os.getenv('INSA_PASSWORD')
INSA_DB = os.getenv('INSA_DB')

db_connection = mysql.connect(
    host=INSA_HOST,
    port=int(INSA_PORT),
    user=INSA_USER,
    password=INSA_PASSWORD,
    database=INSA_DB
)

cursor = db_connection.cursor()

query_rides = """
SELECT idRide, latitude, longitude, timeStamp
FROM ConstantMeasurements
WHERE idRide >= 3
ORDER BY idRide, timeStamp;
"""
cursor.execute(query_rides)
ride_results = cursor.fetchall()

query_car = """
SELECT idRide, timeStamp
FROM CarDistanceMeasurements
WHERE idRide >= 3
ORDER BY idRide, timeStamp;
"""
cursor.execute(query_car)
car_results = cursor.fetchall()

query_crash = """
SELECT idRide, timeStamp, roll, pitch, yaw
FROM CrashMeasurements
WHERE idRide >= 3
ORDER BY idRide, timeStamp;
"""
cursor.execute(query_crash)
crash_results = cursor.fetchall()

cursor.close()
db_connection.close()


rides = {}
ride_timestamps = {}
for idRide, latitude, longitude, timeStamp in ride_results:
    if idRide not in rides:
        rides[idRide] = []
        ride_timestamps[idRide] = []
    rides[idRide].append((latitude, longitude))
    ride_timestamps[idRide].append((latitude, longitude, timeStamp))

m = folium.Map(location=[45.75, 4.85], zoom_start=12)
for ride in rides.values():
    folium.PolyLine(ride, color="green", weight=2.5, opacity=1).add_to(m)


for idRide, car_timeStamp in car_results:
    if idRide in ride_timestamps:
        closest_points = sorted(ride_timestamps[idRide], key=lambda x: abs((x[2] - car_timeStamp).total_seconds()))[:2]
        if len(closest_points) == 2:
            folium.PolyLine(
                [(closest_points[0][0], closest_points[0][1]), (closest_points[1][0], closest_points[1][1])],
                color="red",
                weight=3.5,
                opacity=1
            ).add_to(m)

for idRide, crash_timeStamp, roll, pitch, yaw in crash_results:
    if idRide in ride_timestamps:
        closest_point = min(ride_timestamps[idRide], key=lambda x: abs((x[2] - crash_timeStamp).total_seconds()))
        folium.Marker(
            location=[closest_point[0], closest_point[1]],
            popup=f'Crash at {closest_point[2]}: {roll}, {pitch}, {yaw}',
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

m.save("simple_map.html")
print("Map has been created and saved")

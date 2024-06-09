import os
import folium
import numpy as np
import mysql.connector as mysql
from dotenv import load_dotenv
from geopy.distance import geodesic
from datetime import datetime, timedelta

print("::: Script started")
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
print("::: Connected to DB")

current_datetime = datetime.now()
two_weeks_ago = current_datetime - timedelta(weeks=2)
min_idRide = 3

cursor = db_connection.cursor()

query_rides = f"""
SELECT idRide, timeStamp, latitude, longitude
FROM ConstantMeasurements
WHERE idRide >= {min_idRide} AND timeStamp >= '{two_weeks_ago}'
ORDER BY idRide, timeStamp;
"""
cursor.execute(query_rides)
ride_results = cursor.fetchall()

query_car = f"""
SELECT idRide, timeStamp, distanceCar
FROM CarDistanceMeasurements
WHERE idRide >= {min_idRide} AND timeStamp >= '{two_weeks_ago}'
ORDER BY idRide, timeStamp;
"""
cursor.execute(query_car)
car_results = cursor.fetchall()

query_crash = f"""
SELECT idRide, timeStamp, roll, pitch, yaw
FROM CrashMeasurements
WHERE idRide >= {min_idRide} AND timeStamp >= '{two_weeks_ago}'
ORDER BY idRide, timeStamp;
"""
cursor.execute(query_crash)
crash_results = cursor.fetchall()


cursor.close()
db_connection.close()
print("::: Data extracted")

# Create the grid first
m = folium.Map(location=[45.75, 4.85], zoom_start=12)
min_lat, max_lat = 45.65, 45.83
min_lon, max_lon = 4.75, 5.00
lat_step = 0.0027
lon_step = 0.0036
lat_points = np.arange(min_lat, max_lat, lat_step)
lon_points = np.arange(min_lon, max_lon, lon_step)

# We need the matrix to easily run the dijkstra's algorithm
matrix = np.empty((len(lon_points), len(lat_points)), dtype=object)
squares = {}

for col, lat in enumerate(lat_points):
    for row, lon in enumerate(lon_points):
        top_left = (lat, lon)
        top_right = (lat, lon + lon_step)
        bottom_left = (lat + lat_step, lon)
        bottom_right = (lat + lat_step, lon + lon_step)

        center_lat = lat + lat_step / 2
        center_lon = lon + lon_step / 2
        center_point = (center_lat, center_lon)

        matrix[row][col] = [center_point, 0]

        # coordinates, points, color, amount of rides passed through this square
        square = [top_left, top_right, bottom_right, bottom_left, 0, 'grey', set(), row, col]
        squares[center_point] = square
        # folium.CircleMarker(location=center_point, radius=2, color='red', fill=True, fill_opacity=1).add_to(m)


print("::: Grid created")

# "locations" is for display, "ride_timestamps" of for the following analysis
ride_timestamps = {}
locations = {}
for idRide, timeStamp, latitude, longitude in ride_results:
    if idRide not in ride_timestamps.keys():
        ride_timestamps[idRide] = []
        locations[idRide] = []
    ride_timestamps[idRide].append((latitude, longitude, timeStamp))
    locations[idRide].append((latitude, longitude))
    square = squares[tuple(min(squares.keys(), key=lambda x: geodesic((latitude, longitude), x).meters))]
    square[5] = 'green'
    if idRide not in square[6]:
        square[6].add(idRide)

for ride in locations.values():
    folium.PolyLine(ride, color="blue", weight=2.5, opacity=1).add_to(m)

print("::: Trajectories drawn")

# Display the detected cars by finding 2 closest in time locations for each car
for idRide, car_timeStamp, distanceCar in car_results:
    if idRide in ride_timestamps:
        closest_points = sorted(ride_timestamps[idRide], key=lambda x: abs((x[2] - car_timeStamp).total_seconds()))[:2]
        if len(closest_points) == 2:
            folium.PolyLine(
                [(closest_points[0][0], closest_points[0][1]), (closest_points[1][0], closest_points[1][1])],
                color="red",
                weight=3.5,
                opacity=1
            ).add_to(m)

        lat, lon, _ = closest_points[0]
        square = squares[tuple(min(squares.keys(), key=lambda x: geodesic((lat, lon), x).meters))]
        square[4] += np.ceil((1000 - distanceCar) / 100)

print("::: Detected cars are located")

# Display the crashes by adding closest in time
for idRide, crash_timeStamp, roll, pitch, yaw in crash_results:
    if idRide in ride_timestamps:
        closest_point = min(ride_timestamps[idRide], key=lambda x: abs((x[2] - crash_timeStamp).total_seconds()))
        folium.Marker(
            location=[closest_point[0], closest_point[1]],
            popup=f'Crash at {closest_point[2]}: {roll}, {pitch}, {yaw}',
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)

        lat, lon, _ = closest_point
        square = squares[tuple(min(squares.keys(), key=lambda x: geodesic((lat, lon), x).meters))]
        square[4] += 10
print("::: Detected crashes are located")

for square in squares.values():
    if square[5] == 'green':
        danger_level = square[4] / len(square[6])
    else:
        danger_level = -1

    if danger_level > 2:
        square[5] = 'yellow'
    if danger_level > 5:
        square[5] = 'orange'
    if danger_level >= 8:
        square[5] = 'red'

    matrix[square[7]][square[8]][1] = danger_level


"""      
# HERE IS THE PLACE TO INSERT DIJKSTRA'S ALGORITHM
# use values of matrix[row][col][1]
# NOTICE THE INDEX 1, WITH INDEX OF THE CENTER MARK THE SQUARES WE NEED TO VISIT
# UNVISITED SQUARES ARE EQUAL TO -1
"""


for square in squares.values():
    folium.Polygon(
        locations=[square[0], square[1], square[2], square[3], square[0]],
        color=square[5],
        fill=True,
        fill_color=square[5],
        fill_opacity=0.45,
        weight=0
    ).add_to(m)

print("::: Danger levels determined")

for row in matrix:
    res = ''
    for elem in row:
        res += str(elem[1]) + " "
    print(res)

m.save("map_with_danger_levels.html")
print("::: Map has been created and saved")

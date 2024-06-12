#include <Arduino.h>
#include "Ultrasonic.h"
#include "FastIMU.h"
#include <Wire.h>
#include <SensorFusion.h>
#include <Adafruit_NeoPixel.h>

// definitions for LED
#define LED_PIN     5
#define LED_COUNT  12

Adafruit_NeoPixel strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
String mode = "night";

// definitions for bluetooth
bool rideStarted = false;
const int message_delay = 350;

// definitions for distance measurement
Ultrasonic ultrasonic(7);
int distance;

// definitions for gyroscope
#define IMU_6_DOF
#define PERFORM_CALIBRATION
#define PERFORM_SENSOR_FUSION // Euler's angles

#ifdef IMU_6_DOF
  #define IMU_ADDRESS 0x6A
  LSM6DSL IMU;
#endif

AccelData accelData;
GyroData gyroData;
MagData magData;

calData calib = { 0 };

SF fusion;
float yaw = 190.0;
float pitch = 0.0;
float roll = 5.0;
float deltat;
float yaw0 = 0.0;
float pitch0 = 0.0; 
float roll0 = 0.0;
int cst = 25;
int check = 200;
int count = 0;

// definitions for luminosity sensor
const int sensorPin = A5;
const int borderValue = 800;
int luminosity = 0;

// definitions for button
const int buttonPin = 3;
int buttonState = 0;

// frequencies of measurements
unsigned long previousStampDistance = 0;
unsigned long previousStampLuminosity = 0;
unsigned long previousStampAngles = 0;
unsigned long intervalDistance = 2000;
unsigned long intervalLuminosity = 10000;
unsigned long intervalAngles = 100;

// fraquencies for LED
unsigned long previousStampLED = 0;
unsigned long intervalLED = 300;
bool turnedON = false;

// time stamps
unsigned long timeStart = 0;
unsigned long timeEnd = 0;


void setAllPixels(uint32_t color) {
  for(int i = 0; i < LED_COUNT; i++) {
    strip.setPixelColor(i, color);
  }
}

void loadingAnimation(uint32_t color, int delayTime) {
  for(int i=0; i<strip.numPixels(); i++) {
    strip.setPixelColor(i, color);
    strip.show();
    delay(delayTime);
    strip.setPixelColor(i, 0);
  }
}

void blinkLED(String mode, int amount) {
  if (mode == "night") {
    for (int i = 0; i < amount; i++) {
      setAllPixels(strip.Color(255, 0, 0));
      strip.show();
      delay(200);
      setAllPixels(0);
      strip.show();
      delay(100);
    }
  } else if (mode == "day") {
    for (int i = 0; i < amount; i++) {
      setAllPixels(strip.Color(255, 0, 0));
      strip.show();
      delay(300);
    }
  } else if (mode == "verified") {
    for (int i = 0; i < amount; i++) {
      setAllPixels(strip.Color(0, 255, 0));
      strip.show();
      delay(200);
      setAllPixels(0);
      strip.show();
      delay(100);
    }
  } else if (mode == "non-verified") {
    for (int i = 0; i < amount; i++) {
      setAllPixels(strip.Color(255, 0, 0));
      strip.show();
      delay(200);
      setAllPixels(0);
      strip.show();
      delay(100);
    }
  } else if (mode == "waiting"){
    for (int i = 0; i < amount; i++) {
      setAllPixels(strip.Color(0, 0, 255));
      strip.show();
      delay(100);
      setAllPixels(0);
      strip.show();
      delay(100);
      setAllPixels(strip.Color(0, 0, 255));
      strip.show();
      delay(100);
    }
  }
}

void parallelBlinkLED(int currentTime) {
  if (currentTime - previousStampLED >= intervalLED) {
      previousStampLED = currentTime;
      if (turnedON == false){
        setAllPixels(strip.Color(255, 0, 0));
        strip.show();
        turnedON = true;
      } else {
        setAllPixels(0);
        strip.show();
        turnedON = false;
      }
    }
}

void displayAnglesData() {
  Serial.print(accelData.accelX);
  Serial.print("\t");
  Serial.print(accelData.accelY);
  Serial.print("\t");
  Serial.print(accelData.accelZ);
  Serial.print("\t");
  Serial.print(gyroData.gyroX);
  Serial.print("\t");
  Serial.print(gyroData.gyroY);
  Serial.print("\t");
  Serial.print(gyroData.gyroZ);
  Serial.print("\t");
  Serial.print(magData.magX);
  Serial.print("\t");
  Serial.print(magData.magY);
  Serial.print("\t");
  Serial.print(magData.magZ);
  Serial.print("\n");
}

void displayAnglesFusion() {
  Serial.print(yaw);
  Serial.print("\t");
  Serial.print(pitch);
  Serial.print("\t");
  Serial.print(roll);
  Serial.print("\t");
  Serial.print(deltat);
  Serial.print("\n");
}

void performCalibration() {
  //Serial.println("FastIMU calibration & data example");
  Serial.println("FastIMU calibration:");
  if (IMU.hasMagnetometer()) {
    delay(1000);
    Serial.println("Move IMU in figure 8 pattern until done.");
    delay(3000);
    IMU.calibrateMag(&calib);
    Serial.println("Magnetic calibration done!");
    delay(3000);
  }
  Serial.println("Keep IMU level.");
  //delay(5000);
  blinkLED("waiting", 10);
  IMU.calibrateAccelGyro(&calib);
  Serial.println("Accel biases X/Y/Z: ");
  Serial.print(calib.accelBias[0]);
  Serial.print(", ");
  Serial.print(calib.accelBias[1]);
  Serial.print(", ");
  Serial.println(calib.accelBias[2]);
  Serial.println("Gyro biases X/Y/Z: ");
  Serial.print(calib.gyroBias[0]);
  Serial.print(", ");
  Serial.print(calib.gyroBias[1]);
  Serial.print(", ");
  Serial.println(calib.gyroBias[2]);
  if (IMU.hasMagnetometer()) {
    Serial.println("Mag biases X/Y/Z: ");
    Serial.print(calib.magBias[0]);
    Serial.print(", ");
    Serial.print(calib.magBias[1]);
    Serial.print(", ");
    Serial.println(calib.magBias[2]);
    Serial.println("Mag Scale X/Y/Z: ");
    Serial.print(calib.magScale[0]);
    Serial.print(", ");
    Serial.print(calib.magScale[1]);
    Serial.print(", ");
    Serial.println(calib.magScale[2]);
  }
  Serial.println("Calibration done!");
  blinkLED("waiting", 10);
  IMU.init(calib, IMU_ADDRESS);
}

void measureAndSendAngles() {
  yaw0 = yaw;
  pitch0 = pitch;
  roll0 = roll;

  IMU.update();
  IMU.getAccel(&accelData);
  IMU.getGyro(&gyroData);
  IMU.getMag(&magData);

  #ifdef PERFORM_SENSOR_FUSION
    deltat = fusion.deltatUpdate();
    fusion.MadgwickUpdate(
      gyroData.gyroX/180.0f*3.14f, gyroData.gyroY/180.0f*3.14f, gyroData.gyroZ/180.0f*3.14f, 
      accelData.accelX, accelData.accelY, accelData.accelZ, 
      magData.magX, magData.magY, magData.magZ, 
      deltat);
    roll = fusion.getRoll();
    pitch = fusion.getPitch();
    yaw = fusion.getYaw();
    displayAnglesFusion();
  #else
    displayAnglesData();
  #endif

  if ((yaw - yaw0 > cst) or (yaw - yaw0 < -cst) or (pitch - pitch0 > cst) or (pitch - pitch0 < -cst) or (roll - roll0 > cst) or (roll - roll0 < -cst)){
    // or (roll - roll0 > cst) or (roll - roll0 < -cst)
    if (count >=2) {
      int d1 = int(yaw - yaw0);
      int d2 = int(pitch - pitch0);
      int d3 = int(roll - roll0);
      if ((d1 < check) && (d1 > -check) && (d2 < check) && (d2 > -check) && (d3 < check) && (d3 > -check)) {
        // Send in order ROLL PITCH YAW
        String res = "C;" + String(d3) + ";" + String(d2) + ";" + String(d1);
        Serial1.write(res.c_str());
        Serial.println(res);
        delay(message_delay);
      }
      // String res = "C;" + String(d3) + ";" + String(d2) + ";" + String(d1);
      // Serial1.write(res.c_str());
      // Serial.println(res);
      // delay(message_delay);
    }
    count++;
  }
}

void startSystem() {
  Serial.println(">>> RIDE STARTED");
  blinkLED("verified", 2);
  // if (Serial.available()) {
  //   char outgoingData = 'S';
  //   Serial1.write(outgoingData);
  //   Serial.print("Sent: ");
  //   Serial.println(outgoingData);
  //   timeStart = millis();
  // }
}

void stopSystem() {
  Serial.println(">>> RIDE STOPPED");
  blinkLED("verified", 2);

  // timeEnd = millis();
  // int rideDuration = (timeEnd - timeStart) / 1000;
  // if (Serial.available()) {
  //   char outgoingData = 'F';
  //   Serial1.write(outgoingData);
  //   sendInt(rideDuration);
  //   Serial.print("Sent: ");
  //   Serial.print(outgoingData);
  //   Serial.print(" ");
  //   Serial.println(rideDuration);
  // }
}

void sendInt(int number) {
  byte lowByte = number & 0xFF;
  byte highByte = (number >> 8) & 0xFF;
  Serial1.write(lowByte);
  Serial1.write(highByte);
}

void sendIntAsString(int number) {
  String numberString = String(number);
  Serial1.write(numberString.c_str());
}

void sendBoolean(bool value) {
    Serial1.write(value ? 1 : 0);
}

void measureAndSendDistance() {
  distance = int(ultrasonic.read() / 1.0514);

  if (distance <= 330){
    String numberString = "D;" + String(distance);
    Serial1.write(numberString.c_str());
    // Serial1.write(numberString);
    Serial.println(numberString);
    delay(message_delay);
  }
}

void measureAndSendLuminosity() {
  luminosity = analogRead(sensorPin);
  if (luminosity >= borderValue) {
      mode = "night";
      intervalLED = 100;
    } else {
      mode = "day";
      intervalLED = 300;
    }
  String numberString = "L;" + String(luminosity);
  Serial1.write(numberString.c_str());
  //Serial1.write(numberString);
  Serial.println(numberString);
  delay(message_delay);
}


void setup() {
    // Initialization of LED
    strip.begin();
    strip.show();

    // Intialization for button
    pinMode(buttonPin, INPUT);

    // Initialization for Bluetooth
    Serial.begin(9600);

    blinkLED("waiting", 7);
    
    Serial1.begin(9600);
    Serial.println(">>> BT.Serial Communication Started");

    blinkLED("verified", 2);

    // Initialize gyroscope
    Wire.begin();
    Wire.setClock(400000);

    int errIMU = IMU.init(calib, IMU_ADDRESS);
    if (errIMU != 0) {
      blinkLED("non-verified", 3);
      Serial.print("Error initializing IMU: ");
      Serial.println(errIMU);
    } else {
      #ifdef PERFORM_CALIBRATION
        performCalibration();
      #endif

      blinkLED("verified", 2);
    }
}

void loop() {
  unsigned long currentTime = millis() + 1;

  // Bluetooth control
  if (Serial1.available()) {
    char incomingData = char(Serial1.read());
    // ride started
    if (incomingData == 'S' && rideStarted == false) {
      Serial.print("Received: ");
      Serial.println(incomingData);
      startSystem();
      rideStarted = true;
    // ride finished
    } else if (incomingData == 'F' && rideStarted == true){
      Serial.print("Received: ");
      Serial.println(incomingData);
      stopSystem();
      rideStarted = false;
    }
  }

  // Serial monitor control
  if (Serial.available()) {
    char incomingData = char(Serial.read());
    // ride started
    if (incomingData == 'S' && rideStarted == false) {
      Serial.print("Received: ");
      Serial.println(incomingData);
      startSystem();
      rideStarted = true;
    // ride finished
    } else if (incomingData == 'F' && rideStarted == true){
      Serial.print("Received: ");
      Serial.println(incomingData);
      stopSystem();
      rideStarted = false;
    }
  }

  // measure and send data
  if (rideStarted) {
    // blinkLED(mode, 1);
    parallelBlinkLED(currentTime);
    
    // Distance measurement
    if (currentTime - previousStampDistance >= intervalDistance) {
      previousStampDistance = currentTime;
      measureAndSendDistance();
    }

    // Luminosity measurement
    if (currentTime - previousStampLuminosity >= intervalLuminosity) {
      previousStampLuminosity = currentTime;
      measureAndSendLuminosity();
    }

    // Angle measurement
    if (currentTime - previousStampAngles >= intervalAngles) {
      previousStampAngles = currentTime;
      measureAndSendAngles();
    }
  } else {
    blinkLED("waiting", 1);
  }
}

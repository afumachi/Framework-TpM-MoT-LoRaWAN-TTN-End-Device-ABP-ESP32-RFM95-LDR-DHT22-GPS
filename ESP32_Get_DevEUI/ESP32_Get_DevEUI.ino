#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  delay(200);

  // Inicializa o WiFi em modo station para obtermos o MAC
  WiFi.mode(WIFI_STA);
  WiFi.begin();
  delay(500); // aguarda estabilizar


  Serial.println("\n========================================");
  Serial.println("   ESP32 - DevEUI Reader");
  Serial.println("========================================");
  uint8_t mac[6];
  WiFi.macAddress(mac);

  uint8_t deveui[8];
  deveui[0] = mac[0]; deveui[1] = mac[1]; deveui[2] = mac[2];
  deveui[3] = 0xFF;   deveui[4] = 0xFF;
  deveui[5] = mac[3]; deveui[6] = mac[4]; deveui[7] = mac[5];

  Serial.print("DevEUI TTN Console (MSB) : ");
  for (int i = 0; i < 8; i++) {
    if (deveui[i] < 0x10) Serial.print("0");
    Serial.print(deveui[i], HEX);
  }
  Serial.println();

  Serial.print("LMIC C array (LSB)       : { ");
  for (int i = 7; i >= 0; i--) {
    Serial.print("0x");
    if (deveui[i] < 0x10) Serial.print("0");
    Serial.print(deveui[i], HEX);
    if (i > 0) Serial.print(", ");
  }
  Serial.println(" }");
}

void loop() {}
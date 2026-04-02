"""
FILE 1 - Nivel3.py
==============================
Conectar na TTN via MQTT (TLS porta 8883) e savar os dados dos sensores LDR + DHT22 + GPS.


TTN MQTT RULES:
  Username : YOUR_APP_ID@ttn
  Password : API Key (starts with NNSXS...)
  Topic    : v3/YOUR_APP_ID@ttn/devices/DEVICE_ID/up   <-- @ttn in BOTH places
  Broker   : REGION.cloud.thethings.network  port 8883
"""

import base64
import csv
import json
import os
from datetime import datetime
import serial
import math
import time
import struct
import socket
import paho.mqtt.client as mqtt

# ----------------------------------------------------------
# SUA CONFIGURAÇÃO TTN DA APLICAÇÃO ID e END DEVICE ID
# CRIAR UMA API KEY DENTRO DA APLICAÇÃO
# ----------------------------------------------------------
TTN_APP_ID      = "bbc-application"           # ex. "my-ldr-app"
# NNSXS.76WT74RMZMEGLTO6XGHVOTQUF5HIODA4FYSMPPA.ICWGCP6KTM37A4MT7QXOZJG4K33XJ2MQX6V4IJ4QXFE6BBSQGTAQ
TTN_API_KEY     = "NNSXS.76WT74RMZMEGLTO6XGHVOTQUF5HIODA4FYSMPPA.ICWGCP6KTM37A4MT7QXOZJG4K33XJ2MQX6V4IJ4QXFE6BBSQGTAQ"   # inicia com "NNSXS...."
TTN_DEVICE_ID   = "bbc-gps"      # O SEU End Device ID
TTN_REGION      = "au1"          # ex. eu1, nam1, au1

BROKER        = f"au1.cloud.thethings.network"
PORT          = 8883
OUTPUT_CSV    = "Nivel4.csv"
MAX_MESSAGES  = 0       # 0 = Roda Infinito ou insira o número de Uplinks a serem analisados

# Ambos username AND topic path necessários para a @ttn
MQTT_USERNAME  = f"{TTN_APP_ID}@ttn"
MQTT_PASSWORD  = TTN_API_KEY
UPLINK_TOPIC   = f"v3/{TTN_APP_ID}@ttn/devices/{TTN_DEVICE_ID}/up"
WILDCARD_TOPIC = f"v3/{TTN_APP_ID}@ttn/#"   # Coleta TODAS Menssagens APP como fallback
# ----------------------------------------------------------

# Contador de Uplinks
contador_uplinks = 0

# Define o tamanho do Pacote
TAMANHO_PACOTE = 38

# Cria o vetor Pacote
Pacote_UL = [0] * TAMANHO_PACOTE
Pacote_DL = [0] * TAMANHO_PACOTE

def decode_payload(payload_bytes: list) -> dict:
    if len(payload_bytes) < 38:
        raise ValueError(f"Payload pequeno: necessário >=38 bytes, lido:  {len(payload_bytes)}")


    #// BYTES CAMADA PHY
    RSSId = payload_bytes[0] #= 0;     // RSSId; // RSSId RX Rádio LoRa
    SNRd = payload_bytes[1] #= 0;     // SNRd; // SNRu RX Rádio LoRa
    RSSIu = payload_bytes[2] #= 0;     // RSSIu TX Rádio LoRa - Será mensurado pelo Transceptor LoRa Gateway
    SNRu = payload_bytes[3] #= 0;     // SNRu TX Rádio LoRa - Será mensurado pelo Transceptor LoRa Gateway

    #// BYTES CAMADA MAC
    POT_LORA = payload_bytes[4] #= 0;   // POT_LORA; // Potência TX Rádio LoRa
    SF_LORA = payload_bytes[5] #= 0;   // SF_LORA;  // Spreading Factor Rádio LoRa
    BW_LORA = payload_bytes[6] #= 0;   // BW_LORA;  // Bandwidth Rádio LoRa
    CR_LORA = payload_bytes[7] #= 0;   // CR_LORA;  // Cording Rate Rádio LoRa    

    #// BYTES CAMADA DE REDE - NET
    
    #// Byte Destino
    GATEWAY_MONO_ID = payload_bytes[8] #= GATEWAY_MONO_ID;
    reservado1 = payload_bytes[9] #= 0;
    
    #// Byte Origem
    MY_ID = payload_bytes[10] #= MY_ID;
    reservado2 = payload_bytes[11] #= 0;

    #// BYTES CAMADA TRANSPORTE
    reservado3 = payload_bytes[12] #= 0;
    reservado4 = payload_bytes[13] #= 0;
     
    uplink_counter = (payload_bytes[14] << 8) | payload_bytes[15]

    sensor_type    =  payload_bytes[16]
    ldr_value      = (payload_bytes[17] << 8) | payload_bytes[18]

    bateria_type   =  payload_bytes[19]
    bateria        = ((payload_bytes[20] << 8) | payload_bytes[21])/100

    temp_type      =  payload_bytes[22]
    temperatura    = ((payload_bytes[23] << 8) | payload_bytes[24])/100

    umid_type      =  payload_bytes[25]
    umidade        = ((payload_bytes[26] << 8) | payload_bytes[27])/100

    gps_type      = payload_bytes[28]
    # Extrai latitude - bytes (posições 29-32)
    lat_bytes = payload_bytes[29:33]
    # Converte em bytes → int32 (big-endian)
    lat = struct.unpack('>i', lat_bytes)[0]
    # Converte de volta para float - GPS
    latitude = lat / 1e6

    # Extrai longitude bytes (posições 33–36)
    lon_bytes = payload_bytes[33:37]
    # Converte em bytes → int32 (big-endian)
    lon = struct.unpack('>i', lon_bytes)[0]
    # Converte de volta para float - GPS
    longitude = lon / 1e6
    '''
    print(
        f' | Contador UL = {uplink_counter}'
        f' | MY_ID = {MY_ID}'
        f' | Luminosidade = {ldr_value}'
        f' | Bateria = {bateria}'
        f' | Umidade = {umidade}'
        f' | Temperatura = {temperatura}'
        f' | Latitude = {latitude}'
        f' | Longitude = {longitude}'
    )
    '''
    if sensor_type != 44:
        raise ValueError(f"Tipo do Sensor={sensor_type}, deveria ser 44 (LDR) - pulando")
    if bateria_type != 11:
        raise ValueError(f"Bateria type={bateria_type}, deveria ser 11 (BATERIA) - pulando")
    if temp_type != 22:
        raise ValueError(f"Temperatura type={temp_type}, deveria ser 22 (TEMPERATURA) - pulando")
    if umid_type != 22:
        raise ValueError(f"Umidade type={umid_type}, deveria ser 22 (UMIDADE) - pulando")
    if gps_type != 62:
        raise ValueError(f"GPS type={gps_type}, deveria ser 62 (GPS) - pulando")    
    return {"uplink_counter": uplink_counter,
            "MY_ID": MY_ID,
            "ldr_value": ldr_value,
            "bateria": bateria,
            "temperatura": temperatura,
            "umidade": umidade,
            "latitude": latitude,
            "longitude": longitude
            }


def ldr_to_intensity(v: int) -> str:
    if v < 204:   return "Muito Escuro"
    if v < 410:   return "Escuro"
    if v < 614:   return "Sombrio"
    if v < 820:   return "Moderado"
    if v < 1023:  return "Claro"
    return "Muito Claro"


def extract_rf(uplink_msg: dict) -> dict:
    rx = uplink_msg.get("rx_metadata", [])
    if not rx:
        return {"rssi": None, "snr": None, "gateway_id": "unknown"}
    best = max(rx, key=lambda g: g.get("rssi", -999))
    return {
        "rssi":       best.get("rssi", None),
        "snr":        best.get("snr",  None),
        "gateway_id": best.get("gateway_ids", {}).get("gateway_id", "unknown"),
    }


def save_to_csv(timestamp, uplink_counter, ldr_value, intensity, rssi, snr, gateway_id, MY_ID, bateria, temperatura, umidade, latitude, longitude):
    file_exists = os.path.isfile(OUTPUT_CSV)
    with open(OUTPUT_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "uplink_counter", "ldr_value",
                             "intensity", "rssi", "snr", "gateway_id",
                             "MY_ID", "bateria", "temperatura", "umidade",
                             "latitude", "longitude"])
        writer.writerow([timestamp, uplink_counter, ldr_value,
                         intensity, rssi, snr, gateway_id, MY_ID, bateria, temperatura, umidade, latitude, longitude])
    print(f"  SAVED  #{uplink_counter:>4} | {timestamp} | LDR={ldr_value:>5} | "
          f"{intensity:<12} | RSSI={rssi} dBm | SNR={snr} dB | "
          f" TTN Gateway={gateway_id} | End Device={MY_ID} | Nivel bateria={bateria} | "
          f" Temperatura={temperatura} | Umidade={umidade} | Latitude={latitude} | Longitude={longitude}")


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        client.subscribe(UPLINK_TOPIC)
        client.subscribe(WILDCARD_TOPIC)   # fallback wildcard
        print(f"Connected to {BROKER}")
        print(f"MQTT user  : {MQTT_USERNAME}")
        print(f"Topic 1    : {UPLINK_TOPIC}")
        print(f"Topic 2    : {WILDCARD_TOPIC}  (wildcard fallback)\n")
        print(f"  {'#UL':>5}  {'Timestamp':<20}  {'LDR':>6}  {'Intensity':<12}  {'RSSI':>6}  {'SNR':>6}  {'TTN Gateway':<11}  {'MY_ID':<10}  {'Bateria':<12}  {'Temperatura':<11}  {'Umidade':<7}  {'Latitude':<12}  {'Longitude':<12}")
        print(f"  {'-'*5}  {'-'*20}  {'-'*6}  {'-'*12}  {'-'*6}  {'-'*6}  {'-'*11}  {'-'*10}  {'-'*12}  {'-'*11}  {'-'*7}  {'-'*12}  {'-'*12}")
    else:
        errors = {1:"Bad protocol", 2:"Bad client ID", 3:"Server unavailable",
                  4:"Bad credentials - check APP_ID and API_KEY", 5:"Not authorised"}
        print(f"FAILED (rc={rc}): {errors.get(rc, 'Unknown')}")


def on_message(client, userdata, msg):
    global contador_uplinks
    try:
        raw_str = msg.payload.decode("utf-8")
        data    = json.loads(raw_str)

        # Only process uplink data messages - skip join, ack, downlink etc.
        # TTN MQTT delivers the ApplicationUp object directly (no "data" wrapper)
        uplink_msg = data.get("uplink_message")
        if uplink_msg is None:
            print(f"  [skip] Non-uplink message on topic: {msg.topic}")
            return

        frm_payload = uplink_msg.get("frm_payload")
        if not frm_payload:
            print(f"  [skip] No frm_payload in uplink")
            return

        #raw_bytes = list(base64.b64decode(frm_payload))
        raw_bytes = (base64.b64decode(frm_payload))
        decoded   = decode_payload(raw_bytes)
        ldr_value = decoded["ldr_value"]
        intensity = ldr_to_intensity(ldr_value)
        MY_ID = decoded["MY_ID"]
        bateria = decoded["bateria"]
        temperatura = decoded["temperatura"]
        umidade = decoded["umidade"]
        latitude = decoded["latitude"]
        longitude = decoded["longitude"]
        #"MY_ID", "bateria", "temperatura", "umidade", "latitude", "longitude"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rf        = extract_rf(uplink_msg)

        save_to_csv(timestamp, decoded["uplink_counter"], ldr_value,
                    intensity, rf["rssi"], rf["snr"], rf["gateway_id"], MY_ID, bateria, temperatura, umidade, latitude, longitude)

        contador_uplinks += 1
        if MAX_MESSAGES > 0 and contador_uplinks >= MAX_MESSAGES:
            print(f"\nReached {MAX_MESSAGES} messages. Disconnecting.")
            client.disconnect()

    except ValueError as e:
        print(f"  [skip] {e}")
    except Exception as e:
        print(f"  [error] {e}  |  raw={msg.payload[:1200]}") # 120


def on_disconnect(client, userdata, rc, properties=None):
    print(f"\nDisconnected (rc={rc}) -- Total saved: {contador_uplinks}")


def main():
    print("=" * 60)
    print("  TTN UNICAMP PKLoRaWAN LDR + DHT22 + GPS Sensors -- Data Collector  -- ")
    print("=" * 60)
    print(f"  App        : {TTN_APP_ID}")
    print(f"  Device     : {TTN_DEVICE_ID}")
    print(f"  Broker     : {BROKER}:{PORT}")
    print(f"  MQTT user  : {MQTT_USERNAME}   <-- @ttn required")
    print(f"  Topic      : {UPLINK_TOPIC}   <-- @ttn in path too")
    print(f"  Output     : {OUTPUT_CSV}")
    print("=" * 60 + "\n")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set()

    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_disconnect = on_disconnect

    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nStopped by user.")
        client.disconnect()
    except Exception as e:
        print(f"Fatal: {e}")


if __name__ == "__main__":
    main()

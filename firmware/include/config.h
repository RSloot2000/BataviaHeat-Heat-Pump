// Configuratie voor de BataviaHeat Modbus-proxy.
// WiFi-gegevens staan in secrets.h (niet in versiebeheer).
#pragma once
#include <Arduino.h>
#include "secrets.h"

// ---- WiFi ----
// WIFI_SSID en WIFI_PASSWORD komen uit secrets.h.
#define PROXY_HOSTNAME "bataviaheat-proxy"

// ---- Modbus-busparameters (bevestigd uit DR164-data) ----
static const uint8_t  HP_SLAVE_ID = 1;          // warmtepomp slave-ID
static const uint32_t MODBUS_BAUD = 9600;       // 8N1
static const uint16_t TCP_PORT    = 502;        // HA Modbus-TCP-server

// ---- RS485-pinnen (Waveshare auto-direction: geen DE/RE) ----
// Tablet-segment op UART1:
static const int8_t PIN_TABLET_RX = 47;  // board#1 TXD -> ESP RX1
static const int8_t PIN_TABLET_TX = 21;  // ESP TX1 -> board#1 RXD
// Pomp-segment op UART2:
static const int8_t PIN_PUMP_RX   = 14;  // board#2 TXD -> ESP RX2
static const int8_t PIN_PUMP_TX   = 13;  // ESP TX2 -> board#2 RXD

// Auto-direction boards hebben geen richtingspin: -1 = geen DE/RE.
static const int8_t RS485_NO_DE = -1;

// ---- Fail-safe bypass relais ----
// LOW (rust)  = relais valt af -> tablet rechtstreeks op pomp (verwarming blijft werken).
// HIGH (actief) = bus gesplitst via de ESP32 (proxy-modus).
static const int8_t PIN_FAILSAFE_RELAY = 10;

// ---- Timing ----
static const uint32_t PUMP_TIMEOUT_MS = 1000;   // wachttijd op een pompantwoord

// ---- Schaduw-cache + verkeer-decoder ----
// HA-leesverzoeken (FC03/FC04) worden uit de cache beantwoord als alle
// gevraagde registers recenter zijn dan CACHE_MAX_AGE_MS; anders doorgestuurd
// naar de pomp (en daarmee de cache ververst).
static const uint32_t CACHE_MAX_AGE_MS = 5000;
// Decoder/sniffer: logt nieuwe + gewijzigde registers en alle schrijfacties
// op de seriële console (COM6). Zet op false om de bus-log stil te zetten.
static const bool SNIFF_LOG = true;
// Periodieke samenvatting (aantal ontdekte registers) elke N ms; 0 = uit.
static const uint32_t SNIFF_SUMMARY_MS = 30000;


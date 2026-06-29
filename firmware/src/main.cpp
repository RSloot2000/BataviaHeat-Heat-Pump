/*
 * BataviaHeat Modbus-proxy  —  ESP32-S3
 * -------------------------------------------------------------------------
 * Serialiserende man-in-the-middle tussen de warmtepomp-TABLET (Modbus-RTU
 * master) en de WARMTEPOMP (slave). HA praat via Modbus-TCP (poort 502).
 *
 * Architectuur (zie BataviaHeat_Modbus_Proxy_PLAN.md):
 *   - TabletServer : eModbus RTU-server op UART1  (antwoordt de tablet)
 *   - HaServer     : eModbus TCP-server op poort 502 (antwoordt HA)
 *   - pumpTransaction(): ENIGE master op UART2, synchroon + mutex-beschermd
 *     -> alle verzoeken (tablet + HA) worden geserialiseerd -> GEEN botsingen.
 *
 * Beide servers roepen forwardToPump() aan. De mutex garandeert dat er nooit
 * twee transacties tegelijk op de pomp-bus staan.
 *
 * TODO (volgende fases): schaduw-cache (HA-reads uit sniff i.p.v. busverkeer),
 * tablet-prioriteit, fail-safe-relais-watchdog, OTA.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <ArduinoOTA.h>
#include <map>
#include <stdarg.h>

#include "ModbusClientRTU.h"
#include "ModbusServerRTU.h"
#include "ModbusServerWiFi.h"

#include "config.h"

// ---- Seriële poorten ----
HardwareSerial TabletSerial(1);  // UART1 -> tablet-segment
HardwareSerial PumpSerial(2);    // UART2 -> pomp-segment

// ---- eModbus instanties ----
// Pomp-master op UART2: ENIGE master op de pomp-bus. De interne wachtrij van
// de client serialiseert alle verzoeken (tablet + HA) -> geen botsingen.
ModbusClientRTU PumpClient(RS485_NO_DE);  // -1 = auto-direction (geen DE/RE)
// RTU-server richting de tablet (timeout = max. inter-frame stilte in ms).
ModbusServerRTU TabletServer(2000, RS485_NO_DE);
// TCP-server richting Home Assistant.
ModbusServerWiFi HaServer;

// ---- WiFi-log (telnet poort 23): meekijken zonder USB ----
static WiFiServer LogServer(23);
static WiFiClient logClient;

// Log naar de seriële console EN naar een verbonden telnet-client.
static void logf(const char *fmt, ...) {
  char buf[160];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(buf, sizeof(buf), fmt, ap);
  va_end(ap);
  Serial.print(buf);
  if (logClient && logClient.connected()) logClient.print(buf);
}

// ====================================================================
//  Schaduw-cache + verkeer-decoder
//  --------------------------------------------------------------
//  Omdat ELK tablet- en HA-verzoek via forwardToPump() loopt, zien we hier
//  alle requests + pomp-antwoorden volledig gedecodeerd. We:
//   1) bewaren elke registerwaarde (met tijdstempel) in een schaduw-cache;
//   2) loggen nieuwe/gewijzigde registers + alle schrijfacties (decoder);
//   3) beantwoorden HA-leesverzoeken uit de cache als die vers genoeg is.
// ====================================================================
struct RegEntry { uint16_t value; uint32_t ts; };
struct BitEntry { bool value; uint32_t ts; };

static std::map<uint16_t, RegEntry> g_holding;   // FC03/06/16
static std::map<uint16_t, RegEntry> g_input;     // FC04
static std::map<uint16_t, BitEntry> g_coils;     // FC01/05/0F
static std::map<uint16_t, BitEntry> g_discrete;  // FC02

static SemaphoreHandle_t cacheMutex = nullptr;

// Modbus-functiecodes (numeriek om naamconflicten te vermijden).
static const uint8_t FC_READ_COILS      = 0x01;
static const uint8_t FC_READ_DISCRETE   = 0x02;
static const uint8_t FC_READ_HOLDING    = 0x03;
static const uint8_t FC_READ_INPUT      = 0x04;
static const uint8_t FC_WRITE_COIL      = 0x05;
static const uint8_t FC_WRITE_HOLDING   = 0x06;
static const uint8_t FC_WRITE_MULT_COIL = 0x0F;
static const uint8_t FC_WRITE_MULT_HOLD = 0x10;

static inline uint16_t rdWord(ModbusMessage &m, size_t i) {
  return (uint16_t(m[i]) << 8) | m[i + 1];
}

// --- Kern-lookup: alleen geverifieerde live-registers (zie tablet-parameters) ---
struct RegLabel { uint16_t addr; const char *name; bool tenths; };

static const RegLabel kIR[] = {
  {22,"ambient",true},{23,"fincoil",true},{24,"suction",true},{25,"discharge",true},
  {32,"lowpress",true},{33,"highpress",true},{53,"pump_rpm",false},{54,"flow_Lh",false},
  {66,"pump_pct",true},{135,"condenser",true},{137,"mod_out",true},{138,"mod_amb",true},
  {142,"pump_fb",true},
};
static const RegLabel kHR[] = {
  {768,"op_status",false},{772,"calc_setp",true},{773,"discharge",true},{776,"water_out",true},
  {816,"setp_copy",true},{1283,"comp_run",false},{1348,"plateHX_in",true},{1349,"plateHX_out",true},
  {1350,"total_out",true},{3230,"buf_in",true},{3231,"buf_out",true},
};
static const RegLabel kCoil[] = {
  {1024,"unit_ON",false},{1025,"unit_OFF",false},{1073,"silent_ON",false},
  {1074,"silent_OFF",false},{1075,"silent_L1",false},{1076,"silent_L2",false},
};

static const RegLabel *lookup(const char *space, uint16_t addr) {
  const RegLabel *t; size_t n;
  if (space[0]=='I') { t=kIR; n=sizeof kIR/sizeof *kIR; }
  else if (space[0]=='C') { t=kCoil; n=sizeof kCoil/sizeof *kCoil; }
  else { t=kHR; n=sizeof kHR/sizeof *kHR; }
  for (size_t i=0;i<n;i++) if (t[i].addr==addr) return &t[i];
  return nullptr;
}

// Eén register noteren + bij verandering/schrijven loggen (aanname: mutex vast).
static void noteReg(std::map<uint16_t, RegEntry> &map, const char *space,
                    const char *src, uint16_t addr, uint16_t val, bool isWrite) {
  auto it = map.find(addr);
  bool isNew    = (it == map.end());
  bool changed  = !isNew && it->second.value != val;
  map[addr] = { val, millis() };
  if (SNIFF_LOG && (isWrite || isNew || changed)) {
    const char *tag = isWrite ? "<WRITE>" : (isNew ? "<nieuw> " : "<gewijz>");
    const RegLabel *lbl = lookup(space, addr);
    char dec[24] = "";
    if (val==0xFFFF || val==0x8042 || val==0x8044) snprintf(dec,sizeof dec," n/b");
    else if (lbl && lbl->tenths) snprintf(dec,sizeof dec," %.1f", (int16_t)val/10.0);
    logf("[%-6s] %s[%5u] = %5u (0x%04X)%s %-10s %s\n",
                  src, space, addr, val, val, dec, lbl?lbl->name:"", tag);
  }
}

static void noteBit(std::map<uint16_t, BitEntry> &map, const char *space,
                    const char *src, uint16_t addr, bool val, bool isWrite) {
  auto it = map.find(addr);
  bool isNew   = (it == map.end());
  bool changed = !isNew && it->second.value != val;
  map[addr] = { val, millis() };
  if (SNIFF_LOG && (isWrite || isNew || changed)) {
    const char *tag = isWrite ? "<WRITE>" : (isNew ? "<nieuw> " : "<gewijz>");
    const RegLabel *lbl = lookup(space, addr);
    logf("[%-6s] %s[%5u] = %u %-10s %s\n", src, space, addr, val ? 1 : 0,
                  lbl?lbl->name:"", tag);
  }
}

// Decodeer een request+response en werk de cache bij.
static void cacheUpdate(ModbusMessage &req, ModbusMessage &resp,
                        const char *src) {
  if (resp.getError() != SUCCESS) {
    if (SNIFF_LOG) {
      logf("[%-6s] FC%02X addr=%u -> FOUT 0x%02X\n", src,
                    req.getFunctionCode(),
                    req.size() >= 4 ? rdWord(req, 2) : 0, resp.getError());
    }
    return;
  }
  uint8_t fc = req.getFunctionCode();
  xSemaphoreTake(cacheMutex, portMAX_DELAY);
  switch (fc) {
    case FC_READ_HOLDING:
    case FC_READ_INPUT: {
      if (req.size() < 6 || resp.size() < 3) break;
      uint16_t addr = rdWord(req, 2);
      uint16_t cnt  = rdWord(req, 4);
      auto &map = (fc == FC_READ_HOLDING) ? g_holding : g_input;
      const char *sp = (fc == FC_READ_HOLDING) ? "HR" : "IR";
      for (uint16_t i = 0; i < cnt && (3 + i * 2 + 1) < resp.size(); ++i)
        noteReg(map, sp, src, addr + i, rdWord(resp, 3 + i * 2), false);
      break;
    }
    case FC_WRITE_HOLDING: {
      if (req.size() < 6) break;
      noteReg(g_holding, "HR", src, rdWord(req, 2), rdWord(req, 4), true);
      break;
    }
    case FC_WRITE_MULT_HOLD: {
      if (req.size() < 7) break;
      uint16_t addr = rdWord(req, 2);
      uint16_t cnt  = rdWord(req, 4);
      for (uint16_t i = 0; i < cnt && (7 + i * 2 + 1) < req.size(); ++i)
        noteReg(g_holding, "HR", src, addr + i, rdWord(req, 7 + i * 2), true);
      break;
    }
    case FC_READ_COILS:
    case FC_READ_DISCRETE: {
      if (req.size() < 6 || resp.size() < 3) break;
      uint16_t addr = rdWord(req, 2);
      uint16_t cnt  = rdWord(req, 4);
      auto &map = (fc == FC_READ_COILS) ? g_coils : g_discrete;
      const char *sp = (fc == FC_READ_COILS) ? "CO" : "DI";
      for (uint16_t i = 0; i < cnt; ++i) {
        size_t byteIdx = 3 + i / 8;
        if (byteIdx >= resp.size()) break;
        noteBit(map, sp, src, addr + i, (resp[byteIdx] >> (i % 8)) & 1, false);
      }
      break;
    }
    case FC_WRITE_COIL: {
      if (req.size() < 6) break;
      noteBit(g_coils, "CO", src, rdWord(req, 2), rdWord(req, 4) != 0, true);
      break;
    }
    case FC_WRITE_MULT_COIL: {
      if (req.size() < 7) break;
      uint16_t addr = rdWord(req, 2);
      uint16_t cnt  = rdWord(req, 4);
      for (uint16_t i = 0; i < cnt; ++i) {
        size_t byteIdx = 7 + i / 8;
        if (byteIdx >= req.size()) break;
        noteBit(g_coils, "CO", src, addr + i, (req[byteIdx] >> (i % 8)) & 1, true);
      }
      break;
    }
    default:
      break;
  }
  xSemaphoreGive(cacheMutex);
}

// Probeer een HA-leesverzoek (FC03/04) uit de cache te beantwoorden.
// True + gevulde 'out' als alle gevraagde registers vers genoeg zijn.
static bool tryServeFromCache(ModbusMessage &req, ModbusMessage &out) {
  uint8_t fc = req.getFunctionCode();
  if (fc != FC_READ_HOLDING && fc != FC_READ_INPUT) return false;
  if (req.size() < 6) return false;
  uint16_t addr = rdWord(req, 2);
  uint16_t cnt  = rdWord(req, 4);
  if (cnt == 0 || cnt > 125) return false;

  auto &map = (fc == FC_READ_HOLDING) ? g_holding : g_input;
  uint32_t now = millis();
  bool ok = true;
  xSemaphoreTake(cacheMutex, portMAX_DELAY);
  for (uint16_t i = 0; i < cnt; ++i) {
    auto it = map.find(addr + i);
    if (it == map.end() || (now - it->second.ts) > CACHE_MAX_AGE_MS) { ok = false; break; }
  }
  if (ok) {
    out.add(req.getServerID(), fc, (uint8_t)(cnt * 2));
    for (uint16_t i = 0; i < cnt; ++i) out.add(map[addr + i].value);
  }
  xSemaphoreGive(cacheMutex);
  return ok;
}

// ====================================================================
//  Forward: stuur een verzoek synchroon naar de pomp en geef het antwoord.
//  syncRequest() blokkeert tot de pomp antwoordt of de timeout verloopt;
//  de client-wachtrij zorgt dat er nooit twee transacties tegelijk lopen.
// ====================================================================
ModbusMessage forwardToPump(ModbusMessage request, const char *src) {
  static uint32_t token = 0;
  ModbusMessage response = PumpClient.syncRequest(request, ++token);
  cacheUpdate(request, response, src);   // decoder + schaduw-cache bijwerken
  return response;
}

// ---- Worker-callbacks: tablet en HA forwarden allebei naar de pomp ----
ModbusMessage onTabletRequest(ModbusMessage request) {
  // De tablet is de echte master: altijd live doorsturen (en meeluisteren).
  return forwardToPump(request, "TABLET");
}

ModbusMessage onHaRequest(ModbusMessage request) {
  // Leesverzoeken eerst uit de (door de tablet ververste) cache proberen.
  ModbusMessage cached;
  if (tryServeFromCache(request, cached)) return cached;
  return forwardToPump(request, "HA");
}

// ====================================================================
//  Setup
// ====================================================================
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n[proxy] BataviaHeat Modbus-proxy start");

  // Fail-safe relais: tijdens boot in RUST (tablet rechtstreeks op pomp).
  pinMode(PIN_FAILSAFE_RELAY, OUTPUT);
  digitalWrite(PIN_FAILSAFE_RELAY, LOW);

  // RS485-poorten openen (8N1, met expliciete RX/TX-pinnen).
  TabletSerial.begin(MODBUS_BAUD, SERIAL_8N1, PIN_TABLET_RX, PIN_TABLET_TX);
  PumpSerial.begin(MODBUS_BAUD, SERIAL_8N1, PIN_PUMP_RX, PIN_PUMP_TX);

  // Pomp-master starten op UART2 (enige master op de pomp-bus).
  PumpClient.setTimeout(PUMP_TIMEOUT_MS);
  PumpClient.begin(PumpSerial);

  // Cache-mutex aanmaken voordat de servers verkeer kunnen verwerken.
  cacheMutex = xSemaphoreCreateMutex();

  // WiFi voor de HA Modbus-TCP-server.
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(PROXY_HOSTNAME);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("[proxy] WiFi verbinden");
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[proxy] WiFi OK, IP = %s\n", WiFi.localIP().toString().c_str());
    LogServer.begin();       // telnet-log op poort 23
    LogServer.setNoDelay(true);
    Serial.printf("[proxy] log meekijken: telnet %s 23\n", WiFi.localIP().toString().c_str());
    ArduinoOTA.setHostname(PROXY_HOSTNAME);
    ArduinoOTA.begin();      // draadloos updaten na deze flash
    Serial.printf("[proxy] OTA actief: pio run -t upload --upload-port %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("[proxy] WiFi MISLUKT (proxy werkt nog wel tablet<->pomp)");
  }

  // Tablet-server: beantwoord ALLE functiecodes voor slave HP_SLAVE_ID.
  TabletServer.registerWorker(HP_SLAVE_ID, ANY_FUNCTION_CODE, &onTabletRequest);
  TabletServer.begin(TabletSerial);

  // HA-server: idem, via Modbus-TCP.
  HaServer.registerWorker(HP_SLAVE_ID, ANY_FUNCTION_CODE, &onHaRequest);
  HaServer.start(TCP_PORT, 4 /*max clients*/, 2000 /*timeout ms*/);

  // Proxy-modus inschakelen: bus splitsen via het fail-safe relais.
  digitalWrite(PIN_FAILSAFE_RELAY, HIGH);

  Serial.println("[proxy] Klaar: tablet-RTU + HA-TCP -> pomp (geserialiseerd)");
}

void loop() {
  // De eModbus-servers draaien in hun eigen taken; hier alleen housekeeping.
  // TODO: watchdog -> bij langdurig falen pomp-bus, relais terug naar bypass.

  ArduinoOTA.handle();   // draadloze firmware-updates afhandelen

  // Nieuwe telnet-log-client accepteren (oude verbinding vervangen).
  if (LogServer.hasClient()) {
    if (logClient && logClient.connected()) logClient.stop();
    logClient = LogServer.available();
    logClient.println("[proxy] log verbonden — meeluisteren op tablet/pomp");
  }

  // Periodieke samenvatting van het aantal ontdekte registers.
  static uint32_t lastSummary = 0;
  if (SNIFF_SUMMARY_MS && cacheMutex && millis() - lastSummary >= SNIFF_SUMMARY_MS) {
    lastSummary = millis();
    xSemaphoreTake(cacheMutex, portMAX_DELAY);
    size_t hr = g_holding.size(), ir = g_input.size();
    size_t co = g_coils.size(), di = g_discrete.size();
    xSemaphoreGive(cacheMutex);
    logf("[sniff ] ontdekt: HR=%u  IR=%u  CO=%u  DI=%u\n",
                  (unsigned)hr, (unsigned)ir, (unsigned)co, (unsigned)di);
  }

  delay(1000);
}


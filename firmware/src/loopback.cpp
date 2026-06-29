// RS485 dongle-test voor de BataviaHeat-proxy.
// Valideert EEN adapter tegen een (niet-geisoleerde) USB-RS485 dongle, die
// wel bias + een gemeenschappelijke referentie levert -> een GELDIGE test,
// in tegenstelling tot twee geisoleerde adapters rug-aan-rug.
//
// OPSTELLING:
//   adapter RS485-zijde  A+  <-> dongle A
//                        B-  <-> dongle B
//   (optioneel GND <-> GND als de dongle een GND-pin heeft)
//   Op de PC: open de COM-poort van de DONGLE op 9600 8N1.
//
// WAT JE ZIET:
//   - In de dongle-terminal: "ESP->PC #n"  -> bewijst het TX-pad van de adapter.
//   - Typ je iets in de dongle-terminal (+Enter), dan logt de ESP dat hier
//     als [RX van PC]  -> bewijst het RX-pad van de adapter.
//
// Kies hieronder welke adapter aan de dongle hangt en flash opnieuw:
#define TEST_PUMP_ADAPTER 0   // 1 = pomp-adapter (UART2), 0 = tablet-adapter (UART1)

#include <Arduino.h>
#include "config.h"

HardwareSerial TabletSerial(1);  // UART1 -> tablet-adapter
HardwareSerial PumpSerial(2);    // UART2 -> pomp-adapter

#if TEST_PUMP_ADAPTER
  #define RS485    PumpSerial
  #define RS485_RX PIN_PUMP_RX
  #define RS485_TX PIN_PUMP_TX
  static const char *ADAPTER_NAAM = "POMP (UART2)";
#else
  #define RS485    TabletSerial
  #define RS485_RX PIN_TABLET_RX
  #define RS485_TX PIN_TABLET_TX
  static const char *ADAPTER_NAAM = "TABLET (UART1)";
#endif

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== RS485 dongle-test ===");
  Serial.printf("Te testen adapter: %s  (TX=%d RX=%d, baud=%lu)\n",
                ADAPTER_NAAM, RS485_TX, RS485_RX, (unsigned long)MODBUS_BAUD);
  Serial.println("Open op de PC de COM-poort van de DONGLE op 9600 8N1.");
  Serial.println("- Zie je daar 'ESP->PC #n'  -> TX-pad OK.");
  Serial.println("- Typ tekst in de dongle-terminal -> hieronder [RX van PC] -> RX-pad OK.\n");

  pinMode(PIN_FAILSAFE_RELAY, OUTPUT);
  digitalWrite(PIN_FAILSAFE_RELAY, LOW);

  RS485.begin(MODBUS_BAUD, SERIAL_8N1, RS485_RX, RS485_TX);
}

void loop() {
  static uint32_t n = 0;
  ++n;

  // Heartbeat naar de PC.
  String msg = "ESP->PC #" + String(n) + "\r\n";
  RS485.print(msg);
  RS485.flush();                            // wacht tot alles fysiek verzonden is
  delay(5);
  while (RS485.available()) RS485.read();    // eigen half-duplex echo weggooien
  Serial.printf("heartbeat #%lu verzonden\n", (unsigned long)n);

  // ~1s luisteren naar wat de PC (via de dongle) terugstuurt.
  String got;
  uint32_t start = millis();
  while (millis() - start < 1000) {
    while (RS485.available()) got += (char)RS485.read();
  }
  if (got.length()) {
    Serial.print("[RX van PC] \"");
    Serial.print(got);
    Serial.println("\"");
  }
}

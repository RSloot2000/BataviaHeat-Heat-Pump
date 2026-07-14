# BataviaHeat R290 — Tablet Installer Parameters

> De bereik/opties waarden komen uit de meegeleverde handleiding (7 inch draadcontroller, nov 2024).

## N-serie: Systeemconfiguratie

| Code | Parameter | Eenheid | Bereik / Opties | HR-adres |
|------|-----------|---------|-----------------|----------|
| N01 | Power-modus | — | 0=Standaard / 1=Krachtig / 2=Eco / 3=Auto | 6465 |
| N02 | Verwarmings- en koeltype | — | 0=Alleen verwarmen / 1=Verwarmen+koelen / 2=Alleen koelen | 6466 |
| N04 | Vierwegklep instelling | — | 0=Verwarming open / 1=Koeling open | 6468 |
| N05 | Type draadbedieningsschakelaar | — | 0=Tuimelschakelaar / 1=Pulsschakelaar | 6469 |
| N06 | Eenheid Start/Stop controle | — | 0=Unie / 1=Afstandsbed. / 2=Lokaal / 3=Draadsbed. / 4=Netbed. | 6470 |
| N07 | Geheugen bewaren bij uitschakelen | — | 0=Uit / 1=Aan | 6471 |
| N08 | Inkomende stroom zelfstart | — | 0=Uit / 1=Aan | 6472 ⚠ = P01! |
| N11 | Warmwaterfunctie | — | 0=Uit / 1=Aan | 6475 |
| N20 | Tank elektrische verwarming | — | 0=Uit / 1=Aan | 6484 |
| N21 | Onderste retourpomp | — | 0=Uit / 1=Aan | 6485 |
| N22 | Zonne | — | 0=Uit / 1=Aan | 6486 |
| N23 | Koppelingsschakelaar instelling | — | 0=Uit / 1=Koppelactie / 2=Koppelsluiting / 3=Aan-uit draad / 4=Elektr.verw. DHW / 5=Ext.warmtebron | 6487 |
| N26 | Type bediening draadcontroller | — | 0=Enkele zone / 2=Dubbele zone | 6490 |
| N27 | Load correction amplitude | °C | is een bereik | | 
| N32 | Slim netwerk | — | 0=Uit / 1=Aan | 6496 |
| N36 | Inlaattemp.sensor vloerverwarming | — | 0=Uit / 1=Aan | 6500 |
| N37 | Systeem totale uitlaat water temp.sensor | — | 0=Uit / 1=Aan | 6501 |
| N38 | EVU PV-signaal | — | 0=Normaal open / 1=Normaal gesloten | 6502 |
| N39 | SG-Grid-signaal | — | 0=Normaal open / 1=Normaal gesloten | 6503 |
| N41 | Zonne-temperatuursensor | — | 0=Uit / 1=Aan | 6505 |
| N48 | Zone A koeling einde | — | 0=Radiator / 1=Fan Coil / 2=Vloerverwarming | 6512 |
| N49 | Zone A verwarmingseinde | — | 0=Radiator / 1=Fan Coil / 2=Vloerverwarming | 6513 |

## M-serie: Temperatuur & Curve-instellingen

> **Let op: Non-lineaire HR-mapping!** M00-M09 gebruiken simpele offset (HR = 6400 + Mxx).
> Vanaf M10 verschuift de mapping met +15: HR = 6400 + Mxx + 15.
> Dit komt doordat G01-G04 op HR[6412-6415] zitten (overlap met M12-M15 simpele offset).
> HR[6411] is NIET M11 — bewezen in scan 4 (maart 2026).

| Code | Parameter | Eenheid | Bereik / Opties | HR-adres |
|------|-----------|---------|-----------------|----------|
| M01 | Koeling instelling temp. | °C | 15–35 | 6401 |
| M02 | Verwarmingsinstelling temp. | °C | 0–85 | 6402 |
| M03 | Insteltemperatuur warm water | °C | 0–80 | 6403 |
| M04 | Koeling doeltemp. kamer | °C | 0–80 | 6404 |
| M05 | Verwarming doeltemp. kamer | °C | 0–80 | 6405 |
| M08 | Verwarmingsinstelling temp. (B) | °C | 40–60 | 6408 |
| M10 | Zone A koelingscurve | — | 0=Uit / 1-8=Lage temp. curve / 9-16=Hoge temp. curve / 17=Aangepast | **6425** |
| M11 | Zone A verwarmingscurve | — | 0=Uit / 1-8=Lage temp. curve / 9-16=Hoge temp. curve / 17=Aangepast | **6426** |
| M12 | Zone B koelcurve | — | 0=Uit / 1-8=Lage temp. curve / 9-16=Hoge temp. curve / 17=Aangepast | **6427** |
| M13 | Zone B verwarmingscurve | — | 0=Uit / 1-8=Lage temp. curve / 9-16=Hoge temp. curve / 17=Aangepast | **6428** |
| M14 | Aangepaste koelomgevingstemp. 1 | °C | −5 – 46 | **6429** |
| M15 | Aangepaste koelomgevingstemp. 2 | °C | −5 – 46 | **6430** |
| M16 | Aangepaste koeluitlaattemp. 1 | °C | 5–25 | **6431** |
| M17 | Aangepaste koeluitlaattemp. 2 | °C | 5–25 | **6432** |
| M18 | Aangepaste verwarmingsomgevingstemp. 1 | °C | −25 – 35 | **6433** |
| M19 | Aangepaste verwarmingsomgevingstemp. 2 | °C | −25 – 35 | **6434** |
| M20 | Aangepaste verwarmingsuitlaattemp. 1 | °C | 25–65 | **6435** |
| M21 | Aangepaste verwarmingsuitlaattemp. 2 | °C | 25–65 | **6436** |
| M35 | Min. omgevingstemp. auto koeling | °C | 20–29 | **7184** |
| M36 | Max. omgevingstemp. auto koeling | °C | 10–17 | **7185** |
| M37 | Vakantie weg verwarming | °C | 20–25 | **7186** |
| M38 | Vakantie weg warm water | °C | 20–25 | **7187** |
| M39 | Auxilliary electric heater setting | - | 0=Uit / 1=Alleen verwarmen / 2=Alleen DHW / 3=Verwarmen+DHW | **7189** |
| M40 | Externe warmtebron | — | 0=Uit / 1=Alleen verwarmen / 2=Alleen DHW / 3=Verwarmen+DHW | **7190** |
| M55 | Voorverwarmingstemp. vloerverwarming | °C | 25–35 | 6455 |
| M56 | Voorverwarmingsinterval vloerverwarming | min | 10–40 | 6456 |
| M57 | Voorverwarmingstijd vloerverwarming | uur | 48–96 | 6457 |
| M58 | Vloerverwarming water temp. retour | °C | 0–10 | 6458 |
| M59 | Vloerverwarming kamertemp. retourverschil | °C | 0–10 | 6459 |
| M60 | Vloerverwarming voor droging | dag | 4–15 | 6460 |
| M61 | Vloerverwarming tijdens droging | dag | 3–7 | 6461 |
| M62 | Vloerverwarming na droging | dag | 4–15 | 6462 |
| M63 | Vloerverwarming droogtemp. | °C | 30–55 | 6463 |

## F-serie: Ventilator

| Code | Parameter | Eenheid | Bereik / Opties | HR-adres |
|------|-----------|---------|-----------------|----------|
| F06 | Ventilatorsnelheid regeling | — | 0=Handmatig / 1=Omgevingstemp. lineair / 2=Vintemp. lineair | ? |
| F07 | Ventilator handmatige bediening | rps | 0–2000 | ? |

## P-serie: Waterpomp

| Code | Parameter | Eenheid | Bereik / Opties | HR-adres |
|------|-----------|---------|-----------------|----------|
| P01 | Werkingsmodus waterpomp | — | 0=Blijf draaien / 1=Stop bij temp. / 2=Intermitterend | **6472** |
| P02 | Waterpomp regeltype | — | 1=Snelheid / 2=Stroom / 3=AAN-UIT / 4=Vermogen | **7232** |
| P03 | Doelsnelheid waterpomp | rpm | 1000–6800 | **7234** |
| P04 | Fabrikant waterpomp | — | 0–4 | **7235** |
| P05 | Doelstroom waterpomp | L/uur | 0–3600 | **7236** |
| P06 | Onderste retourwaterpomp interval | min | 5–120 | **7237** |
| P07 | Sterilisatie onderste retourpomp | — | 0=Uit / 1=Aan | **7238** |
| P08 | Onderste retourpomp getimed | — | 0=Uit / 1=Aan | **7239** |
| P09 | Water pump intermittent stop time | min | ? | **6507** |
| P20 | Water pump intermittent running time | min | ? | **6511** |

## G-serie: Sterilisatie (DHW)

| Code | Parameter | Eenheid | Bereik / Opties | HR-adres |
|------|-----------|---------|-----------------|----------|
| G01 | Sterilisatiefunctie | — | 0=Uit / 1=Aan | **6412** |
| G02 | Sterilisatietemperatuur | °C | 60–70 | **6413** |
| G03 | Sterilisatie max. cyclus | min | 90–300 | **6414** |
| G04 | Sterilisatie hoge temp. tijd | min | 5–60 | **6415** |

## T-serie: Temperatuur & Status Monitor

> **Live statuswaarden** — alleen-lezen, afgelezen op 17 maart 2026.

### Temperatuursensoren

| Code | Parameter | Waarde | Eenheid | Opmerkingen |
|------|-----------|--------|---------|-------------|
| T01 | Ambient temp | 15,6 | °C | = HR[22] (×0.1) |
| T02 | DHW water temp | uit | °C | N11=0 (DHW uit) |
| T03 | Total water outlet temp | 48,5 | °C | = HR[1] (×0.1) |
| T04 | Total system water outlet temp | 30,5 | °C | N37=1 (sensor aan) |
| T05 | Solar heater temp | uit | °C | N22=0 (solar uit) |
| T06 | Buffer tank upper temp sensor | 51,9 | °C | |
| T07 | Buffer tank lower temp sensor | 51,8 | °C | = HR[5]? (was 38.5°C) |
| T08 | Underfloor heating water inlet temp | uit | °C | N36=0 (sensor uit) |

### Klepstatus

| Code | Parameter | Waarde | Opmerkingen |
|------|-----------|--------|-------------|
| T09 | 3way valve 1 status | 409 | Ruwe waarde |
| T10 | 3way valve 2 status | 410 | Ruwe waarde |
| T11 | 3way valve 3 status | 409 | Ruwe waarde |

### Systeem- & modestatus

| Code | Parameter | Waarde | Opmerkingen |
|------|-----------|--------|-------------|
| T12 | Unit status | 4 | |
| T13 | Inverter status | 35 | |
| T14 | Module compressor numbers | 1 | |
| T15 | Mode | 2 | 2=Verwarming |
| T16 | Current mode | 2 | 2=Verwarming |
| T17 | Adjustable target temp | 28,0 | °C — = HR[772] (×0.1) — berekend stooklijn-setpoint |
| T18 | Adjustable control temp | 51,8 | °C |

### Module-informatie

| Code | Parameter | Waarde | Opmerkingen |
|------|-----------|--------|-------------|
| T19 | 0# module enabled | ● groen | Actief |
| T20–T26 | 1–7# module enabled | ● grijs | Niet actief |
| T27 | Module numbers | 1 | |

### Runtime & compressor

| Code | Parameter | Waarde | Eenheid | Opmerkingen |
|------|-----------|--------|---------|-------------|
| T28 | HP system running time | 127 | uur | |
| T29 | Compressor running speed | 0,0 | rps | Compressor uit op moment van aflezing |
| T30 | Module temp | 20,6 | °C | |
| T31 | Compressor power output | 0,00 | kW | |
| T32 | Compressor target speed | 20,0 | rps | |
| T33 | Compressor current output | 0,0 | A | |
| T34 | Compressor torque output | 0,0 | % | |
| T35 | Compressor voltage output | 0,0 | V | |
| T36 | Compressor bus voltage | 322,8 | V | DC-busspanning inverter |
| T37 | Error code | 0 | — | Geen fout |
| T38 | Inverter current input | 1,3 | A | |
| T39 | PFC temp | 21,4 | °C | Power Factor Correction module |
| T40 | Current speed | 0,0 | rps | |
| T41 | Frequence limit information | 7 | — | Bitfield? |
| T42 | 0# module compressor numbers | 1 | — | |
| T43–T49 | 1–7# compressor numbers | 0 | — | Niet actief |

### Module status (0# module)

> **Ontdekt april 2026** via Modbus register scanning.
> Alleen zichtbaar op het tablet via "Module status" → 0# module detail.
> Waarden zijn geverifieerd tegen tablet-aflezing bij stabiele en dalende temperaturen.

| Code | Parameter | Eenheid | Opmerkingen |
|------|-----------|---------|-------------|
| T78 | Plate HX water inlet temp | °C | = HR[1348] (×0.1) — water inlaat platenwisselaar |
| T79 | Plate HX water outlet temp | °C | = HR[1349] (×0.1) — water uitlaat platenwisselaar |
| T80 | Total water outlet temp | °C | = HR[1350] (×0.1) — totale water uitlaat |
| — | Buffer inlet temperature | °C | = HR[3230] (×0.1) — water inlaat buffertank |
| — | Buffer outlet temperature | °C | = HR[3231] (×0.1) — water uitlaat buffertank |

> **Let op:** HR[3230-3231] worden gespiegeld in HR[3355-3357] (identieke waarden).

### Limieten & overig

| Code | Parameter | Waarde | Eenheid | Opmerkingen |
|------|-----------|--------|---------|-------------|
| T89 | Compressor running time | 34 | uur | Minder dan T28 (127u) — alleen actieve compressortijd |
| T90 | DHW max temp | 75 | °C | |
| T91 | DHW min temp | 18 | °C | |
| T92 | Cooling max temp | 35 | °C | |
| T93 | Cooling min temp | 10 | °C | |
| T94 | Heating max temp | 28 | °C | |
| T95 | Heating min temp | 28 | °C | Gelijk aan max → fixed target? |
| T96 | Zone B heating max temp | 0 | °C | Zone B niet actief (N26=0) |
| T97 | Zone B heating min temp | 0 | °C | |
| T98 | Preheating remaining minutes | 0 | min | |
| T101 | Room temp | 24,7 | °C | = HR[5010] (van tablet sensor) |
| T102 | Cooling power | 0 | — | |
| T103 | Heating power | 0 | — | Compressor stond uit |
| T104 | DHW power | 0 | — | |
| T105 | Cooling capacity | 0 | — | |
| T106 | Heating capacity | 0 | — | |
| T107 | DHW capacity | 0 | — | |

## O-serie: Load Relay Status

> **Relais/actuator status** — alleen-lezen, ● groen = actief, ● grijs = inactief.

| Code | Parameter | Status | Opmerkingen |
|------|-----------|--------|-------------|
| O01 | Defrost indication | ● grijs | Geen ontdooiing |
| O02 | Fault indication | ● grijs | Geen storing |
| O03 | External heat source setting | ● grijs | M40=1, maar niet actief op dit moment |
| O04 | 3way valve 1 | ● grijs | |
| O05 | 3way valve 3 | ● grijs | |
| O06 | 3way valve 2 | ● groen | Actief — stuurt water naar verwarmingscircuit |
| O07 | DHW tank electric heater | ● grijs | N11=0, N20=0 |
| O09 | DHW return water pump | ● grijs | N21=0 |
| O10 | Solar water pump | ● grijs | N22=0 |
| O11 | Underfloor heating water pump | ● grijs | |
| O12 | External circulation pump | ● groen | CV-circulatiepomp draait |

## S-serie: Unit Status (Ingangssignalen)

> **Ingangssignalen** — alleen-lezen, ● groen = actief, ● grijs = inactief.

| Code | Parameter | Status | Opmerkingen |
|------|-----------|--------|-------------|
| S01 | Wire controller switch | ● grijs | Geen bedrade thermostaat |
| S02 | DHW tank electric heater feedback | ● groen | Feedback-signaal actief (ondanks N20=0) |
| S03 | Thermostat C signal | ● grijs | Geen koelvraag |
| S04 | Thermostat H signal | ● grijs | Geen warmtevraag op dit moment |
| S05 | Solar heater signal | ● grijs | N22=0 |
| S06 | Smart grid SG signal | ● grijs | N32=1 maar geen SG-signaal |
| S07 | Smart grid EVU signal | ● grijs | Geen EVU-signaal |

---

## Coils: Tablet knoppen (FC05)

> **Ontdekt via passieve bus-sniffer** op 9 april 2026.
> De tablet stuurt FC05 (Write Single Coil) met waarde 0xFF00 als puls-commando.
> Er is geen toggle — elke actierichting heeft een aparte coil.

### Unit aan/uit

| Coil | Functie | Waarde | Opmerkingen |
|------|---------|--------|-------------|
| 1024 | Unit AAN | 0xFF00 | Schakelt warmtepomp in |
| 1025 | Unit UIT | 0xFF00 | Schakelt warmtepomp uit |

### Stille modus

| Coil | Functie | Waarde | Opmerkingen |
|------|---------|--------|-------------|
| 1073 | Stille modus AAN | 0xFF00 | Activeert stille modus |
| 1074 | Stille modus UIT | 0xFF00 | Deactiveert stille modus |
| 1075 | Stil niveau 1 (laag) | 0xFF00 | Zet dempniveau naar 1 |
| 1076 | Stil niveau 2 (hoog) | 0xFF00 | Zet dempniveau naar 2 |

> **⚠ Geen hardware feedback:** Er is geen uitleesbaar statusregister voor stille modus.
> HR[36] en HR[1309] werden onderzocht maar gaan naar 65535 (niet beschikbaar) bij toggle.
> Zie [Stille modus status register — onderzoek](#stille-modus-status-register--onderzoek-april-2026) voor details.

### Tablet schrijfregisters (FC06/FC16)

| Adres | Functie | Waarde | Opmerkingen |
|-------|---------|--------|-------------|
| HR[5010] | Kamertemperatuur (tablet sensor) | 248 = 24,8°C (×0.1) | Periodiek geschreven door tablet |
| HR[5000..5006] | Tablet configuratie/status blok | — | FC16 schrijfactie, inhoud onbekend |

---

## Foutcodes

> Bron: Bedieningshandleiding 7 inch draadcontroller (nov 2024).
> T37 = "Error code" op het tablet (waarde 0 = geen fout).
> E-codes = storingen (unit stopt), F-codes = waarschuwingen (unit kan doordraaien).

### E-codes (storingen)

| Code | Beschrijving | Mogelijke oorzaken |
|------|-------------|-------------------|
| E01 | Communicatiefout draadcontroller | Slechte verbinding, storing controller/moederbord, interferentie sterke stroom |
| E03 | Compressor hoge druk | Koelmiddellek, gasklephuis vuil/geblokkeerd, compressorlager beschadigd, HP-schakelaar defect |
| E04 | Compressor lage druk | Onvoldoende waterstroom, lage inlaattemp, koelmiddellek, kalkaanslag verdamper |
| E06 | Omvormer communicatiefout | Voedingsspanning storing, inverterprintplaat defect, moederbord defect |
| E06 | Module communicatiefout | Communicatielijn/sterkstroomdraad bij elkaar, slechte verbinding module↔moederbord |
| E10 | Inlaatwatertemp. vloerverw. fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E11 | Uitlaatwatertemp. fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E12 | Warmwatertank / buffertank temp. fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E13 | Binnentemperatuur fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E14 | Omgevingstemperatuur fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E16 | Uitlaattemperatuur fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E21 | EEPROM-gegevensfout | Fout bij lezen gegevens → afsluiten en opnieuw opstarten |
| E24 | Hoge plaat retourwatertemp. | Warmtewisselaar geblokkeerd, sensor defect, lage waterstroom |
| E25 | Koelverdamping/platenwisselaar temp. te laag | — |
| E26 | Uitlaat-/inlaatwatertemp. verschil abnormaal | — |
| E27 | Uitlaattemperatuur te hoog | — |
| E31 | J5 druksensor fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E32 | J6 druksensor fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E44 | Platenwisselaar inlaatwatertemp. fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E55 | Zuigtemperatuur fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E56 | Zonnetemperatuursensor fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E58 | Spoeltemperatuur fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E59 | Zuigtemperatuur te laag | Te veel/te weinig koelmiddel, sensor/moederbord defect |
| E60 | Frequent noodontdooien | Omgevingssensor beschadigd, vuile warmtewisselaar, koelmiddeltekort |
| E61 | Abnormaal temp.verschil aanzuiging/uitlaat | Sensor defect, klep dicht, waterwegverstopping, pomp verkeerd, warmtewisselaar vervuild |
| E62 | Communicatiefout ventilatorconvector 1-32 | Verbindingskabel defect, stroomtoevoer, moederbord |
| E63 | Communicatie abnormaal (intern/extern) | Communicatielijn/sterkstroomdraad bij elkaar, slechte verbinding, moederbord |
| E64 | Protocolversie te laag | Programmafout → update procedure |
| E65 | Abnormale modelinstelling | Moederbordcode fout, fabrieksinstellingen niet hersteld |
| E66 | Systeemonderhoudsgegevens fout | → Herstel parameters in parameterinstelling |
| E67 | Watertank elektr.verwarming overbelast | Spanningsinput fout, schade watertank |
| E68 | Onvoldoende waterstroom | Watersysteem geblokkeerd, pomp ongeschikt, leiding te klein, flowschakelaar vastzit |
| E69 | Koelmiddel gaszijde temp. fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E70 | Koelmiddel vloeistofzijde temp. fout | Bedrading los/beschadigd, sensor defect, moederbord defect |
| E75 | R290-sensor fout | Bedrading los/beschadigd, R290-sensor kapot, moederbord kapot |
| E76 | R290 lekkage alarm ⚠ | Gaslek, externe gasinterferentie, sensor defect |
| E77 | Waterstroomsensor fout | Bedrading los/beschadigd, flowsensor kapot, moederbord kapot |

### F-codes (waarschuwingen)

| Code | Beschrijving | Mogelijke oorzaken |
|------|-------------|-------------------|
| F16 | Compressor lage druk te laag | Onvoldoende waterstroom, lage inlaattemp, koelmiddellek, kalkaanslag |
| F17 | Compressor hoge druk te hoog | Koelmiddeltekort, gasklephuis vuil, compressorlager beschadigd, HP-schakelaar |
| F61 | Abnormale snelheid ventilator 1/2 | Losse kabel, onstabiele spanning, moederbord/ventilator defect |
| F62 | Fancoil 01-32 fout | Stroomtoevoer, motor vastzit, fancoil geblokkeerd/beschadigd |
| F63 | Omgevingstemp. beperkt compressor | Bedrading los/beschadigd, sensor defect, moederbord defect |
| F64 | Omvormerstoring | Losse kabel, onstabiele spanning, moederbord/driverboard defect |
| F65 | Invertermodel instelling in uitvoering | Losse kabel, pomp/omvormer/moederbord defect |
| F66 | Omvormerpomp storing/waarschuwing | Watersysteem geblokkeerd, losse kabel, pomp/omvormer/moederbord defect |

---

## Koelen — probleemoplossing: E25 en/of E68 

> **Symptoom:** In koelmodus geeft de unit **E25 (koelverdamping / platenwisselaar temp. te laag)** en vaak **E68 (onvoldoende waterstroom)**, waarna hij stopt. De fout verdwijnt af en toe; terwijl de compressor kort draait koelt de buffer niet af maar warmt licht op. **Verwarmen werkt probleemloos** op dezelfde waterlus.

### Oorzaak: te weinig waterstroom door de platenwisselaar

In **verwarmen** is de verdamper de **buitencoil (lucht)** — de ventilator levert altijd "flow", dus de lagedruk blijft stabiel (~5 bar). In **koelen** wordt de **platenwisselaar** de verdamper en is die volledig afhankelijk van de **waterstroom** om warmte aan te leveren. Is die flow te laag, dan overkoelt de plaat lokaal, stort de lagedruk in (→ ~3 bar) → **E25**, en de flowschakelaar ziet te weinig → **E68**.

Daarom faalt dezelfde buffer↔warmtepomp-lus die als *condensor* (verwarmen) prima werkt, als *verdamper* (koelen).

### Diagnose-handtekening

| Meting | Verwarmen (OK) | Koelen, te lage flow (fout) | Koelen na fix |
|--------|----------------|-----------------------------|---------------|
| Lagedruk (IR[32]) | stabiel ~5 bar | **stort in naar ~3 bar** | stabiel 4,5–5 bar |
| Hogedruk (IR[33]) | ~13 bar | 11–13 (onstabiel) | 12,7–13,2 bar |
| EEV oververhitting | ~26 K (normaal) | piek 35 K bij collaps | 30–36 K stabiel |

> **Kernpunt:** de absolute oververhitting is *niet* het alarm — deze unit draait normaal ~26–36 K, ook in verwarmen. Het betrouwbare koel-alarmsignaal is dat de **lagedruk instort** onder de stabiele verwarmingswaarde van ~5 bar.

### Oplossing: verhoog het pompdebiet

1. Zet **P02 = 2 (flow)** — HR[7232] — zodat de pomp op debiet regelt i.p.v. vaste snelheid.
2. Verhoog **P05 (doelflow)** — HR[7236] — van 2100 → **3600 L/h**.

Resultaat: lagedruk stabiel op 4,5–5 bar (gelijk aan gezonde verwarming), en E25/E68 blijven weg.

### Ook checken (waterzijde)

- **Ontlucht de kop van de warmtepomp-circulatiepomp** — lucht in de pompvolute of platenwisselaar is onzichtbaar voor automatische ontluchters op buffer/hoogste punt en is een klassieke E68-oorzaak.
- **Check/reinig het vuilfilter** in de leiding warmtepomp ↔ buffer.
- Vuldruk ~2 bar (koud) is prima en sluit lucht-aanzuiging via onderdruk uit.

> **Opmerking (deze installatie):** 4-poorts buffervat met de warmtepomp op 2 poorten en het CV/afgiftecircuit (aparte pomp) op de andere 2. De warmtepomp circuleert altijd alleen buffer ↔ platenwisselaar, dus kleppen/pomp aan de afgiftezijde beïnvloeden E68 niet — het flow-knelpunt zit in de warmtepomp-lus zelf.

---

## Optimalisatie-overzicht (17 maart 2026)

> **Situatie:** Goed geïsoleerd rijhuis, vloerverwarming + radiatoren, alleen CV (geen DHW).
> **Probleem:** Pomp draait continu, verwarmt water naar 50°C, cycleert elk uur — ook zonder warmtevraag.

### Doorgevoerde wijzigingen

| # | Code | Parameter | Oud | Nieuw | HR-adres | Reden |
|---|------|-----------|-----|-------|----------|-------|
| 1 | **P01** | Werkingsmodus waterpomp | 0 (altijd draaien) | **1** (stop bij temp) | 6472 | Voorkomt onnodig rondpompen en warmteverlies via leidingen |
| 2 | **M02** | Verwarmingsinstelling temp. | 50°C | **35°C** | 6402 | Verlaagt max. watertemp (dient als bovengrens voor de weercurve) |
| 3 | **M11** | Zone A verwarmingscurve | 0 (uit) | **17** (aangepaste curve) | 6426 | Activeert weerafhankelijke regeling met bestaande M18-M21 punten |
| 4 | **M21** | Custom verwarmingsuitlaattemp. 2 | 35°C | **38°C** | 6436 | Extra marge bij vorst |

### Automatisch gewijzigd door controller

| Code | Parameter | Oud | Nieuw | HR-adres | Opmerkingen |
|------|-----------|-----|-------|----------|-------------|
| M10 | Curve mode flag | 0 | 2 | 6410 | Auto-enabled toen M11≠0 |
| M13 | Zone B verwarmingscurve | 0 | 17 | 6428 | Auto-sync met M11 (N26=0 = single zone) |

### Actieve weercurve na wijziging (M11=17, custom)

| Buitentemp. | Watertemp. |
|:-----------:|:----------:|
| 7°C (mild)  | 28°C |
| 0°C (vorst) | ~31°C |
| -5°C (koud) | 38°C |

---

## Post-optimalisatie verificatie (scan 4, 17-18 maart 2026)

> 19 uur 49 min meting met tablet losgekoppeld. 3.085.078 metingen, 67.614 wijzigingen, 1237 registers.

### Energieverbruik

| Meting | Vóór (scan 3) | Na (scan 4) | Reductie |
|--------|---------------|-------------|----------|
| Gemiddeld vermogen | 1.430 W | 224 W | **84%** |
| Geschatte COP | ~2,5 | ~4,0+ | +60% |

### Compressor

| Meting | Vóór | Na |
|--------|------|-----|
| Cycli per 20 uur | ~20 | **6** |
| Gemiddelde looptijd | ~12 min | **38,2 min** |
| Duty cycle | ~33% | **19%** |
| Gemiddelde pauze | ~48 min | **87,7 min** |

### Waterpomp (P01=1)

| Meting | Vóór | Na |
|--------|------|-----|
| Pompmodus | Continu (P01=0) | Stop bij temp (P01=1) |
| Pomp UIT-tijd | 0% | **76,8%** |

### Weercurve (M11=17)

| Meting | Vóór | Na |
|--------|------|-----|
| HR[816] watertemp. target | Statisch 50,0°C | **Dynamisch 28,0-29,0°C** |
| Status | INACTIEF | **ACTIEF** |
| Curve reactie | — | 28°C bij 15°C buiten, 29°C onder 6°C |

### Temperaturen (gemiddeld)

| Sensor | Vóór | Na |
|--------|------|-----|
| Discharge temp (HR[36]) | 45,6°C | **23,7°C** |
| Plate HX inlet (HR[40]) | 30,5°C | **17,1°C** |
| Water outlet (HR[1]) | 23,6°C | **30,1°C** |

### Conclusie

De drie wijzigingen (M02=35, M11=17, P01=1) plus de optionele M21=38 resulteerden in:
- **84% lager stroomverbruik** (1430W → 224W gemiddeld)
- **76,8% minder pomptijd** (pomp staat stil wanneer geen warmtevraag)
- **Langere compressorcycli** (38 min i.p.v. ~12 min = minder slijtage, beter rendement)
- **Lagere watertemperatuur** (28-29°C i.p.v. 50°C = veel hogere COP)
- **Hogere outlet temp** (30,1°C i.p.v. 23,6°C — effectiever dankzij langere cycli)

---

## Volledige Modbus Register Map

> **Alle geverifieerde registers** — ontdekt via Modbus scanner (maart 2026), overnacht-monitoring (9+ uur),
> passieve RS-485 bus-sniffer (april 2026) en HACS integratie-ontwikkeling.

### Kritieke ontdekking: FC03 ≠ FC04 (april 2026)

> **FC03 (Read Holding Registers) en FC04 (Read Input Registers) zijn NIET uitwisselbaar voor alle adressen.**
>
> | Adresbereik | FC03 vs FC04 | Status |
> |-------------|-------------|--------|
> | 0–100 | Identieke data | ✓ Geverifieerd |
> | 135+ | **Verschillend** — FC03 geeft foutieve waarden | ⚠ Kritiek |
>
> **Voorbeeld foutieve FC03 data (adressen 135+):**
> - IR[135] plate HX inlet: FC03 → 126°C ❌ / FC04 → correcte waarde ✓
> - IR[136] plate HX outlet: FC03 → 0°C ❌ / FC04 → correcte waarde ✓
> - Dit veroorzaakte thermal power = −351 kW in de eerste versie van de integratie
>
> **Oplossing:** Alle input registers worden nu exclusief via FC04 gelezen in de HACS integratie.

### Speciale markerwaarden

| Waarde | Hex | Betekenis |
|--------|-----|-----------|
| 65535 | 0xFFFF | Register/sensor niet beschikbaar op dit apparaat |
| 32834 | 0x8042 | Sensor losgekoppeld (−3270.2°C na ×0.1 schaling, signed) |
| 32836 | 0x8044 | Sensor losgekoppeld (−3270.4°C na ×0.1 schaling, signed) |

### Input Registers — FC04 (alleen-lezen, live sensordata)

> Deze registers bevatten betrouwbare real-time data van de warmtepomp hardware.
> Schaalwaarden zijn geverifieerd tegen tabletweergave.

| Adres | Parameter | Eenheid | Schaal | Tablet code | Opmerkingen |
|-------|-----------|---------|--------|-------------|-------------|
| IR[22] | Omgevingstemperatuur | °C | ×0.1 | T01 | Buitentemperatuur |
| IR[23] | Vincoil (verdamper) temperatuur | °C | ×0.1 | — | Lager dan ambient bij draaiende compressor (normaal) |
| IR[24] | Zuigtemperatuur | °C | ×0.1 | — | Koelmiddel inlaat compressor |
| IR[25] | Uitlaattemperatuur (discharge) | °C | ×0.1 | — | Koelmiddel uitlaat compressor |
| IR[32] | Lage druk | bar | ×0.1 | — | Koelmiddel verdampzijde |
| IR[33] | Hoge druk | bar | ×0.1 | — | Koelmiddel condenszijde |
| IR[53] | Pomp doelsnelheid | rpm | ×1 | — | Waterpomp target speed |
| IR[54] | Pomp debiet (flowrate) | L/h | ×1 | — | Waterdoorstroming; bron voor thermal power |
| IR[66] | Pomp regelsignaal | % | ×0.1 | — | PWM output naar pomp |
| IR[135] | Condenser temperatuur (koelmiddelzijde) | °C | ×0.1 | — | ⚠ ALLEEN via FC04! ~81°C bij draaiende compressor. Voorheen foutief als "plate HX water inlaat" gedocumenteerd |
| IR[136] | (niet aangesloten) | °C | ×0.1 | — | ⚠ ALLEEN via FC04! Toont 0°C — sensor niet aangesloten |
| IR[137] | Module water uitlaat temp. | °C | ×0.1 | T30? | Module 0# |
| IR[138] | Module omgevingstemperatuur | °C | ×0.1 | — | Vaak 0 — mogelijk redundant met IR[22] |
| IR[142] | Pomp feedback signaal | % | ×0.1 | — | Terugmelding snelheid van pomp |

### Holding Registers — FC03 (operationele status)

> Alleen-lezen statusregisters van de buitenunit. Gaan naar 0 wanneer compressor uit staat — dit is normaal.

| Adres | Parameter | Eenheid | Schaal | Tablet code | Opmerkingen |
|-------|-----------|---------|--------|-------------|-------------|
| HR[768] | Operationele status | — | ×1 | T12 | >0 = unit draait; state_register voor unit_power switch |
| HR[772] | Berekend verwarmings-setpoint | °C | ×0.1 | T17 | Actief stooklijn-setpoint; geïnterpoleerd uit curve-parameters. Ontdekt april 2026 |
| HR[773] | Compressor uitlaattemperatuur | °C | ×0.1 | — | Discharge temp (HR-kopie) |
| HR[776] | Water uitlaattemperatuur | °C | ×0.1 | — | Systeemwater uitlaat |
| HR[816] | Watertemperatuur target (kopie) | °C | ×0.1 | — | Kopie van HR[772]; niet gebruikt in integratie |
| HR[1283] | Compressor draait | — | ×1 | — | 0=uit, >0=aan; binary_sensor in integratie |

### Holding Registers — FC03 (watertemperaturen)

> Ontdekt april 2026. Deze registers bevatten de watertemperaturen van de platenwisselaar
> en buffertank, overeenkomend met de tablet T78/T79/T80 waarden en buffertank in/uit.

| Adres | Parameter | Eenheid | Schaal | Tablet code | Opmerkingen |
|-------|-----------|---------|--------|-------------|-------------|
| HR[1348] | Platenwisselaar water inlaat | °C | ×0.1 | T78 | Water retour naar platenwisselaar |
| HR[1349] | Platenwisselaar water uitlaat | °C | ×0.1 | T79 | Water aanvoer van platenwisselaar; bron voor thermal power |
| HR[1350] | Totale water uitlaat | °C | ×0.1 | T80 | Water na platenwisselaar |
| HR[3230] | Buffer inlaattemperatuur | °C | ×0.1 | — | Water inlaat buffertank |
| HR[3231] | Buffer uitlaattemperatuur | °C | ×0.1 | — | Water uitlaat buffertank |

### Holding Registers — FC06 (schrijfbaar, setpoints)

> Configuratieparameters die via de integratie of tablet geschreven kunnen worden.
> Zie M-serie en N-serie tabellen hierboven voor volledige beschrijvingen.

| Adres | Parameter | Code | Bereik | In integratie |
|-------|-----------|------|--------|---------------|
| HR[6402] | Max. verwarmingstemperatuur | M02 | 0–85°C | ✓ number entity |
| HR[6426] | Zone A verwarmingscurve | M11 | 0–17 | ✓ number entity |
| HR[6433] | Custom verw. omgevingstemp. 1 | M18 | −25 – 35°C | ✓ number entity |
| HR[6434] | Custom verw. omgevingstemp. 2 | M19 | −25 – 35°C | ✓ number entity |
| HR[6435] | Custom verw. uitlaattemp. 1 | M20 | 25–65°C | ✓ number entity |
| HR[6436] | Custom verw. uitlaattemp. 2 | M21 | 25–65°C | ✓ number entity |
| HR[6465] | Power-modus | N01 | 0–3 | ✓ select entity |
| HR[7184-7187] | M35-M38 koel/vakantie | M35-M38 | div. | ✓ number entity |
| HR[7189-7190] | Aux/ext warmtebron | M39-M40 | 0–3 | ✓ select entity |
| HR[6472] | Werkingsmodus waterpomp | P01 | 0–2 | ✓ select entity |
| HR[7232] | Waterpomp regeltype | P02 | 1–4 | ✓ select entity |
| HR[7234-7237] | Snelheid/fabr./flow/interval | P03-P06 | div. | ✓ number entity |
| HR[7238-7239] | Steril./getimed retourpomp | P07-P08 | 0–1 | ✓ select entity |
| HR[6507], HR[6511] | Pomp stop/loop tijd | P09, P20 | min | ✓ number entity |

### Holding Registers — NIET betrouwbaar als sensor

> Uit overnight monitoring (9+ uur zonder tablet) bleek dat deze registers 0 of inconsistente waarden tonen.
> Ze worden waarschijnlijk alleen gevuld wanneer de tablet-app actief is.

| Adres | Oorspronkelijke mapping | Status |
|-------|------------------------|--------|
| HR[1], HR[4], HR[5] | Water outlet, target, tank temp | ⚠ Alleen betrouwbaar met tablet actief |
| HR[72], HR[74-76] | Temperatuursensoren | ❌ Verwijderd uit integratie |
| HR[187-189] | Energiesensoren | ❌ Verwijderd uit integratie |
| HR[41] | Compressor power (kW) | ❌ Verwijderd — extern kWh-meter als vervanging |
| HR[163-165] | 16-bit Wh tellers | ❌ Overflow elke ~65,5 kWh (~12 dagen) — onbruikbaar |

### Coils — FC05 (pulse-commando's, alleen-schrijven)

> Samenvatting van alle ontdekte coils. Geen van deze is uitleesbaar (FC01/FC02).
> Elke schrijfactie is een puls (0xFF00). Er is geen toggle — elke richting heeft een aparte coil.

| Coil | Functie | State register | In integratie |
|------|---------|----------------|---------------|
| 1024 | Unit AAN | HR[768] > 0 = aan | ✓ switch (unit_power) |
| 1025 | Unit UIT | HR[768] = 0 = uit | ✓ (off_coil) |
| 1073 | Stille modus AAN | Geen ⚠ | ✓ switch (silent_mode, RestoreEntity) |
| 1074 | Stille modus UIT | Geen ⚠ | ✓ (off_coil) |
| 1075 | Stil niveau 1 (laag) | Geen ⚠ | ✓ (off_coil van silent_level_2) |
| 1076 | Stil niveau 2 (hoog) | Geen ⚠ | ✓ switch (silent_level_2, RestoreEntity) |

### Berekende sensoren (niet uit Modbus register)

| Sensor | Formule | Bronregisters | Eenheid |
|--------|---------|---------------|---------|
| Thermisch vermogen | `flow × (outlet − inlet) × 4.186 / 3600` | IR[54], HR[1349], HR[1348] | kW |
| Geleverde warmte | Riemann-somintegratie op thermisch vermogen | (berekend in HA) | kWh |

> **Thermal power bescherming:**
> - Waarden met |result| > 30 kW → `None` (onrealistisch voor 3-8kW pomp)
> - Negatieve waarden → `0.0` (clamp; in verwarmingsmodus moet thermal power ≥ 0 zijn)

### Nog niet gescande bereiken

| Bereik | Status | Opmerkingen |
|--------|--------|-------------|
| HR[300-699] | ⬜ Niet gescand | Gateway lockup bij grote scans |
| HR[1400-6399] | ⬜ Niet gescand | Mogelijk stille modus level-register |
| Discrete Inputs (FC02) | ⬜ Niet gescand | O-serie en S-serie status mogelijk hier |

---

## Stille modus status register — onderzoek (april 2026)

> **Doel:** Hardware-feedbackregister vinden voor stille modus (aan/uit en level 1/2).

### Onderzochte kandidaten

| Register | Methode | Resultaat |
|----------|---------|-----------|
| HR[36] | 3-snapshot scan + gerichte verificatie | Gaat van 0 → 65535 (niet beschikbaar) bij coil toggle |
| HR[1309] | 3-snapshot scan + gerichte verificatie | Gaat van 0 → 65535 (niet beschikbaar) bij coil toggle |
| HR[768] | Gemonitord tijdens silent toggle | Stabiel op 4 — geen verandering |
| HR[1283] | Gemonitord tijdens silent toggle | Stabiel op 0 — geen verandering |

### Conclusie

**Geen bruikbaar hardware-feedbackregister gevonden voor stille modus.**

De warmtepomp heeft geen register dat de huidige silent mode status reflecteert.
De coils (1073-1076) zijn write-only puls-commando's zonder uitleesbare tegenhanger.
De HACS integratie gebruikt daarom `RestoreEntity` (HA persistent state) voor de silent_mode en silent_level_2 switches.

Mogelijke toekomstige locatie: bereik HR[300-699] of HR[1400-6399] (nog niet gescand).

---

## HACS Integratie architectuur

> **Repository:** [`RSloot2000/BataviaHeat-Heat-Pump`](https://github.com/RSloot2000/BataviaHeat-Heat-Pump)
> **Domain:** `batavia_heat` | **pymodbus:** ≥3.6.0

### Platforms

| Platform | Entities | Bron |
|----------|----------|------|
| sensor | Alle IR en HR sensoren + thermal_power + energy + COP | FC04 + FC03 |
| binary_sensor | compressor_running (HR[1283]) | FC03 |
| switch | unit_power, silent_mode, silent_level_2 | FC05 coils |
| number | M02, M11, M18-M21, M35-M38, P03-P06, P09, P20 | FC06 |
| select | N01 power_mode, M39, M40, P01, P02, P07, P08 | FC06 |
| climate | Target temp (HR[6402]), huidige temp (HR[776]), status (HR[768]) | FC03/FC06 |

### Bulk-read strategie (coordinator.py)

> ~10 Modbus-requests per poll-cyclus (elke 10s), gesplitst per function code.

**FC03 — Holding registers:**

| Groep | Adressen | Registers |
|-------|----------|-----------|
| 1 | HR[768-776] | 9 registers (operationele status blok) |
| 2 | HR[1283] | 1 register (compressor running) |
| 3 | HR[6402] | 1 register (max heating temp) |
| 4 | HR[6426-6436] | 11 registers (stooklijn parameters) |
| 5 | HR[6465] | 1 register (power mode) |
| 6 | HR[7184-7190] | 7 registers (M35-M40 koel/vakantie/aux/ext) |
| 7 | HR[6472]+HR[6507]+HR[6511] | P01, P09, P20 (los) |
| 8 | HR[7232-7239] | 8 registers (P02-P08 pomp regeltype) |

**FC04 — Input registers:**

| Groep | Adressen | Registers |
|-------|----------|-----------|
| 1 | IR[22-25] | 4 registers (temperaturen) |
| 2 | IR[32-33] | 2 registers (drukken) |
| 3 | IR[53-54] | 2 registers (pomp) |
| 4 | IR[66] | 1 register (pomp regelsignaal) |
| 5 | IR[135-142] | 8 registers (module temps + pomp feedback) |

### Stabiliteitsmaatregelen

- **`_reset_client()`**: Force-close TCP-verbinding bij elke fout → verse connectie bij volgende poll
- **Timeout 5s**: Voldoende marge voor Modbus TCP gateway latentie
- **Thermal power clamp**: |result| > 30kW → None; negatief → 0.0
- **RestoreEntity**: silent_mode en silent_level_2 herstellen staat na HA herstart
- **COP gap guard**: Bij verbindingsuitval > 1 uur pauzeren thermische én elektrische accumulatie gelijktijdig

---
name: tiziano-security-review
description: eseguire security audit e governance lifecycle-aware su codice, dipendenze, api, identity, dati, database, container, nginx, integrazioni ed applicazioni ai. usare per individuare vulnerabilita, verificare finding, proporre fix minimi, mitigazioni, accettazione del rischio o requisiti per la delivery. ogni fonte, scanner e modifica richiede approvazione dell'utente. non usare come skill primaria per sviluppo funzionale, testing, observability o delivery.
---

# Tiziano Security Review

## Obiettivo

Eseguire un Security Audit & Governance decisionale, proporzionato alla fase del ciclo di vita. Individuare vulnerabilita e rischi, verificare la loro applicabilita reale e aiutare l'utente a decidere quali correggere, mitigare, accettare o rinviare.

La decisione finale appartiene sempre all'utente. Non applicare automaticamente hardening, scanner, fix, upgrade o modifiche di configurazione.

## Principi inderogabili

- L'utente definisce requisiti, vincoli, perimetro e profondita.
- Analizzare, proporre e segnalare; implementare solo dopo approvazione esplicita.
- Preferire il fix minimo compatibile con il requisito.
- Non complicare codice o architettura senza beneficio concreto.
- Non trattare automaticamente ogni finding o CVE come vulnerabilita sfruttabile.
- Non dichiarare autonomamente un rischio accettato.
- Segnalare rischi ulteriori senza ampliare autonomamente l'intervento.
- Essere lifecycle-aware: DEV, TEST, PRE-PROD e PROD richiedono livelli diversi.
- I requisiti aziendali, PSN e i vincoli forniti dall'utente hanno precedenza operativa.
- Demandare deployment, alta disponibilita, backup, scalabilita e hardening di produzione a `tiziano-delivery`.

## Workflow obbligatorio

1. Definire fase, perimetro, requisiti interni e baseline attive.
2. Chiedere autorizzazione separata per fonti esterne e scanner.
3. Analizzare solo il perimetro approvato.
4. Verificare i finding nel contesto reale.
5. Presentare opzioni e modifica minima.
6. Attendere la decisione dell'utente.
7. Implementare solo gli interventi approvati e secondo le indicazioni ricevute.
8. Rieseguire soltanto le verifiche autorizzate.
9. Trasferire alla delivery i requisiti rinviati.

## Allineamento iniziale

```text
Fase: DEV / TEST / PRE-PROD / PROD
Profondita: POC minima / DEV completa / pre-delivery / personalizzata
Domini inclusi:
Requisiti interni prioritari:
Baseline esterne attive:
Consultazione online autorizzata: si / no
Fonti autorizzate:
Scanner autorizzati:
File, servizi e ambienti autorizzati:
Modifiche consentite: nessuna / da approvare singolarmente
```

Se sono richiesti solo standard interni, non consultare fonti esterne.

## Domini attivabili

Attivare solo quelli scelti dall'utente:

1. Codice applicativo: injection, input validation, path traversal, command execution, deserializzazione, file/upload e dipendenze.
2. Identity e access: authentication, authorization, ruoli, privilegi, sessioni, token e service identity.
3. Data security: segreti, cifratura, dati sensibili, query, accessi, backup e retention.
4. Runtime e infrastruttura: container, Docker, Compose, Nginx, rete, TLS, filesystem e permessi.
5. API, eventi e integrazioni: endpoint, webhook, broker, code, servizi esterni, replay e rate limiting.
6. AI application security: prompt injection, excessive agency, tool authorization, leakage e improper output handling.
7. Supply chain: PyPI, immagini container, lock file, provenienza artifact, vulnerabilita e SBOM.

La skill puo segnalare brevemente un'area collegata non inclusa, senza analizzarla o modificarla.

## Lifecycle awareness

### DEV

- Individuare vulnerabilita evidenti e rischi critici.
- Consentire strumenti di debug concordati.
- Non applicare hardening che impedisce lo sviluppo.
- Un rischio puo essere accettato temporaneamente solo dall'utente e con rivalutazione.

### TEST

- Approfondire codice, API, dipendenze, identity, dati e container nel perimetro scelto.
- Verificare mitigazioni approvate.
- Nessun active scan senza autorizzazione specifica.

### PRE-PROD

- Rivalutare accettazioni temporanee.
- Verificare esposizione reale, configurazioni, dipendenze, image security e controlli di accesso.
- Preparare requisiti obbligatori e residui per la delivery.

### PROD

- Solo controlli autorizzati e non distruttivi.
- Non eseguire penetration test, ZAP active scan, secret rotation o modifiche runtime senza autorizzazione esplicita.

## Classificazione e decisione

Non usare scoring numerico arbitrario. Usare bassa, media, alta o critica, sempre motivate.

```text
Vulnerabilita:
Componente:
Evidenza:
Scenario realistico di esposizione:
Impatto:
Probabilita:
Priorita proposta:
Fonte del rilievo: requisito interno / decisione utente / standard autorizzato / normativa autorizzata / analisi tecnica

Opzioni:
1. Fix immediato
2. Mitigazione temporanea
3. Accettazione del rischio
4. Rinvio alla delivery
5. Non applicabile

Modifica minima proposta:
Complessita introdotta:
Rischio residuo:
Decisione dell'utente:
```

## Registro del rischio

Produrlo solo se richiesto:

```text
ID:
Vulnerabilita:
Componente:
Ambiente:
Decisione: fix / mitigazione / accettazione temporanea / accettazione definitiva / rinvio delivery / non applicabile
Motivazione:
Vincoli:
Rischio residuo:
Misura compensativa:
Responsabile della decisione:
Data o fase di rivalutazione:
```

- Nessuna accettazione implicita.
- I rischi non corretti restano visibili.
- Le accettazioni temporanee devono avere una rivalutazione.
- I finding rinviati diventano input per `tiziano-delivery`.

## Fonti e baseline ufficiali

Tutte le fonti sono disattivate per default. Consultarle online solo dopo approvazione dell'utente. Usare la versione ufficiale aggiornata e citare ogni requisito derivato.

Vedere `references/official_sources.md`.

La baseline serve a individuare e classificare, non a imporre ogni controllo. Non dichiarare una norma applicabile senza perimetro e contesto confermati.

## Scanner e strumenti

Nessuno scanner viene eseguito automaticamente. Rispettare strumenti gia presenti. Se mancano, proporre il tool minimo:

- Bandit per analisi statica Python.
- pip-audit per vulnerabilita note delle dipendenze Python.
- Trivy per immagini container, filesystem, dipendenze e configurazioni.
- Gitleaks per possibili segreti.
- OWASP ZAP per applicazioni web/API autorizzate, soprattutto TEST o PRE-PROD.
- Semgrep, SBOM avanzata o altri strumenti solo con necessita concreta.

Prima di eseguire:

```text
Tool:
Scopo:
Perimetro analizzato:
Comando:
Accesso di rete necessario:
File potenzialmente sensibili:
Output prodotto:
Modifiche automatiche: nessuna
```

Regole:

- Nessun autofix.
- Nessun upgrade automatico.
- Nessuna modifica a dipendenze o lock file.
- Preferire container o ambiente DEV autorizzato.
- Un finding automatico e un'indicazione da verificare.
- Classificare come confermato, probabile, falso positivo, non applicabile o da approfondire.
- Non eseguire ZAP active scan o operazioni invasive senza approvazione esplicita.

## Dipendenze vulnerabili

Per ogni finding:

```text
Package:
Versione installata:
Vulnerabilita:
Dipendenza: diretta / transitiva
Componente vulnerabile utilizzato: si / no / da verificare
Esposizione reale:
Versione corretta disponibile:
Impatto dell'upgrade:
Decisione proposta: aggiornare / mitigare / accettare temporaneamente / non applicabile / rinviare
```

Verificare presenza, uso, reachability, esposizione, fase, fix disponibile e regressioni. Non ignorare una dipendenza perche transitiva. Non aggiornare package, immagini o lock file senza decisione dell'utente.

## Segreti e dati sensibili

- Nessun segreto hardcoded in codice, Dockerfile, Compose, YAML, `.env.example`, test o log.
- Non aprire `.env` reali senza autorizzazione.
- Non mostrare mai il valore di un segreto.
- Un finding riporta solo file, riga, tipo presunto e stato da verificare.
- Non ruotare, revocare o sostituire credenziali automaticamente.
- Secret locali o placeholder in DEV solo se concordati.
- Secret store e managed identity possono diventare requisiti per la delivery.
- Scansione della cronologia Git solo con approvazione esplicita.

```text
Tipo di dato:
Posizione:
Esposizione potenziale:
Valore mostrato: mai
Rotazione necessaria: da decidere
Mitigazione proposta:
Intervento immediato:
Intervento per delivery:
```

## Authentication, authorization e identity

Distinguere sempre chi e l'identita, cosa puo fare, come i workload accedono alle risorse e come sono gestite le sessioni.

- Non introdurre IAM o authentication autonomamente.
- Rispettare provider e protocolli esistenti, per esempio Microsoft Entra ID, OAuth 2.0, OpenID Connect o API key.
- Verificare authorization lato server.
- Applicare least privilege senza inventare ruoli.
- Evitare credenziali utente nel service-to-service.
- Non memorizzare token in log, URL o codice.
- Verificare firma, issuer, audience e scadenza solo se pertinenti.
- Analizzare cookie, CORS, CSRF, sessioni e refresh token solo se usati.
- Per agenti AI distinguere identita agente, identita utente, tool autorizzati e risorse.

## API, eventi e integrazioni

- Validare input ai boundary, senza duplicare controlli ovunque.
- Prevenire SQL/NoSQL injection, command injection, path traversal, unsafe deserialization e SSRF.
- Verificare authentication e authorization lato server.
- Non inventare soglie di rate limiting.
- Per webhook valutare firma, timestamp, replay e provenienza, se richiesti.
- Per eventi verificare identita, permessi, schema, duplicati, idempotenza richiesta, messaggi invalidi e DLQ.
- Non aggiungere retry, circuit breaker, idempotency key o DLQ automaticamente.
- Per servizi esterni verificare timeout, TLS, certificati, credenziali e dati trasmessi.
- Per Nginx verificare esposizione, header, proxying e TLS senza hardening indiscriminato.

## AI application security

Restare nell'integrazione software, non nel training o model evaluation.

Valutare se incluso:

- prompt injection da input, documenti RAG, tool output o fonti esterne;
- tool authorization ed excessive agency;
- data leakage in prompt, risposta, retrieval, log, trace e cache;
- improper output handling prima di SQL, shell, HTML, API o file;
- autorizzazione e filtri prima del retrieval;
- consumo di risorse con soglie decise dall'utente;
- provenienza di modello, embedding, prompt template e configurazioni;
- human approval per azioni irreversibili o ad alto impatto;
- fallback definito dall'utente.

Non aggiungere automaticamente framework di guardrail o filtri.

## Container, runtime e infrastruttura

### DEV
- Esposizioni involontarie, segreti nelle immagini, porte, volumi, base image e dipendenze.
- Tool di debug consentiti se necessari.

### TEST e PRE-PROD
- Utente non-root se compatibile.
- Filesystem read-only se compatibile.
- Capability minime, rete e porte limitate.
- Immagini versionate, health check, TLS, separazione config/segreti.
- Trivy solo se approvato.

### PROD
- Requisiti finali con `tiziano-delivery`: immagini minimali, identity, secret store, rete, risorse, backup, recovery, patching e hardening.

Non modificare Dockerfile, Compose, Nginx, YAML o runtime senza approvazione. Non imporre distroless, scratch o Alpine. Valutare impatto prima di cambiare utente, porte, mount o filesystem.

## Database e dati

- Query parametrizzate e validazione separata degli identificatori dinamici.
- Verificare privilegi di utenti applicativi, admin e migration account.
- Non modificare ruoli, grant, trigger, schema o policy senza approvazione.
- Analizzare cifratura solo se nel perimetro.
- Verificare esposizione di PostgreSQL, MongoDB, Redis, DuckDB e vector DB.
- Per Redis considerare authentication, rete, persistenza e ruolo cache/broker/stream/storage.
- Per vector DB verificare isolamento, metadata filtering e authorization prima del retrieval.
- Backup, recovery, replica, sharding e continuita diventano requisiti per la delivery.
- Nessun accesso, scan o modifica dei dati reali senza autorizzazione.
- Log, trace, prompt e query non devono esporre dati sensibili.

## Implementazione delle modifiche

Dopo approvazione:

- Applicare solo il fix scelto dall'utente.
- Mantenere la modifica chirurgica e leggibile.
- Non introdurre nuove astrazioni, librerie o configurazioni non approvate.
- Non correggere finding aggiuntivi durante la modifica.
- Non modificare file critici non inclusi.
- Per cambi funzionali complessi, passare l'implementazione a `tiziano-sw-eng` con requisiti chiari.
- Per verifiche successive, usare `tiziano-testing-debug`.

## Output finale

```text
### Perimetro
- Fase:
- Domini analizzati:
- Baseline e fonti attive:
- Scanner eseguiti:

### Finding
- Confermati:
- Probabili:
- Falsi positivi:
- Non applicabili:
- Da approfondire:

### Decisioni approvate
- Fix:
- Mitigazioni:
- Rischi accettati:
- Rinvii alla delivery:

### Modifiche effettuate
- File:
- Interventi:
- Complessita introdotta:

### Rischio residuo
- ...

### Requisiti per la delivery
- ...

### Fonti consultate
- ...
```

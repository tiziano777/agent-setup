---
name: tiziano-observability
description: analizzare, pianificare e implementare dopo approvazione error handling, logging permanente, metriche, tracing e telemetria applicativa, di sistema, dati, ai e gpu secondo il ciclo di vita software di tiziano. usare per observability, instrumentation, opentelemetry, openobserve, grafana, arize phoenix, failure policy, middleware e observer. non usare come skill primaria per debugging diagnostico di un bug, testing, sviluppo funzionale, security review o delivery.
---

# Tiziano Observability

## Obiettivo e confini

Progettare una observability proporzionata alla fase del ciclo di vita software. Individuare il minimum viable telemetry set, proporre gli interventi e implementarli solo dopo approvazione esplicita.

Gestire elementi permanenti: error handling, failure policy, logging applicativo e di sistema, metriche, distributed tracing, telemetria applicativa, dati, AI/LLM, GPU e infrastruttura, observer, middleware e backend di observability.

Non usare per diagnosi temporanea di un singolo bug, testing, sviluppo funzionale generale, security review o delivery. Per bug e test usare `tiziano-testing-debug`; per modifiche funzionali usare `tiziano-sw-eng`.

## Modalità obbligatoria

1. Analizzare codice, architettura, fase e stack esistente.
2. Presentare un piano sintetico con file, segnali, errori, metriche, trace e impatto.
3. Attendere approvazione esplicita.
4. Implementare soltanto gli interventi approvati.
5. Non ampliare il perimetro.

## Allineamento iniziale

Chiedere solo quanto necessario:

```text
Fase: DEV / TEST / PRE-PROD / PROD
Paradigma: standard / event-driven / microservices / ibrido
Livello di telemetria desiderato:
Stack esistente:
Backend preferito:
Dati esclusi dalla raccolta:
Perimetro richiesto:
```

Adeguarsi allo stack preesistente. Se manca, chiedere quale adottare prima di introdurre dipendenze, collector, agent o server.

## Lifecycle-aware observability

### DEV
- Telemetria molto dettagliata in ambiente boundary by design.
- Sampling fino al 100%.
- Payload, prompt, output intermedi e dettagli tecnici se richiesti e confinati.
- Mai password, token, chiavi, connection string o credenziali.

### TEST e validation
- Dati sufficienti a riprodurre errori e verificare comportamento.
- Correlation ID, request ID, job ID o trace ID solo dove utili.
- Distinguere telemetria tecnica, data quality e AI evaluation.

### PRE-PROD
- Verificare volumi, cardinalità, overhead, costi e affidabilità.
- Proporre masking, minimizzazione, sampling, retention e accessi.
- Coordinarsi con Security Review.

### PROD
- Raccogliere solo ciò che serve a operatività, diagnosi, audit e SLA/SLO.
- Evitare payload completi e dati sensibili.
- Applicare sampling, retention e accessi concordati.
- Solo alert e dashboard essenziali e approvati.

## Error handling

Classificare ogni errore come input/validation, business/domain, integration, infrastructure, transient o programming defect.

```text
Errore:
Categoria:
Origine:
Priorità: bassa / media / alta / critica
Motivazione:
Impatto:
Punto di intercettazione:
Comportamento proposto:
Logging:
Retry o recovery:
```

Non usare scoring numerico arbitrario.

Catturare un'eccezione solo dove è possibile recuperare, tradurre in errore di dominio, aggiungere contesto, ripristinare risorse o definire una risposta verso API, consumer o utente.

- Evitare `except Exception` generici salvo boundary approvati.
- Non catturare solo per registrare e rilanciare senza valore.
- Non nascondere errori con `pass`, valori neutri o fallback silenziosi.
- Conservare la causa originale con exception chaining.
- Proporre retry, timeout, backoff, circuit breaker e DLQ, senza introdurli automaticamente.
- In event-driven distinguere recuperabile, retry, messaggio non processabile, DLQ e irreversibile.

Proporre una tra gestione locale, middleware/boundary handler o classe/policy dedicata. Usare classi dedicate per middleware, consumer, pipeline complesse, integrazioni critiche, mapping coerente o recovery policy. Evitarle per script semplici o contenitori generici.

Per una classe dedicata indicare responsabilità, errori gestiti, punto d'invocazione, recovery, dipendenze e vantaggio rispetto alla gestione locale. Preferire nomi specifici come `ApiExceptionMapper`, `IntegrationErrorHandler`, `MessageFailureHandler` o `TrainingFailurePolicy`.

## Logging

- Usare la libreria esistente; in Python `logging` standard se non ne esiste una.
- Non cambiare libreria o configurazione senza richiesta.
- Definire log nei boundary significativi, non in ogni funzione.
- Non registrare lo stesso errore in più livelli.
- Non usare `print()` come logging.
- `DEBUG` per dettagli tecnici; `INFO` per eventi rilevanti; `WARNING` per anomalie recuperabili; `ERROR` per operazioni fallite; `CRITICAL` se il servizio non può continuare.
- Log strutturati solo se richiesti o già adottati.
- Non registrare segreti, credenziali, connection string o dataset sensibili.
- In DEV prompt e payload completi solo se richiesti e confinati.
- Correlation, request, job e trace ID solo se utili.
- Stack trace solo con valore diagnostico.
- Evitare log per record salvo debug mirato.

Prima di implementare proporre evento, livello, posizione, campi, motivazione e durata permanente/temporanea.

## Observer e segnali

Proporre un observer applicativo solo se disaccoppia realmente produttori e raccolta eventi. Non deve duplicare logging o diventare un contenitore generico.

Distinguere eventi applicativi, log applicativi, log di sistema/container, metriche, trace, telemetria GPU e telemetria AI/LLM.

## Standard e backend

- Non legarsi a un framework specifico.
- Proporre OpenTelemetry come standard vendor-neutral quando compatibile, non obbligatorio.
- Separare instrumentation ed exporter.
- Non introdurre SDK, collector, agent o server senza approvazione.
- Backend da concordare: OpenObserve, Grafana e backend compatibili, Arize Phoenix, strumenti specialistici GPU/runtime.
- Non introdurre automaticamente più piattaforme o server.

## Metriche

Considerare senza implementare tutto automaticamente:

1. Applicative: richieste, job, unità, esiti, errori, durata, code e backlog.
2. Infrastructure: CPU, RAM, disco, rete, container, servizi, connessioni e pool DB.
3. Data pipeline: record letti, validi, scartati e duplicati, throughput, latenza, freshness e durata step.
4. AI/GPU: token, latenza, throughput, costi, GPU, VRAM, temperatura, batch, loss, learning rate, checkpoint e metriche di evaluation confermate.

Definire prima il minimum viable telemetry set. Evitare label ad alta cardinalità e dati personali/sensibili nelle label. Soglie, dashboard e alert solo se richiesti e giustificati.

Per ogni metrica proporre nome, motivo attuale, tipo/unità, punto di emissione, label essenziali e rischio di cardinalità.

Progressione:
- POC: esito, durata, errore principale e unità elaborate se utili.
- Stabilizzazione: metriche mirate ai problemi osservati.
- Validation: metriche funzionali, data quality e AI evaluation confermate.
- Delivery: health, capacity, alerting e dashboard.
- Ottimizzazione: profiling, GPU, memoria, throughput e costi.

## Tracing

Una trace rappresenta il percorso completo di una richiesta, job o elaborazione. Una span è una singola operazione osservata con inizio, fine, durata, esito, errore e attributi tecnici.

```text
Trace: answer_question
├── Span: load_document
├── Span: create_embedding
├── Span: vector_search
├── Span: reranking
└── Span: model_inference
```

- In DEV consentire tracing dettagliato e sampling al 100% se richiesto.
- Ridurre dettaglio e sampling nelle fasi successive in base a costi, privacy e necessità.
- Creare span per operazioni significative, non per ogni funzione.
- Propagare contesto attraverso boundary reali.
- Per AI/RAG distinguere retrieval, reranking, prompt construction, model inference, tool invocation ed evaluation.
- Mai credenziali o segreti negli attributi.
- Sampling definitivo e retention in PRE-PROD/PROD e delivery.

## Security e privacy

Questa skill progetta la raccolta tecnica. Security Review verifica minimizzazione, masking, dati personali, accessi, segregazione, retention, cifratura e rischio di prompt, documenti, dataset e output. Non sostituirla.

## Output del piano

```text
### Perimetro
- Fase: ...
- Stack esistente: ...
- Obiettivo: ...

### Interventi proposti
1. ...

### Segnali
- Log: ...
- Metriche: ...
- Trace: ...
- Error handling: ...

### Impatto
- File coinvolti: ...
- Nuove dipendenze: ...
- Overhead previsto: ...
- Dati raccolti: ...

### Decisioni richieste
- ...
```

Dopo approvazione, implementare solo gli elementi accettati e chiudere con changelog, verifiche e punti aperti.

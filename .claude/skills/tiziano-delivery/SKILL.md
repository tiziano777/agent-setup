---
name: tiziano-delivery
description: rendere un servizio software delivery-ready traducendo requisiti di operation, infrastruttura, testing, observability e security in artifact, configurazioni, checklist e handover. usare per containerizzazione finale, nginx, health check, ci/cd, scaling, sistemi distribuiti, backup, recovery, migrazioni, rollback e predisposizione al rilascio. ogni requisito e sotto-attivita deve essere scelto e approvato dall'utente; non eseguire deploy o modifiche arbitrarie.
---

# Tiziano Delivery

## Obiettivo

Rendere una POC validata facile da mettere in produzione da parte del team delivery. Tradurre requisiti ricevuti in artifact e verifiche chiare, senza sostituirsi al team infrastrutturale e senza eseguire automaticamente il rilascio.

## Principi inderogabili

- L'utente seleziona i requisiti minimi applicabili.
- Nessuna capacita e obbligatoria per default.
- Non inventare requisiti infrastrutturali mancanti.
- Pianificare e procedere una sotto-attivita alla volta.
- Tracciare dipendenze, decisioni, blocchi e stato.
- Non passare automaticamente alla sotto-attivita successiva.
- Non riscrivere funzionalita applicative, test o security controls.
- Se serve una modifica applicativa, formulare un requisito chiaro per `tiziano-sw-eng`.
- Rilasciare, pubblicare, promuovere o modificare ambienti solo su richiesta esplicita.
- Preferire il meccanismo minimo che garantisce la semantica richiesta.
- Valutare sempre beneficio, costo, complessita e rischio residuo.

## Workflow

1. Raccogliere soltanto i requisiti selezionati dall'utente o ricevuti dal team delivery.
2. Scomporre il problema in sotto-attivita piccole.
3. Evidenziare dipendenze sequenziali e attivita indipendenti.
4. Segnalare input mancanti e blocchi.
5. Far scegliere all'utente la prossima sotto-attivita.
6. Proporre piano e artifact relativi a quella sola attivita.
7. Attendere approvazione.
8. Implementare e verificare soltanto quanto approvato.
9. Aggiornare lo stato senza passare automaticamente oltre.

## Decomposizione obbligatoria

```text
ID:
Attivita:
Obiettivo:
Dipende da:
Input richiesti:
Output previsto:
Decisione richiesta:
Stato: non iniziata / approvata / in corso / completata / bloccata
```

Esempio:

```text
D1 - Definizione artifact
Dipende da: nessuna

D2 - Dockerfile target
Dipende da: D1

D3 - Health check
Dipende da: requisiti applicativi

D4 - Gestione segreti
Dipende da: security review e piattaforma target

D5 - Backup PostgreSQL
Dipende da: dati persistenti, RPO e RTO approvati

D6 - Rollback
Dipende da: strategia deployment e migrazioni
```

## Input selezionabili

Non richiedere tutto insieme. Presentare come checklist e lasciare scegliere all'utente:

```text
Target: DEV / TEST / PRE-PROD / PROD
Piattaforma target:
Modalita di deployment:
Requisiti ricevuti dal team delivery:
Artifact richiesti:
Registry previsto:
Gestione configurazioni e segreti:
Identity del workload:
Networking e porte:
Storage persistente:
Database e dipendenze:
Health check richiesti:
CPU, RAM, storage e GPU:
Scalabilita richiesta:
Backup e recovery:
Observability richiesta:
Requisiti security approvati:
Strategia di rollback:
Responsabilita del rilascio:
```

Se un dato non e pertinente o non definito, registrarlo senza inventarlo.

## Artifact predisponibili su richiesta

- Dockerfile definitivo.
- Docker Compose per target specifici.
- Configurazione Nginx.
- Template YAML o file `conf`.
- Esempio variabili d'ambiente senza segreti.
- Manifest richiesti dalla piattaforma.
- Health, readiness e startup check.
- Script startup e graceful shutdown.
- Pipeline CI/CD.
- Checklist di rilascio e rollback.
- Matrice porte, volumi, dipendenze e servizi.
- Documento di handover.

Non creare tutto per default. Non introdurre Kubernetes, Helm, Terraform o altre tecnologie se non richieste. Non inserire valori reali o credenziali. Non eseguire deploy, push o modifica pipeline senza richiesta esplicita.

## Containerizzazione e runtime

- Rispettare tecnologia, immagini e versioni gia scelte.
- Rendere build riproducibile secondo i requisiti approvati.
- Multi-stage build solo con beneficio concreto.
- Non imporre distroless, scratch o Alpine.
- Definire utente, filesystem, capability, volumi, porte e resource limit solo se richiesti.
- Non rimuovere tool necessari senza decisione.
- Non cambiare entrypoint o startup flow senza verificarne l'impatto.
- Trattare Docker Compose come strumento coerente con il target definito, non automaticamente come produzione.

## Health check e graceful shutdown

Distinguere:

- liveness: il processo e vivo;
- readiness: puo ricevere traffico;
- startup: ha completato l'avvio;
- dependency check: dipendenze necessarie disponibili.

Regole:

- Non aggiungere tutti i check automaticamente.
- Evitare dipendenze esterne nella liveness per non creare restart loop.
- Includere nella readiness solo dipendenze realmente necessarie.
- Non esporre dettagli sensibili.
- Timeout e comportamento degradato devono essere decisi.
- Per job lunghi o agentici distinguere accettazione, elaborazione, worker e completamento.
- Durante shutdown: smettere di accettare traffico, gestire operazioni attive, rilasciare risorse ed evitare duplicazioni.
- Non inventare timeout, retry o grace period.

```text
Check:
Scopo:
Dipendenze incluse:
Condizione di successo:
Condizione di fallimento:
Timeout:
Impatto sul traffico:
Dipende da:
Decisione richiesta:
```

## Configurazioni e segreti

Solo su richiesta:

- separare configurazione applicativa, infrastrutturale, segreti e valori di ambiente;
- non inserire valori reali nel repository;
- non inserire segreti in Dockerfile, Compose, YAML, pipeline o immagini;
- non scegliere autonomamente secret store, managed identity o variabili d'ambiente;
- evitare duplicazioni tra `.env`, YAML, Compose e codice;
- lasciare i valori reali al team delivery.

Prima di aggiungere una variabile:

```text
Nome:
Scopo:
Tipo:
Obbligatoria:
Default sicuro:
Contiene dati sensibili:
Ambienti interessati:
Componente consumatore:
```

Password, token e connection string non hanno default. Produrre matrice ambiente solo su richiesta.

## Scalabilita e disponibilita

### Istanza singola

Default quando soddisfa i requisiti. Definire solo quanto richiesto: stato, dipendenze, health e restart policy.

### Duplicazione

Solo su richiesta e dopo verifica di:

- statelessness reale;
- sessioni e cache locali;
- file temporanei;
- job schedulati e duplicazioni;
- load balancing;
- health e graceful shutdown;
- eventuale session affinity.

### Alta disponibilita e distribuzione

Solo con requisiti espliciti: replica, failover, sharding, broker, idempotenza, consistenza eventuale, distributed lock, leader election, backup e disaster recovery.

## Teoria dei sistemi distribuiti

In presenza di network partition, esplicitare il trade-off tra consistency e availability. La partition tolerance e una condizione da gestire nei sistemi realmente distribuiti. La disponibilita e sempre un requisito operativo da definire, con QoS calibrata rispetto a costo e task.

Prima di proporre pattern distribuiti:

```text
Tipo di servizio:
Task deterministica o agentica:
Comportamento durante partition:
Consistency richiesta:
Availability e QoS:
SLO di disponibilita:
RTO e RPO:
Pattern lettura/scrittura:
Letture stale ammesse:
Conflitti ammissibili:
Costo massimo:
```

Proporre e far approvare, se pertinenti:

- strong o eventual consistency;
- read-your-writes;
- monotonic reads;
- consistent prefix;
- quorum read/write;
- single-writer o multi-writer;
- conflict resolution;
- optimistic o pessimistic concurrency;
- idempotenza;
- event ordering;
- at-most-once, at-least-once o exactly-once applicativo;
- transazioni locali o distribuite;
- compensating transaction o Saga.

Non introdurre pattern automaticamente.

### Availability e costi

Distinguere restart singola istanza, piu istanze, replica DB, failover, multi-zone, disaster recovery e multi-region.

Per task agentiche valutare costo per richiesta/tool, timeout, massimo numero di step, concorrenza, retry, duplicazione azioni, token/GPU, indisponibilita di modello o tool e azioni parziali.

```text
Beneficio:
Costo infrastrutturale:
Costo operativo:
Complessita introdotta:
Failure mode coperto:
Failure mode residuo:
Decisione richiesta:
```

## Backup, recovery e migrazioni

Niente e obbligatorio per default.

RPO indica quanti dati e accettabile perdere. RTO indica quanto tempo il servizio puo restare indisponibile. Se non sono richiesti o noti, registrarli come non definiti.

- Distinguere backup, replica e disaster recovery.
- La replica non sostituisce il backup.
- Un backup richiede una procedura di restore verificabile per essere considerato affidabile.
- Non configurare backup, retention, replica o restore automaticamente.
- Non copiare dati reali in DEV senza autorizzazione.
- Non eseguire restore, truncate, drop o operazioni distruttive.
- PostgreSQL, MongoDB, Redis, vector DB, artifact AI e filesystem richiedono strategie distinte.

Per migrazioni:

- verificare compatibilita applicazione/schema;
- preferire backward compatibility solo se richiesta;
- distinguere schema, dati e configurazione;
- definire ordine deployment/migrazione;
- pianificare rollback o forward-fix;
- non applicare migrazioni automaticamente;
- considerare coesistenza temporanea di versioni diverse.

## CI/CD e promozione

Solo su richiesta e sulla tecnologia scelta, per esempio Azure DevOps Pipelines o GitHub Actions.

Sotto-attivita indipendenti:

1. Build e versionamento artifact.
2. Quality gate approvati.
3. Publish nel registry autorizzato.
4. Promotion tra ambienti.
5. Deploy.
6. Rollback o forward-fix.

- Non generare pipeline completa per default.
- Non modificare CI/CD esistente senza approvazione.
- Non eseguire push, deploy, release o promozione automaticamente.
- Non inserire segreti.
- Non inventare branch strategy, environment, registry, service connection o approval gate.
- Se un gate fallisce, fermare il rilascio e rimandare alla skill competente.

## Observability e security in delivery

Consumare solo requisiti approvati provenienti da `tiziano-observability` e `tiziano-security-review`.

- Non ridefinire metriche, logging, trace, retention o alert.
- Non riaprire rischi gia decisi, salvo conflitto con il target.
- Tracciare rischi accettati, mitigazioni e requisiti aperti nell'handover.
- Segnalare incompatibilita tra requisiti applicativi e infrastrutturali.

## Release, rollback e handover

Checklist composta solo dai requisiti selezionati:

```text
Artifact buildato:
Versione identificabile:
Test approvati superati:
Security finding valutati:
Observability predisposta:
Configurazioni target disponibili:
Segreti gestiti dal team delivery:
Health check approvati:
Migrazioni pianificate:
Backup/restore richiesti:
Rollback definito:
Responsabili identificati:
```

Rollback da pianificare, non inventare o eseguire automaticamente. Considerare artifact, schema, dati, configurazioni, job in corso e criterio di interruzione.

Handover opzionale:

- artifact e versioni;
- porte ed endpoint;
- dipendenze;
- configurazioni e segreti da valorizzare;
- health check;
- risorse approvate;
- startup e shutdown;
- deployment e rollback;
- rischi accettati e requisiti aperti;
- responsabilita applicative e infrastrutturali.

## Stato finale

La skill puo dichiarare soltanto:

- `delivery-ready`: requisiti selezionati soddisfatti;
- `delivery-ready con eccezioni`: eccezioni approvate e tracciate;
- `bloccata`: manca un requisito necessario.

Non dichiarare production-ready in senso assoluto. Non eseguire il rilascio senza richiesta esplicita.

## Output finale

```text
### Obiettivo corrente
- ...

### Sotto-attivita
- ID / dipendenze / stato

### Requisiti selezionati
- ...

### Artifact predisposti
- ...

### Verifiche eseguite
- ...

### Decisioni e blocchi
- ...

### Requisiti aperti
- ...

### Stato delivery
- delivery-ready / delivery-ready con eccezioni / bloccata

### Handover
- prodotto / non richiesto
```

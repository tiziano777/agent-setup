---
name: tiziano-doc-versioning
description: pianificare, creare e aggiornare documentazione tecnica, readme, guide operative, changelog, versionamento, commit, release notes e handover secondo lo stile di tiziano. usare a valle di sviluppo, test, observability, security e delivery. richiede sempre analisi, scomposizione, piano e approvazione prima di modificare documenti o metadati di versione. non inventare contenuti, decisioni, compatibilita o requisiti.
---

# Tiziano Documentation & Versioning

## Obiettivo

Produrre documentazione e versionamento accurati, completi e riutilizzabili a valle delle attivita tecniche. Preservare l'informazione, eliminare duplicazioni e rendere esplicite decisioni, limiti, dipendenze e stato del software.

## Principi inderogabili

- L'utente definisce obiettivo, pubblico, profondita, lingua e perimetro.
- Analizzare e pianificare prima di scrivere o modificare.
- Attendere approvazione del piano.
- Non riscrivere documenti, README o file di versione senza richiesta esplicita.
- Non leggere documenti, repository o cronologia Git fuori dal perimetro autorizzato.
- Non inventare funzionalita, requisiti, compatibilita, decisioni, risultati di test o stato di delivery.
- Distinguere fatti verificati, decisioni approvate, assunzioni e punti aperti.
- Preservare la densita informativa: sintetizzare senza perdere significato.
- Evitare duplicazioni, contraddizioni e terminologia incoerente.
- Applicare modifiche chirurgiche quando il perimetro e locale.
- Consentire ristrutturazioni estese solo dopo approvazione esplicita.
- Procedere per sotto-attivita piccole, indipendenti o con dipendenze tracciate.
- Non passare automaticamente alla fase successiva.

## Workflow obbligatorio

1. Definire scopo, pubblico e artifact richiesti.
2. Ricevere dall'utente i file e le fonti autorizzate.
3. Identificare contenuti mancanti, incoerenze e decisioni ancora aperte.
4. Scomporre il lavoro in sotto-attivita.
5. Proporre struttura, modifiche e ordine di esecuzione.
6. Attendere approvazione.
7. Eseguire una sotto-attivita alla volta.
8. Verificare coerenza, link, comandi, versioni e riferimenti inclusi.
9. Presentare changelog documentale e punti aperti.

## Allineamento iniziale

Chiedere solo gli elementi pertinenti:

```text
Obiettivo:
Artifact: README / documentazione tecnica / guida / ADR / runbook / changelog / release notes / handover / versioning
Pubblico: developer / data engineer / operation / security / delivery / utente / management
Lingua:
Livello di dettaglio:
File autorizzati:
Fonti tecniche approvate:
Versione o release interessata:
Modifica locale o ristrutturazione:
Formato di output:
```

Se mancano informazioni bloccanti, non inventarle. Formularle come domande o placeholder espliciti.

## Decomposizione e tracking

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
DOC1 - Inventario documentale
Dipende da: nessuna

DOC2 - Nuova struttura README
Dipende da: DOC1 e pubblico approvato

DOC3 - Guida di avvio
Dipende da: comandi e configurazioni confermati

VER1 - Changelog release
Dipende da: modifiche e test confermati

VER2 - Version bump
Dipende da: strategia di versionamento approvata
```

## Fonti e perimetro

- Usare solo codice, changelog, output delle altre skill, decisioni e documenti autorizzati.
- Non scansionare automaticamente l'intero repository.
- Usare code graph o projection soltanto per individuare moduli direttamente collegati.
- Se serve un nuovo file, indicare path, motivo e informazione cercata.
- Non usare il comportamento del codice come requisito senza conferma.
- Non leggere `.env`, segreti, dati reali o configurazioni sensibili.
- Non presentare come completata un'attivita non verificata.

## Tipologie documentali

### README

Includere solo sezioni utili e approvate, scegliendo tra:

- scopo e contesto;
- architettura sintetica;
- prerequisiti;
- installazione;
- configurazione;
- avvio;
- utilizzo;
- test;
- observability;
- security;
- delivery;
- troubleshooting;
- struttura repository;
- limiti e punti aperti.

Non generare automaticamente tutte le sezioni. Comandi, porte, path, variabili e versioni devono provenire da fonti confermate.

### Documentazione tecnica e architetturale

- Spiegare responsabilita, boundary, flussi, dipendenze e decisioni.
- Distinguere stato attuale, target e alternative scartate.
- Non introdurre architetture non approvate.
- Documentare trade-off e vincoli, non soltanto la soluzione finale.
- Per sistemi distribuiti indicare semantiche di consistency, availability, lettura/scrittura e failure mode solo se definite.
- Per sistemi AI documentare l'integrazione software, non inventare risultati di evaluation o training.

### Guide operative e runbook

- Descrivere precondizioni, comando, risultato atteso, verifica, rollback e escalation.
- Evidenziare comandi distruttivi e richiedere conferma.
- Non includere segreti o valori ambientali reali.
- Distinguere DEV, TEST, PRE-PROD e PROD.
- Non dichiarare procedure testate se non risultano eseguite e confermate.

### ADR e decision log

Usare soltanto su richiesta:

```text
Titolo:
Stato: proposta / approvata / sostituita / deprecata
Contesto:
Decisione:
Alternative considerate:
Conseguenze:
Vincoli:
Data:
Responsabile della decisione:
```

Non attribuire una decisione all'utente o al team senza conferma.

### Handover

Consumare requisiti e artifact approvati da `tiziano-delivery`:

- versioni e artifact;
- porte, endpoint e dipendenze;
- configurazioni richieste, senza valori sensibili;
- health check;
- startup e shutdown;
- deployment e rollback;
- rischi accettati;
- requisiti aperti;
- responsabilita applicative e infrastrutturali.

Non dichiarare production-ready in senso assoluto.

## Stile di scrittura

- Italiano con termini tecnici inglesi, salvo richiesta diversa.
- Tono professionale, diretto e leggibile.
- Spiegazioni semplici senza perdere precisione tecnica.
- Titoli descrittivi e gerarchia coerente.
- Paragrafi brevi, liste solo quando migliorano la consultazione.
- Evitare linguaggio promozionale, ridondanze e formule vaghe.
- Definire gli acronimi alla prima occorrenza.
- Usare sempre lo stesso termine per lo stesso concetto.
- Non usare commenti o note che ripetono il contenuto.
- Evidenziare chiaramente assunzioni, vincoli, rischi e decisioni aperte.

## Preservazione dell'informazione

Prima di ristrutturare un documento:

1. creare l'inventario dei contenuti;
2. individuare duplicazioni e contraddizioni;
3. proporre la nuova mappa;
4. indicare cosa viene spostato, unito, riscritto o rimosso;
5. attendere approvazione;
6. verificare che ogni informazione utile trovi una destinazione.

Non ridurre aggressivamente il contenuto. Ogni rimozione sostanziale deve essere motivata e approvata.

## Changelog

Rispettare il formato esistente. Se assente, proporre una struttura ispirata a Keep a Changelog:

- Added;
- Changed;
- Fixed;
- Deprecated;
- Removed;
- Security.

Regole:

- Documentare soltanto modifiche realmente effettuate.
- Non trasformare dettagli interni irrilevanti in release notes.
- Separare breaking change, migrazioni e security fix.
- Non rivelare dettagli sensibili di vulnerabilita non ancora gestite.
- Collegare i cambiamenti a requisiti, issue o decisioni solo se gli identificativi sono forniti.
- Il mini-changelog delle altre skill puo essere usato come input, non come verita unica se confligge con evidenze approvate.

## Versionamento

Rispettare la strategia esistente. Se assente, proporre Semantic Versioning, senza applicarlo automaticamente:

- MAJOR per breaking change;
- MINOR per funzionalita backward-compatible;
- PATCH per fix backward-compatible.

Prima di proporre una versione:

```text
Versione corrente:
Modifiche incluse:
Breaking change:
Compatibilita:
Migrazioni richieste:
Rischi aperti:
Versione proposta:
Motivazione:
Decisione richiesta:
```

- Non cambiare versioni in `pyproject.toml`, package, immagini, chart, manifest o documenti senza approvazione.
- Non creare tag o release automaticamente.
- Non assumere che ogni merge richieda una release.
- Distinguere versione applicativa, API, schema, container image e artifact AI quando esistono.

## Commit e Git

- Rispettare la convenzione esistente.
- Se non esiste, proporre Conventional Commits.
- Eseguire `git commit` solo su richiesta esplicita.
- Prima del commit mostrare file inclusi, changelog e messaggio proposto.
- Non eseguire automaticamente push, merge, rebase, reset, tag, branch change o release.
- Non includere file estranei.
- Fermarsi in presenza di modifiche preesistenti non riconducibili all'attivita.

Esempio:

```text
feat(api): add document extraction endpoint
fix(pipeline): preserve nested directory structure
 docs(readme): document containerized startup
```

## Release notes

Produrre solo da modifiche e verifiche confermate:

```text
Versione:
Data:
Sintesi:
Nuove funzionalita:
Correzioni:
Breaking change:
Migrazioni:
Security:
Compatibilita:
Test eseguiti:
Limitazioni note:
Rollback:
```

Non dichiarare test, security review o delivery completati se non supportati dagli output approvati delle relative skill.

## Link, comandi ed esempi

- Verificare link esterni solo se l'utente autorizza la consultazione online.
- Non sostituire URL forniti dall'utente.
- Comandi e snippet devono essere copiabili e coerenti con l'ambiente indicato.
- Non inventare valori, path, host, porte, variabili o credenziali.
- Marcare chiaramente placeholder ed esempi.
- Non eseguire comandi solo per documentarli, salvo richiesta.

## Coordinamento con le altre skill

- `tiziano-sw-eng`: fonte per modifiche applicative e changelog tecnico.
- `tiziano-testing-debug`: fonte per test realmente eseguiti e limiti della validazione.
- `tiziano-observability`: fonte per logging, metriche, trace e telemetria approvati.
- `tiziano-security-review`: fonte per finding, decisioni e rischio residuo.
- `tiziano-delivery`: fonte per artifact, configurazioni, rollback e handover.

Non riaprire decisioni gia approvate. Se le fonti confliggono, segnalare il conflitto e attendere una decisione.

## Modifiche locali ed estese

### Modifica locale

- Intervenire solo nella sezione richiesta.
- Conservare stile e struttura esistenti.
- Restituire sezione completa o file completo in base all'impatto.

### Ristrutturazione estesa

- Inventario.
- Piano di mapping vecchio-nuovo.
- Approvazione.
- Esecuzione per capitoli o sezioni.
- Verifica finale di completezza e coerenza.

## Output del piano

```text
### Obiettivo
- ...

### Pubblico e formato
- ...

### Fonti autorizzate
- ...

### Sotto-attivita
- ID / dipendenze / stato

### Struttura proposta
- ...

### Contenuti da preservare
- ...

### Decisioni richieste
- ...
```

## Output finale

```text
### Artifact aggiornati
- ...

### Modifiche documentali
- Added:
- Changed:
- Removed:

### Versionamento
- Versione proposta o applicata:
- Commit proposto o eseguito:
- Tag/release: non eseguiti / ...

### Verifiche
- Coerenza:
- Link:
- Comandi:
- Completezza:

### Assunzioni e punti aperti
- ...

### Sotto-attivita residue
- ...
```

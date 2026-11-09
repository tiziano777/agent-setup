---
name: tiziano-sw-eng
description: implementare o modificare in modo chirurgico poc software, script, moduli, query e configurazioni secondo le convenzioni tecniche di tiziano. usare per richieste di coding in python, bash, duckdb, postgresql, mongodb, redis, database vettoriali, dockerfile, docker compose, nginx, yaml e file conf, incluse pipeline data engineering, ai engineering, inference, rag, training e fine-tuning. non usare come skill primaria per code review, testing, debugging, observability, security review, ottimizzazione, delivery o sola documentazione.
---

# Tiziano Software Engineering

## Obiettivo

Realizzare una prima release POC funzionante, semplice, leggibile, modulare ed estendibile. Applicare modifiche minime e non distruttive, senza inventare requisiti, architetture o componenti.

## Principi inderogabili

- Applicare KISS: preferire la soluzione più semplice che soddisfa il requisito confermato.
- Essere chirurgici: modificare solo il perimetro richiesto.
- Non decidere aspetti non specificati dall'utente.
- Chiedere quando una scelta strutturale, architetturale o funzionale non è definita.
- Non fare reverse engineering dei requisiti dal codice.
- Non introdurre funzionalità, fallback, validazioni, test, error handling o refactoring non richiesti.
- Non sostituire tecnologie, librerie, pattern o interfacce senza richiesta esplicita.
- Rispettare struttura, naming, stile e dipendenze già presenti nel progetto.
- Segnalare eventuali miglioramenti vicini, ma non implementarli.
- Trattare l'utente come interlocutore tecnico esperto, soprattutto su DBMS e AI engineering: essere sintetici e concreti.

## Workflow obbligatorio

### 1. Allineare il contesto minimo

Prima di implementare, determinare solo le informazioni necessarie:

1. Tipo di lavoro: script, applicazione semplice, servizio/API, pipeline dati, progetto AI/training o modifica locale.
2. Fase: assumere POC se non diversamente specificato, dichiarandolo.
3. Paradigma:
   - standard, sincrono, monolitico o modulare;
   - reactive manifesto, event-driven o microservices;
   - ibrido.
4. Approccio concordato: funzioni, classi o combinazione delle due.
5. File e componenti realmente coinvolti.
6. Nuove dipendenze o decisioni ancora aperte.

Per reactive/event-driven chiedere solo quanto necessario alla modifica: broker o stream già scelto, REST/eventi, semantica di consegna, idempotenza e reale confine dei servizi. Non avviare un questionario architetturale completo.

Usare questo mini-allineamento quando serve:

```text
Tipo: ...
Fase: POC
Paradigma: ...
Approccio: ...
File coinvolti: ...
Nuove dipendenze: nessuna / da confermare
Decisioni richieste: nessuna / ...
```

Se non esistono decisioni aperte, procedere senza chiedere conferme inutili.

### 2. Definire il cambiamento

- Per modifica locale, identificare la sezione e il punto esatto.
- Per modifica distribuita, elencare brevemente i file coinvolti.
- Per un nuovo progetto, proporre la struttura minima adatta al tipo di lavoro.
- Non creare directory, layer o moduli senza responsabilità immediata.
- Non leggere documenti o repository ulteriori se l'utente ha chiesto di non farlo.

### 3. Implementare

- Scrivere esclusivamente il codice richiesto.
- Conservare compatibilità e interfacce non coinvolte.
- Fornire una sezione completa per modifiche locali e file completi per cambiamenti intrecciati.
- Per molti file, mostrare prima elenco e piano sintetico.
- Non implementare casi limite o eccezioni non richiesti. Segnalarli e chiedere come gestirli.

### 4. Verificare senza ampliare il perimetro

- Consentire controlli locali non distruttivi di sintassi, import e compilazione.
- Usare strumenti locali già disponibili, per esempio `python -m compileall`, `py_compile`, `ruff check` o `shellcheck`.
- Non trasformare questi controlli in test funzionali o code review.
- Eseguire o scrivere test solo su richiesta esplicita.
- Non avviare servizi, container, migrazioni o script con effetti sui dati senza richiesta.
- Non connettersi autonomamente a database o ambienti esterni.
- Non aggiungere al progetto gli strumenti usati solo dall'agente.

### 5. Restituire il risultato

Adattare l'output:

- modifica locale: sezione completa, file e posizione esatta;
- modifica intrecciata: file completi;
- molti file: piano sintetico e poi file completi.

Chiudere con un riepilogo riutilizzabile come changelog, omettendo categorie vuote:

```text
### Modifiche
- Added: ...
- Changed: ...
- Fixed: ...
- Removed: ...

### Impatto
- File coinvolti: ...
- Interfacce modificate: nessuna / ...
- Compatibilità: mantenuta / ...

### Verifiche
- Controlli eseguiti: ...
- Test eseguiti: nessuno / ...

### Assunzioni e punti aperti
- Nessuna / ...
```

Descrivere solo modifiche e verifiche realmente effettuate.

## POC e modularità

- POC significa validazione funzionale, non pipeline necessariamente elementare.
- Costruire moduli semplici, leggibili ed estendibili.
- Predisporre punti di estensione concreti senza implementarli anticipatamente.
- Usare struttura modulare e interfacce chiare come default.
- Introdurre abstract interfaces, dependency injection, adapter o strategy pattern solo quando esiste una seconda implementazione concreta o un'integrazione realmente prevista.
- Non applicare nella prima release sharding, replica, failover, load balancing o tecniche avanzate di distributed systems.
- Demandare hardening, scalabilità e produzione alla skill di delivery.

## Funzioni, classi e modelli dati

- Definire prima se il componente richiede funzioni, classi o entrambe.
- Usare funzioni per trasformazioni, operazioni modulari e logiche senza stato.
- Usare classi quando servono stato, configurazione persistente, ciclo di vita o responsabilità coesa.
- Se il progetto usa classi ma una logica è naturalmente funzionale, collocarla in un modulo coerente, per esempio `strategies/`, `services/` o `utils/`.
- Usare `utils` solo per utilità realmente generiche, mai come contenitore residuale.
- Usare type hints per input, output e strutture dati.
- Prima di introdurre un nuovo modello, proporre e motivare in una frase una tra:
  - `dataclass` per strutture interne semplici e già validate;
  - Pydantic `BaseModel` per API, JSON, configurazioni, parsing, validazione o serializzazione;
  - `TypedDict` per dizionari strutturati senza comportamento o validazione;
  - tipi semplici o tuple per dati locali minimi.
- Attendere conferma prima di introdurre il nuovo modello.
- Rispettare i modelli già presenti senza sostituirli autonomamente.

## Python e documentazione inline

- Usare `snake_case` per moduli, funzioni e variabili, `PascalCase` per classi e modelli, `UPPER_CASE` per costanti.
- Nominare le funzioni con verbi e le classi per responsabilità concreta.
- Evitare nomi generici come `manager`, `helper`, `handler`, `processor` o `data` quando non descrivono una responsabilità precisa.
- Aprire ogni nuovo file Python con una module docstring in inglese contenente path relativo e responsabilità del modulo.
- Scrivere docstring in inglese conformi a PEP 257 sotto ogni funzione e classe.
- Spiegare responsabilità, input, output ed effetti collaterali senza ripetere banalmente il codice.
- Usare commenti inline solo per integrazioni non evidenti, operazioni critiche o business logic difficile da leggere.
- Non commentare ogni riga e non proliferare commenti.

Esempio:

```python
"""
Path: src/services/document_extractor.py

Provide document extraction operations used by the processing pipeline.
"""


def extract_documents(source_path: Path) -> list[Path]:
    """Extract supported documents from the provided source path.

    Args:
        source_path: Path containing the documents to process.

    Returns:
        Paths of the extracted documents.
    """
```

## Dipendenze e tooling

- Riutilizzare librerie e tecnologie già presenti.
- Chiedere prima di introdurre una nuova dipendenza, spiegando in una riga perché è necessaria.
- Non aggiornare versioni autonomamente.
- Non creare astrazioni per tecnologie future ipotetiche.
- Rispettare formatter, linter e configurazioni esistenti.
- Non introdurre Ruff, Black, isort, mypy, pre-commit o equivalenti senza richiesta.
- Non riformattare codice estraneo alla modifica.
- Se non esiste tooling, scrivere nuovo codice conforme a PEP 8 senza aggiungerlo.

## Async e concorrenza

- Rispettare il modello sincrono o asincrono esistente.
- Non introdurre o rimuovere `async/await` autonomamente.
- Chiedere prima se la modifica propaga asincronia alle funzioni chiamanti.
- Non introdurre thread, processi, task concorrenti, code o parallelismo senza richiesta.

## Error handling, logging e observability

- Lasciare propagare le eccezioni per default.
- Non aggiungere `try/except`, fallback o eccezioni custom non richiesti.
- Segnalare gli errori potenziali e demandare l'analisi alla skill dedicata.
- Usare in Python il package standard `logging` o la libreria già adottata; usare equivalenti esistenti negli altri linguaggi.
- Non usare `print()` come logging.
- Nei moduli complessi di nuova implementazione, concordare preventivamente se e dove inserire log `DEBUG`, `INFO`, `WARNING` o `ERROR`.
- Nelle modifiche a codice esistente, non aggiungere logging se non richiesto.
- Non sostituire librerie o inventare tecniche e punti di logging.

## Configurazione e segreti

- Non hardcodare valori sensibili.
- Non inventare variabili d'ambiente.
- Riutilizzare il sistema di configurazione esistente.
- Prima di aggiungere una variabile d'ambiente, proporre nome, significato e default.
- Non assegnare default a password, token, connection string o credenziali.
- Non modificare `.env`, YAML, Compose o file `conf` estranei alla richiesta.
- Se la configurazione attraversa più livelli, mostrare il flusso e chiedere conferma.

## Data access e DBMS

Applicare a DuckDB, PostgreSQL, MongoDB, Redis e database vettoriali:

- Usare client e astrazioni già presenti.
- Non introdurre ORM, repository pattern o layer aggiuntivi senza richiesta.
- Scrivere query esplicite, leggibili e parametrizzate.
- Prevenire sempre injection: non concatenare o interpolare input nelle query.
- Validare esplicitamente identificatori dinamici non parametrizzabili.
- Separare valori, nomi di tabelle o colonne e frammenti SQL.
- Non modificare schema, indici, migrazioni, vincoli, TTL, trigger o procedure autonomamente.
- Concordare transazioni, batching, pooling e caching.
- Non ottimizzare senza richiesta o evidenza.
- Non trattare DuckDB come PostgreSQL.
- Per Redis chiarire se viene usato come cache, broker, stream o storage.
- Per database vettoriali chiarire embedding, metadati, filtri e metrica di similarità.
- Non scegliere autonomamente tra `pgvector`, Qdrant, Milvus, Weaviate o alternative.
- Proporre solo su richiesta trigger, recovery policy, livello di isolamento, locking, rollback, retry e livello minimo di garanzia transazionale adatto allo use case.
- Per MongoDB non applicare automaticamente logiche relazionali.

## Docker, Nginx e runtime

- Scrivere Dockerfile semplici con un numero contenuto di layer.
- Mantenere immagini e versioni del progetto.
- Usare multi-stage build solo con beneficio concreto.
- Non lasciare tool di debug nell'immagine finale salvo richiesta.
- Usare Compose per orchestrazione locale senza trattarlo automaticamente come architettura di produzione.
- Concordare volumi, network, health check, utente non-root e restart policy.
- Non inserire segreti in Dockerfile, Compose, `ARG`, immagini o repository.
- Mantenere Bash di avvio semplice, con quoting corretto e senza duplicare inutilmente Compose.
- Usare Nginx per reverse proxy, TLS termination, routing o load balancing solo quando richiesto.
- Valutare replica primaria/secondaria, replica set MongoDB, backup, recovery, sharding, duplicazione di istanze, load balancing, session affinity e failover solo nella fase delivery o su richiesta esplicita.

## AI engineering e training

- Distinguere inference, RAG, training, fine-tuning ed evaluation.
- Chiedere inizialmente modello di partenza, dataset e formato, obiettivo, hardware, tecnica di fine-tuning e metrica di valutazione quando rilevanti.
- Non scegliere autonomamente modello, provider, framework, dataset strategy o tecnica di training.
- Riutilizzare codice, strutture e pattern indicati dall'utente.
- Non introdurre LangChain, LlamaIndex, Hugging Face TRL, PEFT o framework analoghi senza richiesta.
- Consentire pipeline avanzate nella POC quando requisiti e pattern sono definiti.
- Separare data preparation, training/fine-tuning, evaluation, inference e persistenza degli artifact senza creare framework interni.
- Affrontare ottimizzazione solo in una fase successiva e su richiesta: profiling, mixed precision, quantizzazione, LoRA/QLoRA, gradient checkpointing, batching, compilazione, parallelismo, distributed training, memoria e throughput.

## Security minima

Applicare sempre solo queste protezioni inderogabili:

- niente segreti hardcoded;
- niente injection;
- niente credenziali nei log;
- niente disabilitazione arbitraria di TLS o verifica certificati;
- niente permessi più ampi del necessario;
- nessuna architettura di sicurezza aggiunta autonomamente.

Demandare autenticazione, autorizzazione, hardening e threat modeling alla skill Security Review.

## Test, Git e documentazione

- Non creare o modificare test senza richiesta esplicita.
- Eseguire test esistenti solo su richiesta.
- Non dedurre nuovi requisiti dai test o dal codice.
- Consentire `git commit` solo su richiesta esplicita.
- Prima del commit mostrare file modificati, changelog e messaggio proposto.
- Rispettare la convenzione esistente; se non identificabile, proporre Conventional Commits.
- Non eseguire autonomamente `push`, merge, rebase, reset, tag o cambio branch.
- Non includere file estranei alla modifica.
- Se esistono modifiche preesistenti non riconducibili al lavoro corrente, fermarsi e segnalarle.
- Aggiornare solo la documentazione direttamente richiesta.
- Non riscrivere README, guide o documenti architetturali.
- Segnalare eventuali documenti da aggiornare e demandare il lavoro alla skill Documentation & Versioning.

## Confini con le altre skill

Questa skill implementa soltanto la POC o la modifica richiesta. Non assumere come responsabilità primaria:

1. Error Handling, Logging & Debug.
2. Security Review.
3. Testing & Validation.
4. Delivery Engineering.
5. Documentation & Versioning.
6. Ottimizzazione AI o runtime.

Se una richiesta include più fasi, completare solo l'implementazione concordata e indicare sinteticamente le fasi successive appropriate.


INPUT: Prompt utente                              

[Step 1] Catalog Extractor (deterministico)                               
    
• Legge dal DB la lista completa di:                                       
    - Nomi tabelle (schema.public)
    - [ opzionale ] trigger e altre info                                           
• Output: List of target tables ["customers", "orders", "products", "payments", ...]  
•  Alternative output: 
    {
    "tables": ["customers", "orders", "payments"],
    "relations": [
        "orders.user_id = users.id",
        "orders.product_id = products.id"
    ]}     
                                                                  
[Step 2] LLM - Table Selector (NER specializzato)                         
    
  Prompt:                                                                   
    "Date queste tabelle: [List of target tables]                                  
     Quali sono necessarie per rispondere a: '{prompt utente}'?               
     Estrai SOLO i nomi delle tabelle.                
  • Output: ["customers", "orders", "payments"]                            

[Step 3] Graph Expander (deterministico con regole)                       
    
    • Regola: nessuna tabella target orfana (deve avere almeno 1 relazione   
        inbound/outbound) altrimenti devi fare discovery di tabelle intermedie 
                                                                             
  Algoritmo:                                                                 
    1. Parti dalle tabelle selezionate (seed set)                            
    2. Per ogni tabella, naviga FKs e referenced_by tabelle vicine           
    3. Se una tabella espansa NON ha FKs in ingresso/uscita → WARNING        
    4. Forza inclusione delle tabelle necessarie per connettere il grafo   (usa un algoritmo dalla letteratura che credi ottimale e che magari offre una libreria gia pronta che accetta i nostri parametri in input, altrimenti crea la funzione ad-hoc.  
                                                                             
  Output: expanded_tables = ["customers", "orders", "payments",              
                             "order_items", "products"]                      

[Step 4] Context Builder (LLM o deterministico - tu scegli)               
  
  Input: expanded_tables + DDL completo + metadati (config/umano)           
                                                                             
  Opzione A (deterministica - più sicura):                                   
    • Prendi DDL grezzo delle sole tabelle expanded                           
    • Aggiungi metadati da config file (es. "type è tier","valori in japanese", "questa tabella è un vocabolario"...) 
    • Formatta (se esiste qualcosain letteratura)come Compact Table Schema (CTS) LLM-friendly T1(a,b,c) T2(a1,b1,c1) T1.a=T2.c1 ...  e cosi via, in modod che output finale sia contesto con DDL compattato + metadati di config/umani
                                                                             
  Opzione B (LLM-based - più flessibile):                                    
    • LLM legge DDL + metadati delle sole tabelle expanded                    
    • Genera rappresentazione compatta umana/LLM-friendly                    
                                                                           
  Output: context_string (pronto per SQL generator)                         

[Step 5] SQL Generator + Validator (feedback loop correttivo)                       

 dato in input prompt + tables description and metadata (context) , risolvi problema text2sql e usa un feedback loop per problemi di esecuzione e correzione della query, causata da un possibile errore di linguaggio/sintassi, o propagazione errore nella creazione del contesto!
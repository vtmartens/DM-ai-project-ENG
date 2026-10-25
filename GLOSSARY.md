# Italian → English glossary

Generated from the codebase, not from guesswork. This is the single source of truth for the translation: `ident_map.json` (identifiers), `json_key_map.json` (JSON keys), `json_value_coupled.json` (logic-coupled string values) and the data-file rename map are all derived from it.

## How names are derived

1. **Override wins.** Exact-identifier entries in `overrides` are used verbatim.
2. **Word by word.** Identifiers split on `_` and on camel/Pascal boundaries; each word is looked up here. Camel sub-words re-join *without* an underscore, so `ValueError` stays `ValueError` and `CombattimentoState` → `CombatState`.
3. **Head-noun flip** (`nome_file` → `file_name`): Italian puts the complement after the head noun.
4. **Modifier swap** (`stato_corrente` → `current_state`): Italian adjectives follow their noun.
5. **Never touched:** dunders (`__init__`, `__getstate__`), Python builtins, stdlib/exception names, and position-tuple keys like `"(12, 14)"`.
6. Unknown words are kept and reported (`unknown_words.txt`) — the list contains only English words, abbreviations and stdlib names.

## Content words (450)

| Italian | English |
|---|---|
| a | to |
| abilita | ability |
| abilita_speciali | special_abilities |
| acceso | on |
| accessori | accessories |
| accessorio | accessory |
| accetta | accept |
| acqua | water |
| acquista | purchase |
| addio | goodbye |
| adiacente | adjacent |
| affari | business |
| aggiungi | add |
| aiuto | help |
| alleati | allies |
| altare | altar |
| altezza | height |
| ambiente | environment |
| amichevole | friendly |
| amuleto | amulet |
| anello | ring |
| annulla | cancel |
| antica | ancient |
| applica | apply |
| apre | opens |
| apri | open |
| area | area |
| arma | weapon |
| arma_sconosciuta | unknown_weapon |
| armatura | armor |
| armature | armor |
| armi | weapons |
| attacca | attack |
| attacco | attack |
| attaco | attack |
| attendi | wait |
| attiva | activate |
| attive | active |
| attivo | active |
| attributi | attributes |
| aumentare | increase |
| avanti_ | forward |
| avventura | adventure |
| avversario | opponent |
| azione | action |
| azioni | actions |
| bastone | staff |
| baule | chest |
| bersagli | targets |
| bersaglio | target |
| bevi | drink |
| birra | beer |
| bloccante | blocking |
| bloccata | blocked |
| bloccato | blocked |
| bomba | bomb |
| calcola | calculate |
| cambia | change |
| cambio | change |
| campi | fields |
| campo | field |
| caratteristica | attribute |
| caratteristiche | attributes |
| carica | load |
| caricatore | loader |
| carisma | charisma |
| casuale | random |
| categoria | category |
| cella | cell |
| cerca | search |
| chiave | key |
| chiavi | keys |
| chiedi | ask |
| cintura | belt |
| classe | class_ |
| classi | classes |
| clienti | clients |
| collega | link |
| collegamento | connection |
| collegati | linked |
| colpisco | hit |
| comando | command |
| combatti | fight |
| combattimento | combat |
| competenza | proficiency |
| competenze | skills |
| completa | complete |
| completata | completed |
| completate | completed |
| completo | complete |
| compra | buy |
| con | with |
| concludi | conclude |
| conferma | confirm |
| conferma_ | confirm |
| consigli | advice |
| contenuto | content |
| contesto | context |
| contestuali | contextual |
| continua | continue |
| continua_ | continue |
| controlla | check |
| conversa | converse |
| conversare | converse |
| conversazione | conversation |
| corda | rope |
| corrente | current |
| costituzione | constitution |
| costo | cost |
| crea | create |
| critico | critical |
| cultisti | cultists |
| cuoio | leather |
| cura | heal |
| da | from |
| dadi | dice |
| dado | dice |
| danneggiata | damaged |
| danneggiato | damaged |
| danno | damage |
| dati | data |
| dato | datum |
| descrivi | describe |
| descrizione | description |
| descrizioni | descriptions |
| destinazione | destination |
| destrezza | dexterity |
| dettagli | details |
| dettagliato | detailed |
| dialoga | converse |
| dialogo | dialogue |
| difendi | defend |
| difficolta | difficulty |
| direzione | direction |
| direzioni | directions |
| disattiva | deactivate |
| disponibili | available |
| dizionario | dictionary |
| drago | dragon |
| duello | duel |
| durata | duration |
| e | and |
| effettivo | effective |
| effetto | effect |
| elabora | process |
| elementi | elements |
| elenca | list |
| elimina | delete |
| elmo | helmet |
| entita | entity |
| entra | enter |
| equipaggia | equip |
| equipaggiabile | equippable |
| equipaggiabili | equippable |
| equipaggiamento | equipment |
| equipaggiata | equipped |
| equipaggiati | equipped |
| equipaggiato | equipped |
| erba | herb |
| errore | error |
| errori | errors |
| esamina | examine |
| esaminato | examined |
| esci | exit |
| esecuzione | execution |
| esegui | run |
| esistente | existing |
| esperienza | experience |
| esplora | explore |
| esporta | export |
| eventi | events |
| evento | event |
| facce | faces |
| fallimento | failure |
| fase | phase |
| fatto | done |
| favori | favors |
| ferisci | wound |
| fiala | vial |
| filtrati | filtered |
| fine | end |
| fontana | fountain |
| formattato | formatted |
| formula | formula |
| fortuna | luck |
| forza | strength |
| fuga | escape |
| fuggi | flee |
| gemma | gem |
| genera | generate |
| generale | general |
| gestione | management |
| gestisci | manage |
| gestore | manager |
| getta | drop |
| giocatore | player |
| gioco | game |
| griglia | grid |
| guadagna | gain |
| guadagnata | gained |
| guadagnato | gained |
| guanti | gloves |
| guarda | look |
| guaritrice | healer |
| ha | has |
| identita | identity |
| importa | import |
| imposta | set |
| inattiva | inactive |
| inattivo | inactive |
| indice | index |
| indietro | back |
| indizio | clue |
| inizia | start |
| iniziale | initial |
| inizializza | initialize |
| integra | intact |
| intelligenza | intelligence |
| interagisci | interact |
| interattivi | interactive |
| interazione | interaction |
| inventario | inventory |
| invio | enter |
| istanza | instance |
| larghezza | width |
| lavoro | job |
| leggenda | legend |
| leggi | read |
| lette | read |
| leva | lever |
| libro | book |
| limite | limit |
| lista | list |
| livelli | levels |
| livello | level |
| lotta | fight |
| magia | magic |
| maglia | chainmail |
| mantello | cloak |
| mappa | map |
| mappa_ | map |
| mappe | maps |
| materiali | materials |
| mazza | mace |
| mercante | merchant |
| mercato | market |
| merce | goods |
| messaggi | messages |
| messaggio | message |
| missione | quest |
| missioni | quests |
| modalita | mode |
| modifica | modify |
| modificati | modified |
| modificatore | modifier |
| modulo | module |
| moneta | coin |
| monete | coins |
| mostra | show |
| mostri | monsters |
| mostro | monster |
| movimento | movement |
| multipli | multiple |
| muovi | move |
| muro | wall |
| necessaria | required |
| nemici | enemies |
| nemico | enemy |
| nessuna | none |
| nessuno | none |
| nome | name |
| nomi | names |
| non | not |
| normale | normal |
| notifica | notification |
| notifiche | notifications |
| npcs | npcs |
| npg | npc |
| numero | number |
| nuova | new |
| nuovo | new |
| o | or |
| obbligatori | required |
| offri | offer |
| ogg | itm |
| oggetti | items |
| oggetto | item |
| opzione | option |
| opzioni | options |
| ora | now |
| originale | original |
| origine | origin |
| oro | gold |
| ostile | hostile |
| ottieni | get |
| parametri | parameters |
| parla | talk |
| parola | word |
| partita | game |
| passaggio | passage |
| passo | step |
| pausa | pause |
| per | for |
| percorso | path |
| pergamena | scroll |
| pesante | heavy |
| pietra | stone |
| porta | door |
| porte | doors |
| posizionato | positioned |
| posizione | position |
| posizioni | positions |
| possibili | possible |
| posto | place |
| preferenze | preferences |
| premi | press |
| presenti | present |
| prezzo | price |
| prima | first |
| primo | first |
| principale | main |
| processa | process |
| professione | profession |
| progresso | progress |
| prova | check |
| pugnale | dagger |
| pulito | clean |
| quantita | quantity |
| raccogli | pick_up |
| raggio | radius |
| ragno | spider |
| rappresentazione | representation |
| razione | ration |
| richiede | requires |
| richiedi | request |
| richiesta | required |
| richieste | requirements |
| ricompensa | reward |
| riga | row |
| righe | rows |
| rimozione | removal |
| rimuovi | remove |
| rimuovi_item | remove_item |
| riprendi | resume |
| risposta | answer |
| risultante | resulting |
| risultato | result |
| ritorno | return |
| rotta | broken |
| rotto | broken |
| saggezza | wisdom |
| sali | ascend |
| salva | save |
| salvata | saved |
| salvataggi | saves |
| salvataggio | save |
| salvati | saved |
| salvezza | saving |
| sblocca | unlock |
| sbloccati | unlocked |
| scaffale | shelf |
| scappa | run |
| scegli | choose |
| scelta | selection |
| sconosciuto | unknown |
| scudo | shield |
| segreta | secret |
| segreto | secret |
| selezionato | selected |
| serializzabile | serializable |
| serializzabili | serializable |
| serializzata | serialized |
| sessione | session |
| sessioni | sessions |
| sfida | challenge |
| simbolo | symbol |
| sistema | system |
| solo | only |
| sospetto | suspicious |
| spada | sword |
| specifica | specific |
| specifico | specific |
| spento | off |
| sporco | dirty |
| sposta | move |
| spostamento | movement |
| stanza | room |
| stati | states |
| statistiche | stats |
| stato | state |
| statua | statue |
| stivali | boots |
| strano | strange |
| stringa | string |
| strutturato | structured |
| su | on |
| subisci | take |
| successo | success |
| sulla | on |
| svantaggio | disadvantage |
| temporanei | temporary |
| temporaneo | temporary |
| tenta | attempt |
| tentativi | attempts |
| termina | terminate |
| terminato | finished |
| tesoro | treasure |
| testo | text |
| tipi | types |
| tipo | type |
| tira | roll |
| tiri | rolls |
| tiro | roll |
| torcia | torch |
| torna | return |
| torna_indietro | go_back |
| totale | total |
| transizione | transition |
| trappola | trap |
| trasferisci | transfer |
| trovata | found |
| trovato | found |
| turno | turn |
| tutte | all |
| tutti | all |
| ultima | last |
| ultimo | last |
| usa | use |
| utilizzabile | usable |
| vai | go |
| valida | valid |
| valore | value |
| vantaggio | advantage |
| vecchio | old |
| veleno | poison |
| vende | sells |
| vendere | sell |
| vendi | sell |
| vendita | sale |
| verifica | verify |
| versione | version |
| veste | robe |
| viaggia | travel |
| vicini | nearby |
| visita | visit |
| visualizza | display |
| vivo | alive |
| voci | rumors |
| zaino | backpack |
| zona | area |

## Post-noun modifiers (81) — relocated before their noun

| Italian | English |
|---|---|
| adiacente | adjacent |
| antica | ancient |
| antico | ancient |
| attive | active |
| attivo | active |
| attuale | current |
| casuale | random |
| completa | complete |
| completata | completed |
| completate | completed |
| completo | complete |
| contestuali | contextual |
| corrente | current |
| dettagliato | detailed |
| disponibili | available |
| effettivo | effective |
| equipaggiabili | equippable |
| equipaggiata | equipped |
| equipaggiati | equipped |
| equipaggiato | equipped |
| filtrati | filtered |
| filtrato | filtered |
| formattato | formatted |
| gigante | giant |
| giovane | young |
| grave | grave |
| guadagnata | gained |
| guadagnato | gained |
| iniziale | initial |
| interattivi | interactive |
| leggera | light |
| leggero | light |
| lette | read |
| magica | magic |
| magico | magic |
| massima | max |
| massimo | max |
| modificati | modified |
| multipli | multiple |
| necessaria | required |
| nuova | new |
| nuovo | new |
| obbligatori | required |
| ostile | hostile |
| posizionato | positioned |
| possibili | possible |
| precedente | previous |
| presenti | present |
| prima | first |
| primo | first |
| principale | main |
| richiesta | required |
| richieste | required |
| risultante | resulting |
| rotta | broken |
| salvata | saved |
| salvati | saved |
| sbloccati | unlocked |
| segreta | secret |
| segreta_ | secret |
| selezionato | selected |
| serializzabile | serializable |
| serializzabili | serializable |
| serializzata | serialized |
| sospetta | suspicious |
| specifica | specific |
| specifico | specific |
| strana | strange |
| strutturato | structured |
| temporanei | temporary |
| temporaneo | temporary |
| terminato | finished |
| totale | total |
| trovata | found |
| trovato | found |
| ultima | last |
| ultimo | last |
| valida | valid |
| vecchia | old |
| vecchio | old |
| vicini | nearby |

## Domain vocabulary (102) — renamed in code strings *and* JSON *and* saves

These are load-bearing: they are compared in code, matched against JSON, or used to build attribute names at runtime.


**Ability scores & stats**

| Italian | English |
|---|---|
| forza | strength |
| destrezza | dexterity |
| costituzione | constitution |
| intelligenza | intelligence |
| saggezza | wisdom |
| carisma | charisma |
| difesa | defense |
| oro | gold |
| esperienza | experience |
| livello | level |
| iniziativa | initiative |
| fortuna | luck |

**Skills (ASSOCIATED_SKILLS keys)**

| Italian | English |
|---|---|
| acrobazia | acrobatics |
| furtività | stealth |
| giocare d'azzardo | gambling |
| addestrare animali | animal_handling |
| percezione | perception |
| intuito | insight |
| natura | nature |
| religione | religion |
| arcano | arcana |
| storia | history |
| indagare | investigation |
| persuasione | persuasion |
| intimidire | intimidation |
| inganno | deception |
| atletica | athletics |
| sopravvivenza | survival |
| medicina | medicine |

**Item types**

| Italian | English |
|---|---|
| arma | weapon |
| armatura | armor |
| accessorio | accessory |
| chiave | key |
| cura | heal |
| cura_leggera | light_heal |
| cura_grave | grave_heal |
| potenziamento | buff |
| veleno | poison |
| bomba | bomb |
| vario | misc |
| pozione | potion |

**Object types & states**

| Italian | English |
|---|---|
| oggetto_interattivo | interactive_object |
| oggetto_rompibile | breakable_object |
| baule | chest |
| porta | door |
| leva | lever |
| trappola | trap |
| chiuso | closed |
| aperto | open |
| attiva | active |
| attivata | activated |
| disattivata | deactivated |
| integro | intact |

**Character classes**

| Italian | English |
|---|---|
| guerriero | fighter |
| mago | wizard |
| ladro | rogue |
| chierico | cleric |

**Monsters**

| Italian | English |
|---|---|
| goblin | goblin |
| orco | orc |
| lupo | wolf |
| scheletro | skeleton |
| troll | troll |
| drago_giovane | young_dragon |
| ragno_gigante | giant_spider |
| zombie | zombie |

**Difficulty**

| Italian | English |
|---|---|
| facile | easy |
| medio | medium |
| difficile | hard |

**Map names**

| Italian | English |
|---|---|
| taverna | tavern |
| mercato | market |
| cantina | cellar |

**Conversation states & effects**

| Italian | English |
|---|---|
| inizio | start |
| consegna_oro | give_gold |
| aggiungi_item | add_item |
| rimuovi_item | remove_item |
| scambio | trade |
| riposo | rest |
| cura_leggera | light_heal |

## Directories

| Italian | English |
|---|---|
| backup | backups |
| data/mappe | data/maps |
| data/npc | data/npcs |
| salvataggi | saves |
| sessioni | sessions |

## Data files

| Italian | English |
|---|---|
| data/items/accessori.json | data/items/accessories.json |
| data/items/armature.json | data/items/armor.json |
| data/items/armi.json | data/items/weapons.json |
| data/items/chiavi.json | data/items/keys.json |
| data/items/mappe_oggetti.json | data/items/map_objects.json |
| data/items/oggetti_interattivi.json | data/items/interactive_objects.json |
| data/items/pozioni.json | data/items/potions.json |
| data/mappe/cantina.json | data/maps/cellar.json |
| data/mappe/mercato.json | data/maps/market.json |
| data/mappe/taverna.json | data/maps/tavern.json |
| data/npc/conversations.json | data/npcs/conversations.json |
| data/npc/mappe_npg.json | data/npcs/map_npcs.json |
| data/npc/npcs.json | data/npcs/npcs.json |

## Scale

| Item | Count |
|---|---|
| Python identifiers renamed | 629 |
| JSON keys renamed | 176 |
| Logic-coupled string values renamed | 123 |
| Display strings needing prose translation | see json_display_text.txt |
| Hand-written identifier overrides | 552 |

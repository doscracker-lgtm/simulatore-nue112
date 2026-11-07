# NUE112 Studio Web — prototipo di distribuzione

## Stato reale
Questo pacchetto contiene sito statico e workflow di preparazione/pubblicazione, NON gli archivi ANNCSU. Nessun sito è stato pubblicato. Il download ufficiale e la compatibilità delle intestazioni CSV non sono stati verificati end-to-end in questo ambiente. La pipeline si ferma su schema non riconosciuto: non inventa dati.
Non è una replica completa del gestionale AREU. Incroci e POI non ancora integrati; mappa solo per coordinate puntuali valide. Non usa Google né Nominatim. Le 52 classificazioni sono trascritte dalle immagini fornite, non costituiscono configurazione PCCT ufficiale.

## Pubblicazione (una volta, per il gestore)
1. Creare un repository pubblico GitHub con ramo main.
2. Caricare il CONTENUTO di questa cartella alla radice, compresa la directory nascosta .github. Non caricare soltanto lo ZIP.
3. Settings > Pages > Source: GitHub Actions.
4. Actions > Prepara ANNCSU e pubblica sito > Run workflow.
5. Attendere la conclusione positiva di build e deploy. Il link appare in Pages e nel job deploy.
Nessuno studente installa Python. Python gira soltanto nel runner GitHub.
Se build fallisce sullo schema, scaricare artifact schema-diagnostic e adattare tools/columns.json ai nomi ufficiali verificati. Non è un passaggio richiesto agli studenti; è una verifica tecnica prima della distribuzione.

## Dati e aggiornamenti
Il builder individua i link Campania nella pagina ANNCSU, scarica gli ZIP, legge gli archivi e crea JSON per Comune. Numeri privi di coordinate rimangono ricercabili. Soglia prudenziale del sito 900 MiB: build bloccata oltre tale dimensione. Eventuali variazioni dello schema o nomi Comune mancanti richiedono adattamento. Non si sostiene completezza assoluta né certificazione della georeferenziazione.
Per aggiornare: eseguire di nuovo il workflow; verificare sempre i dati prima di distribuirli. Non è impostato aggiornamento automatico mensile.

## Uso studente
Aprire il link in un browser moderno. Digitare saler, frecce, Invio. Aggiungere via dopo Salerno e confermare, poi -n. I Comuni visitati vengono memorizzati con IndexedDB; spazio e persistenza dipendono dal browser. La mappa richiede rete e consenso. Il sito non viene precaricato integralmente e non scarica tile offline.
Report salvati nel browser, esportabili in JSON. Non usare nominativi, telefoni o dettagli di emergenze reali. La scelta ente è dello studente: nessuna validazione PCCT.

## Test eseguiti
Sintassi Python verificata. Eventuale controllo sintassi JavaScript indicato in TEST.txt. Non eseguiti test browser né download/importazione/pubblicazione reali.

## Fonti e condizioni
ANNCSU: https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/
Download: https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/Accedi-ai-servizi-di-dowload-massivo-in-Open-data/
Preservare attribuzioni e verificare la licenza associata all'archivio acquisito prima della ridistribuzione.
OpenStreetMap: https://www.openstreetmap.org/copyright
GitHub Pages: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

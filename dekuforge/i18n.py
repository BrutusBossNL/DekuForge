"""Complete launcher translations, selected independently of the game's language."""

LANGUAGES = {"en": "English", "nl": "Nederlands", "de": "Deutsch", "es": "Español", "fr": "Français"}

FILE_LABELS = {
    "en": {"all_files": "All files", "game_file": "Game executable"},
    "nl": {"all_files": "Alle bestanden", "game_file": "Spelprogramma"},
    "de": {"all_files": "Alle Dateien", "game_file": "Spielprogramm"},
    "es": {"all_files": "Todos los archivos", "game_file": "Ejecutable del juego"},
    "fr": {"all_files": "Tous les fichiers", "game_file": "Exécutable du jeu"},
}

MESSAGES = {
"en": {
"home":"Home", "build":"Build game", "settings":"Settings", "tagline":"Reforging a legend.",
"welcome":"Your next adventure starts here.", "welcome_help":"Choose your installation and continue playing, or build from your own game archive.",
"installation":"Game installation", "no_install":"No game selected", "choose_install":"Choose installation", "play":"Play", "playing":"Game is running", "game_ended":"Game closed (code {code}).", "open_folder":"Open folder",
"ready":"Ready to play", "not_ready":"Choose a built game to enable Play.", "build_help":"Build a native installation from your own game files.",
"source_step":"1  Game files", "destination_step":"2  Installation", "progress_step":"3  Build",
"source_title":"Choose your game archive", "source_help":"Select a NUP archive. Other ROM formats need a different engine and are not supported by this builder.", "source":"Game archive", "browse":"Browse…", "next":"Next", "back":"Back", "check":"Check archive", "check_ok":"Archive checked. {files} files; {size} GiB when fully extracted.",
"destination_title":"Where should the game be installed?", "destination_help":"Use a separate folder. Your current game installation and saves will remain untouched.", "destination":"Installation folder", "review":"Review and build", "start_build":"Start build", "build_title":"Forge your installation", "build_review":"Check your game archive and destination before starting.", "progress":"Build progress", "elapsed":"Elapsed: {time}", "remaining":"Remaining: {time}", "estimating":"Estimating…", "not_started":"Not started", "working":"Working…", "finished":"Build complete", "failed":"Build stopped", "logs":"Details and build log", "open_log":"Open log folder", "new_build":"Start another build", "use_build":"Use this installation",
"engine_pending":"The independent engine is not ready to produce a playable game yet. Preparation can run; unsupported stages will be reported in the log.",
"language":"Launcher language", "language_help":"Changes apply immediately. The game's language is configured separately.", "hide":"Hide launcher while playing", "on":"On", "off":"Off", "saved":"Settings saved", "error":"Something went wrong", "active_build":"A build is active. Leave the launcher open until it finishes.", "invalid_source":"Choose an existing NUP archive. Other ROM formats are not supported yet.", "invalid_destination":"Choose a separate, empty installation folder or a folder previously owned by DekuForge.", "source_missing":"Select a game archive first.", "file_selected":"Selected: {name}", "select_exe":"Choose the built game's executable", "logs_empty":"No build log yet.", "prepared":"Preparation", "generating":"Code generation", "normalizing":"Module decoding", "checking":"Checking game files", "selected":"Selected installation", "available":"Engine readiness", "cancel_nav":"Back to home", "development":"Development build", "about":"An independent, open-source project. Built with care, for your own adventure."
},
"nl": {
"home":"Hoofdmenu", "build":"Build game", "settings":"Instellingen", "tagline":"Reforging a legend.",
"welcome":"Je volgende avontuur begint hier.", "welcome_help":"Kies je installatie om verder te spelen, of bouw het spel vanuit je eigen gamearchief.",
"installation":"Spelinstallatie", "no_install":"Geen spel geselecteerd", "choose_install":"Installatie kiezen", "play":"Play", "playing":"Het spel draait", "game_ended":"Spel afgesloten (code {code}).", "open_folder":"Map openen",
"ready":"Klaar om te spelen", "not_ready":"Kies een gebouwd spel om Play te activeren.", "build_help":"Bouw een native installatie vanuit je eigen gamebestanden.",
"source_step":"1  Gamebestanden", "destination_step":"2  Installatie", "progress_step":"3  Bouwen",
"source_title":"Kies je gamearchief", "source_help":"Selecteer een NUP-archief. Andere ROM-formaten hebben een andere engine nodig en worden door deze builder niet ondersteund.", "source":"Gamearchief", "browse":"Bladeren…", "next":"Volgende", "back":"Terug", "check":"Archief controleren", "check_ok":"Archief gecontroleerd. {files} bestanden; {size} GiB na volledig uitpakken.",
"destination_title":"Waar wil je het spel installeren?", "destination_help":"Gebruik een aparte map. Je huidige spelinstallatie en saves blijven intact.", "destination":"Installatiemap", "review":"Controleren en bouwen", "start_build":"Bouwen starten", "build_title":"Smeed je installatie", "build_review":"Controleer je gamearchief en doelmap voordat je begint.", "progress":"Bouwvoortgang", "elapsed":"Verstreken: {time}", "remaining":"Resterend: {time}", "estimating":"Wordt berekend…", "not_started":"Nog niet gestart", "working":"Bezig…", "finished":"Build voltooid", "failed":"Build gestopt", "logs":"Details en bouwlog", "open_log":"Logmap openen", "new_build":"Nieuwe build starten", "use_build":"Deze installatie gebruiken",
"engine_pending":"De zelfstandige engine kan nog geen speelbaar spel opleveren. Voorbereiding kan wel; ontbrekende stappen worden in het log vermeld.",
"language":"Taal van de launcher", "language_help":"Wijzigingen gelden direct. De speltaal stel je afzonderlijk in.", "hide":"Launcher verbergen tijdens spelen", "on":"Aan", "off":"Uit", "saved":"Instellingen opgeslagen", "error":"Er ging iets mis", "active_build":"Er loopt een build. Laat de launcher open tot deze klaar is.", "invalid_source":"Kies een bestaand NUP-archief. Andere ROM-formaten worden nog niet ondersteund.", "invalid_destination":"Kies een aparte, lege installatiemap of een map die eerder door DekuForge is aangemaakt.", "source_missing":"Kies eerst een gamearchief.", "file_selected":"Geselecteerd: {name}", "select_exe":"Kies het programmabestand van het gebouwde spel", "logs_empty":"Nog geen bouwlog.", "prepared":"Voorbereiding", "generating":"Codegeneratie", "normalizing":"Modules uitpakken", "checking":"Gamebestanden controleren", "selected":"Geselecteerde installatie", "available":"Gereedheid van de engine", "cancel_nav":"Naar hoofdmenu", "development":"Ontwikkelversie", "about":"Een onafhankelijk opensourceproject. Met zorg gebouwd, voor jouw eigen avontuur."
},
"de": {
"home":"Startseite", "build":"Spiel erstellen", "settings":"Einstellungen", "tagline":"Reforging a legend.",
"welcome":"Dein nächstes Abenteuer beginnt hier.", "welcome_help":"Wähle deine Installation zum Weiterspielen oder erstelle das Spiel aus deinem eigenen Archiv.",
"installation":"Spielinstallation", "no_install":"Kein Spiel ausgewählt", "choose_install":"Installation wählen", "play":"Spielen", "playing":"Das Spiel läuft", "game_ended":"Spiel beendet (Code {code}).", "open_folder":"Ordner öffnen",
"ready":"Spielbereit", "not_ready":"Wähle ein erstelltes Spiel, um Spielen zu aktivieren.", "build_help":"Erstelle eine native Installation aus deinen eigenen Spieldateien.",
"source_step":"1  Spieldateien", "destination_step":"2  Installation", "progress_step":"3  Erstellen",
"source_title":"Wähle dein Spielarchiv", "source_help":"Wähle ein NUP-Archiv. Andere ROM-Formate benötigen eine andere Engine und werden hier nicht unterstützt.", "source":"Spielarchiv", "browse":"Durchsuchen…", "next":"Weiter", "back":"Zurück", "check":"Archiv prüfen", "check_ok":"Archiv geprüft. {files} Dateien; {size} GiB vollständig entpackt.",
"destination_title":"Wo soll das Spiel installiert werden?", "destination_help":"Verwende einen separaten Ordner. Deine aktuelle Installation und Spielstände bleiben unverändert.", "destination":"Installationsordner", "review":"Prüfen und erstellen", "start_build":"Erstellung starten", "build_title":"Schmiede deine Installation", "build_review":"Prüfe Spielarchiv und Zielordner vor dem Start.", "progress":"Fortschritt", "elapsed":"Vergangen: {time}", "remaining":"Verbleibend: {time}", "estimating":"Wird berechnet…", "not_started":"Noch nicht gestartet", "working":"In Arbeit…", "finished":"Erstellung abgeschlossen", "failed":"Erstellung gestoppt", "logs":"Details und Protokoll", "open_log":"Protokollordner öffnen", "new_build":"Neue Erstellung starten", "use_build":"Diese Installation verwenden",
"engine_pending":"Die eigenständige Engine kann noch kein spielbares Spiel erstellen. Die Vorbereitung ist möglich; fehlende Schritte werden protokolliert.",
"language":"Sprache des Launchers", "language_help":"Änderungen gelten sofort. Die Spielsprache wird separat eingestellt.", "hide":"Launcher beim Spielen ausblenden", "on":"Ein", "off":"Aus", "saved":"Einstellungen gespeichert", "error":"Ein Fehler ist aufgetreten", "active_build":"Eine Erstellung läuft. Lass den Launcher bis zum Abschluss geöffnet.", "invalid_source":"Wähle ein vorhandenes NUP-Archiv. Andere ROM-Formate werden noch nicht unterstützt.", "invalid_destination":"Wähle einen separaten, leeren Installationsordner oder einen zuvor von DekuForge erstellten Ordner.", "source_missing":"Wähle zuerst ein Spielarchiv.", "file_selected":"Ausgewählt: {name}", "select_exe":"Wähle die Programmdatei des erstellten Spiels", "logs_empty":"Noch kein Protokoll.", "prepared":"Vorbereitung", "generating":"Codegenerierung", "normalizing":"Module entpacken", "checking":"Spieldateien prüfen", "selected":"Ausgewählte Installation", "available":"Engine-Bereitschaft", "cancel_nav":"Zur Startseite", "development":"Entwicklungsversion", "about":"Ein unabhängiges Open-Source-Projekt. Mit Sorgfalt für dein eigenes Abenteuer entwickelt."
},
"es": {
"home":"Inicio", "build":"Crear juego", "settings":"Ajustes", "tagline":"Reforging a legend.",
"welcome":"Tu próxima aventura empieza aquí.", "welcome_help":"Elige tu instalación para seguir jugando o crea el juego desde tu propio archivo.",
"installation":"Instalación del juego", "no_install":"Ningún juego seleccionado", "choose_install":"Elegir instalación", "play":"Jugar", "playing":"El juego está en ejecución", "game_ended":"Juego cerrado (código {code}).", "open_folder":"Abrir carpeta",
"ready":"Listo para jugar", "not_ready":"Elige un juego compilado para activar Jugar.", "build_help":"Crea una instalación nativa desde tus propios archivos del juego.",
"source_step":"1  Archivos", "destination_step":"2  Instalación", "progress_step":"3  Compilación",
"source_title":"Elige el archivo del juego", "source_help":"Selecciona un archivo NUP. Otros formatos ROM necesitan un motor diferente y no son compatibles con este constructor.", "source":"Archivo del juego", "browse":"Examinar…", "next":"Siguiente", "back":"Atrás", "check":"Verificar archivo", "check_ok":"Archivo verificado. {files} archivos; {size} GiB al extraerlos.",
"destination_title":"¿Dónde quieres instalar el juego?", "destination_help":"Usa una carpeta independiente. Tu instalación actual y tus partidas se conservarán.", "destination":"Carpeta de instalación", "review":"Revisar y compilar", "start_build":"Iniciar compilación", "build_title":"Forja tu instalación", "build_review":"Revisa el archivo del juego y la carpeta de destino antes de empezar.", "progress":"Progreso", "elapsed":"Transcurrido: {time}", "remaining":"Restante: {time}", "estimating":"Calculando…", "not_started":"Sin iniciar", "working":"Trabajando…", "finished":"Compilación terminada", "failed":"Compilación detenida", "logs":"Detalles y registro", "open_log":"Abrir registros", "new_build":"Nueva compilación", "use_build":"Usar esta instalación",
"engine_pending":"El motor independiente aún no puede crear un juego jugable. La preparación está disponible; las etapas pendientes se indican en el registro.",
"language":"Idioma del lanzador", "language_help":"Los cambios se aplican al instante. El idioma del juego se configura por separado.", "hide":"Ocultar el lanzador al jugar", "on":"Sí", "off":"No", "saved":"Ajustes guardados", "error":"Se ha producido un error", "active_build":"Hay una compilación activa. Mantén el lanzador abierto hasta que termine.", "invalid_source":"Elige un archivo NUP existente. Otros formatos ROM aún no son compatibles.", "invalid_destination":"Elige una carpeta independiente vacía o una creada previamente por DekuForge.", "source_missing":"Selecciona primero un archivo del juego.", "file_selected":"Seleccionado: {name}", "select_exe":"Elige el ejecutable del juego compilado", "logs_empty":"Todavía no hay registro.", "prepared":"Preparación", "generating":"Generación de código", "normalizing":"Descompresión de módulos", "checking":"Verificando archivos", "selected":"Instalación seleccionada", "available":"Estado del motor", "cancel_nav":"Volver al inicio", "development":"Versión de desarrollo", "about":"Un proyecto independiente de código abierto. Creado con cuidado para tu propia aventura."
},
"fr": {
"home":"Accueil", "build":"Créer le jeu", "settings":"Paramètres", "tagline":"Reforging a legend.",
"welcome":"Votre prochaine aventure commence ici.", "welcome_help":"Choisissez votre installation pour continuer à jouer ou créez le jeu depuis votre propre archive.",
"installation":"Installation du jeu", "no_install":"Aucun jeu sélectionné", "choose_install":"Choisir une installation", "play":"Jouer", "playing":"Le jeu est en cours", "game_ended":"Jeu fermé (code {code}).", "open_folder":"Ouvrir le dossier",
"ready":"Prêt à jouer", "not_ready":"Choisissez un jeu compilé pour activer Jouer.", "build_help":"Créez une installation native à partir de vos propres fichiers.",
"source_step":"1  Fichiers", "destination_step":"2  Installation", "progress_step":"3  Compilation",
"source_title":"Choisissez votre archive de jeu", "source_help":"Sélectionnez une archive NUP. Les autres formats ROM nécessitent un autre moteur et ne sont pas pris en charge ici.", "source":"Archive de jeu", "browse":"Parcourir…", "next":"Suivant", "back":"Retour", "check":"Vérifier l’archive", "check_ok":"Archive vérifiée. {files} fichiers ; {size} Gio après extraction complète.",
"destination_title":"Où installer le jeu ?", "destination_help":"Utilisez un dossier séparé. Votre installation actuelle et vos sauvegardes resteront intactes.", "destination":"Dossier d’installation", "review":"Vérifier et compiler", "start_build":"Lancer la compilation", "build_title":"Forgez votre installation", "build_review":"Vérifiez l’archive et le dossier de destination avant de commencer.", "progress":"Progression", "elapsed":"Écoulé : {time}", "remaining":"Restant : {time}", "estimating":"Calcul en cours…", "not_started":"Non démarré", "working":"En cours…", "finished":"Compilation terminée", "failed":"Compilation arrêtée", "logs":"Détails et journal", "open_log":"Ouvrir les journaux", "new_build":"Nouvelle compilation", "use_build":"Utiliser cette installation",
"engine_pending":"Le moteur indépendant ne peut pas encore produire de jeu jouable. La préparation est disponible ; les étapes manquantes sont indiquées dans le journal.",
"language":"Langue du lanceur", "language_help":"Les modifications sont immédiates. La langue du jeu se règle séparément.", "hide":"Masquer le lanceur pendant le jeu", "on":"Oui", "off":"Non", "saved":"Paramètres enregistrés", "error":"Une erreur est survenue", "active_build":"Une compilation est en cours. Laissez le lanceur ouvert jusqu’à la fin.", "invalid_source":"Choisissez une archive NUP existante. Les autres formats ROM ne sont pas encore pris en charge.", "invalid_destination":"Choisissez un dossier d’installation séparé et vide, ou créé auparavant par DekuForge.", "source_missing":"Choisissez d’abord une archive de jeu.", "file_selected":"Sélectionné : {name}", "select_exe":"Choisissez l’exécutable du jeu compilé", "logs_empty":"Aucun journal pour le moment.", "prepared":"Préparation", "generating":"Génération du code", "normalizing":"Décompression des modules", "checking":"Vérification des fichiers", "selected":"Installation sélectionnée", "available":"État du moteur", "cancel_nav":"Retour à l’accueil", "development":"Version de développement", "about":"Un projet indépendant et open source. Conçu avec soin, pour votre propre aventure."
}}


from .launcher_labels import extend
extend(MESSAGES)

_BUILD_PHASES = {
    "en": ("Compiling game", "Preparing shaders", "Preparing button prompts", "Building game files"),
    "nl": ("Game compileren", "Shaders voorbereiden", "Knopaanwijzingen voorbereiden", "Gamebestanden opbouwen"),
    "de": ("Spiel kompilieren", "Shader vorbereiten", "Tastenhinweise vorbereiten", "Spieldateien erstellen"),
    "es": ("Compilando el juego", "Preparando shaders", "Preparando indicaciones de botones", "Creando archivos del juego"),
    "fr": ("Compilation du jeu", "Préparation des shaders", "Préparation des indications de touches", "Création des fichiers du jeu"),
}
for _language, _labels in _BUILD_PHASES.items():
    MESSAGES[_language].update(zip(("compiling", "shaders", "prompts", "extracting"), _labels))

_STABLE_BUILD_HELP = {
    "en": "Build the game from your own archive. The first build also prepares its shaders.",
    "nl": "Bouw het spel vanuit je eigen gamearchief. De eerste build bereidt ook de shaders voor.",
    "de": "Erstelle das Spiel aus deinem eigenen Spielarchiv. Beim ersten Build werden auch die Shader vorbereitet.",
    "es": "Crea el juego desde tu archivo. La primera compilaci\u00f3n tambi\u00e9n prepara los shaders.",
    "fr": "Construisez le jeu depuis votre archive. La premi\u00e8re compilation pr\u00e9pare aussi les shaders.",
}
for _language, _help in _STABLE_BUILD_HELP.items():
    MESSAGES[_language]["engine_pending"] = _help





_PIPELINE_PHASE_LABELS = {
    "en": "Preparing graphics pipelines",
    "nl": "Grafische pipelines voorbereiden",
    "de": "Grafik-Pipelines vorbereiten",
    "es": "Preparando pipelines gr\u00e1ficos",
    "fr": "Pr\u00e9paration des pipelines graphiques",
}
for _language, _label in _PIPELINE_PHASE_LABELS.items():
    MESSAGES[_language]["pipelines"] = _label


_UPDATE_MESSAGES = {'en': {'update_pending': 'Updates verify downloads, preserve your saves and keep the working game until a '
                          'rebuild succeeds.',
        'release_incompatible': 'This release has no compatible updater package.',
        'update_confirm': 'Install {version}? The launcher will restart. Changed engine code is rebuilt '
                          'locally from your own game archive. Your current game and saves are retained.',
        'update_downloading': 'Downloading and verifying the release...',
        'update_download_progress': 'Downloading and verifying: {percent}%',
        'update_error': 'Update stopped; the previous installation is retained. {error}',
        'rebuild_update': 'Rebuild for installed release',
        'update_rebuild_wait': 'Close the game and select your game archive to finish the engine update.',
        'update_game_ready': 'Updated game is ready. The previous build remains available.'},
 'nl': {'update_pending': 'Updates controleren downloads, bewaren je saves en behouden de werkende game tot '
                          'de rebuild slaagt.',
        'release_incompatible': 'Deze release heeft geen geschikt updatepakket.',
        'update_confirm': '{version} installeren? De launcher herstart. Gewijzigde enginecode wordt lokaal '
                          'gebouwd vanuit je eigen gamearchief. Je huidige game en saves blijven behouden.',
        'update_downloading': 'Release downloaden en controleren...',
        'update_download_progress': 'Downloaden en controleren: {percent}%',
        'update_error': 'Update gestopt; de vorige installatie is behouden. {error}',
        'rebuild_update': 'Herbouwen voor geinstalleerde release',
        'update_rebuild_wait': 'Sluit de game en kies je gamearchief om de engine-update af te ronden.',
        'update_game_ready': 'Bijgewerkte game gereed. De vorige build blijft beschikbaar.'},
 'de': {'update_pending': 'Updates pruefen Downloads, behalten Spielstaende und erhalten das laufende Spiel '
                          'bis zum erfolgreichen Neubau.',
        'release_incompatible': 'Diese Version hat kein kompatibles Updatepaket.',
        'update_confirm': '{version} installieren? Der Launcher startet neu. Geaenderter Engine-Code wird '
                          'lokal aus Ihrem Spielarchiv gebaut. Spiel und Spielstaende bleiben erhalten.',
        'update_downloading': 'Version wird geladen und geprueft...',
        'update_download_progress': 'Laden und pruefen: {percent}%',
        'update_error': 'Update gestoppt; die vorherige Installation bleibt erhalten. {error}',
        'rebuild_update': 'Spiel fuer installierte Version neu bauen',
        'update_rebuild_wait': 'Spiel schliessen und eigenes Spielarchiv waehlen, um das Update '
                               'abzuschliessen.',
        'update_game_ready': 'Aktualisiertes Spiel bereit. Der vorherige Build bleibt verfuegbar.'},
 'es': {'update_pending': 'Las actualizaciones verifican descargas y conservan las partidas y el juego '
                          'anterior hasta completar la compilacion.',
        'release_incompatible': 'Esta version no tiene un paquete de actualizacion compatible.',
        'update_confirm': 'Instalar {version}? El lanzador se reiniciara. Los cambios del motor se compilan '
                          'localmente desde tu archivo del juego. Se conservan el juego y las partidas.',
        'update_downloading': 'Descargando y verificando la version...',
        'update_download_progress': 'Descargando y verificando: {percent}%',
        'update_error': 'Actualizacion detenida; se conserva la instalacion anterior. {error}',
        'rebuild_update': 'Compilar para la version instalada',
        'update_rebuild_wait': 'Cierra el juego y elige tu archivo para finalizar la actualizacion del '
                               'motor.',
        'update_game_ready': 'Juego actualizado listo. La compilacion anterior sigue disponible.'},
 'fr': {'update_pending': 'Les mises a jour verifient les fichiers et conservent les sauvegardes et le jeu '
                          'precedent avant la fin de la compilation.',
        'release_incompatible': 'Cette version ne contient pas de paquet de mise a jour compatible.',
        'update_confirm': 'Installer {version} ? Le lanceur redemarrera. Les changements du moteur sont '
                          'compiles localement depuis votre archive. Le jeu et les sauvegardes sont '
                          'conserves.',
        'update_downloading': 'Telechargement et verification de la version...',
        'update_download_progress': 'Telechargement et verification : {percent}%',
        'update_error': 'Mise a jour arretee ; installation precedente conservee. {error}',
        'rebuild_update': 'Recompiler pour la version installee',
        'update_rebuild_wait': 'Fermez le jeu et choisissez votre archive pour terminer la mise a jour du '
                               'moteur.',
        'update_game_ready': 'Jeu mis a jour pret. La compilation precedente reste disponible.'}}
for _language, _messages in _UPDATE_MESSAGES.items():
    MESSAGES[_language].update(_messages)


_REPORT_MESSAGES = {'en': {'report': 'Report a problem',
        'report_help': 'Review hardware, versions and log excerpts before sending. No game files or saves '
                       'are included.',
        'report_title': 'Short title',
        'report_details': 'What happened? Include steps to reproduce.',
        'report_expected': 'What did you expect?',
        'report_logs': 'Include recent text logs (personal paths and tokens filtered)',
        'report_preview': 'Report preview',
        'report_direct': 'Send to GitHub',
        'report_browser': 'Open browser',
        'report_export': 'Save report',
        'report_auth': 'Browser submission uses your GitHub account and a shorter log excerpt. Direct '
                       'sending uses an existing GitHub CLI sign-in or GH_TOKEN. DekuForge does not store '
                       'your token.',
        'report_sent': 'Report submitted: {url}',
        'report_send_error': 'Could not confirm submission: {error}. Check GitHub before retrying to avoid '
                             'duplicates.',
        'report_required': 'Enter a title and describe what happened.',
        'report_signin': 'Sign in with GitHub CLI or use the browser button.',
        'report_crash': 'The game exited unexpectedly (code {code}). You can review and report it below.',
        'report_previous': 'A previous crash or launcher error is available for review.',
        'report_unknown': 'Unknown'},
 'nl': {'report': 'Probleem melden',
        'report_help': 'Controleer hardware, versies en logregels voor verzending. Spelbestanden en saves '
                       'worden niet meegestuurd.',
        'report_title': 'Korte titel',
        'report_details': 'Wat gebeurde er? Vermeld stappen om het te herhalen.',
        'report_expected': 'Wat verwachtte je?',
        'report_logs': 'Recente tekstlogs toevoegen (paden en tokens gefilterd)',
        'report_preview': 'Voorbeeld van melding',
        'report_direct': 'Naar GitHub sturen',
        'report_browser': 'Browser openen',
        'report_export': 'Melding opslaan',
        'report_auth': 'Via de browser gebruik je je GitHub-account en een korter logfragment. Direct '
                       'versturen gebruikt een bestaande GitHub CLI-aanmelding of GH_TOKEN. DekuForge '
                       'bewaart je token niet.',
        'report_sent': 'Melding verstuurd: {url}',
        'report_send_error': 'Verzending niet bevestigd: {error}. Controleer GitHub voor je opnieuw '
                             'verstuurt.',
        'report_required': 'Vul een titel in en beschrijf wat er gebeurde.',
        'report_signin': 'Meld je aan met GitHub CLI of gebruik de browserknop.',
        'report_crash': 'De game is onverwacht gestopt (code {code}). Controleer de melding hieronder.',
        'report_previous': 'Een eerdere crash of launcherfout is beschikbaar om te melden.',
        'report_unknown': 'Onbekend'},
 'de': {'report': 'Problem melden',
        'report_help': 'Hardware, Versionen und Logauszuege vor dem Senden pruefen. Keine Spieldateien oder '
                       'Spielstaende werden beigefuegt.',
        'report_title': 'Kurzer Titel',
        'report_details': 'Was ist passiert? Schritte zur Wiederholung angeben.',
        'report_expected': 'Was wurde erwartet?',
        'report_logs': 'Aktuelle Textlogs beifuegen (Pfade und Tokens gefiltert)',
        'report_preview': 'Meldung pruefen',
        'report_direct': 'An GitHub senden',
        'report_browser': 'Browser oeffnen',
        'report_export': 'Meldung speichern',
        'report_auth': 'Im Browser wird Ihr GitHub-Konto mit kurzem Logauszug verwendet. Direktes Senden '
                       'nutzt eine bestehende GitHub-CLI-Anmeldung oder GH_TOKEN. DekuForge speichert kein '
                       'Token.',
        'report_sent': 'Meldung gesendet: {url}',
        'report_send_error': 'Senden nicht bestaetigt: {error}. Vor einem weiteren Versuch GitHub auf '
                             'Duplikate pruefen.',
        'report_required': 'Titel und Problembeschreibung eingeben.',
        'report_signin': 'Mit GitHub CLI anmelden oder den Browser verwenden.',
        'report_crash': 'Spiel unerwartet beendet (Code {code}). Meldung unten pruefen.',
        'report_previous': 'Ein frueherer Absturz oder Launcherfehler kann gemeldet werden.',
        'report_unknown': 'Unbekannt'},
 'es': {'report': 'Informar problema',
        'report_help': 'Revisa hardware, versiones y extractos antes de enviar. No se incluyen archivos del '
                       'juego ni partidas.',
        'report_title': 'Titulo breve',
        'report_details': 'Que ocurrio? Incluye los pasos para reproducirlo.',
        'report_expected': 'Que esperabas?',
        'report_logs': 'Incluir registros recientes (rutas y tokens filtrados)',
        'report_preview': 'Vista previa',
        'report_direct': 'Enviar a GitHub',
        'report_browser': 'Abrir navegador',
        'report_export': 'Guardar informe',
        'report_auth': 'El navegador usa tu cuenta de GitHub y un extracto mas corto. El envio directo usa '
                       'GitHub CLI o GH_TOKEN existentes. DekuForge no guarda tu token.',
        'report_sent': 'Informe enviado: {url}',
        'report_send_error': 'No se confirmo el envio: {error}. Comprueba GitHub antes de reintentar para '
                             'evitar duplicados.',
        'report_required': 'Introduce un titulo y describe el problema.',
        'report_signin': 'Inicia sesion con GitHub CLI o utiliza el navegador.',
        'report_crash': 'El juego termino inesperadamente (codigo {code}). Revisa el informe.',
        'report_previous': 'Hay un fallo anterior del juego o del lanzador para revisar.',
        'report_unknown': 'Desconocido'},
 'fr': {'report': 'Signaler un probleme',
        'report_help': 'Verifiez materiel, versions et extraits avant envoi. Aucun fichier de jeu ni '
                       'sauvegarde ne sera joint.',
        'report_title': 'Titre court',
        'report_details': 'Que se passe-t-il ? Indiquez les etapes de reproduction.',
        'report_expected': 'Quel resultat attendiez-vous ?',
        'report_logs': 'Inclure les journaux recents (chemins et jetons filtres)',
        'report_preview': 'Apercu du rapport',
        'report_direct': 'Envoyer a GitHub',
        'report_browser': 'Ouvrir navigateur',
        'report_export': 'Enregistrer',
        'report_auth': 'Le navigateur utilise votre compte GitHub et un extrait plus court. Envoi direct '
                       'avec une connexion GitHub CLI ou GH_TOKEN existante. DekuForge ne conserve pas votre '
                       'jeton.',
        'report_sent': 'Rapport envoye : {url}',
        'report_send_error': 'Envoi non confirme : {error}. Verifiez GitHub avant de reessayer pour eviter '
                             'un doublon.',
        'report_required': 'Saisissez un titre et decrivez le probleme.',
        'report_signin': 'Connectez GitHub CLI ou utilisez le navigateur.',
        'report_crash': 'Le jeu a quitte de facon inattendue (code {code}). Verifiez le rapport.',
        'report_previous': 'Un ancien plantage ou une erreur du lanceur peut etre examine.',
        'report_unknown': 'Inconnu'}}
for _language,_messages in _REPORT_MESSAGES.items():
    MESSAGES[_language].update(_messages)


for _language,_text in {"en":"Uninstall DekuForge","nl":"DekuForge verwijderen","de":"DekuForge deinstallieren","es":"Desinstalar DekuForge","fr":"Desinstaller DekuForge"}.items():
    MESSAGES[_language]["uninstall"]=_text


for _language, _text in {
    "en": "A build tool was unexpectedly interrupted by Windows (0xC000013A). Completed work is retained. Keep the launcher open and retry with the same archive and build folder. See the build log for details.",
    "nl": "Een bouwtool is onverwacht onderbroken door Windows (0xC000013A). Voltooid werk blijft bewaard. Laat de launcher open en probeer opnieuw met hetzelfde archief en dezelfde bouwmap. Bekijk de bouwlog voor details.",
    "de": "Ein Build-Werkzeug wurde unter Windows unerwartet unterbrochen (0xC000013A). Fertige Arbeit bleibt erhalten. Lassen Sie den Launcher offen und versuchen Sie es mit demselben Archiv und Build-Ordner erneut. Details stehen im Build-Protokoll.",
    "es": "Una herramienta se interrumpio inesperadamente en Windows (0xC000013A). El trabajo completado se conserva. Mantenga el lanzador abierto y reintente con el mismo archivo y carpeta de compilacion. Consulte el registro para mas detalles.",
    "fr": "Un outil de compilation a ete interrompu sous Windows (0xC000013A). Le travail termine est conserve. Gardez le lanceur ouvert et reessayez avec la meme archive et le meme dossier de compilation. Consultez le journal pour les details.",
}.items():
    MESSAGES[_language]["build_interrupted"] = _text


def translate(language, key, **values):
    selected = language if language in MESSAGES else "en"
    text = FILE_LABELS[selected][key] if key in FILE_LABELS[selected] else MESSAGES[selected].get(key,MESSAGES["en"].get(key,key.replace("_"," ").title()))
    return text.format(**values)

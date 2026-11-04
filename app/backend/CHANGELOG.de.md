# Änderungen (Deutsch)

Die deutsche Fassung von CHANGELOG.md, für «Neuigkeiten» in der Vereins-App
und in manage. CHANGELOG.md (Englisch) ist die Vorlage: gleiche Versionen,
gleiche Abschnitte (die Überschriften `### Added`, `### Changed`, `### Fixed` …
bleiben englisch, die Apps übersetzen sie) und gleich viele Einträge pro
Abschnitt, in derselben Reihenfolge. Weicht eine Version davon ab, zeigen die
Apps für diese Version den englischen Text, bis die Übersetzung nachgeführt ist.

## [Unreleased]

### Changed

- **Eigenes Plattform-Backend** (k3s, mit Compose optional): die Plattform-API (`/api/v1/manager`, `/api/v1/admin`, `/api/v1/system`), die Plattform-Jobs (Backups, Prüfungen, Upgrades, Plugins, Alarme), die Migrationen und der Zeitplaner laufen in eigenen Diensten `platform-backend` und `platform-worker`, aus demselben Build, veröffentlicht als `ghcr.io/hubra-app/hubra/platform-backend`. Ein reines Plattform-Update startet das Vereins-Backend nicht mehr neu. Die Plattform-Version muss gleich oder neuer sein als die Vereins-Version. Siehe docs/platform-backend.md.
- **Navigation in manage nach Aufgaben geordnet**: Die Seitenleiste hat die Bereiche Vereine, Betrieb, Dienste, Zugriff & Sicherheit und Hubra, und die Tabs einer Seite gehören zu einer Aufgabe. Die Sammelseite Plattform-Einstellungen gibt es nicht mehr: Jede Einstellung steht auf der Seite, die sie betrifft (Mail-Relay und Systemabsender unter Mail, Backup-Speicher unter Backups › Speicher, Discord-Zugangsdaten und -Kanäle unter Discord, Limits pro Tarif unter Alle Vereine, Versand der Warnungen unter Warnungen › Regeln, Grenzwerte unter Diagnose › Leistung). Vereinsanfragen sind ein Tab von Alle Vereine, Mail-Versand und Mailserver kamen von Diagnose zu Mail, der Discord-Status zu Discord, die API-Berechtigungen zu Rollen, Leistung von Warnungen zu Diagnose; Wartung hat eine eigene Seite, und Support-Zugriffe sind ein Tab des Audit-Logs. Alte Adressen leiten weiter, Lesezeichen und Links in Warnmails und Discord-Meldungen führen weiter auf die richtige Seite.

- **Keine Warnung «High API Error Rate» mehr nach jedem Update**: Die Prüfung zählte 4xx und 5xx über den ganzen Monat, also lösten die 401 abgelaufener Anmeldungen nach einem Neustart sie aus. Jetzt zählt sie Serverfehler (5xx) der letzten Stunde (alle 10 Minuten, ab 50 Anfragen, Schwelle `API_ERROR_RATE_THRESHOLD`, 5 %), übergeht Fehler in den ersten zwei Minuten eines Backends, schickt eine Warnung pro Vorfall und eine Entwarnung, wenn es wieder läuft.
- **Systemwarnungen gehen ins Discord-Protokoll der Plattform** statt an einen Webhook: `DISCORD_WEBHOOK_URL` fällt weg. Den Protokollkanal stellst du in manage › Plattform-Einstellungen › Discord ein.
- **`FERNET_KEY` ist im Betrieb Pflicht** (Änderung in `.env`): Ohne ihn startet das Backend nicht mehr. Bisher gespeicherte Werte waren mit einem aus `SECRET_KEY` abgeleiteten Schlüssel verschlüsselt und bleiben lesbar. Setze also einen neuen Schlüssel und führe `flask crypto rotate` aus.

### Added

- **API-Tokens** (`Authorization: Bearer hbr_…`), vorerst nur im Backend: persönliche Tokens für ein Mitglied in einem Verein, Vereins-Tokens von Vereinsadmins und Plattform-Tokens nur zum Lesen für Plattform-Admins. Ein Token handelt als seine Person, kann deren aktuelle Rechte nur auf die gewählten Bereiche einschränken (Standard: nur lesen), wird einmal angezeigt und nur als Hash gespeichert, läuft nach höchstens einem Jahr ab (Plattform-Tokens nach 30 Tagen) und öffnet nie Konto-, Anmelde-, Token-, Bestätigungs- oder Plugin-Routen. Zum Erstellen braucht es Zwei-Faktor-Anmeldung und eine frische Passwortbestätigung. Mitglieder erhalten persönliche Tokens nur, wenn der Verein es erlaubt. Siehe docs/api-tokens.md.

- **Module in Tarifen, Modulpreise pro Mitglied oder pro Lizenz**: In manage › Alle Vereine › Tarife & Preise führt ein Tarif die Module und Plugins, die er enthält, jedes entweder inklusive oder mit eigenem Preis im Tarif. Jeder Modulpreis (im Tarif, als Listenpreis eines Zusatzmoduls oder beim Verein) gilt pauschal, pro Mitglied (nicht archivierte Mitglieder) oder pro Lizenz. Die Abrechnung eines Vereins zählt die Module des Tarifs und seine Zusatzmodule mit ihrer Menge (Lizenzen pro Verein), und ein Zusatzmodul beim Verein ersetzt den Tarifpreis für dieses Modul. Die öffentliche Preis-API zeigt die Module jedes Tarifs, die Einheit jedes Zusatzmodul-Preises und welche öffentlichen Tarife es enthalten (docs/public-api.md).

- **Vereine richten ihren Backup-Schlüssel selbst ein**: Einstellungen › Verschlüsselung in der Vereins-App führt Vereinsadmins durch: wofür der Schlüssel da ist, ein age-Schlüsselpaar im Browser erzeugen (der private Schlüssel erreicht den Server nie), ihn sicher aufbewahren (herunterladen oder kopieren, mit Tipps) und zeigen, dass er gespeichert ist, indem man die Schlüsseldatei einfügt oder wählt, bevor der öffentliche Schlüssel gespeichert wird. Danach zeigt der Tab den Schlüssel, wann und von wem er eingerichtet wurde, das letzte Backup mit diesem Schlüssel, eine Prüfung des gespeicherten Schlüssels, Ersetzen und Entfernen sowie wie man ein Backup mit `age` öffnet. Vereine mit eigenem age-Schlüssel können dessen öffentlichen Schlüssel einfügen. Neue API `GET/PUT/DELETE /api/v1/admin/backup-key` (Vereinsadmins); ein dorthin gesendeter privater Schlüssel wird abgelehnt. Ein Verein kann auch **Nur unser Schlüssel** wählen (mit getippter Bestätigung): Neue Backups sind dann nur mit dem Vereinsschlüssel verschlüsselt, und Hubra kann sie nicht mehr wiederherstellen; manage › Verschlüsselung markiert diese Vereine.

- **Plattform-Admins in Discord** (braucht Discord-Plugin 2.3.0): Vereinsanfragen im Plattform-Protokoll haben Knöpfe Annehmen / Ablehnen (Ablehnen fragt nach dem Grund), Warnungen haben Bestätigen, 1 h stumm und In manage öffnen und werden grün, wenn das Problem weg ist. Auf dem Plattform-Server gibt es `/plattform status|verein|backup` und `/wartung jetzt|planen|ende|abbrechen` (`planen` legt eine geplante Wartung für alle Vereine an). Neue Kategorien im Plattform-Protokoll: Tagesübersicht um 08:00, Neuerungen jeder neuen Version und Sicherheitsmeldungen (Plattform-Admins auf neuem Gerät oder ohne Zwei-Faktor, viele Fehlanmeldungen von einer Adresse, Schlüssel älter als ein Jahr). Nur verknüpfte Plattform-Admins mit Zwei-Faktor und dem passenden Recht dürfen das. Vereine können Versions- und Wartungshinweise auf ihrem Server einschalten. Discord-Interaktionen laufen jetzt auch während der Wartung. Siehe docs/discord.md, «Platform admins in Discord».

- **Rollen auf dem Plattform-Server** (manage › Plattform-Einstellungen › Discord, standardmässig aus): Wer Discord verknüpft hat, bekommt auf dem Server des Plattform-Protokolls die Rollen Plattform-Admin (Plattform-Team mit Zwei-Faktor), Vereinsinhaber, Vereinsadmin und Vereinsmitglied, alle zehn Minuten und gleich nach dem Verknüpfen nachgeführt. Der Bot macht diese Rollen selbst, ohne Rechte, und fasst andere nie an; Ausschalten löscht sie. Der Bot braucht dort «Rollen verwalten».

- **Neuigkeiten und Roadmap**: Die Neuigkeiten in der Vereins-App öffnen die neuste Version (die ersten sechs Änderungen, «alle zeigen» für den Rest), frühere Versionen liegen zugeklappt darunter, fünf aufs Mal, dazu ein Roadmap-Tab. Ein Punkt im Menü markiert die Neuigkeiten, bis die neusten gelesen sind. manage hat dafür eine eigene Seite unter Hubra › Neuigkeiten & Roadmap (die Änderungen sind aus der Diagnose dorthin umgezogen). Die Roadmap kommt aus `app/backend/ROADMAP.yaml` (jetzt / als Nächstes / später / erledigt, deutsch und englisch) über das öffentliche `GET /api/v1/version/roadmap`. Die Änderungen gibt es jetzt auch auf Deutsch (`CHANGELOG.de.md`, `GET /api/v1/version/changelog?lang=de`).
- **Wartungsmodus**: manage › Warnungen › Übersicht oder `flask maintenance on|off|status [--minutes N] [--message TEXT]`. Die Vereins-Apps zeigen eine Wartungsseite (die Vereins-API antwortet mit 503 `MAINTENANCE`), manage, Anmeldung und Konto funktionieren weiter, Warnungen pausieren, und der Modus endet zur eingestellten Zeit von selbst. `GET /api/v1/maintenance` ist öffentlich.
- **Warnregeln** (manage › Warnungen › Regeln): ein Hauptschalter für alle Warnmails und Discord-Posts (`alerts.enabled`) und pro Warnart Mail und Discord ein oder aus (`alerts.mail_off`, `alerts.discord_off`). `GET/PUT /manager/platform/alerts/switches`, `GET/PUT /manager/platform/maintenance`.
- **Plattform-Aktionen mit Passkey bestätigen**: Der Dialog «Passwort bestätigen» in manage (Plugins installieren, aktualisieren und Quellen, Signaturschlüssel, Backup wiederherstellen/löschen, Schlüsselwechsel, einen Verein als Mitglied öffnen) bietet Konten mit Passkey «Mit Passkey bestätigen» an. Das öffnet SSO `/confirm` in einem kleinen Fenster, weil Passkeys an die SSO-Adresse gebunden sind. Neu sind `GET /account/step-up`, `POST /account/step-up/passkey/options` und `POST /account/step-up/passkey`; die Challenge gilt nur für dieses Konto und diese Anmeldung und taugt nicht zum Anmelden. Gleiches Zehn-Minuten-Fenster wie beim Passwort, das als Ausweichweg bleibt. Konten nur mit Passkey bestätigen weiterhin mit Passwort und einem Wiederherstellungscode.
- **Status des Discord-Bots** (manage › Diagnose › Discord): Einstellungen, die Anmeldung des Bots (live, 5 Minuten zwischengespeichert, «Jetzt prüfen»), die Server, auf denen er ist, die Interactions Endpoint URL im Vergleich zur erwarteten, der Protokollkanal der Plattform mit letztem Post und Fehler, das Plugin, verknüpfte Konten, jeder Vereinsserver mit seinem letzten Fehler sowie die Redirect-URIs und die Interactions-URL fürs Developer Portal. Ein falsches Token, ein unerreichbarer Protokollkanal oder fehlschlagende Posts erscheinen unter manage › Warnungen. docs/discord.md erklärt die Einrichtung Schritt für Schritt mit Berechtigungen und Redirects.
- **Mitglieder wählen ihre Benachrichtigungen**: Konto › Mitgliedschaft › Benachrichtigungen listet die Themen (neue Beiträge, Anlässe, Umfragen; Erinnerungen; meine Anmeldungen; Stimmen in meinen Umfragen; Aufgaben für mich) mit Glocke, Browser-Push und bei Erinnerungen Mail. Sicherheitshinweise kommen immer. Migration `d6f2b8e4a1c7` ergänzt `members.notify_prefs`; `GET/PUT /members/me/notifications`.
- **Warn-Einstellungen**: manage › Plattform-Einstellungen › Warnungen legt die Pause zwischen Warnmails fest (`alerts.cooldown_minutes`, 60), wie lange das Ereignisprotokoll bleibt (`alerts.retention_days`, 30) und die manage-Adresse für den Knopf in Warnmails (`alerts.manage_url`, sonst `MANAGE_BASE_URL`). Warnmails gehen jetzt nur an Plattform-Admins (Superadmins und Rollen mit `platform.settings`), nicht mehr an den Support.
- **Plattform-Protokoll auf Discord**: Der Hubra-Bot postet Plattform-Ereignisse (Vereine, Vereinsanfragen, Rollen und Stellvertretung, Plugins, Backups, Plattform-Einstellungen, Systemwarnungen) in einen Kanal auf dem eigenen Discord-Server der Plattform. Plattform-Einstellungen `discord.log_channel_id` und `discord.log_events`, ein Testknopf und ein Einladungslink in manage › Plattform-Einstellungen › Discord. Eingereichte, angenommene und abgelehnte Vereinsanfragen stehen jetzt im Audit-Log der Plattform. Siehe docs/discord.md, «Platform log».
- **Warnungsseite der Plattform** (manage › Plattform › Warnungen): offene Probleme, neuste Warnungen, Anzahl pro Bereich in 24 Stunden, das Ereignisprotokoll (aus der Diagnose hierher verschoben) und die Warnmail-Auswahl jeder Admin-Person. Neue Warnquellen: Ausfälle und Erholung von Datenbank, Redis und IMAP (aus der 20-Sekunden-Prüfung, nach einer Minute Ausfall), fehlgeschlagene geplante Backups, Plugin-Updates (standardmässig aus). Warnmails nutzen das Hubra-Mail-Layout (Stufe, Detailbox, Zeit und Instanz, ein Knopf zur Warnungsseite, wenn `MANAGE_BASE_URL` gesetzt ist) in der Sprache der Admin-Person. Die Merge-Migration `a6e2c8f4b1d7` vereint die zwei Köpfe aus #97 und #98.
- **Überwachung des Mailversands**: manage › Diagnose hat einen Tab Mail-Versand (Haupt- und Ersatz-Relay alle 5 Minuten per Anmeldung geprüft, «Jetzt prüfen», gesendet/Ersatz/fehlgeschlagen der letzten 24 Stunden, «Wieder das Haupt-Relay nutzen») und einen Tab Ereignisprotokoll (jede gesendete oder fehlgeschlagene Mail, Relay-Ausfälle, Systemwarnungen; 30 Tage). Plattform-Mitarbeitende erhalten Warnmails, wenn ein Relay ausfällt oder zurückkommt, das Ersatz-Relay übernimmt, eine Mail nicht zugestellt werden kann oder eine Systemwarnung auftritt, und wählen selbst, welche. Migration `b5d9e3f7a1c6` ergänzt `platform_events` und `users.platform_alerts`.
- **Schlüsselwechsel für gespeicherte Geheimnisse**: `FERNET_OLD_KEYS` hält alte Schlüssel lesbar, `flask crypto rotate` verschlüsselt jedes gespeicherte Geheimnis in jedem Vereinsschema neu, `flask crypto check` bestätigt, dass nichts mehr auf einem alten Schlüssel liegt. Siehe docs/operator-guide.md, «Change the encryption key».
- **Backups mit öffentlichem Schlüssel**: Mit `BACKUP_PUBLIC_KEY` (ein age-Schlüssel aus `flask backups keygen`) sind Backups so verschlüsselt, dass der Server sie schreiben, aber nicht lesen kann; Wiederherstellen und vollständiges Prüfen fragen nach dem privaten Schlüssel, der einmal verwendet und nie gespeichert wird. Ein Verein kann einen eigenen Schlüssel haben (`flask backups club-key`) und seine Backups selbst öffnen. Prüfen ohne Schlüssel kontrolliert die Prüfsumme der Datei. `.dump.gpg`-Backups öffnen weiterhin mit `BACKUP_ENCRYPTION_KEY`. Migration `d1a7c3e9b5f2` ergänzt `tenants.backup_public_key`; das Backend-Image enthält jetzt `age`.
- **Eigene Schlüssel pro Verein**: Jeder Verein (und die Plattform) hat einen eigenen zufälligen Datenschlüssel (`data_keys`, Migration `e3b9d5f1a7c4`), geschützt durch `FERNET_KEY`. Werte sind AES-256-GCM und an ihren Verein und ihre Spalte gebunden, ein Wert öffnet sich also nie in einem anderen Verein. Ein Wechsel des Hauptschlüssels verschlüsselt nur eine Zeile pro Verein neu. Neue Vereinsschlüssel über manage › Plattform-Einstellungen › Verschlüsselung oder `flask crypto rotate --new-keys [--club <slug>]`; wer einen Verein endgültig löscht, löscht auch seine Schlüssel. **Nach dem Update dort einmal «Neu verschlüsseln» drücken (oder `flask crypto rotate` ausführen).**
- **Öffentlicher Backup-Schlüssel als Plattform-Einstellung** (`backup.public_key`, Standard `BACKUP_PUBLIC_KEY`) und der Backup-Schlüssel jedes Vereins im Tab Verschlüsselung.

## [0.6.0] - 2026-07-13

### Added

- **Zählung der API-Aufrufe**: Redis-Zähler pro Verein (`api:calls:{tenant_id}:{YYYY-MM}`) erfassen die monatliche API-Nutzung, 45 Tage gültig. OPTIONS/HEAD und Health-Endpunkte zählen nicht.
- **Fehlerquote der API**: Globale Redis-Zähler (`api:errors:count`, `api:errors:total`) überwachen die Fehlerquote über alle Anfragen.
- **Speicherverbrauch**: Fasst die Grösse des PostgreSQL-Schemas und das WildDuck-Mailkontingent pro Verein zusammen.
- **Warnungen per Discord-Webhook**: Hilfsfunktionen `send_alert()`, `alert_error()`, `alert_warning()`, `alert_resolved()` mit `urllib.request` (keine neuen Abhängigkeiten). Einstellbar über `DISCORD_WEBHOOK_URL`.
- **Warnung bei fehlgeschlagenen Celery-Aufgaben**: Der Signal-Handler `@task_failure` schickt Discord-Warnungen, höchstens eine pro Stunde und Aufgabe.
- **Celery-Aufgabe für die Fehlerquote**: `check_api_error_rate_task` läuft stündlich und warnt, wenn die Fehlerquote die einstellbare Schwelle überschreitet.
- **Prüfung der Infrastruktur**: `check_disk_space()`, `check_redis_health()`, `check_postgres_health()` mit Discord-Warnungen und Entwarnungen. Läuft stündlich über Celery Beat.
- **Nutzungszahlen der Vereine sind echt**: `get_usage_stats()` liefert echte API-Aufrufe und Speicherbytes statt fester Nullen.

### Changed

- Beat-Zeitplan ergänzt: `infra-checks-hourly` (Minute 30) und `api-error-rate-hourly` (Minute 15).
- `tasks/__init__.py` lädt jetzt die Aufgabenmodule `monitoring` und `infra_checks`.

## [0.5.0] - 2026-07-12

### Changed

- **Rollen und Berechtigungen gelten pro Verein**: `roles`, `permissions` und `role_permissions` liegen nicht mehr nur global (im public-Schema), sondern in `TABLES_TO_CLONE`, sodass jeder Verein eigene Rollen und Berechtigungen hat. `_seed_tenant()` legt für jeden neuen Verein alle Rollen an (Admin, Manager, Members, Finances, Inventory, Member) mit der richtigen Berechtigungsmatrix.

### Removed

- **Altes SystemUser-Modell**: `vollbuild/models/system_user.py` und die Tabelle `system_users` gelöscht, abgelöst durch das Modell `User`.
- **Rollen im public-Schema**: `flask seed` legt keine Rollen und Berechtigungen im public-Schema mehr an. Rollen entstehen nur noch pro Verein beim Einrichten.

### Fixed

- **Fehlende Modell-Exporte**: `EventRegistration`, `GroupMembership` und `member_roles` in `models/__init__.py` ergänzt.

## [0.4.2] - 2026-07-12

### Fixed

- **Vereinsschema anlegen**: 5 Verwechslungen von Ein- und Mehrzahl in `TABLES_TO_CLONE` behoben (`settings`→`setting`, `feature_flags`→`feature_flag`, `translations`→`translation`, `backup_records`→`backup_record`, `invoice_reminder_histories`→`invoice_reminder_history`). Deswegen schlug `create_tenant_schema()` mit `UndefinedTable` fehl, der Verein wurde zurückgerollt und liess sich nicht einrichten. Ein Regressionstest prüft `TABLES_TO_CLONE` jetzt gegen die SQLAlchemy-Modelle.

## [0.4.1] - 2026-07-10

### Fixed

- **Umfragen**: Kleine `<Button>`-Symbolknöpfe durch `<ActionIcon>` ersetzt (erinnern, bearbeiten, löschen). Der Ladezustand gilt jetzt pro Umfrage, der Ladekreis erscheint also nur bei der Umfrage, die gerade bearbeitet wird, nicht bei allen.
- **Systemprüfung**: Prüfungen für WildDuck API, ZoneMTA SMTP und Haraka SMTP entfernt, die alle nicht mehr im Stack sind. `check_smtp_submission` heisst jetzt `check_smtp` (prüft Infomaniak SMTP über `SMTP_HOST`/`SMTP_PORT`). `check_imap` prüft Infomaniak IMAP. Dienstnamen im Frontend, `docs/configuration.md` und `.env.example` ohne WildDuck/ZoneMTA/Haraka.
- **Tab-Titel im Frontend**: Ein gemeinsamer `PageHead` für OperationsTabScreen, FinanceTabScreen und MembersTabScreen; der doppelte `PageHead` in 20 Tab-Inhalten ist weg, weil die Tab-Gruppe den Titel schon nennt. Aktionsknöpfe sitzen in schlanken Aktionsleisten. Eyebrow-Zeilen bei Einstellungen, System, Dashboard und Mail entfernt.
- **Schutz vor doppelter Weiterleitung bei 401**: Das Flag `_authFailed` in `apiFetch` sorgt dafür, dass `onAuthFailure` pro Anmeldefehler nur einmal aufgerufen wird. Danach bleibt die Anfrage offen, so blitzen keine Fehlermeldungen auf, bevor die Weiterleitung zum SSO greift.

## [0.4.0] - 2026-07-09

### Fixed

- **Typsicherheit (mypy)**: Alle 192 mypy-Fehler in 23 Backend-Dateien behoben. `[tool.mypy]`-Konfiguration mit Ausnahmen für Flask-SQLAlchemy (`db.Model`, `ma.Schema`). Behoben wurden arg-type, union-attr, assignment, return-value, attr-defined, operator und call-overload in Anmeldung, Finanzen, Health, i18n, Mail, Mitgliedern, Einstellungen, Setup, System, Stufen, Preisen, Backup, mail_i18n, managed_mail, mail_provisioning, qr_bill und den Aufgabenmodulen.
- **Frontend-Build (CI)**: Ein toter `useEffect`-Block in `PostDetailScreen`, der nicht vorhandene State-Setter aufrief (`setPost`, `setComments`, `setLoading`), ist entfernt. Die TS2552-Fehler blockierten die Pre-Commit-Pipeline.

### Changed

- **CI-Pre-Commit-Job**: `npm ci` für die Frontend-Abhängigkeiten ergänzt, damit der Hook `frontend-build` in der CI laufen kann.

## [0.3.0] - 2026-07-09

### Fixed

- **Genauigkeit bei Beträgen**: Der `float()`-Umweg bei `Invoice.amount` ist weg; Decimal-Werte landen direkt in der Spalte `Numeric(12,2)`, also keine Rundungsfehler mehr beim Erstellen vieler Rechnungen.
- **Token in URLs**: Tokens für Passwort-Reset und E-Mail-Bestätigung stehen nicht mehr im Query-Teil der URL (`?token=`), sondern im Fragment (`#token=`). So landen sie nicht im Browserverlauf, in Server-Logs oder im Referer. Backend und Frontend angepasst.
- **Personendaten in Logs**: E-Mail-Adressen aus `Member.__repr__` und `Application.__repr__` entfernt; schützenswerte Personendaten landen nicht mehr in den Logs.
- **Geheimnisse in Logs**: `Setting.__repr__` maskiert Werte mit `sensitive=True`; API-Schlüssel, SMTP-Passwörter und Bankzugänge stehen nicht mehr in den Logs.
- **Veralteter Test**: `test_double_vote_conflict` heisst jetzt `test_vote_change_allowed`. `PollService.vote` erlaubt bewusst, die Stimme in offenen Umfragen zu ändern; der Test prüft jetzt die Antwort 200 und die verschobene Stimme.

### Added

- **Eigener Fernet-Schlüssel**: Neue Umgebungsvariable `FERNET_KEY` für die Verschlüsselung gespeicherter Daten. Ohne sie wird wie bisher aus `SECRET_KEY` abgeleitet. In `.env.example` mit Anleitung zum Erzeugen beschrieben.

### Changed

- **PostgreSQL-Port**: Die Portfreigabe `5432:5432` in `docker-compose.yml` ist weg; die Datenbank ist nur noch im internen Docker-Netz erreichbar.
- **ZoneMTA-Lieferkette**: Der git clone von `zone-mta-template` ist auf `v1.11.2` mit `--depth 1` festgelegt, für reproduzierbare und sichere Builds.
- **Abhängigkeit cryptography**: Mindestversion `>=42.0.4` (wegen CVE-2023-50782).
- **HSTS-Preload**: Flag `preload` im Header `Strict-Transport-Security`.
- **Trivy-Scan in der CI**: Schwelle von `CRITICAL` auf `CRITICAL,HIGH` angehoben.
- **Trivy-Installation in der CI**: Fest auf das Release-Archiv `v0.58.0` statt curl-pipe-sh vom Branch `main`.
- **Grenze für Übersetzungsimporte**: Höchstens 2 MiB pro Übersetzungsdatei, damit der Speicher nicht ausgeht.

## [0.2.0] - 2026-07-02

### Added

- Passwort zurücksetzen per Mail: Wer das Passwort vergessen hat, kann es zurücksetzen, mit Bestätigung per Mail und sicheren Tokens.
- Zwei-Faktor-Anmeldung (2FA): Einrichtung mit Authenticator-App und Ersatzcodes.
- Besseres Logging und Monitoring: Strukturierte Logs und Überwachung für mehr Einblick in die Anwendung.

### Removed

- Schwache Passwörter: Hubra verlangt jetzt stärkere Passwörter.

## [0.1.0] - 2026-07-02

### Added

- Erste Version mit Versionsnummer.

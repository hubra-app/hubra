// The API answers in English. When the page is not in English, the messages a
// person can actually run into are shown in German; anything else (mostly
// developer-facing field checks) keeps the API's own text.

const DE: Record<string, string> = {
  // Sign-in, sign-up and passwords
  "Invalid credentials": "E-Mail oder Passwort stimmt nicht.",
  "Account has been disabled by an administrator": "Dieses Konto wurde gesperrt.",
  "Account is temporarily locked due to too many failed login attempts. Try again later.":
    "Zu viele Fehlversuche. Das Konto ist kurz gesperrt; versuche es später nochmals.",
  "Account is temporarily locked. Cannot refresh token.":
    "Das Konto ist kurz gesperrt. Bitte melde dich später neu an.",
  "An account with this email already exists": "Mit dieser E-Mail-Adresse gibt es schon ein Konto.",
  "Email already in use": "Diese E-Mail-Adresse wird schon verwendet.",
  "Email already registered": "Diese E-Mail-Adresse ist schon registriert.",
  "Invalid email address": "Diese E-Mail-Adresse ist ungültig.",
  "Current password is incorrect": "Das aktuelle Passwort stimmt nicht.",
  "Password must be at least 8 characters": "Das Passwort braucht mindestens 8 Zeichen.",
  "Reset token is invalid or has expired": "Der Link zum Zurücksetzen ist ungültig oder abgelaufen.",
  "Verification link is invalid or has expired": "Der Bestätigungslink ist ungültig oder abgelaufen.",
  "Email address is already verified": "Diese E-Mail-Adresse ist schon bestätigt.",
  "System mail is not set up": "Der Mailversand ist noch nicht eingerichtet.",
  "name, email, and password are required": "Name, E-Mail und Passwort sind nötig.",
  "token and password are required": "Link und Passwort sind nötig.",
  "currentPassword and newPassword are required": "Aktuelles und neues Passwort sind nötig.",
  "email is required": "Die E-Mail-Adresse fehlt.",
  "password is required": "Das Passwort fehlt.",
  "Name cannot be empty": "Der Name darf nicht leer sein.",
  "First name cannot be empty": "Der Vorname darf nicht leer sein.",
  "Last name cannot be empty": "Der Nachname darf nicht leer sein.",
  "Profile note exceeds 5000 characters": "Die Notiz ist länger als 5000 Zeichen.",
  "Avatar exceeds maximum size": "Das Profilbild ist zu gross.",
  "Invalid SVG avatar data URI": "Das Profilbild ist ungültig.",
  "Invalid base64 SVG avatar": "Das Profilbild ist ungültig.",
  "Session not found": "Diese Sitzung gibt es nicht mehr.",
  "Session not found or already revoked": "Diese Sitzung ist schon beendet.",
  "Device not found": "Dieses Gerät gibt es nicht mehr.",
  "Device not found or no active sessions": "Auf diesem Gerät ist niemand mehr angemeldet.",
  "Private email must be verified before enabling forwarding":
    "Bestätige zuerst deine private E-Mail-Adresse, dann kannst du die Weiterleitung einschalten.",
  "Forwarding to a club domain address would create a mail loop":
    "Eine Weiterleitung an eine Vereinsadresse würde eine Schleife erzeugen.",

  // Clubs, joining and leaving
  "Club not found": "Diesen Verein gibt es nicht.",
  "Tenant not found": "Diesen Verein gibt es nicht.",
  "You are already a member of this club": "Du bist schon Mitglied in diesem Verein.",
  "User is already a member of this tenant": "Diese Person ist schon Mitglied.",
  "Your request to join this club is pending": "Deine Beitrittsanfrage wird noch geprüft.",
  "An application from this email is already pending":
    "Für diese E-Mail-Adresse wartet schon eine Anfrage.",
  "You are not a member of this tenant": "Du bist nicht Mitglied in diesem Verein.",
  "No member profile in this tenant": "Du hast in diesem Verein kein Mitgliedsprofil.",
  "Confirm your email address before opening a club":
    "Bestätige zuerst deine E-Mail-Adresse, dann kannst du den Verein öffnen.",
  "A tenant with this slug already exists": "Diese Adresse ist schon vergeben.",
  "A pending request with this slug already exists": "Für diese Adresse wartet schon eine Anfrage.",
  "slug must be between 3 and 64 characters": "Die Adresse braucht 3 bis 64 Zeichen.",
  "name and slug are required": "Name und Adresse sind nötig.",
  "Tenant request not found": "Diese Anfrage gibt es nicht mehr.",
  "Unknown membership tier": "Diese Mitgliedschaftsstufe gibt es nicht.",
  "No request to leave from this member": "Diese Person hat keinen Austritt beantragt.",
  "This member is archived; restore them in the club first":
    "Dieses Mitglied ist archiviert. Stelle es zuerst im Verein wieder her.",
  "A club needs at least one owner": "Ein Verein braucht mindestens eine Inhaberin oder einen Inhaber.",
  "Cannot remove the last Owner of the tenant":
    "Die letzte Inhaberin oder der letzte Inhaber kann nicht entfernt werden.",
  "Only an owner can name another owner": "Nur Inhaber/innen können weitere Inhaber/innen bestimmen.",
  "Only an owner can remove an owner": "Nur Inhaber/innen können Inhaber/innen entfernen.",
  "Only the club's admins can do this": "Das dürfen nur die Admins des Vereins.",
  "Not an admin of this club": "Du bist nicht Admin in diesem Verein.",
  "Module settings are stored per club; pick a club first":
    "Moduleinstellungen gelten pro Verein. Wähle zuerst einen Verein.",

  // Members
  "Member not found": "Dieses Mitglied gibt es nicht.",
  "User not found": "Diese Person gibt es nicht.",
  "Username already taken": "Dieser Benutzername ist schon vergeben.",
  "You cannot archive your own account": "Du kannst dich nicht selbst archivieren.",
  "You cannot delete your own account": "Du kannst dein eigenes Konto nicht löschen.",
  "You cannot permanently delete your own account": "Du kannst dein eigenes Konto nicht löschen.",
  "You cannot disable your own account": "Du kannst dich nicht selbst sperren.",
  "Cannot disable an Owner role member": "Inhaber/innen können nicht gesperrt werden.",
  "Cannot disable an Admin role member": "Admins können nicht gesperrt werden.",
  "No file provided": "Es wurde keine Datei mitgeschickt.",
  "No file selected": "Es ist keine Datei ausgewählt.",
  "No file uploaded": "Es wurde keine Datei hochgeladen.",
  "File must be a CSV": "Die Datei muss eine CSV-Datei sein.",
  "CSV file is empty": "Die CSV-Datei ist leer.",
  "No valid entries found in file": "In der Datei sind keine gültigen Einträge.",
  "No active members found for the given filter": "Kein aktives Mitglied passt zu diesem Filter.",

  // Roles and settings
  "Role not found": "Diese Rolle gibt es nicht.",
  "A role with this name already exists": "Eine Rolle mit diesem Namen gibt es schon.",
  "User already has this role": "Diese Person hat die Rolle schon.",
  "Role assignment not found": "Diese Rollenzuweisung gibt es nicht.",
  "Cannot delete a default role": "Die Standardrolle kann nicht gelöscht werden.",
  "Cannot delete a system role": "Systemrollen können nicht gelöscht werden.",
  "Cannot delete an admin role": "Admin-Rollen können nicht gelöscht werden.",
  "Cannot delete a role that is assigned to members":
    "Diese Rolle ist Mitgliedern zugewiesen und kann nicht gelöscht werden.",
  "Cannot modify a system role": "Systemrollen können nicht geändert werden.",
  "Cannot modify a system role's permissions": "Die Rechte von Systemrollen können nicht geändert werden.",
  "Cannot modify an admin role": "Admin-Rollen können nicht geändert werden.",
  "Cannot modify an admin role's permissions": "Die Rechte von Admin-Rollen können nicht geändert werden.",
  "Only admins can change is_admin": "Nur Admins können das ändern.",
  "Setting not found": "Diese Einstellung gibt es nicht.",
  "Cannot modify a restricted setting": "Diese Einstellung ist gesperrt.",
  "Cannot delete a restricted setting": "Diese Einstellung ist gesperrt.",
  "Cannot delete a required setting": "Diese Einstellung ist nötig und kann nicht gelöscht werden.",
  "Insufficient permissions to write this setting": "Dafür fehlt dir die Berechtigung.",
  "Insufficient permissions to delete this setting": "Dafür fehlt dir die Berechtigung.",
  "Insufficient permissions to revert this setting": "Dafür fehlt dir die Berechtigung.",
  "Insufficient permissions": "Dafür fehlt dir die Berechtigung.",
  "Token invalid or expired": "Bitte melde dich neu an.",
  "Nothing to update": "Es gibt nichts zu speichern.",
  "No valid fields provided": "Es gibt nichts zu speichern.",

  // Groups, functions, posts, polls, events
  "Group not found": "Diese Gruppe gibt es nicht.",
  "Default groups cannot be deleted": "Standardgruppen können nicht gelöscht werden.",
  "Member is already in this group": "Diese Person ist schon in der Gruppe.",
  "Member is not linked to this group": "Diese Person ist nicht in der Gruppe.",
  "Ask a group lead to add you": "Bitte eine Gruppenleitung, dich hinzuzufügen.",
  "Function name cannot be empty": "Der Name der Funktion darf nicht leer sein.",
  "Member already holds this function": "Diese Person hat die Funktion schon.",
  "Holder not found for this function": "Diese Person hat die Funktion nicht.",
  "Cannot assign archived member to a function": "Archivierte Mitglieder können keine Funktion haben.",
  "You can only edit your own posts": "Du kannst nur eigene Beiträge bearbeiten.",
  "You can only delete your own posts": "Du kannst nur eigene Beiträge löschen.",
  "You can only delete your own comments": "Du kannst nur eigene Kommentare löschen.",
  "You already voted in this poll": "Du hast schon abgestimmt.",
  "This poll is closed": "Diese Umfrage ist geschlossen.",
  "This poll does not allow proxies": "Bei dieser Umfrage ist keine Stellvertretung möglich.",
  "You cannot be your own proxy": "Du kannst nicht deine eigene Stellvertretung sein.",
  "You already gave your vote to someone": "Du hast deine Stimme schon übertragen.",
  "You have not given a proxy": "Du hast keine Stimme übertragen.",
  "You do not hold this member's proxy": "Du hast die Stimme dieser Person nicht.",
  "You hold proxies and cannot give yours away":
    "Du vertrittst andere und kannst deine Stimme nicht weitergeben.",
  "You gave your vote to a proxy; take it back to vote yourself":
    "Du hast deine Stimme übertragen. Nimm sie zurück, um selbst abzustimmen.",
  "Already registered for this event": "Du bist schon angemeldet.",
  "No active registration found": "Es gibt keine Anmeldung.",
  "No registration found for this member": "Diese Person ist nicht angemeldet.",
  "Unknown calendar": "Diesen Kalender gibt es nicht.",
  "end_date is before date": "Das Enddatum liegt vor dem Beginn.",

  // Finance
  "Invoice not found": "Diese Rechnung gibt es nicht.",
  "This invoice is already paid": "Diese Rechnung ist schon bezahlt.",
  "Payment not found": "Diese Zahlung gibt es nicht.",
  "This payment is already booked": "Diese Zahlung ist schon verbucht.",
  "This payment has no suggestion": "Für diese Zahlung gibt es keinen Vorschlag.",
  "Only incoming payments can pay an invoice": "Nur Zahlungseingänge können eine Rechnung begleichen.",
  "Category not found": "Diese Kategorie gibt es nicht.",
  "Cannot delete a default category": "Standardkategorien können nicht gelöscht werden.",
  "Category is referenced by existing transactions":
    "Diese Kategorie wird in Buchungen verwendet und kann nicht gelöscht werden.",
  "Payment plan not found": "Diesen Zahlungsplan gibt es nicht.",
  "This plan is not available": "Dieser Zahlungsplan ist nicht verfügbar.",
  "This plan belongs to another tier": "Dieser Zahlungsplan gehört zu einer anderen Stufe.",
  "Upload a bank file": "Lade eine Bankdatei hoch.",
  "Approved budgets cannot be changed": "Genehmigte Budgets können nicht geändert werden.",
  "Approved budgets cannot be deleted": "Genehmigte Budgets können nicht gelöscht werden.",
  "Budget not found": "Dieses Budget gibt es nicht.",

  // Mail and platform
  "Mail feature is disabled": "Das Mail-Modul ist ausgeschaltet.",
  "Mail server integration is not configured": "Der Mailserver ist nicht eingerichtet.",
  "SMTP not configured": "Der Mailversand ist nicht eingerichtet.",
  "Set the relay host and the system sender address first":
    "Trage zuerst den Mail-Relay und die Absenderadresse des Systems ein.",
  "Check the server settings": "Prüfe die Servereinstellungen.",
  "Mailbox not found": "Dieses Postfach gibt es nicht.",
  "Message not found": "Diese Nachricht gibt es nicht.",
  "The message is no longer on the server": "Die Nachricht ist nicht mehr auf dem Server.",
  "Quota must be between 0.1 GB and 100 GB": "Der Speicher muss zwischen 0,1 GB und 100 GB liegen.",
  "Backup record not found": "Dieses Backup gibt es nicht.",
  "Only completed backups can be restored": "Nur fertige Backups können wiederhergestellt werden.",
  "Only completed backups can be verified": "Nur fertige Backups können geprüft werden.",
  "Only a backup of an existing club can be restored":
    "Nur das Backup eines bestehenden Vereins kann wiederhergestellt werden.",
  "Type the club's address to confirm the restore":
    "Tippe zur Bestätigung die Adresse des Vereins ein.",
  "Take the key back before deleting it": "Nimm den Schlüssel zuerst zurück, dann kannst du ihn löschen.",
  "Take the key back before retiring it":
    "Nimm den Schlüssel zuerst zurück, dann kannst du ihn ausmustern.",
  "Unknown language": "Diese Sprache gibt es nicht.",
  "An unexpected error occurred.": "Etwas ist schiefgelaufen. Bitte versuche es nochmals.",
};

// Messages that carry a name or number.
const DE_PATTERNS: [RegExp, (...m: string[]) => string][] = [
  [/^Password must be at least (\d+) characters$/, (n) => `Das Passwort braucht mindestens ${n} Zeichen.`],
  [/^No Hubra account for (.+); they need to sign up first$/, (e) =>
    `Für ${e} gibt es noch kein Hubra-Konto. Die Person muss sich zuerst registrieren.`],
  [/^No user found with email (.+)$/, (e) => `Für ${e} gibt es kein Konto.`],
  [/^A member with email (.+) already exists$/, (e) => `Ein Mitglied mit ${e} gibt es schon.`],
  [/^\S+ name '(.+)' (?:is already taken|already in use)$/, (n) => `«${n}» ist schon vergeben.`],
  [/^\S+ '(.+)' already exists$/, (n) => `«${n}» gibt es schon.`],
  [/^Cannot delete tier: (\d+) member\(s\) still reference it$/, (n) =>
    `Diese Stufe kann nicht gelöscht werden: ${n} Mitglieder haben sie noch.`],
  [/^The (.+) module is not enabled$/, (m) => `Das Modul ${m} ist ausgeschaltet.`],
  [/^(.+) has an overdue invoice$/, (n) => `${n} hat eine überfällige Rechnung.`],
  [/^(.+) has not been instructed on (.+)$/, (n, i) => `${n} hat noch keine Einführung für ${i}.`],
  [/^File too large \(max (\d+) KiB\)$/, (n) => `Die Datei ist zu gross (höchstens ${n} KiB).`],
  [/^Permission '.+' required$/, () => "Dafür fehlt dir die Berechtigung."],
  [/ not found(?: or archived)?$/, () => "Diesen Eintrag gibt es nicht (mehr)."],
];

// What a status says when the message itself says nothing useful.
const DE_STATUS: Record<number, string> = {
  401: "Bitte melde dich neu an.",
  403: "Dafür fehlt dir die Berechtigung.",
  413: "Die Datei ist zu gross.",
  429: "Zu viele Versuche. Bitte warte einen Moment und versuche es nochmals.",
  500: "Etwas ist schiefgelaufen. Bitte versuche es nochmals.",
  502: "Der Server ist gerade nicht erreichbar. Bitte versuche es gleich nochmals.",
  503: "Der Server ist gerade nicht erreichbar. Bitte versuche es gleich nochmals.",
  504: "Der Server antwortet nicht. Bitte versuche es gleich nochmals.",
};

const DE_CODE: Record<string, string> = {
  MODULE_DISABLED: "Dieses Modul ist für den Verein ausgeschaltet.",
  REMINDER_NOT_SENT: "Die Erinnerung wurde nicht verschickt: Die Empfängerin oder der Empfänger hat keine (bestätigte) E-Mail-Adresse.",
  REGISTRATION_CLOSED: "Die Anmeldung für diesen Anlass ist geschlossen.",
  CANCELLATION_CLOSED: "Die Abmeldefrist für diesen Anlass ist vorbei.",
  POLL_HAS_VOTES: "Es wurde schon abgestimmt; die Antworten können nicht mehr geändert werden.",
  USE_CHECKOUT: "Ob ein Gegenstand ausgeliehen ist, ändert sich nur mit Ausleihen und Zurückgeben.",
  ROLE_LOCKED: "Diese Rolle ist geschützt und kann so nicht geändert werden.",
  EMAIL_NOT_VERIFIED: "Bestätige zuerst deine E-Mail-Adresse.",
  MUST_CHANGE_PASSWORD: "Bitte ändere zuerst dein Passwort.",
  LAST_OWNER: "Die letzte Inhaberin oder der letzte Inhaber kann den Verein nicht verlassen.",
  WEAK_PASSWORD: "Dieses Passwort ist zu schwach.",
};

function pageLanguage(): string {
  return typeof document === "undefined" ? "de" : document.documentElement.lang || "de";
}

/** The message to show for a failed request, in the page's language. */
export function localizeError(status: number, code: string | undefined, message: string): string {
  if (pageLanguage().toLowerCase().startsWith("en")) {
    return status === 429 ? "Too many attempts. Please wait a moment and try again." : message;
  }
  if (DE[message]) return DE[message];
  for (const [pattern, build] of DE_PATTERNS) {
    const m = message.match(pattern);
    if (m) return build(...m.slice(1));
  }
  if (code && DE_CODE[code]) return DE_CODE[code];
  if (DE_STATUS[status] && (status >= 500 || status === 429 || /^HTTP \d+$/.test(message) || message === code))
    return DE_STATUS[status];
  return message;
}

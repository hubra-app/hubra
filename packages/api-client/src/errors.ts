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
  "The code is not correct": "Der Code stimmt nicht.",
  "The sign-in took too long. Start again.":
    "Die Anmeldung hat zu lange gedauert. Bitte beginne nochmals von vorn.",
  "Turn on two-factor sign-in in your account first":
    "Schalte zuerst in deinem Konto die Zwei-Faktor-Anmeldung ein.",
  "Two-factor sign-in is already on": "Die Zwei-Faktor-Anmeldung ist schon eingeschaltet.",
  "Two-factor sign-in is off": "Die Zwei-Faktor-Anmeldung ist ausgeschaltet.",
  "The passkey could not be checked": "Der Passkey konnte nicht geprüft werden.",
  "Passkeys are not set up here": "Passkeys sind auf diesem Server nicht eingerichtet.",
  "This account has the most passkeys allowed": "Mehr Passkeys sind für dieses Konto nicht möglich.",
  "Passkey not found": "Passkey nicht gefunden.",
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
  "A value is too large or has the wrong format": "Ein Wert ist zu gross oder hat das falsche Format.",
  "A value is too long or not valid for its field.": "Ein Wert ist zu lang oder passt nicht in sein Feld.",

  // Clubs, joining and invites
  "Open the club to continue": "Öffne den Verein, um weiterzumachen.",
  "This club is not active": "Dieser Verein ist nicht aktiv.",
  "Your membership in this club is switched off": "Deine Mitgliedschaft in diesem Verein ist ausgeschaltet.",
  "Change email and password on your account page; they need your current password":
    "E-Mail und Passwort änderst du auf deiner Kontoseite; dafür brauchst du dein aktuelles Passwort.",
  "This club takes new members by invite only": "Dieser Verein nimmt neue Mitglieder nur auf Einladung auf.",
  "This invite is invalid or has expired": "Diese Einladung ist ungültig oder abgelaufen.",
  "This invite was sent to another email address": "Diese Einladung ging an eine andere E-Mail-Adresse.",
  "name must be 1 to 255 characters": "Der Name braucht 1 bis 255 Zeichen.",
  "name is longer than 255 characters": "Der Name ist länger als 255 Zeichen.",
  "No club selected": "Kein Verein ausgewählt.",

  // Members, roles and groups
  "You cannot suspend yourself": "Du kannst dich nicht selbst pausieren.",
  "Cannot suspend an Owner or Admin role member":
    "Mitglieder mit der Rolle Inhaber/in oder Admin können nicht pausiert werden.",
  "This member left the club; invite them to bring them back":
    "Dieses Mitglied hat den Verein verlassen. Lade es ein, um es zurückzuholen.",
  "The applicant has no account yet": "Die Person hat noch kein Konto.",
  "Name, email and contact details belong to the member's own account; they change them themselves":
    "Name, E-Mail und Kontaktangaben gehören zum eigenen Konto des Mitglieds; nur es selbst kann sie ändern.",
  "Name is too long": "Der Name ist zu lang.",
  "avatarColor must be #rrggbb": "Die Farbe muss die Form #rrggbb haben.",
  "A group cannot be its own parent": "Eine Gruppe kann nicht in sich selbst liegen.",
  "System role flags cannot be set via API": "Systemrollen lassen sich so nicht ändern.",

  // Tiers, finance, events and polls
  "color must look like #1a2b3c": "Die Farbe muss die Form #1a2b3c haben.",
  "surcharge_pct must be 0 to 100": "Der Zuschlag muss zwischen 0 und 100 % liegen.",
  "due is before issued": "Die Fälligkeit liegt vor dem Rechnungsdatum.",
  "This sign-up is not waiting for approval": "Diese Anmeldung wartet nicht auf eine Bestätigung.",
  "This proxy is no longer valid": "Diese Vollmacht gilt nicht mehr.",

  // Settings, branding and mail
  "This setting has no stored default value": "Für diese Einstellung ist kein Standardwert hinterlegt.",
  "Mail prefix cannot be empty": "Der Mail-Präfix darf nicht leer sein.",
  "Mail prefix must be 1-64 chars, alphanumeric with hyphens/dots, starting and ending with alphanumeric":
    "Der Mail-Präfix braucht 1 bis 64 Zeichen: Buchstaben, Ziffern, Punkte und Bindestriche, am Anfang und Ende ein Buchstabe oder eine Ziffer.",
  "mail.domain setting is not configured": "Für den Verein ist noch keine Mail-Domain eingerichtet.",
  "Invalid 'to' email address": "Die Empfängeradresse ist ungültig.",
  "The test email could not be sent": "Die Test-E-Mail konnte nicht gesendet werden.",
  "Forwarding targets cannot be set on catch-all addresses":
    "Eine Sammeladresse (Catch-all) kann keine Weiterleitungen haben.",
  "Cannot delete address for group while the group exists.":
    "Die Adresse einer Gruppe lässt sich erst löschen, wenn die Gruppe gelöscht ist.",
  "Cannot delete address for function while the function exists.":
    "Die Adresse eines Amts lässt sich erst löschen, wenn das Amt gelöscht ist.",
  "Cannot delete address for member while the member exists.":
    "Die Adresse eines Mitglieds lässt sich erst löschen, wenn das Mitglied gelöscht ist.",
  "Group managed mail address could not be provisioned — check WildDuck connectivity":
    "Die Mail-Adresse der Gruppe konnte nicht angelegt werden. Ist der Mailserver erreichbar?",
  "This system address has no provisioned WildDuck mailbox":
    "Zu dieser Systemadresse gibt es noch kein Postfach auf dem Mailserver.",

  // Integrations (keys and bindings)
  "Binding already exists": "Diese Verknüpfung gibt es schon.",
  "Cannot delete a protected key": "Ein geschützter Schlüssel kann nicht gelöscht werden.",
  "Cannot delete key with existing bindings. Remove bindings first.":
    "Der Schlüssel hat noch Verknüpfungen. Entferne sie zuerst.",
  "Cannot change allow_multiple while bindings exist":
    "Solange es Verknüpfungen gibt, lässt sich «mehrere erlauben» nicht ändern.",
  "Cannot change the key of a protected binding": "Bei einer geschützten Verknüpfung lässt sich der Schlüssel nicht ändern.",
  "Cannot toggle a protected binding": "Eine geschützte Verknüpfung lässt sich nicht ein- oder ausschalten.",
  "Cannot delete a protected binding": "Eine geschützte Verknüpfung kann nicht gelöscht werden.",
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
  MEMBERSHIP_SUSPENDED: "Deine Mitgliedschaft in diesem Verein ist pausiert. Melde dich beim Vorstand.",
  BEYOND_OWN_PERMISSIONS: "Du kannst nur Rechte vergeben, die du selbst hast.",
  OWNER_ONLY: "Nur eine Inhaberin oder ein Inhaber kann die Inhaber-Rolle vergeben oder entziehen.",
  ADMIN_ONLY: "Nur Admins können eine Admin-Rolle vergeben oder entziehen.",
};

// Field checks arrive as the API's validation dict, e.g.
// {'color': ['Missing data for required field.']}. Turn them into a sentence.
const DE_FIELDS: Record<string, string> = {
  name: "Name",
  first_name: "Vorname",
  last_name: "Nachname",
  email: "E-Mail",
  public_email: "E-Mail",
  phone: "Telefon",
  color: "Farbe",
  date: "Datum",
  due: "Fälligkeit",
  amount: "Betrag",
  price_chf: "Preis",
  description: "Beschreibung",
  logo: "Logo",
  title: "Titel",
  body: "Text",
  category_id: "Kategorie",
  member_id: "Mitglied",
  tier_id: "Stufe",
  method: "Zahlungsart",
  type: "Typ",
  status: "Status",
  slug: "Adresse",
  password: "Passwort",
  start: "Beginn",
  end: "Ende",
  starts_at: "Beginn",
  ends_at: "Ende",
  location: "Ort",
  capacity: "Plätze",
};

function deProblem(problem: string): string {
  if (/^Missing data for required field/.test(problem)) return "fehlt";
  if (/^Field may not be (null|blank)/.test(problem)) return "darf nicht leer sein";
  if (/^Not a valid email/.test(problem)) return "ist keine gültige E-Mail-Adresse";
  if (/^Not a valid (number|integer|decimal)/.test(problem)) return "ist keine gültige Zahl";
  if (/^Not a valid (date|datetime)/.test(problem)) return "ist kein gültiges Datum";
  if (/^Unknown field/.test(problem)) return "ist hier nicht erlaubt";
  const tooLarge = problem.match(/too large \(max (\d+) ?MB\)/);
  if (tooLarge) return `ist zu gross (höchstens ${tooLarge[1]} MB)`;
  if (/^Must be one of/.test(problem)) return "hat einen ungültigen Wert";
  if (/^(Shorter|Longer) than|^Length must be/.test(problem)) return "ist zu kurz oder zu lang";
  const min = problem.match(/^Must be greater than (?:or equal to )?(\d+(?:\.\d+)?)/);
  if (min) return `muss grösser als ${min[1]} sein`;
  return "ist ungültig";
}

function parseFieldErrors(message: string): [string, string[]][] | null {
  if (!/^\{\s*'/.test(message)) return null;
  const out: [string, string[]][] = [];
  const entry = /'([\w.]+)':\s*\[([^\]]*)\]/g;
  for (const m of message.matchAll(entry)) {
    const problems = [...m[2].matchAll(/'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"/g)].map(
      (p) => p[1] ?? p[2],
    );
    out.push([m[1], problems]);
  }
  return out.length ? out : null;
}

function humanField(field: string): string {
  return field === "_schema" ? "" : field.replace(/_id$/, "").replace(/_/g, " ");
}

function fieldErrorsMessage(message: string, english: boolean): string | null {
  const fields = parseFieldErrors(message);
  if (!fields) return null;
  if (english) {
    const parts = fields.map(([f, p]) =>
      f === "_schema" ? p.join(" ") : `${humanField(f)} (${p.join(" ")})`,
    );
    return `Please check: ${parts.join(", ")}`;
  }
  const parts = fields.map(([f, p]) =>
    f === "_schema"
      ? "die Angaben passen nicht zusammen"
      : `${DE_FIELDS[f] ?? humanField(f)} ${deProblem(p[0] ?? "")}`,
  );
  return `Bitte prüfe die Eingaben: ${parts.join(", ")}.`;
}

function pageLanguage(): string {
  return typeof document === "undefined" ? "de" : document.documentElement.lang || "de";
}

/** The message to show for a failed request, in the page's language. */
export function localizeError(status: number, code: string | undefined, message: string): string {
  const english = pageLanguage().toLowerCase().startsWith("en");
  const fieldText = fieldErrorsMessage(message, english);
  if (fieldText) return fieldText;
  if (english) {
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

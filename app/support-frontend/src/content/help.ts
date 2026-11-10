/**
 * The help articles of the support site. Written for club admins and
 * members, German first, English second, in the Markdown subset of
 * components/Markdown.tsx. Menu names follow the club app (German labels,
 * the English ones in the English text). Keep them in step with the app:
 * docs/club-admin-guide.md is the longer version for admins.
 */

export type Category = 'start' | 'members' | 'finance' | 'events' | 'account' | 'modules'

export interface Article {
  slug: string
  category: Category
  title: { de: string; en: string }
  summary: { de: string; en: string }
  body: { de: string; en: string }
  /** Extra words people search for. */
  keywords?: string
}

export const CATEGORIES: Record<Category, { de: string; en: string }> = {
  start: { de: 'Erste Schritte', en: 'Getting started' },
  members: { de: 'Mitglieder', en: 'Members' },
  finance: { de: 'Finanzen', en: 'Finance' },
  events: { de: 'Anlässe und Trainings', en: 'Events and trainings' },
  account: { de: 'Konto und Sicherheit', en: 'Account and security' },
  modules: { de: 'Module und Plugins', en: 'Modules and plugins' },
}

export const ARTICLES: Article[] = [
  {
    slug: 'verein-starten',
    category: 'start',
    keywords: 'gründen neu anfangen start club erstellen',
    title: { de: 'Einen Verein auf Hubra starten', en: 'Start a club on Hubra' },
    summary: {
      de: 'Vom Antrag bis zum ersten eingeladenen Mitglied.',
      en: 'From the request to the first invited member.',
    },
    body: {
      de: `Ein Hubra-Konto gehört dir als Person und kann in mehreren Vereinen sein. Einen Verein startest du mit deinem Konto.

## Antrag stellen

1. Melde dich an oder erstelle ein Konto.
2. Öffne **Verein starten** und gib Name und Adresse des Vereins ein.
3. Das Hubra-Team prüft den Antrag. Du bekommst eine Mail, sobald der Verein bereit ist, und bist dann seine **Inhaberin** bzw. sein **Inhaber**.

## Die ersten Einstellungen

1. **Einstellungen › Verein:** Name, Beschreibung, Farben und Logo.
2. **Einstellungen › Module:** schalte aus, was ihr nicht braucht. Die Daten bleiben erhalten.
3. **Mitglieder › Stufen:** die Mitgliedschaften und was sie kosten.
4. **Berechtigungen:** prüfe die Rollen, bevor du Leute einlädst.
5. Lade die ersten Mitglieder ein (siehe [Mitglieder einladen](/hilfe/mitglieder-einladen)).

> Die Checkliste [Verein einrichten](/start) führt dich Schritt für Schritt durch und merkt sich, was du schon erledigt hast.`,
      en: `A Hubra account belongs to you as a person and can be in several clubs. You start a club with your account.

## Send the request

1. Sign in or create an account.
2. Open **Start a club** and enter the club's name and address.
3. The Hubra team checks the request. You get a mail once the club is ready, and you are then its **owner**.

## The first settings

1. **Settings › Club:** name, description, colours and logo.
2. **Settings › Modules:** switch off what you don't need. The data stays.
3. **Members › Tiers:** the memberships and what they cost.
4. **Permissions:** check the roles before you invite people.
5. Invite the first members (see [Invite members](/hilfe/mitglieder-einladen)).

> The [Set up a club](/start) checklist walks you through it step by step and remembers what you have done.`,
    },
  },
  {
    slug: 'mitglieder-einladen',
    category: 'members',
    keywords: 'einladung link import csv beitreten antrag invite',
    title: { de: 'Mitglieder einladen', en: 'Invite members' },
    summary: {
      de: 'Einladungslinks, Beitrittsanträge und CSV-Import.',
      en: 'Invite links, join requests and CSV import.',
    },
    body: {
      de: `Ein Verein legt nie selbst Konten an und setzt nie Passwörter. Neue Mitglieder kommen immer über eine Einladung, die sie selbst annehmen.

## Einzeln einladen

1. Öffne **Mitglieder** und wähle **Mitglied einladen**.
2. Gib die Mailadresse ein. Stufe, Gruppen und Rollen sind freiwillig.
3. Die Person bekommt einen persönlichen Link, der **14 Tage** gilt. Sie meldet sich an oder erstellt ein Konto mit dieser Adresse und nimmt an.

Offene Einladungen siehst du in der Mitgliederliste. Du kannst sie erneut senden oder zurückziehen.

## Viele auf einmal

Beim **CSV-Import** bekommt jede Adresse aus der Datei eine eigene Einladung. Niemand wird ohne Zustimmung Mitglied.

## Beitrittsanträge

Ist der Verein auffindbar, können Leute auf der Beitrittsseite um Aufnahme bitten. Die Anträge findest du unter **Mitglieder › Anträge**. **Annehmen** macht die Person zum Mitglied.

## Die Mail kommt nicht an

- Prüfe die Adresse auf Tippfehler.
- Bitte die Person, im Spam-Ordner nachzusehen.
- Sende die Einladung erneut. Hilft das nicht, [melde ein Problem](/melden).`,
      en: `A club never creates accounts and never sets passwords. New members always come through an invitation that they accept themselves.

## Invite one person

1. Open **Members** and choose **Invite member**.
2. Enter the mail address. Tier, groups and roles are optional.
3. The person gets a personal link that is valid for **14 days**. They sign in or create an account with that address and accept.

Open invitations show in the member list. You can send them again or withdraw them.

## Many at once

With the **CSV import**, every address in the file gets its own invitation. Nobody becomes a member without agreeing.

## Join requests

When the club can be found, people can ask to join on the join page. The requests are under **Members › Applications**. **Approve** makes the person a member.

## The mail does not arrive

- Check the address for typos.
- Ask the person to look in their spam folder.
- Send the invitation again. If that does not help, [report a problem](/melden).`,
    },
  },
  {
    slug: 'rollen-und-rechte',
    category: 'members',
    keywords: 'rollen berechtigungen admin vorstand funktion permissions',
    title: { de: 'Rollen, Rechte und Funktionen', en: 'Roles, permissions and functions' },
    summary: {
      de: 'Wer was sehen und ändern darf.',
      en: 'Who may see and change what.',
    },
    body: {
      de: `## Rollen

Unter **Berechtigungen** stehen die Rollen des Vereins. Jede Rolle gibt Rechte pro Bereich (Mitglieder, Finanzen, Anlässe, Einstellungen …): lesen, erstellen, ändern, löschen. Wer mehrere Rollen hat, bekommt alles, was eine davon erlaubt.

- **Inhaber** und **Admin** haben immer vollen Zugriff.
- Neue Mitglieder bekommen die Rolle, die als Standard markiert ist.
- **Vorlagen** legen einen typischen Satz Rollen in einem Schritt an.
- Eine Rolle kann auf eine **Gruppe** beschränkt sein: eine Trainerin verwaltet dann nur die Anlässe ihres Teams.

## Funktionen

**Mitglieder › Funktionen** (Präsidium, Kasse, Aktuariat …) halten fest, wer ein Amt hat. Eine Funktion kann eine Rolle mitbringen, damit die Kassierin automatisch die Finanzrechte bekommt.

> Gib Rechte sparsam: lieber eine Rolle mehr anlegen als allen Admin geben.`,
      en: `## Roles

**Permissions** lists the club's roles. Each role grants rights per area (members, finance, events, settings …): read, create, change, delete. Someone with several roles gets everything any of them allows.

- **Owner** and **Admin** always have full access.
- New members get the role marked as default.
- **Templates** set up a typical set of roles in one step.
- A role can be limited to one **group**: a coach then manages only their team's events.

## Functions

**Members › Functions** (president, treasurer, secretary …) record who holds an office. A function can bring a role with it, so the treasurer gets the finance rights automatically.

> Give rights sparingly: rather add one more role than make everyone an admin.`,
    },
  },
  {
    slug: 'verein-verlassen',
    category: 'members',
    keywords: 'austritt austreten kündigen leave',
    title: { de: 'Einen Verein verlassen', en: 'Leave a club' },
    summary: {
      de: 'Austreten, ohne das Konto zu verlieren.',
      en: 'Leave without losing your account.',
    },
    body: {
      de: `Du trittst in der Vereins-App aus: **Konto-Menü › Kontoeinstellungen › Mitgliedschaft › Verein verlassen**.

- Je nach Verein bist du sofort draussen, oder der Vorstand bestätigt den Austritt zuerst.
- Rechnungen und Einträge bleiben beim Verein, denn sie gehören zu seiner Buchhaltung.
- Dein Hubra-Konto und deine anderen Vereine bleiben, wie sie sind.

Willst du dein ganzes Konto löschen, verlasse zuerst alle Vereine und gehe dann zu [Meine Daten](/datenschutz).`,
      en: `You leave in the club app: **account menu › Account settings › Membership › Leave club**.

- Depending on the club you are out at once, or the board confirms first.
- Invoices and entries stay with the club, because they belong to its books.
- Your Hubra account and your other clubs stay as they are.

To delete your whole account, leave all clubs first and then go to [My data](/datenschutz).`,
    },
  },
  {
    slug: 'rechnungen-qr',
    category: 'finance',
    keywords: 'rechnung qr einzahlungsschein beitrag mahnung invoice twint bezahlen',
    title: { de: 'Rechnungen und QR-Einzahlungsscheine', en: 'Invoices and Swiss QR bills' },
    summary: {
      de: 'Beiträge in Rechnung stellen, Zahlungen verbuchen, mahnen.',
      en: 'Bill fees, book payments, send reminders.',
    },
    body: {
      de: `## Voraussetzungen

Unter **Finanzen › Einstellungen** (oder **Einstellungen › Bank & QR-Rechnung**) brauchst du die **IBAN** bzw. QR-IBAN und die Adresse des Vereins. Ohne sie lässt sich kein QR-Einzahlungsschein drucken.

## Beiträge automatisch

Jede **Stufe** hat einen Betrag und einen Zahlungsplan. Hubra erstellt die Rechnungen zur Fälligkeit selbst:

- **Fester Stichtag** (z. B. jedes Jahr am 1. Januar). Wer unter dem Jahr eintritt, kann einen anteiligen ersten Beitrag zahlen.
- **Eintrittsdatum:** jedes Mitglied zahlt ein Jahr nach seinem Eintritt.

## Einzelne Rechnung

**Finanzen › Rechnungen › Neue Rechnung**. Das Mitglied sieht sie in der Vereins-App und bekommt sie als PDF mit QR-Einzahlungsschein per Mail.

## Zahlungen und Zahlungserinnerungen

- Verbuche eine Zahlung von Hand oder mit dem Modul **Bankimport** (camt.053, MT940, CSV).
- Offene Rechnungen nach der Frist bekommen auf Wunsch eine Erinnerung.`,
      en: `## Before you start

Under **Finance › Settings** (or **Settings › Bank & QR invoice**) you need the club's **IBAN** or QR-IBAN and address. Without them no QR bill can be printed.

## Fees automatically

Each **tier** has an amount and a payment plan. Hubra creates the invoices itself when they are due:

- **Fixed date** (for example every 1 January). Someone who joins during the year can pay a prorated first fee.
- **Join date:** each member pays one year after they joined.

## A single invoice

**Finance › Invoices › New invoice**. The member sees it in the club app and gets it as a PDF with a QR bill by mail.

## Payments and reminders

- Book a payment by hand or with the **Bank import** module (camt.053, MT940, CSV).
- Overdue invoices can get a reminder.`,
    },
  },
  {
    slug: 'trainings-anwesenheit',
    category: 'events',
    keywords: 'training serie wöchentlich anwesenheit präsenz j+s attendance',
    title: { de: 'Trainings und Anwesenheit', en: 'Trainings and attendance' },
    summary: {
      de: 'Wiederkehrende Anlässe anlegen und Präsenz erfassen.',
      en: 'Create recurring events and take attendance.',
    },
    body: {
      de: `## Eine Trainingsserie anlegen

1. **Anlässe › Neuer Anlass**, dann **Wöchentlich wiederholen** einschalten.
2. Wähle die Wochentage, den Rhythmus (jede Woche, alle zwei Wochen …) und das Enddatum.
3. Gib die **Gruppe** an: ihre Mitglieder werden bei jedem Datum erwartet.

Jedes Datum ist ein eigener Anlass. Fällt ein Training aus, lösche nur dieses Datum. Änderst du Zeit oder Ort, wähle, ob es nur für dieses oder auch für alle folgenden Daten gilt.

## Anwesenheit erfassen

Öffne das Datum und wähle **Anwesenheit erfassen**. Markiere jede Person als **anwesend**, **entschuldigt** oder **abwesend**. Auf dem Handy geht das mit einem Tipp pro Person.

## Auswertung

Die Übersicht zeigt die Präsenz pro Person und Datum. Der CSV-Export eignet sich als Grundlage für J+S-Meldungen.`,
      en: `## Create a training series

1. **Events › New event**, then switch on **Repeat weekly**.
2. Pick the weekdays, the rhythm (every week, every two weeks …) and the end date.
3. Choose the **group**: its members are expected at every date.

Each date is an event of its own. If a training is cancelled, delete just that date. When you change the time or place, choose whether it applies to this date only or to all following dates.

## Take attendance

Open the date and choose **Take attendance**. Mark each person **present**, **excused** or **absent**. On a phone that is one tap per person.

## Overview

The overview shows attendance per person and date. The CSV export works as a basis for J+S reports.`,
    },
  },
  {
    slug: 'anmelden-zwei-faktor',
    category: 'account',
    keywords: 'login passwort vergessen 2fa totp passkey sicherheit anmelden',
    title: { de: 'Anmelden, Passwort und Zwei-Faktor', en: 'Sign-in, password and two-factor' },
    summary: {
      de: 'Ein Konto für alle Vereine, sicher mit Passkey oder Code.',
      en: 'One account for every club, safe with a passkey or code.',
    },
    body: {
      de: `Du meldest dich einmal an und bist in allen deinen Vereinen angemeldet. Name, Mailadresse und Passwort änderst nur du selbst, unter **Mein Konto**.

## Passwort vergessen

Wähle auf der Anmeldeseite **Passwort vergessen** und folge dem Link in der Mail. Der Link gilt eine Stunde.

## Zwei-Faktor einrichten

Unter **Mein Konto › Zwei-Faktor**:

- **Authenticator-App** (z. B. Aegis, 1Password, Google Authenticator): scanne den QR-Code und gib den Code ein.
- **Passkey:** melde dich mit Fingerabdruck, Gesicht oder Gerätesperre an, ganz ohne Passwort.
- Speichere die **Wiederherstellungscodes** an einem sicheren Ort.

Manche Vereine verlangen Zwei-Faktor für Vorstandsmitglieder oder für alle.

## Neues Gerät

Meldest du dich auf einem unbekannten Gerät an, bekommst du eine Mail. Warst das nicht du, ändere sofort dein Passwort und beende unter **Mein Konto › Sitzungen** alle anderen Sitzungen.`,
      en: `You sign in once and are signed in to all your clubs. Only you change your name, mail address and password, under **My account**.

## Forgot your password

Choose **Forgot password** on the sign-in page and follow the link in the mail. The link is valid for one hour.

## Set up two-factor

Under **My account › Two-factor**:

- **Authenticator app** (for example Aegis, 1Password, Google Authenticator): scan the QR code and enter the code.
- **Passkey:** sign in with your fingerprint, face or device lock, without a password at all.
- Keep the **recovery codes** somewhere safe.

Some clubs require two-factor for board members or for everyone.

## New device

When you sign in on a device Hubra does not know, you get a mail. If that was not you, change your password right away and end all other sessions under **My account › Sessions**.`,
    },
  },
  {
    slug: 'benachrichtigungen',
    category: 'account',
    keywords: 'mail push erinnerung benachrichtigung discord notifications',
    title: { de: 'Benachrichtigungen und Erinnerungen', en: 'Notifications and reminders' },
    summary: {
      de: 'Mail, Push im Browser und Discord.',
      en: 'Mail, browser push and Discord.',
    },
    body: {
      de: `Hubra erinnert an Anlässe, Umfragen und offene Rechnungen. Wie, entscheidest du selbst unter **Mein Konto › Benachrichtigungen**:

- **Mail** an deine Kontoadresse.
- **Push** im Browser oder auf dem Handy. Erlaube die Mitteilungen, wenn der Browser fragt.
- **Discord**, wenn dein Verein den Hubra-Bot nutzt und du dein Discord-Konto verknüpft hast.

Kommt nichts an, schau auf der [Statusseite](/status), ob Mails gerade verzögert sind.`,
      en: `Hubra reminds you of events, polls and open invoices. You decide how under **My account › Notifications**:

- **Mail** to your account address.
- **Push** in the browser or on your phone. Allow notifications when the browser asks.
- **Discord**, when your club uses the Hubra bot and you linked your Discord account.

If nothing arrives, check the [status page](/status) to see whether mail is delayed right now.`,
    },
  },
  {
    slug: 'module',
    category: 'modules',
    keywords: 'module plugin einschalten ausschalten inventar codes budget discord',
    title: { de: 'Module ein- und ausschalten', en: 'Switch modules on and off' },
    summary: {
      de: 'Was der Verein nutzt, und was mit den Daten passiert.',
      en: 'What the club uses, and what happens to the data.',
    },
    body: {
      de: `Unter **Einstellungen › Module** steht alles, was dein Verein nutzen kann: Anlässe, Finanzen, Gruppen, Umfragen, Beiträge und mehr.

- **Ausschalten** blendet das Modul und seine Menüpunkte für alle aus. Die Daten bleiben und sind beim Wiedereinschalten zurück.
- Manche Module bauen auf anderen auf: Hubra lässt ein Modul nicht ausschalten, das ein anderes eingeschaltetes braucht.
- **Weitere Module** wie Inventar, Codes, Budgets, Bankimport oder Discord erscheinen in derselben Liste, sobald die Plattform sie anbietet.

Fehlt dir ein Modul? Wähle am Ende der Liste **Fehlt ein Modul?** oder [schlage eine Idee vor](/idee). Steht sie auf der [Roadmap](/roadmap), kann jeder Verein dafür stimmen.`,
      en: `**Settings › Modules** lists everything your club can use: events, finance, groups, polls, posts and more.

- **Switching off** hides the module and its menu entries for everyone. The data stays and is back when you switch it on again.
- Some modules build on others: Hubra won't switch off a module that another enabled one needs.
- **More modules** such as inventory, codes, budgets, bank import or Discord show up in the same list once the platform offers them.

Missing a module? Choose **Missing a module?** at the end of the list or [suggest an idea](/idee). Once it is on the [roadmap](/roadmap), every club can vote for it.`,
    },
  },
  {
    slug: 'backups-schluessel',
    category: 'modules',
    keywords: 'backup sicherung wiederherstellen schlüssel verschlüsselung age',
    title: { de: 'Backups und eigener Schlüssel', en: 'Backups and your own key' },
    summary: {
      de: 'Was gesichert wird und wie ihr eure Backups selbst öffnen könnt.',
      en: 'What is backed up and how you can open your backups yourself.',
    },
    body: {
      de: `Hubra sichert jeden Verein täglich, wöchentlich und monatlich, verschlüsselt und auf Servern in Europa.

## Etwas wurde gelöscht

[Melde dich beim Hubra-Team](/kontakt) mit dem Zeitpunkt, bis zu dem alles stimmte. Wir stellen euren Verein aus einem Backup davor wieder her. Andere Vereine sind nicht betroffen, aber alles in eurem Verein seit diesem Backup wird ersetzt.

## Euer eigener Schlüssel

Unter **Einstellungen › Verschlüsselung** erstellt eine Anleitung ein Schlüsselpaar in deinem Browser. Jedes neue Backup wird dann auch für euren Schlüssel verschlüsselt, und ihr könnt es mit dem freien Werkzeug [age](https://age-encryption.org) selbst öffnen.

> Mit **Nur unser Schlüssel** kann niemand ausser euch die Backups öffnen, auch das Hubra-Team nicht. Dann können wir euren Verein aber auch nicht wiederherstellen, und ein verlorener Schlüssel heisst verlorene Backups.`,
      en: `Hubra backs up every club daily, weekly and monthly, encrypted and on servers in Europe.

## Something was deleted

[Contact the Hubra team](/kontakt) with the time up to which everything was right. We restore your club from a backup from before then. Other clubs are not affected, but everything in your club since that backup is replaced.

## Your own key

Under **Settings › Encryption** a guide creates a key pair in your browser. Every new backup is then also encrypted to your key, and you can open it yourselves with the free tool [age](https://age-encryption.org).

> With **Only our key**, nobody but you can open the backups, the Hubra team included. Then we can't restore your club either, and a lost key means lost backups.`,
    },
  },
]

export function articleBySlug(slug: string): Article | undefined {
  return ARTICLES.find((a) => a.slug === slug)
}

/** Articles whose title, summary, keywords or text hold every word of `q`. */
export function searchArticles(q: string, lang: 'de' | 'en'): Article[] {
  const words = q
    .toLowerCase()
    .split(/\s+/)
    .filter((w) => w.length > 1)
  if (!words.length) return []
  const scored = ARTICLES.map((a) => {
    const head = `${a.title[lang]} ${a.title.de} ${a.summary[lang]} ${a.keywords ?? ''}`.toLowerCase()
    const body = a.body[lang].toLowerCase()
    let score = 0
    for (const w of words) {
      if (head.includes(w)) score += 3
      else if (body.includes(w)) score += 1
      else return { a, score: 0 }
    }
    return { a, score }
  })
  return scored
    .filter((s) => s.score > 0)
    .sort((x, y) => y.score - x.score)
    .map((s) => s.a)
}

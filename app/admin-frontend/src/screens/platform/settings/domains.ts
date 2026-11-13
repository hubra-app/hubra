import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'domains',
  keys: [
    'domains.serving',
    'domains.cname_target',
    'domains.cluster_issuer',
    'domains.ingress_class',
    'domains.service',
  ],
  builtIn: [
    'domains.serving',
    'domains.cluster_issuer',
    'domains.ingress_class',
    'domains.service',
  ],
  title: () => tr('Vereinsdomains', 'Club domains'),
  desc: () =>
    tr(
      'Vereine bestätigen ihre Domain mit einem TXT-Eintrag und lassen sie per CNAME auf die Plattform zeigen. Ist das Ausliefern eingeschaltet, legt der Plattform-Worker alle zwei Minuten pro bestätigter Domain ein Zertifikat (cert-manager) und, sobald es ausgestellt ist, ein Ingress an; Besucher werden zum Verein in der App weitergeleitet. Nur auf k3s, mit dem Service-Account aus deploy/app/domains-rbac.yaml. Fehlt nach einem Tag das Zertifikat, kommt eine Systemwarnung.',
      'Clubs verify their domain with a TXT record and point it at the platform with a CNAME. With serving on, the platform worker creates a certificate (cert-manager) for each verified domain every two minutes and, once it is issued, an Ingress; visitors are sent on to the club in the app. k3s only, with the service account from deploy/app/domains-rbac.yaml. A domain without a certificate after a day raises a system alert.',
    ),
  de: {
    'domains.serving': [
      'Vereinsdomains ausliefern',
      'on: jede bestätigte Vereinsdomain bekommt ein Zertifikat und ein eigenes Ingress (k3s mit cert-manager), Besucher werden zum Verein weitergeleitet. off: die Ingresses werden entfernt (Notschalter)',
    ],
    'domains.cname_target': [
      'Ziel für Vereinsdomains',
      'Der Host, auf den Vereine ihre Domain zeigen lassen (CNAME), z. B. clubs.hubra.club; wird den Vereinen angezeigt',
    ],
    'domains.cluster_issuer': ['Zertifikats-Aussteller', 'Der ClusterIssuer von cert-manager für Vereinsdomains'],
    'domains.ingress_class': ['Ingress-Klasse', 'Die Ingress-Klasse der Vereinsdomains'],
    'domains.service': [
      'Service für Vereinsdomains',
      "Der Service (Port 'http'), an den Vereinsdomains gehen; er leitet Besucher zum Verein weiter",
    ],
  },
})

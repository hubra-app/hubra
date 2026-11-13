import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'files',
  keys: [
    'files.s3.endpoint',
    'files.s3.bucket',
    'files.s3.region',
    'files.s3.access_key',
    'files.s3.secret_key',
    'files.max_mb',
  ],
  title: () => tr('Dateispeicher', 'File storage'),
  desc: () =>
    tr(
      'Hierhin gehen die Dateien der Vereine (z. B. die Dokumentenablage), jede verschlüsselt mit dem Schlüssel ihres Vereins. Ohne Bucket liegen sie im Ordner FILES_DIR auf dem Server; das reicht nur für einen einzelnen Server.',
      "Clubs' files go here (e.g. the document library), each encrypted with its club's key. Without a bucket they stay in the folder FILES_DIR on the server, which only suits a single server.",
    ),
  de: {
    'files.s3.endpoint': [
      'S3-Endpunkt für Dateien',
      'S3-kompatible Adresse für Vereinsdateien, z. B. https://eu2.contabostorage.com. Leer: Dateien bleiben auf dem Server',
    ],
    'files.s3.bucket': [
      'S3-Bucket für Dateien',
      'Bucket für Vereinsdateien (nicht der Backup-Bucket). Jede Datei wird mit dem Schlüssel ihres Vereins verschlüsselt, bevor sie den Server verlässt',
    ],
    'files.s3.region': ['S3-Region für Dateien', "Bei Contabo meist 'default'"],
    'files.s3.access_key': ['S3-Access-Key für Dateien', 'Wird verschlüsselt gespeichert'],
    'files.s3.secret_key': ['S3-Secret-Key für Dateien', 'Wird verschlüsselt gespeichert'],
    'files.max_mb': [
      'Grösste Datei (Standard)',
      'Grösste Datei, die ein Verein hochladen kann, in MB, wenn sein Tarif keine eigene Grenze hat',
    ],
  },
})

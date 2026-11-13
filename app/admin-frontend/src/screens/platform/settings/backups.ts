import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'backups',
  keys: [
    'backup.public_key',
    'backup.s3.endpoint',
    'backup.s3.bucket',
    'backup.s3.region',
    'backup.s3.access_key',
    'backup.s3.secret_key',
  ],
  title: () => tr('Backup-Speicher', 'Backup storage'),
  desc: () =>
    tr(
      'Hierhin gehen das globale Backup und die Backups jedes Vereins, verschlüsselt mit dem öffentlichen Backup-Schlüssel. Er ist nicht geheim; den privaten Schlüssel braucht es nur zum Öffnen, und er gehört nicht auf den Server.',
      'The global backup and every club backup go here, encrypted to the backup public key. It is not secret; the private key is only needed to open a backup and does not belong on the server.',
    ),
  de: {
    'backup.public_key': [
      'Öffentlicher Backup-Schlüssel',
      'age-Schlüssel (age1…), mit dem jedes Backup verschlüsselt wird (flask backups keygen). Der private Schlüssel bleibt ausserhalb des Servers; die Wiederherstellung fragt danach',
    ],
    'backup.s3.endpoint': [
      'S3-Endpunkt',
      'S3-kompatible Adresse, z. B. https://eu2.contabostorage.com',
    ],
    'backup.s3.bucket': ['S3-Bucket', 'Bucket, in den die verschlüsselten Backups gehen'],
    'backup.s3.region': ['S3-Region', "Bei Contabo meist 'default'"],
    'backup.s3.access_key': ['S3-Access-Key', 'Wird verschlüsselt gespeichert'],
    'backup.s3.secret_key': ['S3-Secret-Key', 'Wird verschlüsselt gespeichert'],
  },
})

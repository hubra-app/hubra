import { tr } from '@/lang'
import { defineSettings } from './registry'

export default defineSettings({
  id: 'translate',
  keys: [
    'translate.deepl_key',
    'translate.deepl_url',
  ],
  builtIn: [
    'translate.deepl_url',
  ],
  title: () => tr('Maschinelle Übersetzung', 'Machine translation'),
  desc: () =>
    tr(
      'Mit einem DeepL-Schlüssel können Vereine Beiträge in weitere Sprachen übersetzen lassen.',
      'With a DeepL key, clubs can have posts translated into more languages.',
    ),
  de: {
    'translate.deepl_key': [
      'DeepL-API-Schlüssel',
      'Maschinelle Übersetzung für Beiträge in mehreren Sprachen. Leer: keine maschinelle Übersetzung, Vereine schreiben jede Sprache selbst. Wird verschlüsselt gespeichert',
    ],
    'translate.deepl_url': [
      'DeepL-API-Adresse',
      'https://api-free.deepl.com für einen kostenlosen Schlüssel, https://api.deepl.com für einen bezahlten',
    ],
  },
})

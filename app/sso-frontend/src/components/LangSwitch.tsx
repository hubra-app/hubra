import { SegmentedControl } from '@mantine/core'
import { useLang, type Lang } from '@/lang'

/** DE / EN switch; German is the default. */
export function LangSwitch() {
  const { lang, setLang } = useLang()
  return (
    <SegmentedControl
      size="xs"
      ml="auto"
      value={lang}
      onChange={(v) => setLang(v as Lang)}
      data={[
        { value: 'de', label: 'DE' },
        { value: 'en', label: 'EN' },
      ]}
      aria-label="Sprache / Language"
    />
  )
}

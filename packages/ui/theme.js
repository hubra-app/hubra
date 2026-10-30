// Paints the page in the chosen light or dark scheme before the app loads,
// so a dark-mode user sees no white flash. Same rules as src/colorScheme.ts:
// the hubra_theme cookie, else the club app's old localStorage choice, else
// the browser's own setting. Copied to each app's public/ at build time.
;(function () {
  var value = (document.cookie.match(/(?:^|; )hubra_theme=(light|dark|auto)/) || [])[1]
  if (!value) {
    try {
      value = localStorage.getItem('mantine-color-scheme-value') || 'auto'
    } catch (e) {
      value = 'auto'
    }
  }
  if (value !== 'light' && value !== 'dark') {
    value = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  document.documentElement.setAttribute('data-mantine-color-scheme', value)
})()

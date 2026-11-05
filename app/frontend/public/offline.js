// The offline page (offline.html) in the device's language; German by default.
if (!/^de/i.test(navigator.language || '')) {
  document.documentElement.lang = 'en'
  document.getElementById('t').textContent = 'No connection'
  document.getElementById('d').textContent =
    'Hubra needs the internet. It carries on as soon as your device is back online.'
  document.getElementById('b').textContent = 'Try again'
}
document.getElementById('b').addEventListener('click', () => location.reload())
window.addEventListener('online', () => location.reload())

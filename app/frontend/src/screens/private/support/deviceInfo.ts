/**
 * What a problem report or feature request sends about the device: browser
 * and version, OS and version, phone/tablet/desktop, screen and window size,
 * language and light/dark. Nothing else (no user agent string, no fonts, no
 * IP: the server keeps only these fields too).
 */
export interface DeviceInfo {
  browser?: string
  browserVersion?: string
  os?: string
  osVersion?: string
  deviceType?: 'phone' | 'tablet' | 'desktop'
  screenWidth?: number
  screenHeight?: number
  viewportWidth?: number
  viewportHeight?: number
  language?: string
  theme?: 'light' | 'dark'
}

interface Env {
  userAgent: string
  /** navigator.userAgentData brands, where the browser has them. */
  brands?: { brand: string; version: string }[]
  mobileHint?: boolean
  maxTouchPoints?: number
  screen?: { width: number; height: number }
  viewport?: { width: number; height: number }
  language?: string
  theme?: 'light' | 'dark'
}

function match(ua: string, re: RegExp): string | undefined {
  return ua.match(re)?.[1]
}

/** Browser and major.minor version from the user agent. */
export function browserOf(ua: string): { browser?: string; browserVersion?: string } {
  const rules: [string, RegExp][] = [
    ['Edge', /Edg(?:e|A|iOS)?\/([\d.]+)/],
    ['Opera', /(?:OPR|Opera)\/([\d.]+)/],
    ['Samsung Internet', /SamsungBrowser\/([\d.]+)/],
    ['Firefox', /(?:Firefox|FxiOS)\/([\d.]+)/],
    ['Chrome', /(?:Chrome|CriOS)\/([\d.]+)/],
    ['Safari', /Version\/([\d.]+).*Safari/],
  ]
  for (const [browser, re] of rules) {
    const v = match(ua, re)
    if (v) return { browser, browserVersion: v.split('.').slice(0, 2).join('.') }
  }
  return {}
}

export function osOf(ua: string, maxTouchPoints = 0): { os?: string; osVersion?: string } {
  const ios = match(ua, /(?:iPhone|iPad|iPod).*? OS ([\d_]+)/)
  if (ios) return { os: 'iOS', osVersion: ios.replace(/_/g, '.') }
  // iPadOS asks for the desktop site and says "Macintosh", but has touch.
  if (/Macintosh/.test(ua) && maxTouchPoints > 1) return { os: 'iPadOS' }
  const android = match(ua, /Android ([\d.]+)/)
  if (android) return { os: 'Android', osVersion: android }
  if (/Android/.test(ua)) return { os: 'Android' }
  const win = match(ua, /Windows NT ([\d.]+)/)
  if (win) return { os: 'Windows', osVersion: win === '10.0' ? '10/11' : win }
  const mac = match(ua, /Mac OS X ([\d_.]+)/)
  if (mac) return { os: 'macOS', osVersion: mac.replace(/_/g, '.') }
  if (/CrOS/.test(ua)) return { os: 'ChromeOS' }
  if (/Linux/.test(ua)) return { os: 'Linux' }
  return {}
}

export function deviceTypeOf(
  ua: string,
  mobileHint: boolean | undefined,
  maxTouchPoints = 0,
): DeviceInfo['deviceType'] {
  if (/iPad|Tablet/.test(ua) || (/Android/.test(ua) && !/Mobile/.test(ua))) return 'tablet'
  if (/Macintosh/.test(ua) && maxTouchPoints > 1) return 'tablet'
  if (mobileHint || /Mobi|iPhone|iPod/.test(ua)) return 'phone'
  return 'desktop'
}

export function collectDeviceInfo(env: Env): DeviceInfo {
  const ua = env.userAgent || ''
  let { browser, browserVersion } = browserOf(ua)
  // Chromium browsers name themselves better in their brands.
  const brand = env.brands?.find((b) => !/Not.?A.?Brand|Chromium/i.test(b.brand))
  // Only where the user agent says Chrome (or nothing): a brand and a
  // version from different browsers would make a browser that never was.
  if (brand && (!browser || browser === 'Chrome')) {
    browser = brand.brand.replace(/^Google /, '').replace(/^Microsoft /, '')
    browserVersion = brand.version
  }
  const info: DeviceInfo = {
    browser,
    browserVersion,
    ...osOf(ua, env.maxTouchPoints),
    deviceType: deviceTypeOf(ua, env.mobileHint, env.maxTouchPoints),
    screenWidth: env.screen?.width,
    screenHeight: env.screen?.height,
    viewportWidth: env.viewport?.width,
    viewportHeight: env.viewport?.height,
    language: env.language,
    theme: env.theme,
  }
  return Object.fromEntries(
    Object.entries(info).filter(([, v]) => v !== undefined && v !== ''),
  ) as DeviceInfo
}

/** The device info of this browser, now. */
export function currentDeviceInfo(): DeviceInfo {
  const nav = navigator as Navigator & {
    userAgentData?: { brands?: { brand: string; version: string }[]; mobile?: boolean }
  }
  const scheme = document.documentElement.getAttribute('data-mantine-color-scheme')
  return collectDeviceInfo({
    userAgent: nav.userAgent,
    brands: nav.userAgentData?.brands,
    mobileHint: nav.userAgentData?.mobile,
    maxTouchPoints: nav.maxTouchPoints,
    screen: { width: window.screen.width, height: window.screen.height },
    viewport: { width: window.innerWidth, height: window.innerHeight },
    language: document.documentElement.lang || nav.language,
    theme: scheme === 'dark' ? 'dark' : scheme === 'light' ? 'light' : undefined,
  })
}

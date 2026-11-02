import { describe, expect, it } from 'vitest'
import { collectDeviceInfo } from './deviceInfo'

const ANDROID_FIREFOX =
  'Mozilla/5.0 (Android 14; Mobile; rv:132.0) Gecko/132.0 Firefox/132.0'
const IPHONE_SAFARI =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1'
const WINDOWS_EDGE =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.2849.68'
const IPAD_DESKTOP =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15'

describe('collectDeviceInfo', () => {
  it('reads a phone', () => {
    expect(
      collectDeviceInfo({
        userAgent: ANDROID_FIREFOX,
        screen: { width: 412, height: 915 },
        viewport: { width: 412, height: 800 },
        language: 'de-CH',
        theme: 'dark',
      }),
    ).toEqual({
      browser: 'Firefox',
      browserVersion: '132.0',
      os: 'Android',
      osVersion: '14',
      deviceType: 'phone',
      screenWidth: 412,
      screenHeight: 915,
      viewportWidth: 412,
      viewportHeight: 800,
      language: 'de-CH',
      theme: 'dark',
    })
  })

  it('reads Safari on an iPhone', () => {
    const info = collectDeviceInfo({ userAgent: IPHONE_SAFARI })
    expect(info).toMatchObject({ browser: 'Safari', browserVersion: '17.6', os: 'iOS', osVersion: '17.6', deviceType: 'phone' })
  })

  it('tells Edge from Chrome', () => {
    const info = collectDeviceInfo({ userAgent: WINDOWS_EDGE })
    expect(info).toMatchObject({ browser: 'Edge', browserVersion: '130.0', os: 'Windows', deviceType: 'desktop' })
  })

  it('sees an iPad that asks for the desktop site', () => {
    const info = collectDeviceInfo({ userAgent: IPAD_DESKTOP, maxTouchPoints: 5 })
    expect(info).toMatchObject({ os: 'iPadOS', deviceType: 'tablet', browser: 'Safari' })
  })

  it('names a Chromium browser by its brand, with the brand version', () => {
    const info = collectDeviceInfo({
      userAgent: 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
      brands: [
        { brand: 'Not?A_Brand', version: '99' },
        { brand: 'Chromium', version: '130' },
        { brand: 'Brave', version: '130' },
      ],
    })
    expect(info).toMatchObject({ browser: 'Brave', browserVersion: '130' })
  })

  it('keeps Safari when an iPhone user agent comes with other brands', () => {
    const info = collectDeviceInfo({
      userAgent: IPHONE_SAFARI,
      brands: [{ brand: 'HeadlessChrome', version: '153' }],
    })
    expect(info).toMatchObject({ browser: 'Safari', browserVersion: '17.6' })
  })

  it('leaves out what it does not know', () => {
    expect(collectDeviceInfo({ userAgent: '' })).toEqual({ deviceType: 'desktop' })
  })
})

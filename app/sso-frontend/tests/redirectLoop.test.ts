// Redirect-loop bookkeeping shared by all portals. Run with `npm test`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  LOOP_HOPS,
  WINDOW_MS,
  addHop,
  describeChain,
  isLoop,
  parseHops,
  safeTarget,
  serializeHops,
  stripUrl,
  type Hop,
} from '../../../packages/api-client/src/redirectLoop.ts'

const hop = (t: number, why = 'anon'): Hop => ({
  t,
  from: 'app.hubra.club/demo/app/dashboard',
  to: 'sso.hubra.club/login',
  why,
})

test('only host and path are kept, never query or hash', () => {
  assert.equal(
    stripUrl('https://sso.hubra.club/verify?redirect=x&token=secret#token=secret'),
    'sso.hubra.club/verify',
  )
  assert.equal(stripUrl('/login?x=1', 'https://sso.hubra.club/clubs'), 'sso.hubra.club/login')
  assert.equal(stripUrl('::not a url'), '?')
})

test('a normal sign-in is not a loop', () => {
  let hops: Hop[] = []
  for (const t of [0, 300, 700]) hops = addHop(hops, hop(t), t)
  assert.equal(isLoop(hops, 700), false)
})

test('many redirects in a few seconds are a loop', () => {
  let hops: Hop[] = []
  let t = 0
  for (let i = 0; i < LOOP_HOPS; i++) {
    t += 500
    hops = addHop(hops, hop(t), t)
  }
  assert.equal(isLoop(hops, t), true)
})

test('old hops fall out of the window', () => {
  let hops: Hop[] = []
  for (let i = 0; i < LOOP_HOPS - 1; i++) hops = addHop(hops, hop(i * 100), i * 100)
  const later = WINDOW_MS + 10_000
  hops = addHop(hops, hop(later), later)
  assert.equal(hops.length, 1)
  assert.equal(isLoop(hops, later), false)
})

test('the cookie value round-trips and garbage reads as nothing', () => {
  const hops = [hop(1, 'no-club'), hop(2, 'signed-in')]
  assert.deepEqual(parseHops(serializeHops(hops)), hops)
  assert.ok(!serializeHops(hops).includes(';'))
  assert.ok(!serializeHops(hops).includes('='))
  assert.deepEqual(parseHops('%7Bbroken'), [])
  assert.deepEqual(parseHops(encodeURIComponent('[{"t":"x"}]')), [])
  assert.deepEqual(parseHops(''), [])
})

test('the chain reads from the first page through every target', () => {
  assert.equal(
    describeChain([hop(1, 'no-club'), { ...hop(2, 'signed-in'), from: 'sso.hubra.club/login', to: 'app.hubra.club/demo/app/dashboard' }]),
    'app.hubra.club/demo/app/dashboard → sso.hubra.club/login (no-club) → app.hubra.club/demo/app/dashboard (signed-in)',
  )
})

test('redirects go only to places of this install', () => {
  const here = 'https://app.hubra.club/demo/app/dashboard'
  assert.equal(safeTarget('https://sso.hubra.club/login?redirect=x', here), 'https://sso.hubra.club/login?redirect=x')
  assert.equal(safeTarget('/demo/app/members', here), 'https://app.hubra.club/demo/app/members')
  assert.equal(safeTarget('https://hubra.club/', here), 'https://hubra.club/')
  assert.equal(safeTarget('javascript:alert(1)', here), null)
  assert.equal(safeTarget('data:text/html,hi', here), null)
  assert.equal(safeTarget('https://evil.example/', here), null)
  assert.equal(safeTarget('https://hubra.club.evil.example/', here), null)
  assert.equal(safeTarget('https://user:pw@sso.hubra.club/', here), null)
  assert.equal(safeTarget('https://login.other.ch/', here, ['https://login.other.ch']), 'https://login.other.ch/')
  assert.equal(safeTarget('http://localhost:5175/login', 'http://localhost:5173/x'), 'http://localhost:5175/login')
  // Never down from HTTPS to HTTP, unless that address is configured.
  assert.equal(safeTarget('http://sso.hubra.club/login', here), null)
  assert.equal(safeTarget('http://app.hubra.club/demo/app/members', here), null)
  assert.equal(safeTarget('http://sso.local.test/login', here, ['http://sso.local.test']), 'http://sso.local.test/login')
  assert.equal(safeTarget('http://sso.hubra.club/login', 'http://app.hubra.club/x'), 'http://sso.hubra.club/login')
})

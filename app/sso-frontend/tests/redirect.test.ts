// Where the login portal sends a signed-in user. Run with `npm test`
// (Node's own test runner; Node strips the types).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { clubAppUrl, signedInTarget, validateRedirect } from '../src/redirect.ts'

const urls = { cos: 'https://app.hubra.club', manage: 'https://manage.hubra.club' }

test('everyone without a deep link lands on the club picker', () => {
  assert.equal(signedInTarget(null), null)
})

test('a trusted deep link wins', () => {
  const redirect = 'https://app.hubra.club/demo/app/members'
  assert.equal(signedInTarget(redirect), redirect)
})

test('the bare club app is not a redirect target (it loops back to login)', () => {
  assert.equal(validateRedirect('https://app.hubra.club/', urls), null)
  assert.equal(validateRedirect('https://app.hubra.club', urls), null)
  assert.equal(
    validateRedirect('https://app.hubra.club/demo/app/dashboard', urls),
    'https://app.hubra.club/demo/app/dashboard',
  )
})

test('redirects stay on Hubra hosts', () => {
  assert.equal(validateRedirect(null, urls), null)
  assert.equal(validateRedirect('not a url', urls), null)
  assert.equal(validateRedirect('https://evil.example/', urls), null)
  assert.equal(validateRedirect('http://app.hubra.club/demo/app', urls), null)
  assert.equal(validateRedirect('https://manage.hubra.club/app/tenants', urls), 'https://manage.hubra.club/app/tenants')
  assert.equal(validateRedirect('https://docs.hubra.club/x', urls), 'https://docs.hubra.club/x')
})

test('localhost on any port only while developing', () => {
  const local = { cos: 'http://localhost:8080', manage: 'http://localhost:8081' }
  assert.equal(validateRedirect('http://localhost:5173/x', local), null)
  assert.equal(validateRedirect('http://localhost:5173/x', local, { dev: true }), 'http://localhost:5173/x')
  assert.equal(validateRedirect('http://localhost:8080/', local, { dev: true }), null)
})

test('club slugs are escaped in the club URL', () => {
  assert.equal(clubAppUrl(urls, 'a b'), 'https://app.hubra.club/a%20b/app/dashboard')
})

test('pages of the portal itself are fine (join page, start a club)', () => {
  const self = 'https://login.example.org'
  assert.equal(validateRedirect(`${self}/clubs/ruder-zug`, urls, { self }), `${self}/clubs/ruder-zug`)
  assert.equal(validateRedirect('https://evil.example/clubs/x', urls, { self }), null)
})

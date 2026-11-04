import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ARTICLES, CATEGORIES, articleBySlug, searchArticles } from '../src/content/help.ts'
import { headingsOf, slugify } from '../src/lib/markdown.ts'
import { pathOf } from '../src/lib/labels.ts'

test('every article has both languages, a known category and a unique slug', () => {
  const slugs = new Set<string>()
  for (const a of ARTICLES) {
    assert.ok(!slugs.has(a.slug), `duplicate slug ${a.slug}`)
    slugs.add(a.slug)
    assert.match(a.slug, /^[a-z0-9-]+$/)
    assert.ok(a.category in CATEGORIES, a.slug)
    for (const lang of ['de', 'en'] as const) {
      assert.ok(a.title[lang].trim(), `${a.slug} title ${lang}`)
      assert.ok(a.summary[lang].trim(), `${a.slug} summary ${lang}`)
      assert.ok(a.body[lang].trim(), `${a.slug} body ${lang}`)
    }
    // Same sections in both languages, so the contents lists match.
    assert.equal(headingsOf(a.body.de).length, headingsOf(a.body.en).length, a.slug)
  }
})

test('links inside articles point at pages that exist', () => {
  const pages = new Set(['/start', '/melden', '/idee', '/kontakt', '/roadmap', '/status', '/datenschutz', '/hilfe'])
  for (const a of ARTICLES) {
    for (const lang of ['de', 'en'] as const) {
      for (const [, href] of a.body[lang].matchAll(/\]\((\/[^)\s]*)\)/g)) {
        const path = href.split('?')[0].split('#')[0]
        if (path.startsWith('/hilfe/')) assert.ok(articleBySlug(path.slice(7)), `${a.slug}: ${href}`)
        else assert.ok(pages.has(path), `${a.slug}: ${href}`)
      }
    }
  }
})

test('search needs every word and ranks title hits first', () => {
  const hits = searchArticles('rechnung', 'de')
  assert.equal(hits[0].slug, 'rechnungen-qr')
  assert.deepEqual(searchArticles('rechnung xyzzy', 'de'), [])
  assert.deepEqual(searchArticles(' ', 'de'), [])
  assert.ok(searchArticles('invoice', 'en').some((a) => a.slug === 'rechnungen-qr'))
})

test('slugify makes anchor ids from headings', () => {
  assert.equal(slugify('Die Mail kommt nicht an'), 'die-mail-kommt-nicht-an')
  assert.equal(slugify('Anlässe und Trainings'), 'anlasse-und-trainings')
})

test('pathOf keeps only the path of a pasted address', () => {
  assert.equal(pathOf('https://app.hubra.club/fcx/app/finance?x=1'), '/fcx/app/finance')
  assert.equal(pathOf('/fcx/app'), '/fcx/app')
  assert.equal(pathOf('not a url'), undefined)
  assert.equal(pathOf(''), undefined)
})

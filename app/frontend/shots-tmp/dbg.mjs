import { chromium } from 'playwright'
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const p = await (await b.newContext()).newPage()
p.on('console', m => console.log('console', m.type(), m.text().slice(0,300)))
p.on('pageerror', e => console.log('pageerror', e.message.slice(0,300)))
p.on('requestfailed', r => console.log('fail', r.url()))
await p.goto('http://localhost:5173/demo/app/dashboard'); await p.waitForTimeout(6000)
console.log(p.url()); await b.close()

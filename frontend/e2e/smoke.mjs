// Browser smoke test: drives the real website in headless Chrome and fails on any console error, failed request or broken step.
//
//   1. cd frontend && npm run build          (once)
//   2. cd backend && uvicorn app.main:app --port 8000     (leave running, Demo Mode is fine)
//   3. cd frontend && npm run e2e
//
// Environment:  E2E_URL (default http://127.0.0.1:8000)   CHROME_PATH (path to chrome.exe / chrome / chromium)
//               E2E_EXTRA_ARGS (extra Chrome flags)       E2E_SHOTS=1 (save screenshots into e2e/screenshots)
import fs from 'node:fs'
import path from 'node:path'
import puppeteer from 'puppeteer-core'

const URL_BASE = (process.env.E2E_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const SHOTS = process.env.E2E_SHOTS === '1'
const shotDir = path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')), 'screenshots')

function findChrome() {
  const candidates = [process.env.CHROME_PATH,
    'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].filter(Boolean)
  const found = candidates.find((p) => fs.existsSync(p))
  if (!found) throw new Error('Chrome not found. Set CHROME_PATH to your chrome.exe (or msedge.exe) and run again.')
  return found
}

const problems = []
const steps = []
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function main() {
  const browser = await puppeteer.launch({
    executablePath: findChrome(), headless: 'shell',
    args: ['--no-sandbox', '--disable-gpu', ...(process.env.E2E_EXTRA_ARGS ? process.env.E2E_EXTRA_ARGS.split(' ') : [])],
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 1280, height: 900 })
  page.on('console', (m) => { if (m.type() === 'error') problems.push('console error: ' + m.text()) })
  page.on('pageerror', (e) => problems.push('page error: ' + e.message))
  page.on('requestfailed', (r) => problems.push('request failed: ' + r.url() + ' ' + (r.failure()?.errorText || '')))
  page.on('response', (r) => { if (r.status() >= 400 && r.url().includes('/api/')) problems.push('HTTP ' + r.status() + ' ' + r.url()) })

  const text = () => page.evaluate(() => document.body.innerText)
  const waitText = async (t, ms = 25000) => {
    try { await page.waitForFunction((x) => document.body.innerText.includes(x), { timeout: ms }, t) } catch { throw new Error('Timed out waiting for text: ' + t + '\nPage text was:\n' + (await text()).slice(0, 700)) }
  }
  // Waits (up to 20 s) for the element to exist, because lists and panels load after the page heading appears.
  const clickText = async (selector, label, ms = 20000) => {
    const deadline = Date.now() + ms
    for (;;) {
      const ok = await page.evaluate((sel, lab) => {
        const el = [...document.querySelectorAll(sel)].find((e) => e.innerText && e.innerText.trim().includes(lab) && !e.disabled)
        if (!el) return false
        el.click(); return true
      }, selector, label)
      if (ok) return
      if (Date.now() > deadline) throw new Error('Could not find ' + selector + ' containing "' + label + '" within ' + ms / 1000 + 's')
      await sleep(250)
    }
  }
  const shot = async (name, pg = page) => { if (SHOTS) { fs.mkdirSync(shotDir, { recursive: true }); await pg.screenshot({ path: path.join(shotDir, name + '.png'), fullPage: true }) } }
  const step = async (name, fn) => { await fn(); steps.push(name); console.log('  ok  ' + name) }

  await step('landing page loads', async () => {
    await page.goto(URL_BASE + '/', { waitUntil: 'networkidle0' })
    await waitText('Report Smarter. Resolve Faster. Verify Every Fix.')
    await waitText('mode')                       // Demo mode / Live AI mode banner
    await shot('01-landing')
  })
  await step('landing walkthrough: reused photo is contradicted', async () => {
    await clickText('button', 'Original photo sent again')
    await waitText('Contradicted')
    await clickText('button', 'Genuine repair photo')
    await waitText('Verified')
    await shot('02-walkthrough')
  })

  let id
  await step('student reports a sample problem and gets a complaint ID', async () => {
    await clickText('button', 'Report an Issue')
    await page.waitForFunction(() => location.pathname === '/report')
    await waitText('Try a sample report')
    await clickText('button', 'Broken stair light')
    await page.waitForSelector('img[alt^="Preview"]', { timeout: 20000 })
    await clickText('button', 'Submit complaint')
    await waitText('Complaint ID #')
    id = (await text()).match(/Complaint ID #(\d+)/)[1]
    await waitText('What the system decided')
    await shot('03-report-result')
  })
  await step('duplicate report merges into the same ticket', async () => {
    await clickText('button', 'Broken stair light')
    await page.waitForSelector('img[alt^="Preview"]', { timeout: 20000 })
    await clickText('button', 'Submit complaint')
    await waitText('Already reported')
    await shot('04-duplicate')
  })

  await step('department: reused photo is contradicted, genuine photo is verified', async () => {
    await clickText('button', 'Department')                          // role switcher
    await clickText('a', 'Department queue')
    await page.waitForFunction(() => location.pathname === '/department')
    await waitText('Department queue')
    await clickText('button', '#' + id)
    await waitText('Claim that this is resolved')
    await page.waitForSelector('#sample-evidence', { timeout: 15000 })
    await page.select('#sample-evidence', 'broken_light__after_reused')
    await page.waitForSelector('img[alt*="after-repair"]', { timeout: 15000 })
    await clickText('button', 'Claim resolution')
    await waitText('Contradicted')
    await shot('05-contradicted')
    await page.select('#sample-evidence', 'broken_light__after_genuine')
    await sleep(500)
    await clickText('button', 'Claim resolution')
    await waitText('Verified')
    await shot('06-verified')
  })

  await step('admin dashboard: stats, hotspots, audit check, demo clock, evaluation', async () => {
    await clickText('button', 'Admin')
    await clickText('a', 'Administration')
    await waitText('Total complaints')
    await waitText('Department performance')
    await clickText('button', 'Analyse recurring problems now')
    await waitText('Likely root cause')
    await page.select('#audit-ticket', id)
    await waitText('Integrity check passed')
    await clickText('button', '+24 hours')
    await waitText('Currently +24 h')
    await waitText('Read this first')
    await waitText('Fake closures accepted')
    const body = await text()
    const bad = [/\bundefined\b/, /\bNaN\b/, /\[object Object\]/, /\bn\/a\b/i].filter((re) => re.test(body))   // a broken data mapping shows up as one of these (whole words only: 'Maintenance' is fine)
    if (bad.length) throw new Error('Admin screen shows broken values matching: ' + bad.join(' '))
    await shot('07-admin')
  })

  await step('ticket page by direct link: timeline, images, audit check', async () => {
    await page.goto(URL_BASE + '/tickets/' + id, { waitUntil: 'networkidle0' })
    await waitText('Complaint #' + id)
    await waitText('Complaint timeline')
    await clickText('button', 'Verify audit integrity')
    await waitText('Integrity check passed')
    const broken = await page.evaluate(() => [...document.images].filter((i) => !i.complete || i.naturalWidth === 0).map((i) => i.src))
    if (broken.length) throw new Error('Images failed to load: ' + broken.join(', '))
    await shot('08-ticket')
  })

  await step('reporter role cannot open the admin screen', async () => {
    await clickText('button', 'Reporter')
    await page.goto(URL_BASE + '/admin', { waitUntil: 'networkidle0' })
    await waitText('This screen is for a different role')
  })

  await step('mobile layout (fresh phone-sized page): nothing wider than the screen on any main screen', async () => {
    const phone = await browser.newPage()                          // a NEW page, so phone emulation starts clean
    await phone.setViewport({ width: 375, height: 800, isMobile: true, deviceScaleFactor: 1 })
    phone.on('console', (m) => { if (m.type() === 'error') problems.push('phone console error: ' + m.text()) })
    phone.on('pageerror', (e) => problems.push('phone page error: ' + e.message))
    for (const p of ['/', '/report', '/tickets/' + id]) {
      await phone.goto(URL_BASE + p, { waitUntil: 'networkidle0' })
      await phone.waitForFunction(() => document.body.innerText.length > 50)
      const wide = await phone.evaluate(() => {
        const vw = document.documentElement.clientWidth
        const out = []
        for (const e of document.querySelectorAll('body *')) {
          const r = e.getBoundingClientRect()
          if (r.width > 0 && r.right > vw + 1) {
            let clipped = false
            for (let a = e.parentElement; a; a = a.parentElement) if (['auto', 'scroll', 'hidden'].includes(getComputedStyle(a).overflowX)) { clipped = true; break }
            if (!clipped) out.push(e.tagName.toLowerCase() + ' right=' + Math.round(r.right))
          }
        }
        return { vw, scroll: document.documentElement.scrollWidth, out: out.slice(0, 5) }
      })
      if (wide.scroll > wide.vw + 1 || wide.out.length) throw new Error('Too wide for a phone on ' + p + ': ' + JSON.stringify(wide))
      await shot('09-mobile' + p.replace(/\//g, '-'), phone)
    }
    await phone.close()
  })

  await browser.close()
}

main().then(() => {
  console.log('\n' + steps.length + ' steps passed.')
  if (problems.length) { console.log('\nPROBLEMS FOUND (' + problems.length + '):'); [...new Set(problems)].forEach((p) => console.log(' - ' + p)); process.exit(1) }
  console.log('No console errors, page errors or failed API requests.')
}).catch((e) => {
  console.error('\nE2E FAILED after ' + steps.length + ' steps:\n' + e.message)
  if (problems.length) { console.error('\nProblems seen on the way:'); [...new Set(problems)].forEach((p) => console.error(' - ' + p)) }
  process.exit(1)
})

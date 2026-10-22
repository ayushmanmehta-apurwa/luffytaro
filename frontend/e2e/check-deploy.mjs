// Checks a DEPLOYED site (for example Vercel frontend + Render backend) in a real browser and explains what is wrong.
//
//   SITE_URL=https://your-site.vercel.app npm run check:deploy        (PowerShell:  $env:SITE_URL="https://..."; npm run check:deploy)
//
// It needs Chrome (set CHROME_PATH if it is not found). The first request can take ~1 minute on a free host that was asleep.
import fs from 'node:fs'
import puppeteer from 'puppeteer-core'

const SITE = (process.env.SITE_URL || '').replace(/\/$/, '')
if (!SITE) { console.error('Set SITE_URL, for example: SITE_URL=https://your-site.vercel.app'); process.exit(2) }
const WAIT_MS = Number(process.env.WAIT_SECONDS || 90) * 1000

const chrome = [process.env.CHROME_PATH, 'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].filter(Boolean).find((p) => fs.existsSync(p))
if (!chrome) { console.error('Chrome not found. Set CHROME_PATH to your chrome.exe (or msedge.exe).'); process.exit(2) }

const browser = await puppeteer.launch({ executablePath: chrome, headless: 'shell', args: ['--no-sandbox', '--disable-gpu', ...(process.env.E2E_EXTRA_ARGS ? process.env.E2E_EXTRA_ARGS.split(' ') : [])] })
const page = await browser.newPage()
const consoleErrors = [], api = []
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()) })
page.on('response', (r) => { if (r.url().includes('/api/config') || r.url().includes('/health')) api.push({ url: r.url(), status: r.status(), routing: r.headers()['x-render-routing'] || '' }) })
page.on('requestfailed', (r) => { if (r.url().includes('/api/')) api.push({ url: r.url(), status: 0, failure: r.failure()?.errorText }) })

console.log('Opening ' + SITE + ' (waiting up to ' + WAIT_MS / 1000 + 's for the backend to answer)...')
await page.goto(SITE, { waitUntil: 'domcontentloaded', timeout: 60000 }).catch((e) => console.log('Could not open the site itself: ' + e.message))
const mode = await page.waitForFunction(() => {
  const t = document.body.innerText
  return t.includes('Live AI mode') ? 'live' : t.includes('Demo mode') ? 'demo' : null
}, { timeout: WAIT_MS }).then((h) => h.jsonValue()).catch(() => null)
const bodyText = await page.evaluate(() => document.body.innerText.slice(0, 300)).catch(() => '')
await browser.close()

const siteHost = new URL(SITE).host
const configCall = api.find((a) => a.url.includes('/api/config'))
console.log('\n--- RESULT ---')
if (mode) { console.log('OK: the website reached its backend. Mode: ' + mode.toUpperCase() + '.'); process.exit(0) }
console.log('PROBLEM: the website could not load data from its backend.\n')
if (configCall) console.log('The browser asked: ' + configCall.url + '  ->  ' + (configCall.status || 'FAILED ' + (configCall.failure || '')))
const cors = consoleErrors.find((e) => /CORS/i.test(e))
if (configCall && (configCall.routing || '').includes('suspend')) {
  console.log('\nDIAGNOSIS: the Render service is SUSPENDED.  Render dashboard -> your service -> Resume Service (then wait for "Live").')
} else if (configCall && new URL(configCall.url).host === siteHost) {
  console.log('\nDIAGNOSIS: the website is calling ITSELF (' + siteHost + ') instead of the backend.\n  Vercel -> Settings -> Environment Variables: set VITE_API_BASE=https://YOUR-BACKEND-ADDRESS (no trailing slash), then Deployments -> Redeploy.')
} else if (cors) {
  const m = cors.match(/from origin '([^']+)'/)
  console.log('\nDIAGNOSIS: CORS. The backend does not allow this website.\n  On the backend host set  CORS_ORIGINS=' + (m ? m[1] : SITE) + '  (exactly: https, no trailing slash, same spelling), save, and wait for the redeploy.')
} else if (configCall && [502, 503, 504].includes(configCall.status)) {
  console.log('\nDIAGNOSIS: the backend host answered ' + configCall.status + '. It is probably still waking up or crashed. Open its Logs tab, and try again in a minute.')
} else if (configCall && configCall.status === 0 && /CONNECTION_REFUSED|NAME_NOT_RESOLVED|TIMED_OUT|CONNECTION_RESET|CONNECTION_CLOSED/.test(configCall.failure || '')) {
  console.log('\nDIAGNOSIS: nothing answered at ' + new URL(configCall.url).origin + ' (' + configCall.failure + ').\n  The backend is not running, is still waking up, is suspended, or VITE_API_BASE has a typo. Open that address plus /health in your browser and check the host\'s Logs.')
} else if (configCall && configCall.status === 404) {
  console.log('\nDIAGNOSIS: the address answers but has no /api/config. VITE_API_BASE probably points at the wrong service. Check the address and redeploy the frontend.')
} else {
  console.log('\nDIAGNOSIS: unclear. Console errors: ' + JSON.stringify(consoleErrors.slice(0, 3)) + '\n  Page text: ' + JSON.stringify(bodyText))
}
process.exit(1)

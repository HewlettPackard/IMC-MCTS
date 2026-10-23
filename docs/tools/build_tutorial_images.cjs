/* Export original tutorial diagrams as PNGs. This does not execute the simulator. */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const root = process.argv[2];
if (!root) throw new Error('Pass the website directory as the only argument.');
const out = path.join(root, 'docs/_static/tutorial');
fs.mkdirSync(out, { recursive: true });
const html = fs.readFileSync(path.join(root, 'docs/_includes/search-walkthrough.html'), 'utf8');
const css = fs.readFileSync(path.join(root, 'docs/_static/tutorial.css'), 'utf8');
const js = fs.readFileSync(path.join(root, 'docs/_static/tutorial.js'), 'utf8');
const names = ['start', 'select', 'expand', 'evaluate', 'backup'];
(async () => {
 const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
 const page = await browser.newPage({ viewport: { width: 800, height: 900 }, deviceScaleFactor: 2 });
 await page.setContent('<!doctype html><html data-theme="light"><head><meta charset="utf-8"><style>body{margin:0;background:#fff;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}'+css+'#tutorial-walkthrough{width:720px;margin:0}.tutorial-tree{min-width:0;width:720px}</style></head><body>'+html+'</body></html>');
 await page.addScriptTag({ content: js });
 for (let step = 0; step < names.length; step++) {
  await page.locator('[data-tutorial-go="'+step+'"]').evaluate(el => el.click());
  await page.locator('.tutorial-tree').screenshot({ path: path.join(out, 'step-'+step+'-'+names[step]+'.png') });
 }
 const mapping = fs.readFileSync(path.join(root, 'docs/_static/tutorial-mapping.svg'), 'utf8');
 await page.setContent('<!doctype html><html><head><style>body{margin:0;background:white}svg{display:block;width:760px;height:786px}</style></head><body>'+mapping+'</body></html>');
 await page.locator('svg').screenshot({ path: path.join(out, 'hardware-mapping.png') });
 await browser.close();
 console.log(JSON.stringify({status:'EXPORTED',directory:out,files:fs.readdirSync(out)}));
})().catch(e => { console.error(e); process.exit(1); });

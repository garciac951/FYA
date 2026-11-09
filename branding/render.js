// Renders channel branding PNGs into assets/branding/.
//   node branding/render.js
// Profile pictures: 800x800 (YouTube shows them as a circle).
// Banners: 2560x1440. Everything important sits in the 1546x423 centre "safe area" visible on every device.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const OUT = path.join(__dirname, '..', 'assets', 'branding');

const PALETTE = {
  slate: '#1B2631',
  slateDark: '#141C25',
  slateLight: '#202D3A',
  yellow: '#FFC72C', // matches the caption highlight in the videos
  terracotta: '#C4572A',
  white: '#FFFFFF',
};

const CHANNELS = {
  en: {
    name: 'PORCH TALK', accent: 'PRO',
    tagline: 'Practical know-how in under a minute',
    topics: 'TRUCKS · LAWNS · GRILLING · FISHING · DOGS · TECH · SPORTS',
    cadence: 'New Shorts every day',
    avatarBg: PALETTE.slate,
  },
  es: {
    name: 'PLÁTICA DE', accent: 'PORCHE',
    tagline: 'Consejos prácticos en menos de un minuto',
    topics: 'TROCAS · JARDÍN · ASADOR · PESCA · PERROS · TECNOLOGÍA · DEPORTES',
    cadence: 'Shorts nuevos cada día',
    avatarBg: PALETTE.terracotta,
  },
};

// Porch roof over a speech bubble: "porch talk" in one mark, no words, so it works in both languages.
function icon(size, { bg = 'none', roof = PALETTE.yellow, bubble = PALETTE.white, dots = PALETTE.slate } = {}) {
  return `
  <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 800 800">
    ${bg === 'none' ? '' : `<rect width="800" height="800" fill="${bg}"/>`}
    <polyline points="196,372 400,196 604,372" fill="none" stroke="${roof}" stroke-width="64"
              stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M300 392 H500 Q560 392 560 452 V532 Q560 592 500 592 H392 L318 652 L330 592 H300
             Q240 592 240 532 V452 Q240 392 300 392 Z" fill="${bubble}"/>
    <circle cx="324" cy="492" r="27" fill="${dots}"/>
    <circle cx="400" cy="492" r="27" fill="${dots}"/>
    <circle cx="476" cy="492" r="27" fill="${dots}"/>
  </svg>`;
}

function avatarHtml(lang) {
  const c = CHANNELS[lang];
  return `<!doctype html><html><body style="margin:0">${icon(800, { bg: c.avatarBg, dots: c.avatarBg })}</body></html>`;
}

function bannerHtml(lang) {
  const c = CHANNELS[lang];
  return `<!doctype html><html><head><meta charset="utf-8"><style>
    * { margin: 0; box-sizing: border-box; }
    body { width: 2560px; height: 1440px; overflow: hidden; font-family: 'Inter', sans-serif; }
    .banner {
      position: relative; width: 2560px; height: 1440px;
      /* porch floorboards */
      background:
        radial-gradient(ellipse 900px 520px at 38% 50%, rgba(255,199,44,0.13), rgba(255,199,44,0) 70%),
        repeating-linear-gradient(180deg, ${PALETTE.slate} 0 104px, ${PALETTE.slateLight} 104px 108px,
                                  ${PALETTE.slateDark} 108px 114px);
    }
    .safe {
      position: absolute; left: 507px; top: 508px; width: 1546px; height: 423px;
      display: flex; align-items: center; gap: 60px; padding: 0 40px;
    }
    .mark { flex: none; width: 330px; height: 330px; border-radius: 50%; overflow: hidden;
            box-shadow: 0 0 0 8px rgba(255,199,44,0.55), 0 18px 60px rgba(0,0,0,0.45); }
    .text { flex: 1; min-width: 0; color: ${PALETTE.white}; }
    .name { font-weight: 900; font-size: 128px; line-height: 1; letter-spacing: -2px; white-space: nowrap; }
    .name span { color: ${PALETTE.yellow}; }
    .tag { margin-top: 26px; font-weight: 600; font-size: 50px; color: #E9EDF1; white-space: nowrap; }
    .topics { margin-top: 22px; font-weight: 700; font-size: 31px; letter-spacing: 2px; color: ${PALETTE.yellow};
              white-space: nowrap; }
    .cadence { margin-top: 20px; font-weight: 500; font-size: 32px; color: #AEB8C2; white-space: nowrap; }
  </style></head><body>
    <div class="banner"><div class="safe">
      <div class="mark">${icon(330, { bg: c.avatarBg, dots: c.avatarBg })}</div>
      <div class="text">
        <div class="name">${c.name} <span>${c.accent}</span></div>
        <div class="tag">${c.tagline}</div>
        <div class="topics">${c.topics}</div>
        <div class="cadence">${c.cadence}</div>
      </div>
    </div></div>
    <script>
      // Shrink any line that would overflow the safe area.
      for (const el of document.querySelectorAll('.text > div')) {
        let size = parseFloat(getComputedStyle(el).fontSize);
        while (el.scrollWidth > el.parentElement.clientWidth && size > 10) {
          size -= 1; el.style.fontSize = size + 'px';
        }
      }
    </script>
  </body></html>`;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  for (const lang of Object.keys(CHANNELS)) {
    await page.setViewportSize({ width: 800, height: 800 });
    await page.setContent(avatarHtml(lang));
    await page.screenshot({ path: path.join(OUT, `profile-${lang}.png`) });

    await page.setViewportSize({ width: 2560, height: 1440 });
    await page.setContent(bannerHtml(lang));
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(OUT, `banner-${lang}.png`) });
  }
  await browser.close();
  console.log('Wrote', fs.readdirSync(OUT).join(', '));
})();

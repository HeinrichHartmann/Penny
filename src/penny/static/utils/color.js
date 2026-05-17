/**
 * Color utilities for category visualization.
 */

/**
 * Warm earthy palette for charts.
 */
export const PALETTE = [
  '#5d8a66', '#c67b47', '#7b68a6', '#4a90a4', '#d4a84b',
  '#8b7355', '#a35d6a', '#6b8e9f', '#9b7653', '#6a9a8a',
  '#b86b4c', '#7d8471', '#8c6d8a', '#6e7b8b', '#9c7a97',
  '#7aa37a', '#8b8378', '#5c7a6e', '#7a8b6e', '#9878a0',
];

/**
 * Gray color for transfer categories.
 */
export const TRANSFER_GRAY = '#c8c8c8';

// ── HSL helpers ──────────────────────────────────────────────────────────────

function hexToHsl(hex) {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }
  return [h * 360, s * 100, l * 100];
}

function hslToHex(h, s, l) {
  h /= 360; s /= 100; l /= 100;
  const hue2rgb = (p, q, t) => {
    if (t < 0) t += 1; if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  let r, g, b;
  if (s === 0) {
    r = g = b = l;
  } else {
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1 / 3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1 / 3);
  }
  return '#' + [r, g, b].map((x) => Math.round(x * 255).toString(16).padStart(2, '0')).join('');
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Get color for a category.
 * @param {string|null} category
 * @param {object} colorMap - reactive map of category -> color
 * @returns {string|null}
 */
export const categoryColor = (category, colorMap) => {
  if (!category) return null;
  // Try full path first (subcategory views store colors by full path)
  if (colorMap[category]) return colorMap[category];
  const l1 = category.includes('/') ? category.split('/')[0] : category;
  if (l1 === 'transfer') return TRANSFER_GRAY;
  return colorMap[l1] || null;
};

/**
 * Ensure colors are assigned to categories.
 * L1 categories get palette colors; subcategories get lightness-shifted
 * variants of their parent color to maintain visual family resemblance.
 * @param {string[]} categories - category names (may be full paths like "shopping/amazon")
 * @param {object} colorMap - reactive map to update
 */
export const ensureCategoryColors = (categories, colorMap) => {
  // 1. Assign palette colors to any new L1 categories
  let paletteIdx = Object.keys(colorMap).filter((k) => !k.includes('/')).length;
  const seenL1 = new Set();
  categories.forEach((cat) => {
    const l1 = cat.includes('/') ? cat.split('/')[0] : cat;
    if (colorMap[l1] || seenL1.has(l1)) return;
    seenL1.add(l1);
    colorMap[l1] = l1 === 'transfer' ? TRANSFER_GRAY : PALETTE[paletteIdx++ % PALETTE.length];
  });

  // 2. Derive subcategory colors from parent — group by parent first so we
  //    can spread lightness evenly across all siblings in this call.
  const byParent = {};
  categories.forEach((cat) => {
    if (!cat.includes('/') || colorMap[cat]) return;
    const l1 = cat.split('/')[0];
    (byParent[l1] = byParent[l1] || []).push(cat);
  });

  Object.entries(byParent).forEach(([l1, subcats]) => {
    const parentColor = colorMap[l1];
    if (!parentColor || parentColor === TRANSFER_GRAY) return;
    const [h, s, baseL] = hexToHsl(parentColor);
    const n = subcats.length;
    subcats.forEach((cat, i) => {
      // Distribute lightness evenly across a ±15% range around the parent lightness
      const t = n === 1 ? 0.5 : i / (n - 1); // 0 → 1
      const lOffset = (t - 0.5) * 30;
      colorMap[cat] = hslToHex(h, s, Math.max(28, Math.min(72, baseL + lOffset)));
    });
  });
};

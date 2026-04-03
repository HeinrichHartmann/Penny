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

/**
 * Get color for a category.
 * @param {string|null} category
 * @param {object} colorMap - reactive map of category -> color
 * @returns {string|null}
 */
export const categoryColor = (category, colorMap) => {
  if (!category) return null;
  const l1 = category.includes('/') ? category.split('/')[0] : category;
  if (l1 === 'transfer') return TRANSFER_GRAY;
  return colorMap[l1] || null;
};

/**
 * Ensure colors are assigned to categories.
 * @param {string[]} categories - L1 category names
 * @param {object} colorMap - reactive map to update
 */
export const ensureCategoryColors = (categories, colorMap) => {
  categories.forEach((cat, i) => {
    if (colorMap[cat]) return;
    colorMap[cat] = cat === 'transfer'
      ? TRANSFER_GRAY
      : PALETTE[i % PALETTE.length];
  });
};

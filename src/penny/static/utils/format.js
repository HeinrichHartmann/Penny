/**
 * Formatting utilities for currency and markdown.
 */

/**
 * Format cents as currency (EUR).
 * @param {number|null} cents
 * @returns {string}
 */
export const formatCurrency = (cents) => {
  if (cents == null) return '–';
  return (cents / 100).toLocaleString('de-DE', {
    style: 'currency',
    currency: 'EUR',
  });
};

/**
 * Format cents as compact signed value (e.g., "1.5k+", "200-").
 * @param {number} cents
 * @returns {string}
 */
export const formatCompactSigned = (cents) => {
  const sign = cents >= 0 ? '+' : '-';
  const eur = Math.abs(cents) / 100;
  let value = eur;
  let suffix = '';
  if (eur >= 1_000_000) {
    value = eur / 1_000_000;
    suffix = 'm';
  } else if (eur >= 1_000) {
    value = eur / 1_000;
    suffix = 'k';
  }
  const digits = value >= 10 || suffix === '' ? 0 : 1;
  const text = value.toLocaleString('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
  return `${text}${suffix}${sign}`;
};

/**
 * Escape a value for use in a markdown table cell.
 * @param {*} value
 * @returns {string}
 */
export const escapeMarkdownCell = (value) => {
  return String(value ?? '')
    .replace(/\|/g, '\\|')
    .replace(/\n/g, ' ')
    .trim();
};

/**
 * Convert headers and rows to a markdown table.
 * @param {string[]} headers
 * @param {Array<Array<*>>} rows
 * @returns {string}
 */
export const toMarkdownTable = (headers, rows) => {
  const head = `| ${headers.map(escapeMarkdownCell).join(' | ')} |`;
  const sep = `| ${headers.map(() => '---').join(' | ')} |`;
  const body = rows.map((row) => `| ${row.map(escapeMarkdownCell).join(' | ')} |`);
  return [head, sep, ...body].join('\n');
};

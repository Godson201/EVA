export const THEMES = {
  indigo: { label: 'Indigo', primary: '#4f6ef7', dark: '#3c56d6', light: '#eef1ff' },
  teal: { label: 'Teal', primary: '#0d9488', dark: '#0f766e', light: '#e6f4f2' },
  green: { label: 'Green', primary: '#16a34a', dark: '#15803d', light: '#e9f9ee' },
  purple: { label: 'Purple', primary: '#8b5cf6', dark: '#6d28d9', light: '#f3eefe' },
  rose: { label: 'Rose', primary: '#e11d48', dark: '#be123c', light: '#fde8ec' },
};

export const FONTS = {
  inter: { label: 'Inter (Default)', family: "'Inter', 'Segoe UI', Arial, sans-serif" },
  system: { label: 'System UI', family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" },
  serif: { label: 'Serif', family: "Georgia, 'Times New Roman', serif" },
  mono: { label: 'Monospace', family: "'Consolas', 'Menlo', monospace" },
};

export const MODES = {
  both: { label: 'Both (Default)', sub: 'Show Speech-to-Text and Text-to-Speech together' },
  speech_to_text: { label: 'Speech to Text only', sub: 'Start on the transcription workspace' },
  text_to_speech: { label: 'Text to Speech only', sub: 'Start on the TTS Studio' },
};

export function themeVars(themeColor) {
  const t = THEMES[themeColor] || THEMES.indigo;
  return { '--d-primary': t.primary, '--d-primary-dark': t.dark, '--d-primary-light': t.light };
}

export function fontFamily(fontStyle) {
  return (FONTS[fontStyle] || FONTS.inter).family;
}

import { LanguageInfo } from '../types.js';

/**
 * Language code to full name mapping
 */
const LANGUAGE_NAMES: Record<string, string> = {
  cmn: 'Chinese',
  eng: 'English',
  jpn: 'Japanese',
  kor: 'Korean',
  fra: 'French',
  deu: 'German',
  spa: 'Spanish',
  ita: 'Italian',
  rus: 'Russian',
  ara: 'Arabic',
};

/**
 * Parse language information from SRT filename
 * Examples:
 *   - "video.eng-cmn.srt" -> { firstLang: "eng", secondLang: "cmn", ... }
 *   - "video.cmn-eng.srt" -> { firstLang: "cmn", secondLang: "eng", ... }
 *   - "test.srt" -> null (not bilingual)
 */
export function detectLanguagesFromFilename(filename: string): LanguageInfo | null {
  // Match pattern: {lang1}-{lang2}.srt
  const match = filename.match(/\.([a-z]{3})-([a-z]{3})\.srt$/i);

  if (!match) {
    return null;
  }

  const firstLang = match[1].toLowerCase();
  const secondLang = match[2].toLowerCase();

  return {
    firstLang,
    secondLang,
    firstLangName: LANGUAGE_NAMES[firstLang] || firstLang.toUpperCase(),
    secondLangName: LANGUAGE_NAMES[secondLang] || secondLang.toUpperCase(),
  };
}

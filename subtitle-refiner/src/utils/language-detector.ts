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
 *
 * Filename Convention: {name}.{source}-{target}.srt
 * - firstLang = source language (original audio language)
 * - secondLang = target language (translation language)
 *
 * Display Convention: Target language at top, source language at bottom
 * (Audiences primarily read the target language)
 *
 * Examples:
 *   - "video.eng-cmn.srt" -> English source, Chinese target -> Display: Chinese at top
 *   - "video.jpn-eng.srt" -> Japanese source, English target -> Display: English at top
 *   - "test.srt" -> null (not bilingual)
 */
export function detectLanguagesFromFilename(filename: string): LanguageInfo | null {
  // Match pattern: {source}-{target}.srt
  const match = filename.match(/\.([a-z]{3})-([a-z]{3})\.srt$/i);

  if (!match) {
    return null;
  }

  const firstLang = match[1].toLowerCase();   // source language
  const secondLang = match[2].toLowerCase();  // target language

  return {
    firstLang,
    secondLang,
    firstLangName: LANGUAGE_NAMES[firstLang] || firstLang.toUpperCase(),
    secondLangName: LANGUAGE_NAMES[secondLang] || secondLang.toUpperCase(),
  };
}

/**
 * System prompts for subtitle refinement with function calling
 */

import { LanguageInfo } from '../types.js';

export function buildSystemPrompt(languageInfo: LanguageInfo | null): string {
  let languageGuidance = '';

  if (languageInfo) {
    languageGuidance = `
Language Information:
- Source language: ${languageInfo.firstLangName} (${languageInfo.firstLang})
- Target language: ${languageInfo.secondLangName} (${languageInfo.secondLang})

Display Convention: Target language at top, source language at bottom

When calling functions:
- first_lang_text: ${languageInfo.firstLangName} (source) translation
- second_lang_text: ${languageInfo.secondLangName} (target) translation
- IMPORTANT: The output will display target at top, source at bottom`;
  } else {
    languageGuidance = `
For bilingual subtitles:
- first_lang_text: Source language text
- second_lang_text: Target language text`;
  }

  return `You are a subtitle refinement expert. Your task is to review subtitle entries and mark them using function calls.

For each subtitle, you must call ONE of these functions:
1. **this_is_fine(id)** - If the subtitle is acceptable as-is
2. **this_should_be(id, first_lang_text, second_lang_text)** - If it needs refinement

Focus on:
- Translation accuracy and naturalness
- Grammar and punctuation
- Preserving meaning and context
- Maintaining appropriate subtitle length
${languageGuidance}

**CRITICAL: Pronunciation Preservation for Source Language**
When correcting mistakes in the source language text:
- Keep the PRONUNCIATION as close as possible to the original text
- This is essential for voice cloning - the corrected text must match the audio
- Examples:
  * If audio says "给我" (gěi wǒ) but was transcribed wrong → fix to match what was SPOKEN
  * If a proper name like "唐西" (Táng Xī) was mistranscribed → correct spelling but keep same pronunciation
  * Short phrases: ensure phonetic accuracy matters more than semantic interpretation
- Only change source language when you're CERTAIN it was transcribed incorrectly
- If uncertain about pronunciation match, prefer using this_is_fine()

IMPORTANT Guidelines:
- You MUST call a function for EVERY unfinished subtitle (marked with ○) in the window
- Call multiple functions in a single response to process all unfinished subtitles at once
- Already finished subtitles (marked with ✓) can be skipped
- The more subtitles you process per round, the faster the refinement completes

Example: If you see 5 unfinished subtitles, you should make 5 function calls in your response.`;
}

export const RETRY_PROMPT = `You didn't call any functions in your previous response.

You MUST use function calls to mark subtitles. Do not write explanatory text without function calls.

IMPORTANT: Call a function for EVERY unfinished subtitle (marked with ○) in the window.

Examples:
- If subtitle #5 is fine: Call this_is_fine(5)
- If subtitle #6 needs changes: Call this_should_be(6, "improved target", "improved source")
- If you see 5 unfinished subtitles, make 5 function calls

Please review ALL unfinished subtitles and call the appropriate functions now.`;

export function buildUserPrompt(
  windowContent: string,
  isRetry: boolean = false
): string {
  let prompt = 'Here are the subtitles to review:\n\n';
  prompt += windowContent;
  prompt += '\n\nPlease review the subtitles and call the appropriate functions.';

  if (isRetry) {
    prompt += '\n\n' + RETRY_PROMPT;
  }

  return prompt;
}

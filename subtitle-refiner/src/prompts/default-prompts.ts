/**
 * System prompts for subtitle refinement with function calling
 */

import { LanguageInfo } from '../types.js';

export function buildSystemPrompt(languageInfo: LanguageInfo | null): string {
  let languageGuidance = '';

  if (languageInfo) {
    languageGuidance = `
Language Information:
- First line: ${languageInfo.firstLangName} (${languageInfo.firstLang})
- Second line: ${languageInfo.secondLangName} (${languageInfo.secondLang})

When calling functions:
- first_lang_text: ${languageInfo.firstLangName} translation
- second_lang_text: ${languageInfo.secondLangName} translation
- IMPORTANT: Always return languages in this exact order`;
  } else {
    languageGuidance = `
For bilingual subtitles:
- first_lang_text: First line language
- second_lang_text: Second line language`;
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

Guidelines:
- Review subtitles and call functions for those that need attention
- You can refine subtitles multiple times if you see room for improvement

Make function calls for the subtitles you want to mark or refine.`;
}

export const RETRY_PROMPT = `You didn't call any functions in your previous response.

You MUST use function calls to mark subtitles. Do not write explanatory text without function calls.

Examples:
- If subtitle #5 is fine: Call this_is_fine(5)
- If subtitle #6 needs changes: Call this_should_be(6, "improved target", "improved source")

Please review the subtitles and call the appropriate functions now.`;

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

import { Subtitle, SubtitleWithState, SubtitleState, LanguageInfo } from '../types.js';

/**
 * Manages subtitle processing state
 */
export class SubtitleStateManager {
  private subtitles: SubtitleWithState[];
  private languageInfo: LanguageInfo | null;

  constructor(subtitles: Subtitle[] | SubtitleWithState[], languageInfo: LanguageInfo | null = null) {
    this.languageInfo = languageInfo;

    // Check if subtitles already have state (from checkpoint)
    const firstSub = subtitles[0] as any;
    const hasState = firstSub && 'state' in firstSub;

    if (hasState) {
      // Preserve existing state (checkpoint restore)
      this.subtitles = subtitles as SubtitleWithState[];
    } else {
      // Initialize all subtitles as unfinished (new run)
      this.subtitles = subtitles.map((sub) => ({
        ...sub,
        state: 'unfinished' as SubtitleState,
      }));
    }
  }

  /**
   * Get language info
   */
  getLanguageInfo(): LanguageInfo | null {
    return this.languageInfo;
  }

  /**
   * Get all subtitles with state
   */
  getAll(): SubtitleWithState[] {
    return this.subtitles;
  }

  /**
   * Alias for getAll() - used by checkpoint system
   */
  getAllWithState(): SubtitleWithState[] {
    return this.subtitles;
  }

  /**
   * Get subtitle by index (1-based)
   */
  get(index: number): SubtitleWithState | undefined {
    return this.subtitles[index - 1];
  }

  /**
   * Mark subtitle as finished without changes
   * Returns true only if it was previously unfinished
   */
  markFine(index: number): boolean {
    const sub = this.get(index);
    if (!sub) return false;

    // Only count as progress if it was previously unfinished
    if (sub.state === 'finished') return false;

    sub.state = 'finished';
    return true;
  }

  /**
   * Mark subtitle as finished with refined text
   * Always outputs: target language at top (line1), source language at bottom (line2)
   * Convention: Filename {source}-{target}.srt, display target first
   */
  markRefined(index: number, firstLangText: string, secondLangText: string): boolean {
    const sub = this.get(index);
    if (!sub) return false;

    // Convention: firstLang=source, secondLang=target
    // Display: target at top (line1), source at bottom (line2)
    // So: line1 = secondLangText (target), line2 = firstLangText (source)
    const line1 = secondLangText; // target language (displayed at top)
    const line2 = firstLangText;  // source language (displayed at bottom)

    sub.state = 'finished';
    sub.refined = { firstLangText, secondLangText };
    sub.text = `${line1}\n${line2}`;
    sub.lines = [line1, line2];
    return true;
  }

  /**
   * Find index of first unfinished subtitle (1-based index)
   * Returns -1 if all finished
   */
  findFirstUnfinished(): number {
    const index = this.subtitles.findIndex((sub) => sub.state === 'unfinished');
    return index === -1 ? -1 : index + 1;
  }

  /**
   * Get finished count
   */
  getFinishedCount(): number {
    return this.subtitles.filter((sub) => sub.state === 'finished').length;
  }

  /**
   * Get refined count (finished with changes)
   */
  getRefinedCount(): number {
    return this.subtitles.filter((sub) => sub.refined).length;
  }

  /**
   * Check if all subtitles are finished
   */
  isAllFinished(): boolean {
    return this.findFirstUnfinished() === -1;
  }

  /**
   * Get subtitles in range (1-based, inclusive)
   */
  getRange(start: number, end: number): SubtitleWithState[] {
    const startIdx = Math.max(0, start - 1);
    const endIdx = Math.min(this.subtitles.length, end);
    return this.subtitles.slice(startIdx, endIdx);
  }

  /**
   * Get total count
   */
  getTotalCount(): number {
    return this.subtitles.length;
  }

  /**
   * Export to plain Subtitle array (with refined text applied)
   */
  export(): Subtitle[] {
    return this.subtitles.map((sub) => ({
      index: sub.index,
      start: sub.start,
      end: sub.end,
      text: sub.text,
      lines: sub.lines,
    }));
  }
}

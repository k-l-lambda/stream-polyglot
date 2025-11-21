import { Subtitle } from '../types.js';

/**
 * Parse SRT timestamp to seconds
 * Format: "00:00:04,354" -> 4.354
 */
export function parseTimestamp(timestamp: string): number {
  const parts = timestamp.split(':');
  const hours = parseInt(parts[0], 10);
  const minutes = parseInt(parts[1], 10);
  const secondsParts = parts[2].split(',');
  const seconds = parseInt(secondsParts[0], 10);
  const milliseconds = parseInt(secondsParts[1], 10);

  return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000;
}

/**
 * Format seconds to SRT timestamp
 * 4.354 -> "00:00:04,354"
 */
export function formatTimestamp(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);

  return `${hours.toString().padStart(2, '0')}:${minutes
    .toString()
    .padStart(2, '0')}:${secs.toString().padStart(2, '0')},${ms
    .toString()
    .padStart(3, '0')}`;
}

/**
 * Parse SRT file content into structured subtitle array
 */
export function parseSRT(content: string): Subtitle[] {
  const subtitles: Subtitle[] = [];
  const blocks = content.trim().split(/\n\s*\n/);

  for (const block of blocks) {
    const lines = block.trim().split('\n');
    if (lines.length < 3) continue;

    const index = parseInt(lines[0], 10);
    if (isNaN(index)) continue;

    const timingLine = lines[1];
    const timingMatch = timingLine.match(/(\S+)\s*-->\s*(\S+)/);
    if (!timingMatch) continue;

    const start = parseTimestamp(timingMatch[1]);
    const end = parseTimestamp(timingMatch[2]);

    // Join remaining lines as text (preserve newlines for bilingual)
    const text = lines.slice(2).join('\n');
    const textLines = lines.slice(2);

    subtitles.push({
      index,
      start,
      end,
      text,
      lines: textLines,
    });
  }

  return subtitles;
}

/**
 * Generate SRT file content from subtitle array
 */
export function generateSRT(subtitles: Subtitle[]): string {
  return subtitles
    .map((sub) => {
      const timingLine = `${formatTimestamp(sub.start)} --> ${formatTimestamp(
        sub.end
      )}`;
      return `${sub.index}\n${timingLine}\n${sub.text}\n`;
    })
    .join('\n');
}

/**
 * Detect if subtitles are bilingual (have 2 lines per entry)
 */
export function isBilingual(subtitles: Subtitle[]): boolean {
  if (subtitles.length === 0) return false;

  // Check first few subtitles
  const sample = subtitles.slice(0, Math.min(5, subtitles.length));
  const bilingualCount = sample.filter(
    (sub) => sub.lines && sub.lines.length === 2
  ).length;

  return bilingualCount / sample.length >= 0.8; // 80% threshold
}

/**
 * Extract bilingual lines from subtitle text
 * Returns [targetLanguage, sourceLanguage]
 */
export function extractBilingualLines(subtitle: Subtitle): [string, string] {
  if (subtitle.lines && subtitle.lines.length === 2) {
    return [subtitle.lines[0], subtitle.lines[1]];
  }
  return [subtitle.text, ''];
}

/**
 * Create subtitle from bilingual lines
 */
export function createBilingualSubtitle(
  original: Subtitle,
  targetLine: string,
  sourceLine: string
): Subtitle {
  return {
    ...original,
    text: `${targetLine}\n${sourceLine}`,
    lines: [targetLine, sourceLine],
  };
}

import { LLMProvider } from '../../types.js';
import { OpenAIProvider } from './openai.js';

export function createProvider(
  providerName: string,
  config: {
    openaiKey?: string;
    openaiModel?: string;
    openaiBaseURL?: string;
  }
): LLMProvider {
  switch (providerName.toLowerCase()) {
    case 'openai':
      if (!config.openaiKey) {
        throw new Error('OPENAI_API_KEY is required for OpenAI provider');
      }
      return new OpenAIProvider(
        config.openaiKey,
        config.openaiModel || 'gpt-4-turbo-preview',
        config.openaiBaseURL
      );

    default:
      throw new Error(
        `Unknown provider: ${providerName}. Currently only 'openai' is supported with function calling.`
      );
  }
}

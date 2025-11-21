import OpenAI from 'openai';
import { LLMProvider, SubtitleWindow, FunctionCall } from '../../types.js';
import { logger } from '../../utils/logger.js';
import { getOpenAITools } from '../../utils/function-tools.js';
import { formatWindowForLLM } from '../../utils/window.js';
import { buildUserPrompt } from '../../prompts/default-prompts.js';

export class OpenAIProvider implements LLMProvider {
  private client: OpenAI;
  private model: string;

  constructor(apiKey: string, model: string = 'gpt-4-turbo-preview', baseURL?: string) {
    this.client = new OpenAI({
      apiKey,
      baseURL: baseURL || undefined,
    });
    this.model = model;
  }

  getName(): string {
    return `OpenAI ${this.model}`;
  }

  supportsFunctionCalling(): boolean {
    return true;
  }

  async refine(
    window: SubtitleWindow,
    systemPrompt: string,
    isRetry: boolean = false
  ): Promise<FunctionCall[]> {
    try {
      const windowContent = formatWindowForLLM(window);
      const userPrompt = buildUserPrompt(windowContent, isRetry);

      logger.debug(`Sending request to OpenAI (${this.model})`);
      logger.debug(`Window: ${window.windowStartIndex}-${window.windowEndIndex}`);
      logger.debug(`Unfinished: ${window.unfinishedCount}`);
      if (isRetry) {
        logger.debug(`RETRY mode: Adding retry prompt to user message`);
      }

      const requestPayload: any = {
        model: this.model,
        messages: [
          {
            role: 'system',
            content: systemPrompt,
          },
          {
            role: 'user',
            content: userPrompt,
          },
        ],
        tools: getOpenAITools(),
        tool_choice: 'auto',
      };

      // gpt-5-mini has beta limitations: no custom temperature
      if (!this.model.includes('gpt-5-mini')) {
        requestPayload.temperature = 0.3;
      }

      logger.debug(`Request payload: ${JSON.stringify(requestPayload, null, 2)}`);

      const response = await this.client.chat.completions.create(requestPayload);

      const message = response.choices[0]?.message;
      if (!message) {
        throw new Error('No response from OpenAI');
      }

      // Extract function calls
      const functionCalls: FunctionCall[] = [];

      if (message.tool_calls && message.tool_calls.length > 0) {
        for (const toolCall of message.tool_calls) {
          if (toolCall.type === 'function') {
            const name = toolCall.function.name as 'this_is_fine' | 'this_should_be';
            const args = JSON.parse(toolCall.function.arguments);

            logger.debug(`Raw args: ${JSON.stringify(args)}`);

            functionCalls.push({
              name,
              arguments: {
                id: args.id,
                first_lang_text: args.first_lang_text,
                second_lang_text: args.second_lang_text,
              },
            });

            logger.debug(`Function call: ${name}(${args.id}${args.first_lang_text ? `, "${args.first_lang_text.substring(0, 20)}..."` : ''}${args.second_lang_text ? `, "${args.second_lang_text.substring(0, 20)}..."` : ''})`);
          }
        }
      }

      logger.debug(`Received ${functionCalls.length} function calls`);

      return functionCalls;
    } catch (error) {
      if (error instanceof Error) {
        logger.error(`OpenAI API error: ${error.message}`);
        logger.error(`Error details: ${JSON.stringify(error, null, 2)}`);
      }
      throw error;
    }
  }
}

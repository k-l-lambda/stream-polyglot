/**
 * Function calling tools for LLM
 */

export interface FunctionTool {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: {
      type: 'object';
      properties: Record<string, any>;
      required: string[];
    };
  };
}

/**
 * Tool 1: this_is_fine - Mark subtitle as acceptable
 */
export const THIS_IS_FINE_TOOL: FunctionTool = {
  type: 'function',
  function: {
    name: 'this_is_fine',
    description: 'Mark this subtitle as acceptable with no changes needed',
    parameters: {
      type: 'object',
      properties: {
        id: {
          type: 'number',
          description: 'Subtitle index number',
        },
      },
      required: ['id'],
    },
  },
};

/**
 * Tool 2: this_should_be - Refine subtitle text
 */
export const THIS_SHOULD_BE_TOOL: FunctionTool = {
  type: 'function',
  function: {
    name: 'this_should_be',
    description: 'Refine this subtitle with improved translation',
    parameters: {
      type: 'object',
      properties: {
        id: {
          type: 'number',
          description: 'Subtitle index number',
        },
        first_lang_text: {
          type: 'string',
          description: 'First line language text (refined)',
        },
        second_lang_text: {
          type: 'string',
          description: 'Second line language text (refined)',
        },
      },
      required: ['id', 'first_lang_text', 'second_lang_text'],
    },
  },
};

/**
 * All available tools
 */
export const FUNCTION_TOOLS: FunctionTool[] = [
  THIS_IS_FINE_TOOL,
  THIS_SHOULD_BE_TOOL,
];

/**
 * Get tools in OpenAI format
 */
export function getOpenAITools(): any[] {
  return FUNCTION_TOOLS;
}

/**
 * Get tools in Claude format
 */
export function getClaudeTools(): any[] {
  return FUNCTION_TOOLS.map((tool) => ({
    name: tool.function.name,
    description: tool.function.description,
    input_schema: tool.function.parameters,
  }));
}

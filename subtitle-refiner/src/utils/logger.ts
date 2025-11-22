import chalk from 'chalk';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

class Logger {
  private level: LogLevel;
  private verbose: boolean;

  constructor(level: LogLevel = 'info', verbose: boolean = false) {
    this.level = level;
    this.verbose = verbose;
  }

  setVerbose(verbose: boolean) {
    this.verbose = verbose;
  }

  debug(message: string) {
    if (this.verbose) {
      console.log(chalk.gray(`[DEBUG] ${message}`));
    }
  }

  info(message: string) {
    console.log(chalk.blue(`ℹ ${message}`));
  }

  success(message: string) {
    console.log(chalk.green(`✓ ${message}`));
  }

  warn(message: string) {
    console.log(chalk.yellow(`⚠ ${message}`));
  }

  error(message: string) {
    console.log(chalk.red(`✗ ${message}`));
  }

  progress(message: string) {
    console.log(chalk.cyan(`→ ${message}`));
  }

  header(message: string) {
    console.log();
    console.log(chalk.bold.white(message));
  }

  separator() {
    console.log(chalk.gray('─'.repeat(60)));
  }
}

export const logger = new Logger();

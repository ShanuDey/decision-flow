export interface RetryOptions {
  attempts?: number;
  delayMs?: number;
  sleep?: (ms: number) => Promise<void>;
  onRetry?: (error: unknown, attempt: number) => void;
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export async function retry<T>(work: () => Promise<T>, options: RetryOptions = {}): Promise<T> {
  const { attempts = 6, delayMs = 1000, sleep = wait, onRetry } = options;
  for (let attempt = 1; ; attempt++) {
    try {
      return await work();
    } catch (error) {
      if (attempt >= attempts) throw error;
      onRetry?.(error, attempt);
      await sleep(delayMs * 2 ** (attempt - 1));
    }
  }
}

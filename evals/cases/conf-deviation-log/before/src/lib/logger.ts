export type Fields = Record<string, unknown>;
export type Sink = (line: string) => void;

export interface Logger {
  info(event: string, fields?: Fields): void;
  warn(event: string, fields?: Fields): void;
  error(event: string, fields?: Fields): void;
}

export function createLogger(sink: Sink = (line) => process.stdout.write(line + "\n")): Logger {
  const write = (level: string, event: string, fields: Fields = {}) =>
    sink(JSON.stringify({ level, event, ...fields, ts: new Date().toISOString() }));
  return {
    info: (event, fields) => write("info", event, fields),
    warn: (event, fields) => write("warn", event, fields),
    error: (event, fields) => write("error", event, fields),
  };
}

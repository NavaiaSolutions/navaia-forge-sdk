/**
 * Error classes for the NavaiaForge SDK.
 *
 * All SDK errors extend {@link NavaiaForgeError} so callers can catch
 * them with a single type guard.
 */

/** Base error for all NavaiaForge SDK errors. */
export class NavaiaForgeError extends Error {
  public readonly statusCode: number;

  constructor(statusCode: number, message: string) {
    super(message);
    this.name = "NavaiaForgeError";
    this.statusCode = statusCode;
  }
}

/** Thrown when authentication fails (401). */
export class AuthenticationError extends NavaiaForgeError {
  constructor(message = "Invalid or missing API key") {
    super(401, message);
    this.name = "AuthenticationError";
  }
}

/** Thrown when the caller lacks permission (403). */
export class PermissionError extends NavaiaForgeError {
  constructor(message = "Permission denied") {
    super(403, message);
    this.name = "PermissionError";
  }
}

/** Thrown when a resource is not found (404). */
export class NotFoundError extends NavaiaForgeError {
  constructor(message = "Resource not found") {
    super(404, message);
    this.name = "NotFoundError";
  }
}

/** Thrown when the rate limit is exceeded (429). */
export class RateLimitError extends NavaiaForgeError {
  constructor(message = "Rate limit exceeded") {
    super(429, message);
    this.name = "RateLimitError";
  }
}

/** Thrown when a polling operation exceeds its timeout. */
export class TimeoutError extends NavaiaForgeError {
  constructor(message: string) {
    super(0, message);
    this.name = "TimeoutError";
  }
}

/**
 * Map an HTTP status code to the appropriate error class.
 *
 * @internal
 */
export function errorFromStatus(
  statusCode: number,
  message: string,
): NavaiaForgeError {
  switch (statusCode) {
    case 401:
      return new AuthenticationError(message);
    case 403:
      return new PermissionError(message);
    case 404:
      return new NotFoundError(message);
    case 429:
      return new RateLimitError(message);
    default:
      return new NavaiaForgeError(statusCode, message);
  }
}

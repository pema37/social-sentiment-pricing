// frontend/sentry.server.config.ts
import * as Sentry from "@sentry/nextjs";

function stripPii(event: Sentry.ErrorEvent): Sentry.ErrorEvent {
  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
  const shopDomainRegex = /[a-zA-Z0-9-]+\.myshopify\.com/g;
  const tokenRegex = /Bearer\s+[A-Za-z0-9._~+/=-]+|shpat_[A-Za-z0-9]+|shpua_[A-Za-z0-9]+|eyJ[A-Za-z0-9._-]+/g;

  const redact = (str: string): string =>
    str
      .replace(emailRegex, "[REDACTED_EMAIL]")
      .replace(shopDomainRegex, "[REDACTED_SHOP]")
      .replace(tokenRegex, "[REDACTED_TOKEN]");

  if (event.exception?.values) {
    for (const ex of event.exception.values) {
      if (ex.value) ex.value = redact(ex.value);
    }
  }

  if (event.breadcrumbs) {
    for (const bc of event.breadcrumbs) {
      if (bc.message) bc.message = redact(bc.message);
      if (bc.data) {
        for (const key of Object.keys(bc.data)) {
          if (typeof bc.data[key] === "string") {
            bc.data[key] = redact(bc.data[key]);
          }
        }
      }
    }
  }

  if (event.request) {
    if (event.request.url) event.request.url = redact(event.request.url);
    if (event.request.query_string)
      event.request.query_string = redact(event.request.query_string);
    if (event.request.headers) {
      delete event.request.headers["Authorization"];
      delete event.request.headers["Cookie"];
    }
  }

  if (event.user) {
    event.user = { id: event.user.id };
  }

  return event;
}

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 0.1,
  enabled: process.env.NODE_ENV === "production",
  environment: process.env.NODE_ENV,
  beforeSend: stripPii,
});

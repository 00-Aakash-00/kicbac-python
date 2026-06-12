# Security policy

The Kicbac Python SDK is security-sensitive because it signs requests, handles payment tokens, verifies webhooks, and redacts gateway data.

## Reporting a vulnerability

Do not open a public issue for suspected vulnerabilities. Email the Kicbac maintainers with the affected version, reproduction steps, and impact. Remove security keys, webhook signing keys, card data, and bank data from all reports.

## Integration rules

- Tokenize with Kicbac.js or a Kicbac frontend SDK. Do not build server-side raw card forms.
- Keep `KICBAC_SECURITY_KEY` and webhook signing keys in server-side secret stores.
- Treat declines as typed results. `response=2` is not an exception.
- Verify webhooks from exact raw bytes with `Webhook-Signature: t=<nonce>,s=<sig>`.
- Never commit real keys, raw PANs, bank account numbers, or unscrubbed cassettes.

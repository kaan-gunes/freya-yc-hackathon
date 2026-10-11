# Core final bank mock

This Worker serves the final pack's 34 synthetic customers. It is separate from
the generic builder. The seven POST routes are under `/voice/v1/`, as required by
the 1 October service contract. `test-customers.json` is copied without changes
from the final pack. Every selected fixture retains its HTTP status and response
body, including the one 12-second delay. Unknown keys use the service's documented
404, or `INVALID_ARGUMENTS_ERROR` with HTTP 400 where no 404 is defined.

Live origin: `https://core-freya-final.hamitarsln09.workers.dev`.
Published Worker version: `5b33bf32-04e3-4181-8c8e-0d8bd016a731`.
The local and deployed suites both passed all 617 fixture responses plus invalid
request and unknown-key checks. The deployed suite took 20.18 seconds, including
the required 12-second delay.
Fixture SHA-256: `d6ce155638f61ab17910d53ea993a2b0d68cf4e10d6b9db2fb8e4a7add0ef44d`.

```sh
cd final-mock
npm test
npm run deploy
MOCK_BASE_URL=https://core-freya-final.YOUR-SUBDOMAIN.workers.dev npm test
```

Use the Worker origin as the builder's `--mock-url`. The extracted contract keeps
the complete source paths `/voice/v1/cards.list`, `/voice/v1/cards.balance`, etc.
The final tools must resolve to `https://WORKER/voice/v1/SERVICE`.
`GET /health` reports readiness.

Tokens, headers, call metadata and `aiFlow` are ignored in the test environment,
as the pack requires. Missing required service fields still produce HTTP 400.
Calls are deterministic fixture lookups; no real bank, e-mail or customer data
is involved.

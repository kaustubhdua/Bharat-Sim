# Category-aware risk planner

The planner is deterministic and explainable. It is not an LLM and its risk score is a test-ordering heuristic, not a predicted probability of failure.

## Inputs

- One or more known BharatSim persona IDs (the dashboard currently plans for the selected persona).
- An application category: general, e-commerce, fintech/banking, social, education, delivery/mobility, or media/streaming.
- Up to 10 critical user journeys. The API normalizes whitespace, removes case-insensitive duplicates, and truncates each journey to 80 characters. An empty list falls back to generic journeys.
- A requested maximum scenario count (1–20).

The dashboard supplies category-specific journey presets. Developers can edit them before generating the plan.

## Scoring

Each persona/flow scenario starts at 25 points. The deterministic heuristic then adds:
- +25 for a critical persona, or +15 for a high-risk persona.
- +15 when the journey contains a keyword associated with the selected application category.
- +10 when the persona's profile specifies less than 300 MB free storage.
- Up to +25 from the strongest pairwise condition interaction on that persona.

The final score is capped at 100 and scenarios are sorted by score, then stable scenario ID. These numbers order tests; they are not probabilities or user-population impact estimates.

## Category keywords

- General: network, retry, payment, login.
- E-commerce: checkout, cart, order, payment, inventory, product, search.
- Fintech: payment, transfer, UPI, balance, authentication, login, statement.
- Social: feed, message, chat, upload, image, notification, video.
- Education: course, lesson, video, quiz, download, sync, assignment.
- Delivery/mobility: location, map, tracking, order, payment, address, route.
- Media/streaming: playback, stream, video, audio, buffer, download, offline.

A keyword match is a prioritization hint only. It does not prove the flow exists in the APK, execute it, or establish a failure.

## Interaction hypotheses

The planner enumerates pairs of authored persona conditions and attaches hypotheses such as high latency × limited bandwidth. These are candidate experiments. The dashboard explicitly states that the plan does not execute tests; the developer must run the selected conditions on a disposable target and compare them with single-condition baselines.

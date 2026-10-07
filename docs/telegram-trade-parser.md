# Telegram Trade Parser

The existing FYERS Trade Parser and its WhatsApp queue retain their route. The separate Telegram Trade Parser accepts pasted text or new channel posts and routes each ticket to explicitly selected FYERS or Delta Exchange India.

## Connect

Use a dedicated Telegram bot with membership/access to the chosen channel. Enter its token only in the local masked Bot token field and the channel's @username or numeric -100 ID. Save configuration, then Verify channel access. This performs getMe, getChat, getChatMember and getWebhookInfo; it does not send messages or change an existing webhook. Tokens are stored only in `.private/telegram-review.json` with owner-only permissions and never returned by status. A subscribed Telegram user account alone does not give a bot channel access. Bot API updates cover new posts/edits, not arbitrary past channel history.

## Submission

Default confirmation mode queues messages for Load recommendation → Parse recommendation → Submit order. This one deliberate Submit is the confirmation; there is no preparation step, typed phrase or modal. Broker changes or text edits invalidate the parsed ticket. Tickets expire after 120 seconds; channel recommendations expire after five minutes.

Select broker and positive whole quantity: FYERS lots or Delta contracts. Delta matches exact listed symbols without automatic ATM mapping. Limit and stop-limit entries use native broker terms. Delta stop-limit triggers use last-traded price, a tick-aligned trigger beyond the current executable quote, and a limit one tick beyond the trigger in Auto. Broker authentication, fresh executable quotes, contract metadata, wallet/funds gates, pending-order/position guards and native validations run before submission. A held/running Delta strategy blocks Telegram entries and is never adopted or changed. Recommendation stop/targets are displayed as a plan; protective exits are not automatically created by this parser.

Auto submission is default off. Checking it and deliberately starting configured polling authorizes new actionable channel recommendations to submit to the selected broker and quantity without per-order confirmation. Startup drains the pending update backlog as review records before arming Auto. Explicit BUY/SELL/SHORT, complete parsing, exact contract and fresh original message timestamp are required. Duplicate channel/message IDs and edits do not automatically resubmit. Ambiguous, expired or invalid messages remain blocked with diagnostics. Broker acceptance is not a fill. Queue responses include broker order/filled quantity where available; Refresh broker order status reconciles attributed Delta request IDs or exact FYERS order IDs and trade snapshots. Unknown outcomes are never blindly retried.

Polling and Auto never resume on application restart. Stop polling disables future discovery/submission; it does not cancel already accepted broker orders. Existing held positions are unaffected.

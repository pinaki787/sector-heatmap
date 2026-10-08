# Sector Pulse broker and workspace boundaries

The supported trading brokers are FYERS and Delta India. Indian-market sector
analysis, Analysis Handoff and FYERS execution retain the FYERS boundary. Delta
India uses its separate authenticated adapter and India endpoint. There is no
automatic substitution between these brokers and no other broker execution route.

The opt-in user setup portal supports multiple users and multiple broker accounts
per user. Every account has an isolated dashboard process, source snapshot,
credential files/token cache, settings, Paper balances, journals and ownership
locks. Account dashboards verify the signed-in owner for every request and reject
mutation requests for a broker different from their registered workspace.
Administrator status permits creating users; it does not grant trading access to
another user's workspace. Setup starts no strategy and sends no order.

Each final ticket/runner retains its adapter's fresh identity, exact contract,
quotes, capital/margin, ownership, position and order reconciliation checks.
Tests use fake credentials with live gates disabled. Adding another broker
requires an explicit adapter, policy and invariant-test update.

The existing single-user dashboard is unchanged unless launched as an isolated
workspace. Authentication covers provisioned workspace dashboards, not an
independently running legacy localhost service. This local feature is not a
public Internet hosting configuration. See docs/multi-user-broker-setup.md.

# Analysis Handoff linked exits

New FYERS equity and single bought-option tickets include native takeProfit and stopLoss point offsets with legType=1. All single and batch submission paths use the reviewed protection. Equity levels are rounded toward entry, never widening the requested stop. Bought-option premium levels use the existing constant-IV mapping from fresh underlying quotes; these are estimates, not guaranteed exits at underlying levels.

Dhan cash entries now request native Super Orders with absolute targetPrice and stopLossPrice. Existing Dhan bought-option Super Orders remain intact. Missing or invalid levels fail before order submission. Changed reviewed exits require a replacement preview. Partial-target cash plans remain unsupported; no synthetic independent sell orders are created.

Acknowledgement and entry fill do not confirm active protective legs. Responses and previews retain that distinction. Existing orders and positions are not retrofitted. Native option tickets outside the Analysis Handoff route and multi-leg spreads retain their existing behavior.

Validation: 62 focused mocked tests cover single/batch payloads, cash long/short rounding, option mapping, changed protection, broker rejection, uncertain submission, and reconciliation. No real order was submitted. JavaScript syntax passed. Worker reload and served preview validation remain pending because the current Dhan Live runner is active and the FYERS Paper runner holds a position.

References:
- https://github.com/FyersDev/fyers-go-sdk/blob/master/models.go (OrderRequest native offsets)
- https://dhanhq.co/docs/v2/super-order/ (absolute linked exit prices)

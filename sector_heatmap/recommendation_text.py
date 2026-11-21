"""Broker-independent recommendation extraction; no execution."""
import re

def parse_text(text):
    """Parse a pasted human recommendation into a *non-executable* review ticket.

    This intentionally does not create an order preview.  A message can be
    incomplete or refer to more than one active option expiry, so a parser
    result is useful only after an exact FYERS-master match is established.
    """
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Paste a trade recommendation to parse.")
    if len(raw) > 12_000:
        raise ValueError("Trade recommendation text is limited to 12,000 characters.")
    normalized = re.sub(r"\s+", " ", raw.upper())
    action_match = re.search(r"\b(BUY|SELL|SHORT)\b", normalized)
    # Advisory messages often omit an action; the agreed parser default is
    # BUY, while an explicit SELL or SHORT always overrides it.
    action = {"SHORT": "SELL"}.get(action_match.group(1), action_match.group(1)) if action_match else "BUY"
    # Common advisor format: "MCX CRUDEOIL 17-SEP CE 9100".  It puts
    # expiry and option side before the strike, unlike broker symbols.
    dated_option_match = re.search(r"\b(?:MCX\s+)?([A-Z][A-Z0-9& .-]{0,30}?)\s+(\d{1,2})[-\s]+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(?:[-\s]+(\d{2,4}))?\s+(CE|PE|C|P|CALL|PUT)\s+(\d{3,7}(?:\.\d+)?)\b", normalized)
    side_before_strike_match = re.search(r"\b(?:MCX\s+)?([A-Z][A-Z0-9& .-]{0,30}?)\s+(CE|PE|C|P|CALL|PUT)\s+(\d{3,7}(?:\.\d+)?)\b", normalized)
    option_match = re.search(r"\b([A-Z][A-Z0-9& .-]{0,38}?)\s+(\d{3,7}(?:\.\d+)?)\s*(CE|PE|C|P|CALL|PUT)\b", normalized)
    option_type = None
    underlying = None
    strike = None
    if dated_option_match:
        underlying = re.sub(r"\b(?:COMMODITY|OPTIONS?|INTRADAY|BUY|SELL|SHORT|MCX|TRADE)\b", "", dated_option_match.group(1)).strip(" .-")
        strike = float(dated_option_match.group(6))
        option_type = {"C": "CE", "CALL": "CE", "P": "PE", "PUT": "PE"}.get(dated_option_match.group(5), dated_option_match.group(5))
    elif side_before_strike_match:
        underlying = re.sub(r"\b(?:COMMODITY|OPTIONS?|INTRADAY|BUY|SELL|SHORT|MCX|TRADE)\b", "", side_before_strike_match.group(1)).strip(" .-")
        strike = float(side_before_strike_match.group(3))
        option_type = {"C": "CE", "CALL": "CE", "P": "PE", "PUT": "PE"}.get(side_before_strike_match.group(2), side_before_strike_match.group(2))
    elif option_match:
        underlying = re.sub(r"\b(?:BUY|SELL|SHORT|TRADE|CALL|PUT)\b", "", option_match.group(1)).strip(" .-")
        strike = float(option_match.group(2))
        option_type = {"C": "CE", "CALL": "CE", "P": "PE", "PUT": "PE"}.get(option_match.group(3), option_match.group(3))
    else:
        symbols = re.findall(r"\b[A-Z][A-Z0-9&-]{1,29}\b", normalized)
        ignored = {"BUY", "SELL", "SHORT", "ENTRY", "ABOVE", "AT", "SL", "STOP", "LOSS", "TARGET", "TARGETS", "CMP", "CALL", "PUT", "NSE", "BSE", "MCX"}
        underlying = next((item for item in symbols if item not in ignored), None)

    def amount(pattern):
        match = re.search(pattern, normalized)
        return float(match.group(1)) if match else None

    entry_match = re.search(r"\b(ENTRY|ABOVE|BELOW|BREAKOUT|TRIGGER|AT|CMP)\s*(?:PRICE\s*)?(?:RS\.?\s*)?[:=@-]?\s*(\d+(?:\.\d+)?)", normalized)
    entry = float(entry_match.group(2)) if entry_match else None
    # Advisor language such as BUY ABOVE or SELL BELOW is a trigger, not an
    # immediately executable limit.  Preserve that distinction through the
    # review ticket and the eventual FYERS order payload.
    entry_instruction = "STOP_LIMIT" if entry_match and entry_match.group(1) in {"ABOVE", "BELOW", "BREAKOUT", "TRIGGER"} else "LIMIT"
    stop_loss = amount(r"\b(?:SL|STOP(?:\s+LOSS)?|STOPLOSS)\s*(?:AT\s*)?(?:RS\.?\s*)?[:=@-]?\s*(\d+(?:\.\d+)?)")
    targets = []
    for match in re.finditer(r"\b(?:(?:TARGET|TGT|TP)(?:\s*[1-9](?!\d))?|T[1-9])\s*(?:AT\s*)?(?:RS\.?\s*)?[:=@-]?\s*(\d+(?:\.\d+)?)", normalized):
        value = float(match.group(1))
        if value not in targets:
            targets.append(value)
    block = re.search(r"\b(?:TARGETS?|TGTS?)\s*(?:AT\s*)?[:=@-]?\s*([0-9.,/\- ]+)", normalized)
    if block:
        for value in re.findall(r"\d+(?:\.\d+)?", block.group(1)):
            number = float(value)
            if number not in targets:
                targets.append(number)

    expiry_hint = None
    month_names = "JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC"
    expiry_match = re.search(rf"\b(\d{{1,2}})[-\s]*({month_names})(?:[-\s]*(\d{{2,4}}))?\b", normalized)
    if expiry_match:
        expiry_hint = {"day": int(expiry_match.group(1)), "month": expiry_match.group(2), "year": expiry_match.group(3)}
    return {
        "source_text": raw, "action": action, "underlying": underlying, "option_type": option_type,
        "strike": strike, "entry": entry, "entry_instruction": entry_instruction, "stop_loss": stop_loss, "targets": targets,
        "expiry_hint": expiry_hint,
        "missing": [name for name, value in (("action", action), ("underlying", underlying), ("entry", entry), ("stop loss", stop_loss)) if value is None],
    }


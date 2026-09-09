# NIFTY conditional bear-call basket runner

This runner monitors a defined-risk bearish call spread and can submit it as one
FYERS basket request only when explicitly invoked with `--live`.

- signal: completed 15-minute NIFTY close below 23,465;
- invalidate: completed 15-minute close above 23,525;
- legs: sell 23,600 CE and buy 23,700 CE in the nearest weekly expiry;
- all prices are read fresh from FYERS, exact contracts are checked against the
  FYERS F&O master, and the result is written to `signal.json`.

Run the safe monitor with:

```sh
PYTHONPATH=. python3 strategies/nifty_call_credit_monitor/run.py
```

When the report is `ENTRY_READY`, review its expiry, symbols, limit prices, credit,
and maximum loss. The live route is:

```sh
PYTHONPATH=. python3 strategies/nifty_call_credit_monitor/run.py --live --lots 1
```

`--live` sends a single FYERS basket containing the protection buy leg first and
the short call second. It refuses to submit without a completed trigger, two-sided
quotes, matched master contracts/lot sizes, positive credit, risk below ₹5,000,
no duplicate exposure, and FYERS' live basket-margin result. FYERS can still return partial fills; the runner never
retries automatically, so reconcile both legs in FYERS immediately after a live run.

You can set both legs at runtime. For example, the prepared basket is:

```sh
PYTHONPATH=. python3 strategies/nifty_call_credit_monitor/run.py \
  --short-strike 23600 --long-strike 23700 --lots 1
```

The long-call strike must be above the short-call strike; the runner rejects the
other orientation because it would not be a defined-risk bear-call spread.

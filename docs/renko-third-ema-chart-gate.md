# Simple Brick chart rendering correction

The frontend rejected Simple Brick chart responses using the raw retained Third EMA display selection, although the backend correctly disabled the Third EMA strategy flag. The activation check now uses effectiveFamilySettings, preserving enabled indicator checks while allowing Simple Brick and disabled families to render.

Updated root and seven hosted account JavaScript sources. Five focused Node tests and JavaScript syntax validation passed. Browser refresh only; no backend reload. Hosted FYERS NIFTY50 five-minute chart visibly rendered Renko bricks, live ticks and connected orders. Active Paper runner with open position continued without intervention; settings remained PAPER, SIMPLE_BRICK, five minutes, manual29.77, target premium40. Display study preferences remain preserved. Backup .private/chart-third-ema-gate-1793937087.

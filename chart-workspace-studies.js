/* Analytical series only. These values do not drive execution. */
(function (root) {
  'use strict';

  // OHLC has no trade-by-price breakdown. Estimate it from the candle range,
  // conserving source volume and classifying direction using the candle body.
  function fixedRangeVolumeProfile(bars, rowCount = 24, valueArea = 70, tickSize, ticksPerRow, equalCloseUp = bars.length > 1) {
    if (!bars.length || bars.some(bar => ![bar.low, bar.high, bar.open, bar.close, bar.volume].every(Number.isFinite)
      || bar.high < bar.low || bar.volume < 0)) return null;
    const low = bars.reduce((min, bar) => Math.min(min, bar.low), Infinity);
    const high = bars.reduce((max, bar) => Math.max(max, bar.high), -Infinity);
    const span = high - low;
    const target = Math.max(1, Math.min(200, Math.round(rowCount) || 24));
    const tickGrid = Number.isFinite(tickSize) && tickSize > 0;
    if (ticksPerRow && !tickGrid) return {error: 'Tick size is unavailable for this symbol'};
    const ticks = tickGrid ? span / tickSize : 0;
    const countFor = size => Math.max(1, Math.ceil(ticks / size - 1e-9));
    let step = span / target;
    let count = span > 0 ? target : 1;
    if (tickGrid && span > 0) {
      const smaller = Math.max(1, Math.floor(ticks / target));
      const larger = Math.max(1, Math.ceil(ticks / target));
      const nearest = Math.abs(countFor(smaller) - target) <= Math.abs(countFor(larger) - target) ? smaller : larger;
      const size = ticksPerRow || nearest;
      count = countFor(size);
      if (count > 2000) return {error: 'Increase ticks per row to keep the profile within 2,000 rows'};
      step = size * tickSize;
    }
    const rows = Array.from({length: count}, (_, index) => ({
      low: low + index * step, high: index === count - 1 ? high : low + (index + 1) * step,
      up: 0, down: 0, volume: 0
    }));
    const rowAt = price => step > 0 ? Math.max(0, Math.min(count - 1, Math.floor((price - low) / step))) : 0;
    for (const bar of bars) {
      if (!bar.volume) continue;
      const direction = bar.close > bar.open || (equalCloseUp && bar.close === bar.open) ? 'up' : 'down';
      const first = rowAt(bar.low);
      const last = rowAt(bar.high);
      if (first === last) {
        rows[first][direction] += bar.volume;
        continue;
      }
      for (let index = first; index <= last; index++) {
        const row = rows[index];
        const overlap = Math.max(0, Math.min(bar.high, row.high) - Math.max(bar.low, row.low));
        row[direction] += bar.volume * (overlap / (bar.high - bar.low));
      }
    }
    let poc = 0;
    let total = 0;
    rows.forEach((row, index) => {
      row.volume = row.up + row.down;
      if (row.volume > rows[poc].volume) poc = index;
      total += row.volume;
    });
    if (!(total > 0)) return null;
    const budget = total * Math.min(100, Math.max(1, valueArea)) / 100;
    let first = poc;
    let last = poc;
    let included = rows[poc].volume;
    while (first > 0 || last < count - 1) {
      const below = rows[first - 1]?.volume ?? -1;
      const above = rows[last + 1]?.volume ?? -1;
      const useAbove = above > below || (above === below && last - poc <= poc - first);
      const next = useAbove ? above : below;
      if (included + next > budget + total * Number.EPSILON * 4) break;
      included += next;
      if (useAbove) last++;
      else first--;
    }
    return {rows, poc, first, last, total};
  }

  function sma(values, length) {
    let total = 0;
    return values.map((value, index) => {
      total += value;
      if (index >= length) total -= values[index - length];
      return index >= length - 1 ? total / length : null;
    });
  }

  function vwma(bars, values, length) {
    const valid = bars.map((bar, i) => Number.isFinite(bar.volume) && bar.volume >= 0 && Number.isFinite(values[i]));
    const volume = bars.map((bar, i) => valid[i] ? bar.volume : 0);
    const coverage = sma(valid.map(Number), length);
    const weights = sma(volume, length);
    const weighted = sma(values.map((value, i) => valid[i] ? value * volume[i] : 0), length);
    return weighted.map((value, i) => coverage[i] === 1 && weights[i] > 0 ? value / weights[i] : null);
  }

  function wma(values, length) {
    const denominator = length * (length + 1) / 2;
    return values.map((_, index) => {
      if (index < length - 1) return null;
      let weighted = 0;
      for (let offset = 0; offset < length; offset++) {
        weighted += values[index - offset] * (length - offset);
      }
      return weighted / denominator;
    });
  }

  function hma(values, length) {
    const half = wma(values, Math.max(1, Math.floor(length / 2)));
    const full = wma(values, length);
    const warmup = Math.min(values.length, length - 1);
    const differences = full.slice(warmup).map((value, i) => 2 * half[i + warmup] - value);
    return Array(warmup).fill(null).concat(wma(differences, Math.max(1, Math.round(Math.sqrt(length)))));
  }

  function woodiesCciValues(prices, length) {
    const result = cci(prices, length);
    let unchanged = 0, previous;
    return prices.map((price, i) => {
      unchanged = Number.isFinite(price) ? price === previous ? unchanged + 1 : 1 : 0;
      previous = price;
      return result[i] ?? (unchanged >= length ? 0 : null);
    });
  }

  function woodiesCciColors(values, inputs = {}) {
    const paint = (name, fallback) => /^#[0-9a-f]{6}(?:[0-9a-f]{2})?$/i.test(inputs[name] ?? '') ? inputs[name] : fallback;
    let side = 0, count = 0;
    return values.map(value => {
      const next = Number.isFinite(value) ? Math.sign(value) : 0;
      count = next ? next === side ? count + 1 : 1 : 0;
      side = next;
      return count >= 6 ? paint(side > 0 ? 'upColor' : 'downColor', side > 0 ? '#089981' : '#f23645')
        : count === 5 ? paint('warningColor', '#fdd835') : paint('neutralColor', '#787b86');
    });
  }

  function pringSpecialK(bars, inputs = {}) {
    const source = studyPriceSourceNames.includes(inputs.source) ? pineSources[inputs.source] : pineSources.close;
    const prices = bars.map(source);
    const components = [[10, 10, 1], [15, 10, 2], [20, 10, 3], [30, 15, 4],
      [40, 50, 1], [65, 65, 2], [75, 75, 3], [100, 100, 4],
      [195, 130, 1], [265, 130, 2], [390, 130, 3], [530, 195, 4]];
    const averages = components.map(([lookback, smoothing]) => smaWithGaps(prices.map((price, i) => {
      const prior = prices[i - lookback];
      return Number.isFinite(price) && Number.isFinite(prior) && prior !== 0
        ? 100 * (price - prior) / prior : null;
    }), smoothing));
    const special = prices.map((_, i) => averages.every(series => Number.isFinite(series[i]))
      ? averages.reduce((sum, series, j) => sum + series[i] * components[j][2], 0) : null);
    const length = key => Number.isInteger(inputs[key]) && inputs[key] >= 1 && inputs[key] <= 2000 ? inputs[key] : 100;
    const signal = smaWithGaps(smaWithGaps(special, length('signalLength1')), length('signalLength2'));
    return [special, signal];
  }

  // Fosback indices: compound close returns only on the selected volume direction.
  function volumeIndex(bars, positive, length) {
    let index = 1000, average = null, initialized = false;
    const alpha = 2 / (Math.max(1, Math.round(length) || 255) + 1);
    const values = [], signal = [];
    for (let i = 0; i < bars.length; i++) {
      const bar = bars[i], prior = bars[i - 1];
      if (!Number.isFinite(bar.close) || bar.close <= 0 || !Number.isFinite(bar.volume) || bar.volume < 0) {
        values.push(null); signal.push(null); continue;
      }
      if (initialized && prior && Number.isFinite(prior.close) && prior.close > 0
          && Number.isFinite(prior.volume) && prior.volume >= 0
          && (positive ? bar.volume > prior.volume : bar.volume < prior.volume)) {
        index *= bar.close / prior.close;
      }
      initialized = true;
      if (!Number.isFinite(index)) { values.push(null); signal.push(null); continue; }
      average = average === null ? index : average + alpha * (index - average);
      values.push(index); signal.push(average);
    }
    return [values, signal];
  }

  function ema(values, length, alpha = 2 / (length + 1)) {
    let average = null;
    return values.map(value => {
      average = average === null ? value : average + alpha * (value - average);
      return average;
    });
  }

  function rma(values, length) {
    let average = 0;
    return values.map((value, index) => {
      if (index < length) {
        average += value / length;
        return index === length - 1 ? average : null;
      }
      average += (value - average) / length;
      return average;
    });
  }

  function trueRange(bars, handleMissing) {
    return bars.map((bar, index) => {
      const range = bar.high - bar.low;
      const previous = bars[index - 1]?.close;
      return Number.isFinite(previous)
        ? Math.max(range, Math.abs(bar.high - previous), Math.abs(bar.low - previous))
        : handleMissing(index) ? range : null;
    });
  }

  function atr(bars, length) {
    return rma(trueRange(bars, () => true), length);
  }

  function rangePercent(bars, range) {
    return range.map((value, index) => {
      const close = bars[index].close;
      return Number.isFinite(value) && Number.isFinite(close) && close !== 0 ? 100 * value / close : null;
    });
  }

  function directionalMovement(bars, length, smoothing) {
    if (bars.length < 2) return bars.length ? [[null], [null], [null]] : [[], [], []];
    const moves = bars.slice(1).map(({high, low}, index) => {
      const up = high - bars[index].high;
      const down = bars[index].low - low;
      const comparedUp = Number(up.toFixed(9)), comparedDown = Number(down.toFixed(9));
      return [comparedUp > comparedDown && comparedUp > 0 ? up : 0,
        comparedDown > comparedUp && comparedDown > 0 ? down : 0];
    });
    const range = rma(trueRange(bars, () => false).slice(1), length);
    const directions = [0, 1].map(side => rma(moves.map(move => move[side]), length)
      .map((value, index) => value === null ? null : range[index] ? 100 * value / range[index] : 0));
    const [plus, minus] = directions;
    const dx = plus.slice(length - 1).map((value, offset) => {
      const other = minus[offset + length - 1];
      return value + other ? 100 * Math.abs(value - other) / (value + other) : 0;
    });
    return [[null, ...plus], [null, ...minus],
      [...Array(Math.min(length, bars.length)).fill(null), ...rma(dx, smoothing)]];
  }

  function median(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const middle = (sorted.length - 1) / 2;
    return (sorted[Math.floor(middle)] + sorted[Math.ceil(middle)]) / 2;
  }

  function linearRegression(values, length, offset, output = 'value') {
    const middle = (length - 1) / 2;
    const variance = length * (length ** 2 - 1) / 12;
    return values.map((_, i) => {
      if (i < length - 1) return null;
      let sum = 0, covariance = 0;
      for (let j = 0; j < length; j++) {
        const value = values[i - length + 1 + j];
        if (!Number.isFinite(value)) return null;
        sum += value;
        covariance += (j - middle) * value;
      }
      const slope = variance ? covariance / variance : 0;
      if (output === 'slope') return slope;
      const mean = sum / length;
      if (output === 'standardError') {
        let squaredResiduals = 0;
        for (let j = 0; j < length; j++) {
          const fitted = mean + slope * (j - middle);
          squaredResiduals += (values[i - length + 1 + j] - fitted) ** 2;
        }
        return Math.sqrt(squaredResiduals / (length - 2));
      }
      return mean + slope * (middle - offset);
    });
  }

  function percentRank(values, length) {
    return values.map((value, index) => {
      if (index < length || !Number.isFinite(value)) return null;
      let count = 0;
      for (let previous = index - length; previous < index; previous++) {
        if (!Number.isFinite(values[previous])) return null;
        if (values[previous] <= value) count++;
      }
      return 100 * count / length;
    });
  }

  function rsi(values, length) {
    const changes = values.slice(1).map((value, index) => value - values[index]);
    const up = rma(changes.map(change => Math.max(change, 0)), length);
    const down = rma(changes.map(change => Math.max(-change, 0)), length);
    return [null, ...up.map((gain, index) => {
      if (gain === null) return null;
      if (!down[index]) return 100;
      return 100 - 100 / (1 + gain / down[index]);
    })];
  }

  function renkoAtrSize(bars, length, tick = 0.05) {
    if (!Number.isInteger(length) || length < 1 || bars.length < length) return null;
    if(bars.some(bar=>!Number.isFinite(bar.high)||!Number.isFinite(bar.low)||!Number.isFinite(bar.close)||bar.high<bar.low))return null;
    const latest = atr(bars, length).at(-1);
    if (!Number.isFinite(latest) || latest <= 0) return null;
    return Math.max(1, Math.round(latest / tick)) * tick;
  }

 function withRenkoVolume(source,bricks){
  if(!Array.isArray(source)||!Array.isArray(bricks))throw new TypeError('Source candles and Renko bricks are required');
  const groups=new Map(),output=bricks.map(b=>({...b}));
  for(const brick of output){
   if(!Number.isFinite(brick.sourceTime))throw new TypeError('Renko brick requires its source timestamp');
   if(!groups.has(brick.sourceTime))groups.set(brick.sourceTime,[]);
   groups.get(brick.sourceTime).push(brick);
  }
  let previous=-Infinity,pending=0,known=true;
  for(const bar of source){
   if(!Number.isFinite(bar.time)||bar.time<=previous)throw new RangeError('Source candles must have unique increasing timestamps');
   previous=bar.time;
   const usable=Number.isFinite(bar.volume)&&bar.volume>=0;
   known=known&&usable;
   if(known){pending+=bar.volume;if(!Number.isFinite(pending))known=false;}
   const group=groups.get(bar.time);
   if(!group)continue;
   const developing=Boolean(bar.provisional||bar.historyOnly);
   if(group.some(b=>Boolean(b.provisional||b.historyOnly)!==developing))
    throw new RangeError('Renko and source finality must agree');
   const volume=known?(developing?0:pending/group.length):null;
   for(const brick of group){brick.volume=volume;brick.renkoVolume=true;}
   groups.delete(bar.time);
   if(!developing){pending=0;known=true;}
  }
  if(groups.size)throw new RangeError('Renko source candle is missing');
  return output;
 }

  function renko(bars, size, previousBrick, source = 'close', showWicks = false) {
    const usesOhlc = source === 'ohlc';
    const bricks = [];
    if (!bars.length || !Number.isFinite(size) || size <= 0) return bricks;
    // Prices and brick sizes are decimal values. Snap ratios only within the
    // floating-point error of the division, including the initial grid anchor.
    function gridPosition(price) {
      const ratio = price / size;
      const nearest = Math.round(ratio);
      const tolerance = Math.abs(ratio) * Number.EPSILON * 2;
      return Math.abs(ratio - nearest) <= tolerance ? nearest : ratio;
    }
    // A preceding confirmed brick can initialize a replay with known history.
    const initialPrice = previousBrick ? previousBrick.close : usesOhlc ? bars[0].open : bars[0].close;
    const initial = gridPosition(initialPrice);
    const directionAtStart = previousBrick ? Math.sign(previousBrick.close - previousBrick.open) : 0;
    if (previousBrick && (!Number.isSafeInteger(initial) || !directionAtStart
      || gridPosition(previousBrick.open) !== initial - directionAtStart)) {
      throw new Error('The preceding brick must match the selected brick grid.');
    }
    let level = Math.floor(initial);
    if (!Number.isSafeInteger(level)) throw new Error('Brick size is too small for this price.');

    let direction = directionAtStart;
    let swingHigh = -Infinity;
    let swingLow = Infinity;
    const addPrice = (bar, price) => {
      const delta = gridPosition(price) - level;
      const step = Math.sign(delta);
      const count = Math.floor(Math.abs(delta));
      const reversal = direction !== 0 && step !== direction;
      if (count < (reversal ? 2 : 1)) {
        swingHigh = Math.max(swingHigh, price);
        swingLow = Math.min(swingLow, price);
        return;
      }
      if (count > 1000 || bricks.length + count > 50000) {
        throw new Error('Increase the brick size to display this history.');
      }
      if (reversal) level += step;
      for (let index = reversal ? 1 : 0; index < count; index++) {
        const open = level * size;
        level += step;
        const close = level * size;
        bricks.push({
          time: bricks.length + 1,
          sourceTime: bar.time,
          provisional: !!bar.provisional,
          historyOnly: !!bar.historyOnly,
          open,
          high: showWicks && index === 0 && direction === -1 && step === -1 && swingHigh > open + size
            ? swingHigh : Math.max(open, close),
          low: showWicks && index === 0 && direction === 1 && step === 1 && swingLow < open - size
            ? swingLow : Math.min(open, close),
          close
        });
      }
      direction = step;
      swingHigh = swingLow = price;
    };
    for (const bar of bars) {
      if (usesOhlc) {
        const rising = bar.close >= bar.open;
        addPrice(bar, bar.open);
        addPrice(bar, rising ? bar.low : bar.high);
        addPrice(bar, rising ? bar.high : bar.low);
      }
      addPrice(bar, bar.close);
    }
    return bars.some(bar => Object.hasOwn(bar, 'volume')) ? withRenkoVolume(bars, bricks) : bricks;
  }

  function movingAverage(bars, values, length, type) {
    if (type === 'VWMA') return vwma(bars, values, length);
    const averages = {SMA: sma, EMA: ema, 'SMMA (RMA)': rma, WMA: wma};
    return (Object.hasOwn(averages, type) ? averages[type] : sma)(values, length);
  }

  function rollingDeviation(values, length, multiplier, mean = sma(values, length)) {
    return mean.map((value, index) => {
      if (value === null) return null;
      let squared = 0;
      for (let offset = 0; offset < length; offset++) {
        squared += (values[index - offset] - value) ** 2;
      }
      return multiplier * Math.sqrt(squared / length);
    });
  }

  function bollinger(values, length, multiplier, basis) {
    const mean = sma(values, length);
    basis ??= mean;
    const deviation = rollingDeviation(values, length, multiplier, mean);
    return [
      basis.map((value, index) => value === null || deviation[index] === null ? null : value + deviation[index]),
      basis,
      basis.map((value, index) => value === null || deviation[index] === null ? null : value - deviation[index])
    ];
  }

  function supertrend(bars, length, factor, pine = false) {
    const volatility = atr(bars, length);
    let upper, lower, previousClose, down = true;
    const compared = value => Number(value.toFixed(9));
    const rising = [], falling = [];
    bars.forEach((bar, index) => {
      rising.push(null);
      falling.push(null);
      const multiplier = Array.isArray(factor) ? factor[index] : factor;
      if (volatility[index] === null || !Number.isFinite(multiplier)) return;
      const middle = (bar.high + bar.low) / 2;
      const nextUpper = middle + multiplier * volatility[index];
      const nextLower = middle - multiplier * volatility[index];
      const previousUpper = upper;
      const previousTrend = down ? upper : lower;
      if (upper === undefined || compared(nextUpper) < compared(upper) || compared(previousClose) > compared(upper)) upper = nextUpper;
      if (lower === undefined || compared(nextLower) > compared(lower) || compared(previousClose) < compared(lower)) lower = nextLower;
      down = previousClose === undefined || (compared(previousTrend) === compared(previousUpper)
        ? compared(bar.close) <= compared(upper) : compared(bar.close) < compared(lower));
      (down ? falling : rising)[index] = down ? upper : lower;
      previousClose = bar.close;
    });
    return pine ? [rising.map((value, i) => value ?? falling[i]), rising.map(value => value === null ? 1 : -1)]
      : [rising, falling];
  }

  function pineVwap(args, parse, bands = false) {
    const names = ['source', 'anchor', 'stdev_mult'].slice(0, bands ? 3 : 2);
    const ordered = [];
    let named = false;
    for (const arg of args) {
      const assignment = /^(\w+)\s*=(?!=)\s*(.+)$/.exec(arg);
      const index = assignment ? names.indexOf(assignment[1]) : named ? -1 : ordered.length;
      if (index < 0 || index >= names.length || Object.hasOwn(ordered, index)) {
        throw new Error('Invalid or duplicate argument for ta.vwap().');
      }
      ordered[index] = assignment ? assignment[2] : arg;
      named ||= Boolean(assignment);
    }
    if (!ordered[0] || bands && (!ordered[1] || !ordered[2])) {
      throw new Error('ta.vwap() requires a source. Bands also require an anchor and multiplier.');
    }
    const source = parse(ordered[0]);
    const anchor = ordered[1] && parse(ordered[1]);
    const multiplier = ordered[2] && parse(ordered[2]);
    return context => {
      const values = source(context);
      const anchors = anchor?.(context);
      const multipliers = multiplier?.(context);
      const upper = [], lower = [];
      let session, weight = 0, mean = 0, moment = 0, started = !anchor;
      const offset = context.symbolInfo.sessionOffset ?? 0;
      const vwap = context.bars.map((bar, index) => {
        const day = Math.floor(((bar.sourceTime ?? bar.time) + offset) / 86400);
        if (anchor ? anchors[index] === true : day !== session) {
          started = true;
          session = day;
          weight = mean = moment = 0;
        }
        const value = values[index];
        const valid = started && Number.isFinite(value) && Number.isFinite(bar.volume) && bar.volume >= 0;
        if (valid && bar.volume > 0) {
          const deviation = value - mean;
          weight += bar.volume;
          mean += deviation * (bar.volume / weight);
          moment += bar.volume * deviation * (value - mean);
        }
        const ready = valid && weight > 0;
        if (bands) {
          const mult = multipliers[index];
          const distance = ready && Number.isFinite(mult) ? Math.sqrt(Math.max(0, moment / weight)) * mult : null;
          upper.push(distance === null ? null : mean + distance);
          lower.push(distance === null ? null : mean - distance);
        }
        return ready ? mean : null;
      });
      return bands ? [vwap, upper, lower] : vwap;
    };
  }

  const vwapCalendarMonths = {Month: 1, Quarter: 3, Year: 12, Decade: 120, Century: 1200};

  function vwapPeriodKey(bar, anchor, {sessionOffset = 19800, exchangeDay} = {}) {
    const time = bar.sourceTime ?? bar.time;
    const day = exchangeDay?.(time) ?? Math.floor((time + sessionOffset) / 86400);
    if (anchor === 'Week') return Math.floor((day + 3) / 7);
    const months = vwapCalendarMonths[anchor];
    if (!months) return day;
    const date = new Date(day * 86400000);
    return Math.floor((date.getUTCFullYear() * 12 + date.getUTCMonth()) / months);
  }

  function autoVwapStart(bars, anchor, length, symbolInfo) {
    if (!bars.length) return 0;
    if (anchor === 'Auto') {
      const calendar = /^(\d+)([DWM])$/.exec(symbolInfo.interval ?? '');
      const days = calendar && Number(calendar[1]) * {D: 1, W: 7, M: 30}[calendar[2]];
      anchor = !days ? 'Session' : days === 1 ? 'Month' : days <= 10 ? 'Quarter' : days <= 60 ? 'Year' : 'Decade';
    }
    const field = {'Highest High': 'high', 'Lowest Low': 'low', 'Highest Volume': 'volume'}[anchor];
    if (field) {
      const direction = field === 'low' ? -1 : 1;
      let best = -Infinity;
      let start = bars.length;
      for (let index = Math.max(0, bars.length - length); index < bars.length; index++) {
        const value = bars[index][field];
        if (!Number.isFinite(value) || (field === 'volume' && value <= 0)) continue;
        if (value * direction >= best) {
          best = value * direction;
          start = index;
        }
      }
      return start;
    }
    let start = bars.length - 1;
    const latest = vwapPeriodKey(bars[start], anchor, symbolInfo);
    while (start > 0 && vwapPeriodKey(bars[start - 1], anchor, symbolInfo) === latest) start--;
    return start;
  }

  const twapCalendarAnchors = {'1D': 'Session', '1W': 'Week', '1M': 'Month', '3M': 'Quarter', '12M': 'Year'};
  function anchoredTwap(bars, inputs = {}, symbolInfo = {}) {
    const {anchor = '1D', source = 'ohlc4'} = inputs;
    const calendar = twapCalendarAnchors[anchor];
    const priceSource = studyPriceSourceNames.includes(source) ? pineSources[source] : pineSources.ohlc4;
    let previousKey, count = 0, mean = 0;
    return [bars.map(bar => {
      const key = calendar ? vwapPeriodKey(bar, calendar, symbolInfo) : symbolInfo.twapAnchorKey?.(bar);
      if (key === undefined || key === null) return null;
      if (key !== previousKey) { previousKey = key; count = 0; mean = 0; }
      const value = priceSource(bar);
      if (!Number.isFinite(value)) return null;
      mean += (value - mean) / ++count;
      return mean;
    })];
  }

  function anchoredVwap(bars, inputs = {}, symbolInfo = {}, start) {
    const {anchor = 'Session', source = 'hlc3', hideHigher = false, bandMode = 'Standard deviation'} = inputs;
    const bands = [1, 2, 3].map(index => inputs['showBand' + index] ? inputs['bandMultiplier' + index] ?? index : null);
    const plots = Array.from({length: 7}, () => []);
    const hidden = hideHigher && /[DWM]$/.test(symbolInfo.interval ?? '');
    let previousKey, volume = 0, mean = 0, moment = 0;
    const priceSource = studyPriceSourceNames.includes(source) ? pineSources[source] : pineSources.hlc3;
    for (const [index, bar] of bars.entries()) {
      const key = start === undefined ? vwapPeriodKey(bar, anchor, symbolInfo) : start;
      if (key !== previousKey) {
        previousKey = key;
        volume = mean = moment = 0;
      }
      const price = priceSource(bar);
      const valid = !hidden && (start === undefined || index >= start) && Number.isFinite(price) && Number.isFinite(bar.volume) && bar.volume >= 0;
      if (valid && bar.volume > 0) {
        if (volume === 0) {
          // The first weighted observation has exactly zero dispersion.
          volume = bar.volume;
          mean = price;
          moment = 0;
        } else {
          const deviation = price - mean;
          volume += bar.volume;
          mean += deviation * bar.volume / volume;
          moment += bar.volume * deviation * (price - mean);
        }
      }
      const basis = valid && volume > 0 ? mean : null;
      plots[0].push(basis);
      const unit = basis === null ? 0 : bandMode === 'Percentage'
        ? Math.abs(basis) / 100 : Math.sqrt(Math.max(0, moment / volume));
      bands.forEach((multiplier, index) => {
        const distance = basis === null || multiplier === null ? null : unit * multiplier;
        plots[index * 2 + 1].push(distance === null ? null : basis + distance);
        plots[index * 2 + 2].push(distance === null ? null : basis - distance);
      });
    }
    return plots;
  }

  // Standalone Shadow Candle revision 60, NSE regular-session X/R/M ranges.
  const shadowRatios = [46, 50, 56];
  function shadowRanges(bars, asOf, ratios = shadowRatios) {
    const istOffset = 19800;
    const last = bars.findLast(bar => bar.time + 300 <= asOf);
    if (!last) return [];
    const midnight = Math.floor((last.time + istOffset) / 86400) * 86400 - istOffset;
    const open = midnight + 555 * 60;
    const midday = midnight + 750 * 60;
    const end = midnight + 930 * 60;
    const session = bars.filter(bar => !bar.provisional && bar.time >= open && bar.time < end && bar.time + 300 <= asOf);
    const ranges = [];
    function publish(kind, source) {
      const high = Math.max(...source.map(bar => bar.high));
      const low = Math.min(...source.map(bar => bar.low));
      ranges.push({ kind, published: source.at(-1).time + 300, end, high, low,
        levels: ratios.map(ratio => low + (high - low) * ratio / 100) });
    }
    if (session[0]?.time === open) {
      publish('X', [session[0]]);
      for (let index = 1; index < session.length; index++) {
        const bar = session[index];
        if (bar.time !== open + index * 300) break;
        if (bar.close < bar.open) {
          publish('R', [bar]);
          break;
        }
      }
    }
    const blend = session.filter(bar => bar.time >= midday && bar.time < midday + 1800);
    if (blend.length === 6 && blend.every((bar, index) => bar.time === midday + index * 300)) publish('M', blend);
    return ranges;
  }

  function shadowRangeHistory(bars, asOf, sessions = 3, ratios = shadowRatios) {
    const ranges = [];
    let cutoff = asOf;
    for (let index = 0; index < sessions; index++) {
      const latest = bars.findLast(bar => bar.time + 300 <= cutoff);
      if (!latest) break;
      ranges.push(...shadowRanges(bars, cutoff, ratios));
      cutoff = Math.floor((latest.time + 19800) / 86400) * 86400 - 19800;
    }
    return ranges;
  }

  // V1 follows the selected market session; the standalone Shadow preset retains its defaults.
  function v1ReferenceRanges(bars, asOf, sessionBounds, ratios = [44, 50, 56], limit = 1, interval = 300) {
    const sessions = new Map();
    for (const bar of bars) {
      if (bar.provisional || bar.time + interval > asOf) continue;
      const bounds = sessionBounds(bar.time);
      if (!bounds || bar.time < bounds.open || bar.time >= bounds.end) continue;
      if (!sessions.has(bounds.open)) sessions.set(bounds.open, {bounds, bars: []});
      sessions.get(bounds.open).bars.push(bar);
    }
    const ranges = [];
    for (const {bounds, bars: session} of [...sessions.values()].sort((a, b) => b.bounds.open - a.bounds.open).slice(0, limit)) {
      if (session[0]?.time !== bounds.open) continue;
      for (let index = 1; index < session.length; index++) {
        const bar = session[index];
        if (bar.time !== bounds.open + index * interval) break;
        if (bar.close >= bar.open) continue;
        const {high, low} = bar;
        ranges.push({kind: 'R', published: Math.min(bar.time + interval, bounds.end),
          end: bounds.end, high, low, levels: ratios.map(ratio => low + (high - low) * ratio / 100)});
        break;
      }
    }
    return ranges;
  }

  // V1 target prices. Reach and reveal depend on the chart series and are separate.
  function v1TargetPrices(range, count = 10) {
    const span = range.high - range.low;
    if (!(span > 0)) return [];
    return Array.from({ length: count }, (_, index) => ({
      number: index + 1,
      upper: range.high + (index + 1) * span,
      lower: range.low - (index + 1) * span
    }));
  }

  function v1TargetStates(range, bars, timeOf, forward = 2, count = 10, all = false) {
    const targets = v1TargetPrices(range, count).map(target => ({
      ...target, upperReveal: null, lowerReveal: null, upperHit: null, lowerHit: null
    }));
    if (!targets.length) return targets;
    const span = range.high - range.low;
    for (const bar of bars) {
      const time = timeOf(bar);
      if (time < range.published || time >= range.end) continue;
      // Provisional chart bars may show a hit, but cannot reveal new targets.
      const upAhead = Math.max(1, Math.floor((bar.close - range.high) / span) + forward);
      const downAhead = Math.max(1, Math.floor((range.low - bar.close) / span) + forward);
      for (const target of targets) {
        if (bar.high >= target.upper) target.upperHit ??= bar.time;
        if (bar.low <= target.lower) target.lowerHit ??= bar.time;
        if (all || (!bar.provisional && target.number <= upAhead)) target.upperReveal ??= bar.time;
        if (all || (!bar.provisional && target.number <= downAhead)) target.lowerReveal ??= bar.time;
      }
    }
    return targets;
  }

  function v1ExtraZones(bars, asOf, limit = 8) {
    const zones = [];
    let session, first, found;
    for (const bar of bars) {
      const local = bar.time + 19800;
      const day = Math.floor(local / 86400);
      const minute = Math.floor(local % 86400 / 60);
      if (minute < 555 || minute >= 930) continue;
      if (day !== session) {
        session = day;
        first = minute === 555;
        found = false;
      }
      const published = bar.time + Math.min(30, 930 - minute) * 60;
      if (!first || found || minute === 555 || published > asOf || bar.close >= bar.open) continue;
      const previous = zones.at(-1);
      if (previous) previous.end = published;
      zones.push({ published, high: bar.high, low: bar.low, end: Infinity });
      found = true;
    }
    return zones.slice(-limit);
  }

  function standardPivotLevels(method, previous, currentOpen) {
    if (!previous) return {};
    const {open, high, low, close} = previous;
    if (![open, high, low, close].every(Number.isFinite) || high < low) return {};
    const range = high - low;
    const typical = (high + low + close) / 3;
    const symmetric = (midpoint, offsets) => offsets.map(offset => [midpoint + offset, midpoint - offset]);
    const first = pivot => [2 * pivot - low, 2 * pivot - high];
    let pivot = typical;
    let levels;
    switch (method) {
      case 'Traditional':
        levels = [first(pivot), ...symmetric(pivot, [range]),
          ...[2, 3, 4].map(multiplier => [
            multiplier * (pivot - low) + high,
            multiplier * (pivot - high) + low
          ])];
        break;
      case 'Fibonacci':
        levels = symmetric(pivot, [0.382 * range, 0.618 * range, range]);
        break;
      case 'Woodie': {
        if (!Number.isFinite(currentOpen)) return {};
        pivot = (high + low + 2 * currentOpen) / 4;
        const third = [high + 2 * (pivot - low), low - 2 * (high - pivot)];
        levels = [first(pivot), ...symmetric(pivot, [range]), third, [third[0] + range, third[1] - range]];
        break;
      }
      case 'Classic':
        levels = [first(pivot), ...symmetric(pivot, [range, 2 * range, 3 * range])];
        break;
      case 'DM': {
        const x = high + low + close + (open === close ? close : close > open ? high : low);
        pivot = x / 4;
        levels = [first(pivot)];
        break;
      }
      case 'Camarilla':
        levels = symmetric(close, [12, 6, 4, 2].map(divisor => 1.1 * range / divisor));
        if (low !== 0) {
          const fifth = high / low * close;
          levels.push([fifth, 2 * close - fifth]);
        }
        break;
      default:
        return {};
    }
    return Object.fromEntries([['P', pivot], ...levels.flatMap(([resistance, support], index) => [
      ['R' + (index + 1), resistance], ['S' + (index + 1), support]
    ])]);
  }

  function aggregatePivotCandles(bars, interval, timeZone) {
    const date = new Intl.DateTimeFormat('en-CA', {
      timeZone, year: 'numeric', month: '2-digit', day: '2-digit'
    });
    const monthSpan = Number(interval.slice(0, -1));
    const candles = [];
    let lastDate;
    let key;
    let active;
    for (const bar of bars) {
      const localDate = date.format(bar.time * 1000);
      if (lastDate !== localDate) {
        lastDate = localDate;
        const parts = Object.fromEntries(date.formatToParts(bar.time * 1000).map(({type, value}) => [type, Number(value)]));
        const day = Date.UTC(parts.year, parts.month - 1, parts.day) / 86400000;
        key = interval === '1D' ? day : interval === '1W' ? Math.floor((day + 3) / 7)
          : parts.year * 12 + Math.floor((parts.month - 1) / monthSpan) * monthSpan;
      }
      if (active?.period !== key) {
        active = {period: key, time: bar.time, open: bar.open, high: bar.high, low: bar.low,
          close: bar.close, provisional: Boolean(bar.provisional)};
        candles.push(active);
      } else {
        active.high = Math.max(active.high, bar.high);
        active.low = Math.min(active.low, bar.low);
        active.close = bar.close;
        active.provisional ||= Boolean(bar.provisional);
      }
    }
    // The first visible period may start partway through the session or calendar period.
    return candles.slice(1);
  }

  function standardPivotPeriods(candles, method, asOf, limit) {
    const periods = [];
    for (let index = 1; index < candles.length; index++) {
      const current = candles[index];
      if (current.time > asOf) break;
      const previous = candles[index - 1];
      if (previous.provisional || current.time <= previous.time) continue;
      const levels = standardPivotLevels(method, previous, current.open);
      if (Number.isFinite(levels.P)) periods.push({time: current.time, levels});
    }
    return periods.slice(-Math.max(1, limit));
  }

  function previousShadowPeriods(bars, asOf) {
    const offset = 19800;
    const daySeconds = 86400;
    const localDay = time => Math.floor((time + offset) / daySeconds);
    const current = bars.findLast(bar => bar.time + 300 <= asOf);
    const periods = [
      ['Previous day', localDay],
      ['Previous week', time => Math.floor((localDay(time) + 3) / 7)],
      ['Previous month', time => {
        const local = new Date((time + offset) * 1000);
        return local.getUTCFullYear() * 12 + local.getUTCMonth();
      }]
    ];
    return periods.map(([name, period], index) => {
      if (!current) return { name };
      const currentKey = period(current.time);
      let selectedKey, high = -Infinity, low = Infinity;
      for (let i = bars.length - 1; i >= 0; i--) {
        const bar = bars[i];
        if (bar.time + 300 > asOf) continue;
        const key = period(bar.time);
        if (key === currentKey) continue;
        if (selectedKey === undefined) selectedKey = key;
        if (key !== selectedKey) return { name, high, low };
        high = Math.max(high, bar.high);
        low = Math.min(low, bar.low);
      }
      // The first archive group has no earlier group to establish its left boundary.
      // A daily group can instead be verified from its complete regular session.
      if (index === 0 && selectedKey !== undefined) {
        const start = selectedKey * daySeconds - offset + 555 * 60;
        const previous = bars.filter(bar => period(bar.time) === selectedKey);
        if (previous.length === 75 && previous.every((bar, i) => bar.time === start + i * 300)) {
          return { name, high, low };
        }
      }
      return { name };
    });
  }

  function shadowOscillators(five, thirty, asOf, length = 14, averageLength = 14) {
    const buckets = new Map();
    for (const bar of five) {
      if (bar.time + 300 > asOf) break;
      const istSecond = (bar.time + 19800) % 86400;
      if (istSecond < 33300 || istSecond >= 55800) continue;
      const start = bar.time - (istSecond - 33300) % 900;
      if (!buckets.has(start)) buckets.set(start, []);
      buckets.get(start).push(bar);
    }
    const fifteen = [];
    for (const [time, group] of buckets) {
      if (group.length === 3 && group.every((bar, i) => bar.time === time + i * 300)) {
        fifteen.push({ time, close: group[2].close });
      }
    }
    return [[5, five], [15, fifteen], [30, thirty]].map(([minutes, bars]) => {
      const completed = bars.filter(bar => {
        const sessionEnd = bar.time - (bar.time + 19800) % 86400 + 55800;
        return Math.min(bar.time + minutes * 60, sessionEnd) <= asOf;
      });
      const values = rsi(completed.map(bar => bar.close), length).filter(value => value !== null);
      const means = sma(values, averageLength);
      const average = means.at(-1) ?? null;
      const prior = means.at(-2) ?? null;
      const slope = average === null || prior === null ? null : Math.sign(average - prior);
      return { minutes, value: values.at(-1) ?? null, average, slope };
    });
  }

  function swma(values) {
    return values.map((value, i) => {
      if (i < 3 || ![value, values[i - 1], values[i - 2], values[i - 3]].every(Number.isFinite)) return null;
      return (value + 2 * values[i - 1] + 2 * values[i - 2] + values[i - 3]) / 6;
    });
  }

  function alma(values, length, offset, sigma, floor) {
    const center = offset * (length - 1);
    const mean = floor ? Math.floor(center) : center;
    const deviation = length / sigma;
    const weights = Array.from({length}, (_, index) => Math.exp(-0.5 * ((index - mean) / deviation) ** 2));
    const sum = weights.reduce((a, b) => a + b, 0);
    return values.map((_, index, values) => {
      if (index < length - 1 || !(sum > 0)) return null;
      let weighted = 0;
      for (let j = 0; j < length; j++) {
        const value = values[index - length + 1 + j];
        if (!Number.isFinite(value)) return null;
        weighted += value * weights[j];
      }
      return weighted / sum;
    });
  }

  function cog(values, length) {
    const window = [];
    return values.map(value => {
      if (!Number.isFinite(value)) return null;
      window.push(value);
      if (window.length > length) window.shift();
      if (window.length < length) return null;
      let total = 0, weighted = 0;
      for (let i = 0; i < length; i++) {
        total += window[i];
        weighted += window[i] * (length - i);
      }
      return total === 0 ? null : -weighted / total;
    });
  }

  function accumulationDistribution(bars) {
    let total = 0;
    return bars.map(({high, low, close, volume}) => {
      if (!Number.isFinite(volume) || volume < 0) return null;
      if (high > low) total += (2 * close - high - low) / (high - low) * volume;
      return total;
    });
  }

  const bandBackgroundInputs = [
    {id: 'background', title: 'Show background', type: 'bool', value: true},
    {id: 'backgroundColor', title: 'Background color', type: 'color', value: '#2196f3'},
    {id: 'backgroundOpacity', title: 'Background opacity (%)', value: 5, min: 0, max: 100}
  ];

  const guppyAverages = [
    {group: 'Trader', periods: [3, 5, 8, 10, 12, 15], color: '#00ffff'},
    {group: 'Investor', periods: [30, 35, 40, 45, 50, 60], color: '#ff0000'}
  ].flatMap(({group, periods, color}) => periods.map((period, index) => ({
    id: group.toLowerCase() + (index + 1),
    name: group + ' EMA ' + (index + 1),
    group, period, color
  })));

  const smoothingInputs = [
    {id: 'smoothingType', title: 'Smoothing type', type: 'string', value: 'None',
      options: ['None', 'SMA', 'SMA + Bollinger Bands', 'EMA', 'SMMA (RMA)', 'WMA', 'VWMA']},
    {id: 'smoothingLength', title: 'Smoothing length', value: 14, min: 1, max: 250},
    {id: 'smoothingDeviation', title: 'BB StdDev', type: 'float', value: 2, min: 0.001, max: 50}
  ];

  const movingAverageInputs = [
    {id: 'offset', title: 'Offset', value: 0, min: -500, max: 500},
    ...smoothingInputs
  ];

  function shiftStudyPlots(plots, offset) {
    if (!Number.isInteger(offset) || !offset) return plots;
    const shifted = plots.map(series => series.map((_, index) => series[index - offset] ?? null));
    if (offset > 0) {
      const size = plots[0].length;
      shifted.projected = plots.map(series => series.slice(Math.max(0, size - offset)));
      shifted.projectionOffset = Math.max(0, offset - size);
    }
    return shifted;
  }

  function smoothedStudy(bars, series, {smoothingType = 'None', smoothingLength = 14, smoothingDeviation = 2} = {}) {
    if (smoothingType === 'None') return [series];
    const valid = series.filter(Number.isFinite);
    const align = points => {
      let index = 0;
      return series.map(value => Number.isFinite(value) ? points[index++] : null);
    };
    if (smoothingType === 'SMA + Bollinger Bands') {
      const [upper, basis, lower] = bollinger(valid, smoothingLength, smoothingDeviation);
      return [series, align(basis), align(upper), align(lower)];
    }
    const matchedBars = smoothingType === 'VWMA' ? bars.filter((bar, i) => Number.isFinite(series[i])) : bars;
    return [series, align(movingAverage(matchedBars, valid, smoothingLength, smoothingType))];
  }

  const oscillatorInputs = [
    { id: 'fast', title: 'Fast length', value: 12, min: 1, max: 250 },
    { id: 'slow', title: 'Slow length', value: 26, min: 1, max: 250 },
    { id: 'signal', title: 'Signal length', value: 9, min: 1, max: 250 },
    {id: 'oscillatorType', title: 'Oscillator MA type', type: 'string', value: 'EMA', options: ['EMA', 'SMA']},
    {id: 'signalType', title: 'Signal MA type', type: 'string', value: 'EMA', options: ['EMA', 'SMA']}
  ];

  function movingAverageOscillator(values, overrides = {}, percentage) {
    const period = (id, fallback) => Number.isInteger(overrides[id]) && overrides[id] >= 1 && overrides[id] <= 250
      ? overrides[id] : fallback;
    const result = macd(values.filter(Number.isFinite), period('fast', 12), period('slow', 26),
      period('signal', 9), overrides.oscillatorType, overrides.signalType, percentage).map(series => {
      let index = 0;
      return values.map(value => Number.isFinite(value) ? series[index++] : null);
    });
    const histogram = result[2];
    histogram.colors = histogram.map((value, i) => {
      if (value === null) return undefined;
      const increasing = !Number.isFinite(histogram[i - 1]) || value > histogram[i - 1];
      return value >= 0 ? (increasing ? '#26a69a' : '#b2dfdb') : (increasing ? '#ffcdd2' : '#ff5252');
    });
    return result;
  }

  const alligatorInputs = [
    {id: 'jawLength', title: 'Jaw length', value: 13, min: 1, max: 250},
    {id: 'teethLength', title: 'Teeth length', value: 8, min: 1, max: 250},
    {id: 'lipsLength', title: 'Lips length', value: 5, min: 1, max: 250},
    {id: 'jawOffset', title: 'Jaw offset', value: 8, min: 0, max: 250},
    {id: 'teethOffset', title: 'Teeth offset', value: 5, min: 0, max: 250},
    {id: 'lipsOffset', title: 'Lips offset', value: 3, min: 0, max: 250}
  ];

  const multipleAveragePeriods = [14, 21, 35, 50, 100, 200];
  const ribbonLengths = [20, 50, 100, 200];
  const studyPriceSourceNames = ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'];
  function movingAverageCross(name, shortAverage, longAverage, shortColor, longColor, defaultLongLength, plotNames = ['Short', 'Long', 'Crosses']) {
    return {
      name, plotNames,
      plotColors: [shortColor, longColor, '#2196f3'],
      plotOptions: [{}, {}, {style: 'cross', width: 4}],
      eventPlots: [2],
      inputs: [
        {id: 'shortLength', title: 'Short length', value: 9, min: 1, max: 2000},
        {id: 'longLength', title: 'Long length', value: defaultLongLength, min: 1, max: 2000}
      ],
      run(bars, values, length, multiplier, {shortLength = 9, longLength = defaultLongLength} = {}) {
        const short = shortAverage(values, shortLength);
        const long = longAverage(values, longLength);
        const crosses = short.map((value, i) => {
          if (![value, long[i], short[i - 1], long[i - 1]].every(Number.isFinite)) return null;
          const spread = value - long[i];
          const prior = short[i - 1] - long[i - 1];
          return (spread > 0 && prior <= 0) || (spread < 0 && prior >= 0) ? value : null;
        });
        return [short, long, crosses];
      }
    };
  }

  function pairedPriceStudy(name, calculate) {
    return {
      name, pane: true, secondarySymbol: true, requiresSecondarySymbol: true,
      plotNames: [name], plotColors: ['#800080'],
      inputs: [
        {id: 'source', title: 'Source', type: 'source', value: 'close', options: studyPriceSourceNames},
        {id: 'symbol', title: 'Comparison symbol', type: 'string', value: '',
          tooltip: 'Choose another instrument from the selected OHLC source.'}
      ],
      pairedPlots(bars, reference, length, {source = 'close'} = {}) {
        const price = pineSources[source] ?? pineSources.close;
        const prices = new Map(reference.map(bar => [bar.time, price(bar)]));
        return [bars.map(bar => {
          const primary = price(bar);
          const comparison = prices.get(bar.sourceTime ?? bar.time);
          return Number.isFinite(primary) && Number.isFinite(comparison) ? calculate(primary, comparison) : null;
        })];
      }
    };
  }

  const ribbonMethods = ['SMA', 'EMA', 'SMMA (RMA)', 'WMA', 'VWMA'];

  const ratingColors = [
    ['strongSellColor', 'Strong Sell', '#bb2438'],
    ['sellColor', 'Sell', '#f23645'],
    ['neutralColor', 'Neutral', '#787b86'],
    ['buyColor', 'Buy', '#2962ff'],
    ['strongBuyColor', 'Strong Buy', '#1848bc']
  ];
  const ratingCategory = value => !Number.isFinite(value) ? null
    : value < -0.5 ? -2 : value < -0.1 ? -1 : value > 0.5 ? 2 : value > 0.1 ? 1 : 0;
  const ratingColor = (category, inputs) => {
    const [id, , fallback] = ratingColors[category + 2];
    const value = inputs?.[id];
    return /^#[0-9a-f]{6}$/i.test(value ?? '') ? value : fallback;
  };

  function technicalRatings(bars) {
    const close = bars.map(bar => bar.close);
    const periods = [10, 20, 30, 50, 100, 200];
    const averages = [...periods.map(period => sma(close, period)), ...periods.map(period => ema(close, period)),
      hma(close, 9), vwma(bars, close, 20)];
    const [conversion, base, , spanA, spanB] = indicators.Ichimoku.run(bars, undefined, undefined, undefined, {displacement: 27});
    const strength = rsi(close, 14);
    const [stochK, stochD] = indicators.Stochastic.run(bars, close, 14);
    const channel = cci(close, 20);
    const [plus, minus, adx] = directionalMovement(bars, 14, 14);
    const [awesome] = indicators.AO.run(bars);
    const [momentum] = indicators.Momentum.run(bars, close, 10);
    const [macd, signal] = indicators.MACD.run(bars, close);
    const [rsiK, rsiD] = indicators.StochRSI.run(bars, close);
    const [williams] = indicators.WilliamsR.run(bars, close, 14);
    const powerBasis = ema(close, 13);
    const bullPower = bars.map((bar, i) => bar.high - powerBasis[i]);
    const bearPower = bars.map((bar, i) => bar.low - powerBasis[i]);
    const trendBasis = ema(close, 50);
    const [ultimate] = indicators.UO.run(bars);
    const vote = (source, buy, sell) => !Number.isFinite(source) ? null : buy ? 1 : sell ? -1 : 0;
    const compare = (value, baseline) =>
      vote(baseline, Number.isFinite(value) && value > baseline, Number.isFinite(value) && value < baseline);
    const reversal = (value, previous, low, high) => vote(previous,
      Number.isFinite(value) && value < low && value > previous,
      Number.isFinite(value) && value > high && value < previous);
    const lowCross = (k, d) => Number.isFinite(k) && Number.isFinite(d) && k < 20 && d < 20 && k > d;
    const highCross = (k, d) => Number.isFinite(k) && Number.isFinite(d) && k > 80 && d > 80 && k < d;
    const average = votes => {
      const defined = votes.filter(Number.isFinite);
      return defined.length ? defined.reduce((sum, item) => sum + item, 0) / defined.length : null;
    };
    return close.map((price, i) => {
      const a = spanA[i], b = spanB[i], center = base[i], fast = conversion[i];
      // The library counts an available unshifted cloud as neutral while its displaced spans warm up.
      const cloudReady = Number.isFinite(a) && Number.isFinite(b);
      const cloud = vote(i >= 51 ? price : null,
        cloudReady && a > b && center > a && fast > center && price > fast,
        cloudReady && a < b && center < a && fast < center && price < fast);
      const movingAverages = average([...averages.map(line => compare(price, line[i])), cloud]);
      const trend = trendBasis[i];
      const ao = awesome[i], priorAo = awesome[i - 1], olderAo = awesome[i - 2];
      const awesomeVote = vote(priorAo,
        ao > 0 && (priorAo <= 0 || Number.isFinite(olderAo) && ao > priorAo && priorAo < olderAo),
        ao < 0 && (priorAo >= 0 || Number.isFinite(olderAo) && ao < priorAo && priorAo > olderAo));
      const risingAdx = adx[i] > 20 && Number.isFinite(adx[i - 1]) && adx[i] > adx[i - 1];
      const oscillators = average([
        reversal(strength[i], strength[i - 1], 30, 70),
        vote(stochD[i - 1], lowCross(stochK[i], stochD[i]), highCross(stochK[i], stochD[i])),
        reversal(channel[i], channel[i - 1], -100, 100),
        vote(adx[i], risingAdx && plus[i] > minus[i], risingAdx && plus[i] < minus[i]),
        awesomeVote,
        compare(momentum[i], momentum[i - 1]),
        compare(macd[i], signal[i]),
        vote(trend, price < trend && lowCross(rsiK[i], rsiD[i]), price > trend && highCross(rsiK[i], rsiD[i])),
        reversal(williams[i], williams[i - 1], -80, -20),
        vote(trend, price > trend && bearPower[i] < 0 && bearPower[i] > bearPower[i - 1],
          price < trend && bullPower[i] > 0 && bullPower[i] < bullPower[i - 1]),
        vote(ultimate[i], ultimate[i] > 70, ultimate[i] < 30)
      ]);
      const all = movingAverages === null || oscillators === null
        ? movingAverages ?? oscillators : (movingAverages + oscillators) / 2;
      return {All: all, MAs: movingAverages, Oscillators: oscillators};
    });
  }

  const deltaIntrabarInput = {id: 'intrabarInterval', title: 'Intrabar interval', type: 'string',
    value: 'Auto', options: ['Auto'],
    tooltip: 'Auto selects an interval for the current chart. A larger intrabar interval can cover more history.'};

  function volumeDeltaPlots(candles) {
    const plots = ['close', 'high', 'low', 'open'].map(field => candles.map(candle => candle?.[field] ?? null));
    plots[0].candles = candles;
    return plots;
  }

  function accumulateVolumeDelta(bars, candles, anchorKey, allowPartialStart = false) {
    let priorKey, total = 0, started = false;
    return candles.map((candle, index) => {
      const key = anchorKey(bars[index]);
      if (key !== priorKey) {
        priorKey = key;
        total = 0;
      }
      if (!candle || total === null) {
        if (started || !allowPartialStart) total = null;
        return null;
      }
      started = true;
      const open = total;
      total += candle.close;
      return {open, high: open + candle.high, low: open + candle.low, close: total};
    });
  }

  function tradeDeltaPlots(bars, segments, closeTime, anchorKey) {
    const candles = bars.map(bar => {
      const end = closeTime(bar);
      const segment = segments.findLast(item => item.from <= bar.time
        && (item.through >= end || (bar.provisional && item.active && item.through > bar.time)));
      if (!segment) return null;
      const limit = Math.min(segment.through, end);
      let high = 0, low = 0, close = 0;
      for (const sample of segment.rows) {
        if (sample[0] < bar.time) continue;
        if (sample[0] >= limit) break;
        if (!sample.slice(1).every(Number.isFinite)) return null;
        high = Math.max(high, close + sample[2]);
        low = Math.min(low, close + sample[3]);
        close += sample[4];
      }
      return {open: 0, high, low, close};
    });
    return volumeDeltaPlots(anchorKey ? accumulateVolumeDelta(bars, candles, anchorKey, true) : candles);
  }

  const deltaTickInput = {id: 'tickBased', title: 'Tick-based calculation', type: 'bool', value: false,
    tooltip: 'Use the Delta India exchange-reported aggressor side. Coverage starts with captured trades.'};

  const deltaCandleStyleInputs = [
    ...[['upColor', 'Up body', '#089981'], ['downColor', 'Down body', '#f23645'],
      ['wickUpColor', 'Up wick', '#089981'], ['wickDownColor', 'Down wick', '#f23645'],
      ['borderUpColor', 'Up border', '#089981'], ['borderDownColor', 'Down border', '#f23645']]
      .map(([id, title, value]) => ({id, title, type: 'color', value, section: 'Style', group: 'Candles'})),
    {id: 'wickVisible', title: 'Show wicks', type: 'bool', value: true, section: 'Style', group: 'Candles'},
    {id: 'borderVisible', title: 'Show borders', type: 'bool', value: false, section: 'Style', group: 'Candles'}
  ];

  const indicators = {
    V1Reference: { name: 'Sector Pulse V1 · red-bar reference', shadow: true },
    Shadow: { name: 'Shadow Candle · X/R/M ranges', shadow: true },
    PivotStandard: {
      name: 'Pivot Points Standard', periodOverlay: true,
      inputs: [
        {id: 'method', title: 'Type', type: 'string', value: 'Traditional',
          options: ['Traditional', 'Fibonacci', 'Woodie', 'Classic', 'DM', 'Camarilla']},
        {id: 'period', title: 'Pivots timeframe', type: 'string', value: 'Auto',
          options: ['Auto', 'Daily', 'Weekly', 'Monthly', 'Quarterly', 'Yearly']},
        {id: 'dailyBased', title: 'Use daily-based values', type: 'bool', value: true,
          tooltip: 'Clear this to build pivot periods from loaded intraday chart candles.'},
        {id: 'back', title: 'Number of pivots back', value: 15, min: 1, max: 200},
        {id: 'labels', title: 'Show labels', type: 'bool', value: true},
        {id: 'prices', title: 'Show prices', type: 'bool', value: true},
        {id: 'labelSide', title: 'Labels position', type: 'string', value: 'Left', options: ['Left', 'Right']},
        {id: 'width', title: 'Line width', value: 1, min: 1, max: 4},
        ...['P', ...[1, 2, 3, 4, 5].flatMap(tier => ['R' + tier, 'S' + tier])].flatMap(level => [
          {id: 'show' + level, title: level, type: 'bool', value: true, group: 'Levels', inline: level},
          {id: 'color' + level, title: level + ' color', type: 'color', value: '#fb8c00', group: 'Levels', inline: level}
        ])
      ]
    },
    Ichimoku: {
      name: 'Ichimoku Cloud', plotNames: ['Conversion Line', 'Base Line', 'Lagging Span', 'Leading Span A', 'Leading Span B'],
      plotColors: ['#2962ff', '#b71c1c', '#43a047', '#a5d6a7', '#ef9a9a'],
      inputs: [
        {id: 'conversion', title: 'Conversion line length', value: 9, min: 1, max: 250},
        {id: 'base', title: 'Base line length', value: 26, min: 1, max: 250},
        {id: 'spanB', title: 'Leading Span B length', value: 52, min: 1, max: 500},
        {id: 'displacement', title: 'Displacement', value: 26, min: 1, max: 250},
        {id: 'background', title: 'Show cloud', value: true, type: 'bool'},
        {id: 'bullCloud', title: 'Bullish cloud', value: '#43a047', type: 'color'},
        {id: 'bearCloud', title: 'Bearish cloud', value: '#f44336', type: 'color'},
        {id: 'backgroundOpacity', title: 'Cloud opacity (%)', value: 20, min: 0, max: 100}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const setting = (key, fallback, max) => Number.isInteger(inputs[key]) && inputs[key] >= 1 && inputs[key] <= max
          ? inputs[key] : fallback;
        const high = bars.map(bar => bar.high);
        const low = bars.map(bar => bar.low);
        const midpoints = period => {
          const highs = rollingExtreme(high, period, 1);
          const lows = rollingExtreme(low, period, -1);
          return highs.map((value, index) => index >= period - 1 && Number.isFinite(value) && Number.isFinite(lows[index])
            ? (value + lows[index]) / 2 : null);
        };
        const conversion = midpoints(setting('conversion', 9, 250));
        const base = midpoints(setting('base', 26, 250));
        const spanA = conversion.map((value, index) => Number.isFinite(value) && Number.isFinite(base[index])
          ? (value + base[index]) / 2 : null);
        const spanB = midpoints(setting('spanB', 52, 500));
        const shift = setting('displacement', 26, 250) - 1;
        const lag = bars.map((_, index) => bars[index + shift]?.close ?? null);
        const lead = points => bars.map((_, index) => points[index - shift] ?? null);
        const result = [conversion, base, lag, lead(spanA), lead(spanB)];
        result.projected = [spanA.slice(Math.max(0, bars.length - shift)), spanB.slice(Math.max(0, bars.length - shift))];
        result.projectionOffset = Math.max(0, shift - bars.length);
        return result;
      }
    },
    WilliamsAlligator: {
      name: 'Williams Alligator', plotNames: ['Jaw', 'Teeth', 'Lips'],
      plotColors: ['#2962ff', '#e91e63', '#66bb6a'],
      inputs: alligatorInputs,
      run(bars, values, length, multiplier, inputs = {}) {
        const prices = bars.map(bar => (bar.high + bar.low) / 2);
        const lengths = [inputs.jawLength ?? 13, inputs.teethLength ?? 8, inputs.lipsLength ?? 5];
        const offsets = [inputs.jawOffset ?? 8, inputs.teethOffset ?? 5, inputs.lipsOffset ?? 3];
        const averages = lengths.map(period => rma(prices, period));
        const result = averages.map((average, slot) =>
          bars.map((_, index) => average[index - offsets[slot]] ?? null));
        result.projected = averages.map((average, slot) => Array(Math.max(0, offsets[slot] - bars.length)).fill(null)
          .concat(average.slice(Math.max(0, bars.length - offsets[slot]))));
        return result;
      }
    },
    GatorOscillator: {
      name: 'Gator Oscillator', pane: true, histogramPlots: [0, 1],
      plotNames: ['Jaw–Teeth', 'Teeth–Lips'],
      inputs: [...alligatorInputs,
        {id: 'growingColor', title: 'Expanding color', type: 'color', value: '#089981'},
        {id: 'shrinkingColor', title: 'Contracting color', type: 'color', value: '#f23645'}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const [jaw, teeth, lips] = indicators.WilliamsAlligator.run(bars, values, length, multiplier, inputs);
        const distance = (first, second, direction) => {
          const plot = first.map((value, index) => Number.isFinite(value) && Number.isFinite(second[index])
            ? direction * Math.abs(value - second[index]) : null);
          plot.colors = plot.map((value, index) => {
            const prior = plot[index - 1];
            if (!Number.isFinite(value)) return undefined;
            return Number.isFinite(prior) && Math.abs(value) > Math.abs(prior)
              ? (inputs.growingColor ?? '#089981') : (inputs.shrinkingColor ?? '#f23645');
          });
          return plot;
        };
        return [distance(jaw, teeth, 1), distance(teeth, lips, -1)];
      }
    },
    WilliamsFractals: {
      name: 'Williams Fractals', length: 2, lengthLabel: 'Periods', plotNames: ['Up fractal', 'Down fractal'],
      plotColors: ['#009688', '#f44336'],
      plotOptions: [{marker: 'arrowUp'}, {marker: 'arrowDown'}],
      inputs: [{id: 'allowTies', title: 'Allow equal highs or lows before the swing', type: 'bool', value: false}],
      run(bars, values, length = 2, multiplier, inputs = {}) {
        const fractals = (field, direction) => bars.map((bar, i) => {
          if (i < length || i + length >= bars.length || bars[i + length].provisional) return null;
          const value = bar[field];
          let prior = i - 1;
          // Confirm the last bar of a plateau. Equal bars before the swing do
          // not replace the required lower highs or higher lows on either side.
          if (inputs.allowTies) {
            for (let ties = 0; ties < 4 && bars[prior]?.[field] === value; ties++) prior--;
          }
          if (prior - length + 1 < 0) return null;
          for (let j = 1; j <= length; j++) {
            if (!(direction * (value - bars[prior - j + 1][field]) > 0
              && direction * (value - bars[i + j][field]) > 0)) return null;
          }
          return value;
        });
        return [fractals('high', 1), fractals('low', -1)];
      }
    },
    ZigZag: {
      name: 'Zig Zag', plotNames: ['Zig Zag', 'Projected swing'],
      plotColors: ['#2962ff', '#2962ff'], plotOptions: [{}, {lineStyle: 'dashed'}],
      inputs: [
        {id: 'deviation', title: 'Price deviation for reversals (%)', type: 'float', value: 5, min: 0.001, max: 100},
        {id: 'legs', title: 'Pivot legs', value: 10, min: 2, max: 250},
        {id: 'lineColor', title: 'Line color', type: 'color', value: '#2962ff'},
        {id: 'project', title: 'Calculate projected pivots', type: 'bool', value: true},
        {id: 'showPrice', title: 'Display reversal price', type: 'bool', value: true},
        {id: 'showVolume', title: 'Display cumulative volume', type: 'bool', value: true},
        {id: 'showChange', title: 'Display reversal price change', type: 'bool', value: true},
        {id: 'changeMode', title: 'Reversal price change format', type: 'string', value: 'Absolute', options: ['Absolute', 'Percent']}
      ],
      run(bars, values, length, multiplier, inputs) {
        return zigZagPlots(bars, inputs);
      }
    },
    PivotHighLow: {
      name: 'Pivot Points High Low', plotNames: ['Pivot high', 'Pivot low'],
      plotColors: ['#f23645', '#089981'], plotOptions: [{style: 'circles'}, {style: 'circles'}],
      inputs: [
        {id: 'highLeft', title: 'Pivot high left bars', value: 10, min: 1, max: 250},
        {id: 'highRight', title: 'Pivot high right bars', value: 10, min: 1, max: 250},
        {id: 'lowLeft', title: 'Pivot low left bars', value: 10, min: 1, max: 250},
        {id: 'lowRight', title: 'Pivot low right bars', value: 10, min: 1, max: 250},
        {id: 'showPrices', title: 'Show pivot prices', type: 'bool', value: true}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const pivots = (field, left, right, direction) => {
          const prices = bars.map(bar => bar[field]);
          return prices.map((_, i) => {
            const confirmation = bars[i + right];
            return confirmation && !confirmation.provisional
              ? pivotValue(prices, i, left, right, direction) : null;
          });
        };
        return [
          pivots('high', inputs.highLeft ?? 10, inputs.highRight ?? 10, 1),
          pivots('low', inputs.lowLeft ?? 10, inputs.lowRight ?? 10, -1)
        ];
      }
    },
    Chandelier: {
      name: 'Chandelier Exit', length: 22, lengthLabel: 'Length', plotNames: ['Long exit', 'Short exit'],
      plotColors: ['#2962ff', '#ff6d00'],
      inputs: [
        {id: 'atrLength', title: 'ATR length', value: 22, min: 1, max: 250},
        {id: 'atrMultiplier', title: 'ATR multiplier', type: 'float', value: 3, min: 0, max: 100}
      ],
      run(bars, values, length, multiplier, {atrLength = 22, atrMultiplier = 3} = {}) {
        const volatility = atr(bars, atrLength);
        const high = rollingExtreme(bars.map(bar => bar.high), length, 1);
        const low = rollingExtreme(bars.map(bar => bar.low), length, -1);
        return [
          high.map((value, i) => volatility[i] === null ? null : value - atrMultiplier * volatility[i]),
          low.map((value, i) => volatility[i] === null ? null : value + atrMultiplier * volatility[i])
        ];
      }
    },
    ChandeKroll: {
      name: 'Chande Kroll Stop', plotNames: ['Long stop', 'Short stop'],
      plotColors: ['#2196f3', '#f23645'],
      inputs: [
        {id: 'atrLength', title: 'ATR length', value: 10, min: 1, max: 250},
        {id: 'atrMultiplier', title: 'ATR multiplier', type: 'float', value: 1, min: 0, max: 100},
        {id: 'stopLength', title: 'Stop length', value: 9, min: 1, max: 250}
      ],
      run(bars, values, length, multiplier, {atrLength = 10, atrMultiplier = 1, stopLength = 9} = {}) {
        const volatility = atr(bars, atrLength);
        const highest = rollingExtreme(bars.map(bar => bar.high), atrLength, 1);
        const lowest = rollingExtreme(bars.map(bar => bar.low), atrLength, -1);
        const upper = highest.map((value, i) => volatility[i] === null ? null : value - atrMultiplier * volatility[i]);
        const lower = lowest.map((value, i) => volatility[i] === null ? null : value + atrMultiplier * volatility[i]);
        return [rollingExtreme(lower, stopLength, -1), rollingExtreme(upper, stopLength, 1)];
      }
    },
    PSAR: {
      name: 'Parabolic SAR', plotOptions: [{style: 'cross'}],
      inputs: [
        {id: 'start', title: 'Start', type: 'float', value: 0.02, min: 0, max: 1},
        {id: 'increment', title: 'Increment', type: 'float', value: 0.02, min: 0, max: 1},
        {id: 'maximum', title: 'Max value', type: 'float', value: 0.2, min: 0, max: 1}
      ],
      run(bars, values, length, multiplier, {start = 0.02, increment = 0.02, maximum = 0.2} = {}) {
        let rising, sar, extreme, acceleration;
        const initialAcceleration = Math.min(start, maximum);
        return [bars.map((bar, i) => {
          if (i === 0) return null;
          const previous = bars[i - 1];
          let reset = i === 1;
          if (reset) {
            rising = bar.close > previous.close;
            sar = rising ? previous.low : previous.high;
            extreme = rising ? bar.high : bar.low;
            acceleration = initialAcceleration;
          }
          sar += acceleration * (extreme - sar);
          if (rising ? sar > bar.low : sar < bar.high) {
            sar = rising ? Math.max(bar.high, extreme) : Math.min(bar.low, extreme);
            rising = !rising;
            extreme = rising ? bar.high : bar.low;
            acceleration = initialAcceleration;
            reset = true;
          }
          if (!reset && (rising ? bar.high > extreme : bar.low < extreme)) {
            extreme = rising ? bar.high : bar.low;
            acceleration = Math.min(acceleration + increment, maximum);
          }
          const earlier = bars[i - 2] ?? previous;
          sar = rising ? Math.min(sar, previous.low, earlier.low) : Math.max(sar, previous.high, earlier.high);
          return sar;
        })];
      }
    },
    Supertrend: {
      name: 'Supertrend', length: 10, multiplier: 3, multiplierLabel: 'Factor',
      plotNames: ['Supertrend up', 'Supertrend down'], plotColors: ['#089981', '#f23645'], segmented: true,
      run: (bars, values, length, factor) => supertrend(bars, length, factor)
    },
    VStop: {
      name: 'Volatility Stop', length: 20, minLength: 2, multiplier: 2, multiplierLabel: 'ATR factor',
      plotNames: ['Volatility Stop'],
      run(bars, values, length, factor) {
        const ranges = trueRange(bars, index => index > 0);
        const averages = atr(bars, length);
        let rising = true;
        let extreme;
        let stop;
        const directions = [];
        const points = values.map((value, index) => {
          if (!Number.isFinite(value)) return null;
          const distance = Number.isFinite(averages[index]) ? averages[index] * factor : ranges[index] ?? 0;
          if (stop === undefined) {
            extreme = value;
            stop = value - distance;
          } else {
            extreme = rising ? Math.max(extreme, value) : Math.min(extreme, value);
            const trail = rising ? extreme - distance : extreme + distance;
            stop = rising ? Math.max(stop, trail) : Math.min(stop, trail);
            const nextRising = value >= stop;
            if (nextRising !== rising) {
              rising = nextRising;
              extreme = value;
              stop = rising ? value - distance : value + distance;
            }
          }
          directions[index] = rising;
          return stop;
        });
        points.colors = points.map((_, index) => directions[index] ? '#089981' : '#f23645');
        return [points];
      }
    },
    Volume: {
      name: 'Volume', pane: true, volume: true, format: 'volume', histogramPlots: [0],
      plotNames: ['Volume', 'Volume MA'], plotColors: [undefined, '#0496ff'],
      inputs: [
        {id: 'showAverage', title: 'Show volume average', type: 'bool', value: false},
        {id: 'averageLength', title: 'Volume MA length', value: 20, min: 1, max: 2000}
      ],
      run(bars, values, length, multiplier, {showAverage = false, averageLength = 20} = {}) {
        const volume = bars.map(bar => Number.isFinite(bar.volume) && bar.volume >= 0 ? bar.volume : null);
        if (!showAverage) return [volume];
        const period = Number.isInteger(averageLength) && averageLength >= 1 && averageLength <= 2000 ? averageLength : 20;
        const coverage = sma(volume.map(value => Number(value !== null)), period);
        const average = sma(volume.map(value => value ?? 0), period);
        return [volume, average.map((value, i) => coverage[i] === 1 ? value : null)];
      }
    },
    MajorityRule: {
      name: 'Majority Rule', pane: true,
      plotNames: ['Majority Rule'], plotColors: ['#ff5252'],
      inputs: [{id: 'period', title: 'Rolling Period', value: 14, min: 1, max: 2000}],
      run(bars, values, length, multiplier, {period = 14} = {}) {
        const direction = bars.map(({close}, index) => {
          const previous = bars[index - 1]?.close;
          return Number.isFinite(close) && Number.isFinite(previous) ? Number(close > previous) : null;
        });
        const coverage = sma(direction.map(value => Number(value !== null)), period);
        const fraction = sma(direction.map(value => value ?? 0), period);
        return [fraction.map((value, index) => coverage[index] === 1 ? value * 100 : null)];
      }
    },
    NetVolume: {
      name: 'Net Volume', pane: true, volume: true, format: 'volume',
      plotNames: ['Plot'], plotColors: ['#2196f3'],
      run(bars) {
        return [bars.map(({close, volume}, index) => {
          const previousClose = bars[index - 1]?.close;
          if (!Number.isFinite(close) || !Number.isFinite(previousClose)
              || !Number.isFinite(volume) || volume < 0) return null;
          return close === previousClose ? 0 : close > previousClose ? volume : -volume;
        })];
      }
    },
    MFI: {
      name: 'Money Flow Index', length: 14, pane: true, volume: true,
      run: (bars, values, length) => [moneyFlowIndex(bars, bars.map(bar => (bar.high + bar.low + bar.close) / 3), length)]
    },
    ADL: {
      name: 'Accumulation/Distribution Line', pane: true, volume: true,
      run: bars => [accumulationDistribution(bars)]
    },
    EFI: {
      name: "Elder's Force Index", length: 13, pane: true, volume: true,
      run(bars, values, length) {
        const force = bars.map(({close, volume}, i) => {
          const previous = bars[i - 1]?.close;
          return Number.isFinite(close) && Number.isFinite(previous) && Number.isFinite(volume) && volume >= 0
            ? (close - previous) * volume : null;
        });
        const smoothed = ema(force.filter(Number.isFinite), length);
        let index = 0;
        return [force.map(value => value === null ? null : smoothed[index++])];
      }
    },
    CHO: {
      name: 'Chaikin Oscillator', pane: true, volume: true,
      inputs: [
        {id: 'fastLength', title: 'Fast length', value: 3, min: 1, max: 250},
        {id: 'slowLength', title: 'Slow length', value: 10, min: 1, max: 250}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const adl = accumulationDistribution(bars);
        const available = adl.filter(Number.isFinite);
        const fast = ema(available, inputs.fastLength ?? 3);
        const slow = ema(available, inputs.slowLength ?? 10);
        let index = 0;
        return [adl.map(value => {
          if (value === null) return null;
          const oscillator = fast[index] - slow[index];
          index++;
          return oscillator;
        })];
      }
    },
    Klinger: {
      name: 'Klinger Oscillator', pane: true, volume: true,
      plotNames: ['Klinger', 'Signal'], plotColors: ['#2196f3', '#43a047'],
      plotOptions: [{width: 1}, {width: 1}],
      run(bars) {
        let previousRange = 0;
        let previousPriceSum = null;
        let previousTrend = 0;
        let cumulativeRange = 0;
        const force = bars.map(({high, low, close, volume}) => {
          const range = high - low;
          const priceSum = high + low + close;
          const trend = previousPriceSum === null ? 0 : priceSum > previousPriceSum ? 1 : -1;
          cumulativeRange = range + (trend === previousTrend ? cumulativeRange : previousRange);
          previousRange = range;
          previousPriceSum = priceSum;
          previousTrend = trend;
          if (!trend || !Number.isFinite(volume) || volume < 0) return null;
          return cumulativeRange > 0 ? volume * 200 * (range / cumulativeRange - 1) * trend : 0;
        });
        const available = force.filter(Number.isFinite);
        const fast = ema(available, 34);
        const slow = ema(available, 55);
        const oscillator = fast.map((value, i) => value - slow[i]);
        const signal = ema(oscillator, 13);
        const align = series => {
          let index = 0;
          return force.map(value => value === null ? null : series[index++]);
        };
        return [align(oscillator), align(signal)];
      }
    },
    UlcerIndex: {
      name: 'Ulcer Index', length: 14, pane: true, format: 'percent',
      plotNames: ['Ulcer Index'], plotColors: ['#2962ff'],
      run(bars, values, length) {
        const peaks = rollingExtreme(values, length, 1);
        const squaredDrawdowns = values.map((value, index) => {
          const peak = peaks[index];
          if (!Number.isFinite(value) || !(peak > 0)) return null;
          return (100 * (value - peak) / peak) ** 2;
        });
        return [smaWithGaps(squaredDrawdowns, length).map(value =>
          value === null ? null : Math.sqrt(Math.max(0, value)))];
      }
    },
    HistoricalVolatility: {
      name: 'Historical Volatility', length: 10, pane: true, format: 'percent',
      inputs: [{id: 'periodsPerYear', title: 'Bars per year', value: 365, min: 1, max: 525600}],
      run(bars, values, length, multiplier, {periodsPerYear = 365} = {}) {
        return [closeVolatility(values, length, periodsPerYear)];
      }
    },
    VolatilityCloseToClose: {
      name: 'Volatility Close-to-Close', pane: true, format: 'percent',
      plotNames: ['Plot'], plotColors: ['#2196f3'],
      inputs: [
        {id: 'periods', title: 'Periods', value: 10, min: 2, max: 2000},
        {id: 'daysPerYear', title: 'Days Per Year', value: 252, min: 1, max: 525600}
      ],
      run(bars, values, length, multiplier, {periods = 10, daysPerYear = 252} = {}) {
        return [closeVolatility(bars.map(bar => bar.close), periods, daysPerYear, true)];
      }
    },
    VolatilityZeroTrendCloseToClose: {
      name: 'Volatility Zero Trend Close-to-Close', pane: true, format: 'percent',
      plotNames: ['Plot'], plotColors: ['#2196f3'],
      inputs: [
        {id: 'periods', title: 'Periods', value: 10, min: 1, max: 2000},
        {id: 'daysPerYear', title: 'Days Per Year', value: 252, min: 1, max: 525600}
      ],
      run(bars, values, length, multiplier, {periods = 10, daysPerYear = 252} = {}) {
        const dailyVariance = bars.map((bar, index) => {
          const prior = bars[index - 1];
          const seconds = (bar.sourceTime ?? bar.time) - (prior?.sourceTime ?? prior?.time);
          if (!(seconds > 0) || !(bar.close > 0) || !(prior?.close > 0)) return null;
          const change = Math.log(bar.close) - Math.log(prior.close);
          return Number.isFinite(change) ? change ** 2 * 86400 / seconds : null;
        });
        return [annualizedDailyVariance(dailyVariance, periods, daysPerYear)];
      }
    },
    VolatilityOHLC: {
      name: 'Volatility O-H-L-C', pane: true, format: 'percent',
      plotNames: ['Plot'], plotColors: ['#ff5252'],
      inputs: [
        {id: 'periods', title: 'Periods', value: 10, min: 1, max: 2000},
        {id: 'closedFraction', title: 'Market Closed Percentage', type: 'float', value: 0, min: 0, max: 0.9999,
          tooltip: 'Enter a fraction, for example 0.5 for 50%.'},
        {id: 'daysPerYear', title: 'Days Per Year', value: 252, min: 1, max: 525600}
      ],
      run(bars, values, length, multiplier, {periods = 10, closedFraction = 0, daysPerYear = 252} = {}) {
        const dailyVariance = bars.map((bar, index) => {
          const prior = bars[index - 1];
          const seconds = (bar.sourceTime ?? bar.time) - (prior?.sourceTime ?? prior?.time);
          const {open, high, low, close} = bar;
          if (!(seconds > 0) || ![open, high, low, close].every(value => Number.isFinite(value) && value > 0)) return null;
          const session = 0.5 * Math.log(high / low) ** 2 - (2 * Math.LN2 - 1) * Math.log(close / open) ** 2;
          if (closedFraction === 0) return session * 86400 / seconds;
          if (!(closedFraction > 0 && closedFraction < 1) || !(prior.close > 0)) return null;
          const gap = Math.log(open / prior.close) ** 2;
          return (0.88 * session / (1 - closedFraction) + 0.12 * gap / closedFraction) * 86400 / seconds;
        });
        return [annualizedDailyVariance(dailyVariance, periods, daysPerYear)];
      }
    },
    ChaikinVolatility: {
      name: 'Chaikin Volatility', pane: true, plotColors: ['#ab47bc'], format: 'percent',
      inputs: [
        {id: 'emaLength', title: 'EMA length', value: 10, min: 1, max: 250},
        {id: 'rocLength', title: 'Rate of change lookback', value: 10, min: 1, max: 250}
      ],
      run(bars, values, length, multiplier, {emaLength = 10, rocLength = 10} = {}) {
        const smoothRange = ema(bars.map(bar => bar.high - bar.low), emaLength);
        return indicators.ROC.run(bars, smoothRange, rocLength);
      }
    },
    CMF: {
      name: 'Chaikin Money Flow', length: 20, pane: true, volume: true,
      run(bars, values, length) {
        const volumes = bars.map(bar => Number.isFinite(bar.volume) && bar.volume >= 0 ? bar.volume : null);
        const flow = bars.map((bar, i) => bar.high > bar.low
          ? (2 * bar.close - bar.high - bar.low) / (bar.high - bar.low) * (volumes[i] ?? 0) : 0);
        const volumeMean = sma(volumes.map(value => value ?? 0), length);
        const flowMean = sma(flow, length);
        const coverage = sma(volumes.map(value => Number(value !== null)), length);
        return [flowMean.map((value, i) => coverage[i] === 1 && volumeMean[i] > 0
          ? value / volumeMean[i] : null)];
      }
    },
    VWMA: {
      name: 'Volume Weighted Moving Average', length: 20, volume: true,
      run: (bars, values, length) => [vwma(bars, values, length)]
    },
    NVI: {
      name: 'Negative Volume Index', pane: true, volume: true, length: 255, maxLength: 2000, lengthLabel: 'EMA length',
      plotNames: ['NVI', 'NVI EMA'], plotColors: ['#2962ff', '#ff6d00'],
      run: (bars, values, length) => volumeIndex(bars, false, length)
    },
    PVI: {
      name: 'Positive Volume Index', pane: true, volume: true, length: 255, maxLength: 2000, lengthLabel: 'EMA length',
      plotNames: ['PVI', 'PVI EMA'], plotColors: ['#2962ff', '#ff6d00'],
      run: (bars, values, length) => volumeIndex(bars, true, length)
    },
    OBV: {
      name: 'On-Balance Volume', pane: true, volume: true,
      plotNames: ['OBV', 'OBV moving average', 'Upper band', 'Lower band'],
      plotColors: ['#2962ff', '#f9a825', '#089981', '#089981'], backgroundBand: [2, 3],
      inputs: smoothingInputs,
      run: (bars, values, length, multiplier, inputs) => smoothedStudy(bars, obv(bars), inputs)
    },
    BollingerBars: {
      name: 'Bollinger Bars', bollingerBars: true,
      inputs: [
        {id: 'upColor', title: 'Up body', type: 'color', value: '#089981', section: 'Style'},
        {id: 'downColor', title: 'Down body', type: 'color', value: '#f23645', section: 'Style'},
        {id: 'wickColor', title: 'Wicks', type: 'color', value: '#2962ff', section: 'Style'}
      ]
    },
    VolumeDelta: {
      name: 'Volume Delta', pane: true, volume: true, format: 'volume',
      plotNames: ['Delta', 'High', 'Low', 'Open'], deltaCandles: true,
      plotOptions: [{}, {display: 12}, {display: 12}, {display: 12}],
      inputs: [deltaIntrabarInput, deltaTickInput, ...deltaCandleStyleInputs],
      run(bars, intrabars, closeTime, intrabarClose, cutoff = Infinity) {
        let cursor = 0, priorClose, direction = 0;
        const candles = bars.map(bar => {
          const end = closeTime(bar);
          const limit = Math.min(end, cutoff);
          const first = intrabars[0]?.time;
          let high = 0, low = 0, close = 0, count = 0, invalid = false;
          while (cursor < intrabars.length && intrabars[cursor].time < limit) {
            const sample = intrabars[cursor++];
            direction = Math.sign(sample.close - sample.open)
              || (priorClose === undefined ? 0 : Math.sign(sample.close - priorClose)) || direction;
            priorClose = sample.close;
            if (sample.time < bar.time || intrabarClose(sample) > end
                || (!sample.provisional && intrabarClose(sample) > cutoff)) continue;
            if (!Number.isFinite(sample.volume) || sample.volume < 0 || (!direction && sample.volume > 0)) {
              invalid = true;
              continue;
            }
            close += direction * sample.volume;
            high = Math.max(high, close);
            low = Math.min(low, close);
            count++;
          }
          return count && !invalid && first <= bar.time ? {open: 0, high, low, close} : null;
        });
        return volumeDeltaPlots(candles);
      }
    },
    CumulativeVolumeDelta: {
      name: 'Cumulative Volume Delta', pane: true, volume: true, format: 'volume',
      plotNames: ['Cumulative delta', 'High', 'Low', 'Open'], deltaCandles: true, cumulativeDelta: true,
      plotOptions: [{}, {display: 12}, {display: 12}, {display: 12}],
      inputs: [{id: 'anchor', title: 'Anchor period', type: 'string', value: '1D',
        options: ['1D', '1W', '1M', '3M', '12M']}, deltaIntrabarInput, deltaTickInput, ...deltaCandleStyleInputs],
      run(bars, intrabars, closeTime, intrabarClose, cutoff, anchorKey) {
        const [delta] = indicators.VolumeDelta.run(bars, intrabars, closeTime, intrabarClose, cutoff);
        return volumeDeltaPlots(accumulateVolumeDelta(bars, delta.candles, anchorKey));
      }
    },
    RelativeVolume: {
      name: 'Relative Volume', length: 10, pane: true, volume: true,
      plotNames: ['Relative volume'], plotColors: ['#2962ff'],
      run(bars, values, length) {
        const volume = bars.map(bar => Number.isFinite(bar.volume) && bar.volume >= 0 ? bar.volume : null);
        const average = sma(volume.map(value => value ?? 0), length);
        const coverage = sma(volume.map(value => Number(value !== null)), length);
        return [volume.map((value, index) => {
          const prior = average[index - 1];
          return value !== null && coverage[index - 1] === 1 && prior > 0 ? value / prior : null;
        })];
      }
    },
    RelativeVolumeAtTime: {
      name: 'Relative Volume at Time', length: 10, pane: true, volume: true,
      plotNames: ['Relative volume'], plotColors: ['#2962ff'],
      inputs: [
        {id: 'anchor', title: 'Anchor timeframe', type: 'string', value: '1D',
          options: ['1D', '1W', '1M', '3M', '12M']},
        {id: 'mode', title: 'Calculation mode', type: 'string', value: 'Cumulative', options: ['Cumulative', 'Regular']}
      ],
      run(bars, values, length, multiplier, {anchor = '1D', mode = 'Cumulative'} = {}, symbolInfo = {}) {
        const calendarDays = {D: 1, W: 7, M: 30.44};
        const [,, anchorUnit] = /^(\d+)([DWM])$/.exec(anchor) ?? ['1D', '1', 'D'];
        const [, count, unit] = /^(\d+)([DWM])$/.exec(symbolInfo.interval ?? '') ?? [];
        const anchorSize = Number.parseInt(anchor, 10);
        const resetEachBar = count * calendarDays[unit] >= anchorSize * calendarDays[anchorUnit];
        const sessionOffset = symbolInfo.sessionOffset ?? 0;
        const historical = [];
        let period = [], previous, start, total;
        return [bars.map((bar, index) => {
          const time = (bar.sourceTime ?? bar.time) + sessionOffset;
          const day = Math.floor(time / 86400);
          let key = day;
          if (resetEachBar) key = index;
          else if (anchorUnit === 'W') key = Math.floor((day + 3) / 7);
          else if (anchorUnit === 'M') {
            const date = new Date(time * 1000);
            key = Math.floor((date.getUTCFullYear() * 12 + date.getUTCMonth()) / anchorSize);
          }
          if (key !== previous) {
            if (period.length) {
              historical.push(period);
              if (historical.length > length) historical.shift();
            }
            period = [];
            previous = key;
            start = !resetEachBar && anchorUnit === 'D' && Number.isFinite(symbolInfo.sessionOpen)
              ? Math.min(time, day * 86400 + symbolInfo.sessionOpen) : time;
            total = 0;
          }
          const valid = Number.isFinite(bar.volume) && bar.volume >= 0;
          total = valid && total !== null ? total + bar.volume : null;
          const volume = mode === 'Regular' ? (valid ? bar.volume : null) : total;
          const offset = time - start;
          period.push({offset, volume});
          if (volume === null || historical.length < length) return null;
          let sum = 0, matches = 0;
          for (const prior of historical) {
            let left = 0, right = prior.length;
            while (left < right) {
              const middle = Math.floor((left + right) / 2);
              if (prior[middle].offset <= offset) left = middle + 1;
              else right = middle;
            }
            const reference = prior[left - 1]?.volume;
            if (Number.isFinite(reference)) {
              sum += reference;
              matches++;
            }
          }
          return sum > 0 ? volume * matches / sum : null;
        })];
      }
    },
    PVT: {
      name: 'Price Volume Trend', pane: true, volume: true, plotNames: ['PVT'], plotColors: ['#2962ff'],
      run(bars) {
        let total = 0;
        return [bars.map(({close, volume}, index) => {
          const previous = bars[index - 1]?.close;
          if (!Number.isFinite(previous) || previous === 0 || !Number.isFinite(close)
              || !Number.isFinite(volume) || volume < 0) return null;
          total += (close - previous) / previous * volume;
          return total;
        })];
      }
    },
    TWAP: {
      name: 'Time Weighted Average Price', allPlotOffset: true,
      plotNames: ['TWAP'], plotColors: ['#2962ff'],
      inputs: [
        {id: 'anchor', title: 'Anchor period', type: 'string', value: '1D', options: ['1D', '1W', '1M', '3M', '12M']},
        {id: 'source', title: 'Source', type: 'source', value: 'ohlc4', options: studyPriceSourceNames},
        {id: 'offset', title: 'Offset', value: 0, min: -500, max: 500}
      ],
      run: (bars, values, length, multiplier, inputs, symbolInfo) => anchoredTwap(bars, inputs, symbolInfo)
    },
    VWAP: {
      name: 'Volume Weighted Average Price', volume: true,
      plotNames: ['VWAP', 'Upper band 1', 'Lower band 1', 'Upper band 2', 'Lower band 2', 'Upper band 3', 'Lower band 3'],
      plotColors: ['#2962ff', '#089981', '#089981', '#00bcd4', '#00bcd4', '#7e57c2', '#7e57c2'],
      inputs: [
        {id: 'anchor', title: 'Anchor period', type: 'string', value: 'Session',
          options: ['Session', 'Week', 'Month', 'Quarter', 'Year', 'Decade', 'Century']},
        {id: 'source', title: 'Source', type: 'source', value: 'hlc3', options: studyPriceSourceNames},
        {id: 'hideHigher', title: 'Hide on daily or higher intervals', type: 'bool', value: false},
        {id: 'bandMode', title: 'Band calculation mode', type: 'string', value: 'Standard deviation',
          options: ['Standard deviation', 'Percentage'], group: 'Bands'},
        ...[1, 2, 3].flatMap(index => [
          {id: 'showBand' + index, title: 'Show band ' + index, type: 'bool', value: false, group: 'Bands'},
          {id: 'bandMultiplier' + index, title: 'Band ' + index + ' multiplier',
            type: 'float', value: index, min: 0, max: 100, step: .1, group: 'Bands'}
        ]),
        ...[1, 2, 3].flatMap((index, i) => [
          {id: 'fillBand' + index, title: 'Fill band ' + index, type: 'bool', value: false, section: 'Style', group: 'Band fills'},
          {id: 'fillBandColor' + index, title: 'Band ' + index + ' fill color', type: 'color',
            value: ['#089981', '#00bcd4', '#7e57c2'][i], section: 'Style', group: 'Band fills'},
          {id: 'fillBandOpacity' + index, title: 'Band ' + index + ' fill opacity (%)', value: 10,
            min: 0, max: 100, section: 'Style', group: 'Band fills'}
        ])
      ],
      run: (bars, values, length, multiplier, inputs, symbolInfo) => anchoredVwap(bars, inputs, symbolInfo)
    },
    AutoVWAP: {
      name: 'VWAP Auto Anchored', volume: true,
      get plotNames() { return indicators.VWAP.plotNames; },
      get plotColors() { return indicators.VWAP.plotColors; },
      get inputs() {
        const [anchor, source, , ...bands] = indicators.VWAP.inputs;
        return [
          {...anchor, value: 'Auto', options: ['Auto', 'Highest High', 'Lowest Low', 'Highest Volume', ...anchor.options]},
          source,
          {id: 'lookback', title: 'Length (high, low, or volume anchor)', value: 100, min: 1, max: 5000},
          {id: 'offset', title: 'Offset', value: 0, min: -500, max: 500},
          ...bands
        ];
      },
      run(bars, values, length, multiplier, inputs = {}, symbolInfo = {}) {
        const start = autoVwapStart(bars, inputs.anchor ?? 'Auto', inputs.lookback ?? 100, symbolInfo);
        return shiftStudyPlots(anchoredVwap(bars, inputs, symbolInfo, start), inputs.offset ?? 0);
      }
    },
    HammingMA: {
      name: 'Moving Average Hamming', length: 20, lengthLabel: 'Length',
      plotNames: ['Hamming MA'], plotColors: ['#4caf50'],
      run(bars, values, length) {
        if (length === 1) return [values.map(value => Number.isFinite(value) ? value : null)];
        const weights = Array.from({length}, (_, index) =>
          0.54 - 0.46 * Math.cos(2 * Math.PI * index / (length - 1)));
        const weightSum = weights.reduce((sum, weight) => sum + weight, 0);
        return [values.map((_, index) => {
          if (index < length - 1) return null;
          let weighted = 0;
          for (let lag = 0; lag < length; lag++) {
            const value = values[index - lag];
            if (!Number.isFinite(value)) return null;
            weighted += value * weights[lag];
          }
          return weighted / weightSum;
        })];
      }
    },
    KAMA: {
      name: "Kaufman's Adaptive Moving Average", length: 10, lengthLabel: 'ER length',
      plotNames: ['KAMA'], plotColors: ['#2962ff'],
      inputs: [
        {id: 'fastLength', title: 'Fast length', value: 2, min: 1, max: 1000},
        {id: 'slowLength', title: 'Slow length', value: 30, min: 1, max: 1000}
      ],
      run(bars, values, length, multiplier, {fastLength = 2, slowLength = 30} = {}) {
        const fast = 2 / (fastLength + 1);
        const slow = 2 / (slowLength + 1);
        const changes = values.map((value, index) => {
          const prior = values[index - 1];
          return Number.isFinite(value) && Number.isFinite(prior) ? Math.abs(value - prior) : null;
        });
        const averageNoise = smaWithGaps(changes, length);
        let average;
        return [values.map((value, index) => {
          const noise = averageNoise[index];
          const start = values[index - length];
          if (!Number.isFinite(noise) || !Number.isFinite(start) || !Number.isFinite(value)) {
            average = undefined;
            return null;
          }
          const efficiency = noise > 0 ? Math.min(1, Math.abs(value - start) / (noise * length)) : 0;
          const smoothing = (slow + efficiency * (fast - slow)) ** 2;
          average = average === undefined ? value : average + smoothing * (value - average);
          return average;
        })];
      }
    },
    Guppy: {
      name: 'Guppy Multiple Moving Average',
      plotNames: guppyAverages.map(average => average.name),
      plotColors: guppyAverages.map(average => average.color),
      inputs: guppyAverages.map(({id, name, group, period}) => ({
        id, title: name + ' length', group, value: period, min: 1, max: 1000
      })),
      run(bars, values, length, multiplier, inputs = {}) {
        return guppyAverages.map(({id, period}) => ema(values, inputs[id] ?? period));
      }
    },
    Spread: pairedPriceStudy('Spread', (primary, comparison) => primary - comparison),
    Ratio: pairedPriceStudy('Ratio', (primary, comparison) => comparison === 0 ? null : primary / comparison),
    CorrelationCoefficient: {
      name: 'Correlation Coefficient', length: 20, pane: true, secondarySymbol: true, requiresSecondarySymbol: true,
      plotNames: ['Correlation'], plotColors: ['#2962ff'],
      plotOptions: [{style: 'area'}],
      inputs: [
        {id: 'symbol', title: 'Comparison symbol', type: 'string', value: '',
          tooltip: 'Enter another instrument code from the selected OHLC source.'},
        {id: 'source', title: 'Source', type: 'source', value: 'close', options: studyPriceSourceNames}
      ],
      pairedPlots(bars, reference, length, {source = 'close'} = {}) {
        const price = pineSources[source] ?? pineSources.close;
        const prices = new Map(reference.map(bar => [bar.time, price(bar)]));
        const paired = bars.map(bar => prices.get(bar.sourceTime ?? bar.time));
        return [rollingPearson(bars.map(price), paired, length)];
      }
    },
    CorrelationLog: {
      name: 'Correlation - Log', length: 25, pane: true, secondarySymbol: true, requiresSecondarySymbol: true,
      plotNames: ['Log-return correlation'], plotColors: ['#2196f3'],
      inputs: [
        {id: 'symbol', title: 'Comparison symbol', type: 'string', value: '',
          tooltip: 'Choose another instrument from the selected OHLC source. Correlation uses closing-price log returns.'}
      ],
      pairedPlots(bars, reference, length) {
        const prices = new Map(reference.map(bar => [bar.time, bar.close]));
        const paired = bars.map(bar => prices.get(bar.sourceTime ?? bar.time));
        const returns = values => values.map((value, index) => {
          const prior = values[index - 1];
          if (!Number.isFinite(value) || value <= 0 || !Number.isFinite(prior) || prior <= 0) return null;
          const change = (value - prior) / prior;
          return Number.isFinite(change) && change > -1
            ? Math.log1p(change) : Math.log(value) - Math.log(prior);
        });
        return [rollingPearson(returns(bars.map(bar => bar.close)), returns(paired), length)];
      }
    },
    MovingAverageMultiple: {
      name: 'Moving Average Multiple', secondarySymbol: true,
      plotNames: multipleAveragePeriods.map((_, index) => 'Plot ' + (index + 1)),
      plotColors: ['#9c27b0', '#ff6d00', '#43a047', '#26c6da', '#f50057', '#2196f3'],
      inputs: [
        ...multipleAveragePeriods.map((value, index) => ({
          id: 'period' + index, title: ['1st', '2nd', '3rd', '4th', '5th', '6th'][index] + ' Period',
          value, min: 1, max: 5000
        })),
        {id: 'method', title: 'Method', type: 'string', value: 'Simple', options: ['Simple', 'Exponential', 'Weighted']},
        {id: 'symbol', title: 'Another symbol', type: 'string', value: '', group: 'Source',
          tooltip: 'Enter the exact instrument code for the selected OHLC source. Leave blank to use the chart symbol.'}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const average = inputs.method === 'Exponential' ? ema : inputs.method === 'Weighted' ? wma : sma;
        const closes = bars.map(bar => bar.close);
        return multipleAveragePeriods.map((period, index) => average(closes, inputs['period' + index] ?? period));
      }
    },
    MARibbon: {
      name: 'Moving Average Ribbon',
      plotNames: ribbonLengths.map((_, index) => 'MA ' + (index + 1)),
      plotColors: ['#f6c309', '#fb9800', '#fb6500', '#f23645'],
      inputs: ribbonLengths.flatMap((length, index) => {
        const group = 'MA ' + (index + 1);
        const active = {id: 'show' + index, value: true};
        return [
          {...active, title: 'Show ' + group, type: 'bool', group},
          {id: 'method' + index, title: group + ' type', type: 'string', group, value: 'SMA', options: ribbonMethods, active},
          {id: 'source' + index, title: group + ' source', type: 'source', group, value: 'close', options: studyPriceSourceNames, active},
          {id: 'length' + index, title: group + ' length', group, value: length, min: 1, max: 5000, active}
        ];
      }),
      run(bars, values, length, multiplier, inputs = {}) {
        return ribbonLengths.map((fallback, index) => {
          if (inputs['show' + index] === false) return bars.map(() => null);
          const requestedLength = inputs['length' + index];
          const period = Number.isInteger(requestedLength) && requestedLength >= 1 && requestedLength <= 5000
            ? requestedLength : fallback;
          const source = inputs['source' + index];
          const price = studyPriceSourceNames.includes(source) ? pineSources[source] : pineSources.close;
          return movingAverage(bars, bars.map(price), period, inputs['method' + index]);
        });
      }
    },
    SMA: {
      name: 'Simple Moving Average', length: 20,
      plotNames: ['SMA', 'Smoothing line', 'Upper band', 'Lower band'],
      inputs: movingAverageInputs, primaryPlotOffset: true, backgroundBand: [2, 3],
      run: (bars, values, length, multiplier, inputs) => smoothedStudy(bars, sma(values, length), inputs)
    },
    HMA: {
      name: 'Hull Moving Average', length: 9,
      run(bars, values, length) {
        return [hma(values, length)];
      }
    },
    ALMA: {
      name: 'Arnaud Legoux Moving Average', length: 9,
      run: (bars, values, length, multiplier, inputs) => [alma(values, length,
        Number.isFinite(inputs?.offset) ? inputs.offset : 0.85,
        Number.isFinite(inputs?.sigma) && inputs.sigma > 0 ? inputs.sigma : 6, inputs?.floor === true)]
    },
    COG: {
      name: 'Center of Gravity', length: 10, pane: true,
      run: (bars, values, length) => [cog(values, length)]
    },
    SWMA: { name: 'Symmetrically Weighted Moving Average', run: (bars, values) => [swma(values)] },
    WMA: { name: 'Weighted Moving Average', length: 20, run: (bars, values, length) => [wma(values, length)] },
    DEMA: {
      name: 'Double Exponential Moving Average', length: 9,
      run(bars, values, length) {
        const first = ema(values, length);
        const second = ema(first, length);
        return [first.map((value, i) => 2 * value - second[i])];
      }
    },
    TEMA: {
      name: 'Triple Exponential Moving Average', length: 9,
      run(bars, values, length) {
        const first = ema(values, length);
        const second = ema(first, length);
        const third = ema(second, length);
        return [first.map((value, i) => 3 * (value - second[i]) + third[i])];
      }
    },
    MedianPrice: {
      name: 'Median Price', plotNames: ['Median Price'], plotColors: ['#ff6d00'],
      run: bars => [bars.map(({high, low}) => (high + low) / 2)]
    },
    TypicalPrice: {
      name: 'Typical Price', plotNames: ['Typical Price'], plotColors: ['#ff6d00'],
      run: bars => [bars.map(({high, low, close}) => (high + low + close) / 3)]
    },
    AveragePrice: {
      name: 'Average Price', plotNames: ['Average Price'], plotColors: ['#2196f3'],
      run: bars => [bars.map(({open, high, low, close}) => (open + high + low + close) / 4)]
    },
    Median: {
      name: 'Median', length: 3, lengthLabel: 'Median length',
      plotNames: ['Median', 'Median EMA', 'Upper band', 'Lower band'],
      plotColors: ['#f23645', '#2962ff', '#00c878', '#d33dff'],
      plotOptions: [{width: 3}, {}, {}, {}],
      backgroundBand: [0, 1], backgroundBandColors: ['#00c878', '#d33dff'], backgroundBandOpacity: 70,
      inputs: [
        {id: 'medianSource', title: 'Median source', type: 'source', value: 'hl2', options: studyPriceSourceNames},
        {id: 'atrLength', title: 'ATR length', value: 14, min: 1, max: 5000},
        {id: 'atrMultiplier', title: 'ATR multiplier', type: 'float', value: 2, min: 0, max: 100},
        {id: 'background', title: 'Show cloud', type: 'bool', value: true},
        {id: 'backgroundOpacity', title: 'Cloud opacity (%)', value: 70, min: 0, max: 100}
      ],
      run(bars, values, length, multiplier, {medianSource = 'hl2', atrLength = 14, atrMultiplier = 2} = {}) {
        const source = bars.map(studyPriceSourceNames.includes(medianSource) ? pineSources[medianSource] : pineSources.hl2);
        const center = source.map((_, i) => i < length - 1 ? null : median(source.slice(i - length + 1, i + 1)));
        const warmup = Math.min(length - 1, bars.length);
        const smoothed = center.slice(0, warmup).concat(ema(center.slice(warmup), length));
        const volatility = atr(bars, atrLength);
        const band = direction => center.map((value, i) => Number.isFinite(value) && Number.isFinite(volatility[i])
          ? value + direction * atrMultiplier * volatility[i] : null);
        return [center, smoothed, band(1), band(-1)];
      }
    },
    StandardDeviation: {
      name: 'Standard Deviation', length: 5, lengthLabel: 'Periods', maxLength: 2000, pane: true,
      plotNames: ['Standard Deviation'], plotColors: ['#089981'], plotOptions: [{width: 1}],
      inputs: [{id: 'deviations', title: 'Deviations', type: 'float', value: 1, min: 0, max: 100}],
      run(bars, values, length, multiplier, {deviations = 1} = {}) {
        return [rollingDeviation(values, length, deviations)];
      }
    },
    StandardError: {
      name: 'Standard Error', length: 14, lengthLabel: 'Length', minLength: 3,
      pane: true, plotNames: ['Standard Error'], plotColors: ['#ff6d00'],
      run(bars, values, length) {
        return [length >= 3 ? linearRegression(values, length, 0, 'standardError') : values.map(() => null)];
      }
    },
    StandardErrorBands: {
      name: 'Standard Error Bands', length: 21, lengthLabel: 'Periods', minLength: 3,
      plotNames: ['Upper band', 'Regression center', 'Lower band'],
      plotColors: ['#2196f3', '#ff6d00', '#2196f3'], backgroundBand: [0, 2],
      inputs: [
        {id: 'method', title: 'Method', type: 'string', value: 'Simple', options: ['Simple', 'Exponential', 'Weighted']},
        {id: 'errors', title: 'Standard errors', type: 'float', value: 2, min: 0, max: 100},
        ...bandBackgroundInputs.map(input => ({...input, section: 'Style'}))
      ],
      run(bars, values, length, multiplier, {method = 'Simple', errors = 2} = {}) {
        if (length < 3) return Array.from({length: 3}, () => values.map(() => null));
        const base = linearRegression(values, length, 0);
        const error = linearRegression(values, length, 0, 'standardError');
        const smoothingType = {Simple: 'SMA', Exponential: 'EMA', Weighted: 'WMA'}[method] ?? 'SMA';
        const smooth = series => smoothedStudy(bars, series, {smoothingType, smoothingLength: 3})[1];
        const center = smooth(base);
        const distance = smooth(error).map(value => Number.isFinite(value) ? value * errors : null);
        const band = sign => center.map((value, index) => Number.isFinite(value) && Number.isFinite(distance[index])
          ? value + sign * distance[index] : null);
        return [band(1), center, band(-1)];
      }
    },
    LinearRegressionCurve: {
      name: 'Linear Regression Curve', length: 9, lengthLabel: 'Length', maxLength: 2000, plotNames: ['Linear Regression Curve'], plotColors: ['#2196f3'],
      run(bars, values, length) {
        return [linearRegression(values, length, 0)];
      }
    },
    LinearRegressionSlope: {
      name: 'Linear Regression Slope', pane: true, plotNames: ['Linear Regression Slope'], plotColors: ['#ff5252'],
      inputs: [{id: 'periods', title: 'Periods', value: 14, min: 2, max: 2000}],
      run(bars, values, length, multiplier, {periods = 14} = {}) {
        return [linearRegression(values, periods, 0, 'slope')];
      }
    },
    LSMA: {
      name: 'Least Squares Moving Average', length: 25, plotNames: ['LSMA'],
      inputs: [{id: 'regressionOffset', title: 'Offset', value: 0, min: -5000, max: 5000,
        tooltip: 'Evaluate the regression this many bars back within each window.'}],
      run(bars, values, length, multiplier, {regressionOffset = 0} = {}) {
        return [linearRegression(values, length, regressionOffset)];
      }
    },
    EMA: {
      name: 'Exponential Moving Average', length: 20,
      plotNames: ['EMA', 'Smoothing line', 'Upper band', 'Lower band'],
      inputs: movingAverageInputs, primaryPlotOffset: true, backgroundBand: [2, 3],
      run: (bars, values, length, multiplier, inputs) => smoothedStudy(bars, ema(values, length), inputs)
    },
    SMMA: {
      name: 'Smoothed Moving Average', length: 9,
      plotNames: ['SMMA', 'Smoothing line', 'Upper band', 'Lower band'],
      inputs: movingAverageInputs, primaryPlotOffset: true, backgroundBand: [2, 3],
      run: (bars, values, length, multiplier, inputs) => smoothedStudy(bars, rma(values, length), inputs)
    },
    MACross: movingAverageCross('MA Cross', sma, sma, '#43a047', '#ff6d00', 21),
    EMACross: movingAverageCross('EMA Cross', ema, ema, '#ff6d00', '#43a047', 26),
    MAwithEMACross: movingAverageCross('MA with EMA Cross', ema, sma, '#43a047', '#ff6d00', 26, ['EMA', 'MA', 'Crosses']),
    McGinley: {
      name: 'McGinley Dynamic', length: 14,
      plotNames: ['McGinley Dynamic'], plotColors: ['#2196f3'], plotOptions: [{width: 1}],
      run(bars, values, length) {
        let previous = null;
        return [values.map(value => {
          if (!Number.isFinite(value)) return null;
          if (previous === null || previous === 0) return previous = value;
          const divisor = length * (value / previous) ** 4;
          const next = previous + (value - previous) / divisor;
          return previous = Number.isFinite(next) ? next : value;
        })];
      }
    },
    TRIX: {
      name: 'TRIX', length: 18, pane: true, plotNames: ['TRIX'], plotColors: ['#f23645'],
      run: (bars, values, length) => {
        const logarithms = values.map(value => Number.isFinite(value) && value > 0 ? Math.log(value) : Number.NaN);
        const smoothed = ema(ema(ema(logarithms, length), length), length);
        return [smoothed.map((value, index) => {
          const previous = smoothed[index - 1];
          return Number.isFinite(value) && Number.isFinite(previous) ? 10000 * (value - previous) : null;
        })];
      }
    },
    RSI: {
      name: 'Relative Strength Index', length: 14, pane: true,
      plotNames: ['RSI', 'RSI moving average', 'Upper band', 'Lower band'],
      plotColors: ['#7e57c2', '#f9a825', '#089981', '#089981'], backgroundBand: [2, 3],
      inputs: smoothingInputs,
      run(bars, values, length, multiplier, inputs) {
        return smoothedStudy(bars, rsi(values, length), inputs);
      }
    },
    RCI: {
      name: 'Rank Correlation Index', length: 12, lengthLabel: 'RCI length', pane: true,
      plotNames: ['RCI', 'RCI moving average', 'Upper band', 'Lower band'],
      plotColors: ['#2962ff', '#f9a825', '#089981', '#089981'], backgroundBand: [2, 3],
      inputs: smoothingInputs,
      run(bars, values, length, multiplier, inputs) {
        const midpoint = (length - 1) / 2;
        const timeVariance = length * (length * length - 1) / 12;
        const result = values.map((_, index) => {
          if (length < 2 || index + 1 < length) return null;
          const window = values.slice(index + 1 - length, index + 1);
          if (!window.every(Number.isFinite)) return null;
          const order = Array.from(window.keys()).sort((left, right) => window[left] - window[right]);
          let covariance = 0;
          let rankVariance = 0;
          for (let first = 0; first < length;) {
            let end = first + 1;
            while (end < length && window[order[end]] === window[order[first]]) end++;
            const centeredRank = (first + end - 1) / 2 - midpoint;
            for (let rank = first; rank < end; rank++) {
              covariance += (order[rank] - midpoint) * centeredRank;
              rankVariance += centeredRank * centeredRank;
            }
            first = end;
          }
          return rankVariance ? 100 * covariance / Math.sqrt(timeVariance * rankVariance) : null;
        });
        return smoothedStudy(bars, result, inputs);
      }
    },
    RCIRibbon: {
      name: 'RCI Ribbon', pane: true,
      plotNames: ['Short RCI', 'Middle RCI', 'Long RCI'],
      plotColors: ['#2962ff', '#f23645', '#089981'],
      inputs: [
        {id: 'shortLength', title: 'Short RCI length', value: 10, min: 2, max: 250},
        {id: 'middleLength', title: 'Middle RCI length', value: 30, min: 2, max: 250},
        {id: 'longLength', title: 'Long RCI length', value: 50, min: 2, max: 250}
      ],
      run(bars, values, length, multiplier, {shortLength = 10, middleLength = 30, longLength = 50} = {}) {
        return [shortLength, middleLength, longLength].map(period =>
          indicators.RCI.run(bars, values, period)[0]);
      }
    },
    CRSI: {
      name: 'Connors RSI', pane: true, plotNames: ['CRSI'], plotColors: ['#7e57c2'], referenceBand: '#7e57c2',
      inputs: [
        {id: 'priceLength', title: 'RSI length', value: 3, min: 1, max: 5000},
        {id: 'streakLength', title: 'Up/Down length', value: 2, min: 1, max: 5000},
        {id: 'rankLength', title: 'ROC length', value: 100, min: 1, max: 5000},
        ...bandBackgroundInputs.map(input => input.id === 'backgroundColor' ? {...input, value: '#7e57c2'} : input)
      ],
      run(bars, values, length, multiplier, {priceLength = 3, streakLength = 2, rankLength = 100} = {}) {
        let streak = 0;
        const streaks = values.map((value, index) => {
          const direction = index ? Math.sign(value - values[index - 1]) : 0;
          streak = direction ? direction + (Math.sign(streak) === direction ? streak : 0) : 0;
          return streak;
        });
        const changes = values.map((value, index) => {
          const previous = values[index - 1];
          return Number.isFinite(previous) && previous !== 0 ? 100 * (value - previous) / previous : null;
        });
        const priceRsi = rsi(values, priceLength);
        const streakRsi = rsi(streaks, streakLength);
        const rank = percentRank(changes, rankLength);
        return [values.map((_, index) => Number.isFinite(rank[index]) && Number.isFinite(priceRsi[index]) && Number.isFinite(streakRsi[index])
          ? (priceRsi[index] + streakRsi[index] + rank[index]) / 3 : null)];
      }
    },
    ENV: {
      name: 'Moving Average Envelopes', length: 20, backgroundBand: [1, 2],
      plotNames: ['Basis', 'Upper', 'Lower'], plotColors: ['#ff6d00', '#2962ff', '#2962ff'],
      inputs: [
        {id: 'percent', title: 'Percent', type: 'float', value: 10, min: 0, max: 100},
        {id: 'exponential', title: 'Exponential', type: 'bool', value: false},
        ...bandBackgroundInputs
      ],
      run(bars, values, length, multiplier, {percent = 10, exponential = false} = {}) {
        const basis = (exponential ? ema : sma)(values, length);
        const ratio = percent / 100;
        return [basis, basis.map(value => value === null ? null : value * (1 + ratio)),
          basis.map(value => value === null ? null : value * (1 - ratio))];
      }
    },
    BB: {
      name: 'Bollinger Bands', length: 20, lengthLabel: 'Length', multiplier: 2, multiplierLabel: 'StdDev',
      plotNames: ['BB upper', 'BB basis', 'BB lower'], backgroundBand: [0, 2], allPlotOffset: true,
      inputs: [
        {id: 'offset', title: 'Offset', value: 0, min: -500, max: 500},
        {id: 'basisType', title: 'Basis MA type', type: 'string', value: 'SMA',
          options: ['SMA', 'EMA', 'SMMA (RMA)', 'WMA', 'VWMA']},
        ...bandBackgroundInputs
      ],
      run(bars, values, length, multiplier, {basisType} = {}) {
        const basis = basisType && basisType !== 'SMA' ? movingAverage(bars, values, length, basisType) : undefined;
        return bollinger(values, length, multiplier, basis);
      }
    },
    BBPercent: {
      name: 'Bollinger Bands %B', length: 20, lengthLabel: 'Length', multiplier: 2, multiplierLabel: 'StdDev',
      pane: true, plotNames: ['%B'],
      run(bars, values, length, multiplier) {
        const [upper, , lower] = bollinger(values, length, multiplier);
        return [values.map((value, index) => upper[index] > lower[index]
          ? (value - lower[index]) / (upper[index] - lower[index]) : null)];
      }
    },
    BBWidth: {
      name: 'Bollinger Bands Width', length: 20, lengthLabel: 'Length', multiplier: 2, multiplierLabel: 'StdDev',
      pane: true, format: 'percent', plotNames: ['BB Width', 'Highest Expansion', 'Lowest Contraction'],
      plotColors: ['#2962ff', '#f23645', '#089981'],
      inputs: [
        {id: 'expansionLength', title: 'Highest Expansion Length', value: 125, min: 1, max: 5000},
        {id: 'contractionLength', title: 'Lowest Contraction Length', value: 125, min: 1, max: 5000}
      ],
      run(bars, values, length, multiplier, {expansionLength = 125, contractionLength = 125} = {}) {
        const [upper, basis, lower] = bollinger(values, length, multiplier);
        const width = basis.map((value, index) => value === null || value === 0 || upper[index] === null
          ? null : 100 * (upper[index] - lower[index]) / value);
        return [width, rollingExtreme(width, expansionLength, 1), rollingExtreme(width, contractionLength, -1)];
      }
    },
    BBTrend: {
      name: 'BBTrend', pane: true, plotNames: ['BBTrend'], histogramPlots: [0],
      referenceLevelNames: ['Zero'],
      inputs: [
        {id: 'shortLength', title: 'Short BB Length', value: 20, min: 1, max: 5000},
        {id: 'longLength', title: 'Long BB Length', value: 50, min: 1, max: 5000},
        {id: 'deviation', title: 'StdDev', value: 2, min: 0.001, max: 50, step: 0.001},
        {id: 'risingPositive', title: 'Increasing above zero', type: 'color', value: '#089981', section: 'Style', group: 'Histogram'},
        {id: 'fallingPositive', title: 'Decreasing above zero', type: 'color', value: '#80cbc4', section: 'Style', group: 'Histogram'},
        {id: 'fallingNegative', title: 'Decreasing below zero', type: 'color', value: '#f23645', section: 'Style', group: 'Histogram'},
        {id: 'risingNegative', title: 'Increasing below zero', type: 'color', value: '#faa1a4', section: 'Style', group: 'Histogram'}
      ],
      run(bars, values, length, multiplier, {
        shortLength = 20, longLength = 50, deviation = 2,
        risingPositive = '#089981', fallingPositive = '#80cbc4',
        fallingNegative = '#f23645', risingNegative = '#faa1a4'
      } = {}) {
        const [shortUpper, shortMiddle, shortLower] = bollinger(values, shortLength, deviation);
        const [longUpper, , longLower] = bollinger(values, longLength, deviation);
        const trend = shortMiddle.map((basis, index) => {
          if (!Number.isFinite(basis) || basis === 0 || !Number.isFinite(shortUpper[index])
              || !Number.isFinite(longUpper[index])) return null;
          return 100 * (Math.abs(shortLower[index] - longLower[index])
            - Math.abs(shortUpper[index] - longUpper[index])) / basis;
        });
        trend.colors = trend.map((value, index) => {
          if (value === null) return undefined;
          const prior = trend[index - 1] ?? 0;
          if (value >= 0) return value >= prior ? risingPositive : fallingPositive;
          return value <= prior ? fallingNegative : risingNegative;
        });
        return [trend];
      }
    },
    Keltner: {
      name: 'Keltner Channels', length: 20, multiplier: 2, multiplierLabel: 'Multiplier',
      plotNames: ['KC upper', 'KC basis', 'KC lower'], backgroundBand: [0, 2],
      inputs: [
        {id: 'exponential', title: 'Use exponential MA', type: 'bool', value: true},
        {id: 'bandsStyle', title: 'Bands style', type: 'string', value: 'Average True Range',
          options: ['Average True Range', 'True Range', 'Range']},
        {id: 'atrLength', title: 'ATR length', value: 10, min: 1, max: 250},
        ...bandBackgroundInputs
      ],
      run(bars, values, length, multiplier, overrides = {}) {
        const atrLength = Number.isInteger(overrides.atrLength) && overrides.atrLength >= 1
          && overrides.atrLength <= 250 ? overrides.atrLength : 10;
        const basis = (overrides.exponential === false ? sma : ema)(values, length);
        const width = overrides.bandsStyle === 'True Range' ? trueRange(bars, () => true)
          : overrides.bandsStyle === 'Range' ? rma(bars.map(bar => bar.high - bar.low), length)
          : atr(bars, atrLength);
        const band = direction => basis.map((value, index) =>
          Number.isFinite(value) && Number.isFinite(width[index]) ? value + direction * multiplier * width[index] : null);
        return [band(1), basis, band(-1)];
      }
    },
    MovingAverageChannel: {
      name: 'Moving Average Channel',
      plotNames: ['Upper', 'Lower'], plotColors: ['#2196f3', '#ff6d00'],
      backgroundBand: [0, 1], backgroundBandOpacity: 10,
      inputs: [
        {id: 'upperLength', title: 'Upper Length', value: 20, min: 1, max: 2000},
        {id: 'lowerLength', title: 'Lower Length', value: 20, min: 1, max: 2000},
        {id: 'upperOffset', title: 'Upper Offset', value: 0, min: -250, max: 250},
        {id: 'lowerOffset', title: 'Lower Offset', value: 0, min: -250, max: 250},
        ...bandBackgroundInputs.map(input => input.id === 'backgroundOpacity' ? {...input, value: 10} : input)
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const {upperLength = 20, lowerLength = 20, upperOffset = 0, lowerOffset = 0} = inputs;
        const bands = [
          shiftStudyPlots([sma(bars.map(bar => bar.high), upperLength)], upperOffset),
          shiftStudyPlots([sma(bars.map(bar => bar.low), lowerLength)], lowerOffset)
        ];
        const plots = bands.map(band => band[0]);
        if (bands.some(band => band.projected)) {
          plots.projected = bands.map(band => band.projected &&
            Array(band.projectionOffset).fill(null).concat(band.projected[0]));
        }
        return plots;
      }
    },
    PriceChannel: {
      name: 'Price Channel', length: 20,
      plotNames: ['Highprice Line', 'Lowprice Line', 'Centerprice Line'],
      plotColors: ['#f50057', '#f50057', '#2196f3'],
      inputs: [{id: 'offsetLength', title: 'Offset Length', value: 0, min: 0, max: 2000}],
      run(bars, values, length, multiplier, {offsetLength = 0} = {}) {
        const highs = rollingExtreme(bars.map(bar => bar.high), length, 1);
        const lows = rollingExtreme(bars.map(bar => bar.low), length, -1);
        const upper = highs.map((_, index) => highs[index - offsetLength] ?? null);
        const lower = lows.map((_, index) => lows[index - offsetLength] ?? null);
        const center = upper.map((high, index) => Number.isFinite(high) && Number.isFinite(lower[index])
          ? (high + lower[index]) / 2 : null);
        return [upper, lower, center];
      }
    },
    FiftyTwoWeekHighLow: {
      name: '52 Week High/Low',
      plotNames: ['Highest', 'Lowest'], plotColors: ['#787b86', '#787b86'],
      plotOptions: [{lineStyle: 'dotted'}, {lineStyle: 'dotted'}],
      inputs: [
        {id: 'highSource', title: 'High source', type: 'source', value: 'close', options: studyPriceSourceNames},
        {id: 'lowSource', title: 'Low source', type: 'source', value: 'close', options: studyPriceSourceNames},
        {id: 'formingWeek', title: 'Include forming week', type: 'bool', value: false,
          tooltip: 'Use the current broker week when a live weekly candle is available.'}
      ],
      weeklyLevels(weeks, {highSource = 'close', lowSource = 'close'} = {}) {
        const window = weeks.slice(-52);
        if (window.length < 52) return [null, null];
        const highs = window.map(pineSources[highSource] ?? pineSources.close);
        const lows = window.map(pineSources[lowSource] ?? pineSources.close);
        return [highs.every(Number.isFinite) ? Math.max(...highs) : null,
          lows.every(Number.isFinite) ? Math.min(...lows) : null];
      }
    },
    Donchian: {
      name: 'Donchian Channels', length: 20, plotNames: ['Upper channel', 'Middle channel', 'Lower channel'],
      backgroundBand: [0, 2], inputs: bandBackgroundInputs,
      run(bars, values, length) {
        const upper = rollingExtreme(bars.map(bar => bar.high), length, 1);
        const lower = rollingExtreme(bars.map(bar => bar.low), length, -1);
        return [upper, upper.map((high, index) => (high + lower[index]) / 2), lower];
      }
    },
    Stochastic: {
      name: 'Stochastic Oscillator', length: 14, pane: true, plotNames: ['%K', '%D'],
      inputs: [
        { id: 'smoothK', title: '%K smoothing', value: 3, min: 1, max: 250 },
        { id: 'smoothD', title: '%D smoothing', value: 3, min: 1, max: 250 }
      ],
      run(bars, values, length, multiplier, overrides = {}) {
        const period = value => Number.isInteger(value) && value >= 1 && value <= 250 ? value : 3;
        const raw = stochastic(bars.map(bar => bar.close), bars.map(bar => bar.high),
          bars.map(bar => bar.low), length);
        const k = smaWithGaps(raw, period(overrides.smoothK));
        return [k, smaWithGaps(k, period(overrides.smoothD))];
      }
    },
    StochRSI: {
      name: 'Stochastic RSI', pane: true, plotNames: ['%K', '%D'],
      plotColors: ['#2962ff', '#ff6d00'],
      inputs: [
        { id: 'rsiLength', title: 'RSI length', value: 14, min: 1, max: 250 },
        { id: 'stochLength', title: 'Stochastic length', value: 14, min: 1, max: 250 },
        { id: 'smoothK', title: '%K smoothing', value: 3, min: 1, max: 250 },
        { id: 'smoothD', title: '%D smoothing', value: 3, min: 1, max: 250 }
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const period = (id, fallback) => Number.isInteger(inputs[id]) && inputs[id] >= 1 && inputs[id] <= 250
          ? inputs[id] : fallback;
        const rsiLength = period('rsiLength', 14);
        const stochLength = period('stochLength', 14);
        const strength = rsi(values, rsiLength).slice(rsiLength);
        const raw = stochastic(strength, strength, strength, stochLength);
        const k = smaWithGaps(raw, period('smoothK', 3));
        const d = smaWithGaps(k, period('smoothD', 3));
        const warmup = Array(Math.min(rsiLength, values.length)).fill(null);
        return [[...warmup, ...k], [...warmup, ...d]];
      }
    },
    AO: {
      name: 'Awesome Oscillator', pane: true, plotNames: ['AO'], histogramPlots: [0],
      run(bars) {
        const midpoint = bars.map(bar => (bar.high + bar.low) / 2);
        const fast = sma(midpoint, 5);
        const slow = sma(midpoint, 34);
        const values = slow.map((value, index) => value === null ? null : fast[index] - value);
        values.colors = values.map((value, index) =>
          Number.isFinite(values[index - 1]) && value > values[index - 1] ? '#089981' : '#f23645');
        return [values];
      }
    },
    ASI: {
      name: 'Accumulative Swing Index', pane: true, plotNames: ['ASI'], plotColors: ['#2962ff'],
      inputs: [{id: 'limitMove', title: 'Limit move value', type: 'float', value: 3, min: 0.01, step: 0.01}],
      run(bars, values, length, multiplier, inputs = {}) {
        const limit = Number.isFinite(inputs.limitMove) && inputs.limitMove > 0 ? inputs.limitMove : 3;
        let total = 0;
        return [bars.map((bar, index) => {
          if (!index) return total;
          const previous = bars[index - 1];
          const highMove = Math.abs(bar.high - previous.close);
          const lowMove = Math.abs(bar.low - previous.close);
          const range = bar.high - bar.low;
          const priorBody = previous.close - previous.open;
          const priorAdjustment = Math.abs(priorBody) / 4;
          const denominator = priorAdjustment + (highMove >= lowMove && highMove >= range
            ? highMove - lowMove / 2 : lowMove >= range ? lowMove - highMove / 2 : range);
          if (denominator > 0) {
            const move = bar.close - previous.close + (bar.close - bar.open) / 2 + priorBody / 4;
            total += 50 * (move / denominator) * (Math.max(highMove, lowMove) / limit);
          }
          return total;
        })];
      }
    },
    AcceleratorOscillator: {
      name: 'Accelerator Oscillator', pane: true, plotNames: ['AC'], histogramPlots: [0],
      run(bars) {
        const [momentum] = indicators.AO.run(bars);
        const average = smaWithGaps(momentum, 5);
        const values = average.map((value, index) => Number.isFinite(value)
          ? momentum[index] - value : null);
        values.colors = values.map((value, index) =>
          Number.isFinite(values[index - 1]) && value > values[index - 1] ? '#089981' : '#f23645');
        return [values];
      }
    },
    BBP: {
      name: 'Bull Bear Power', length: 13, pane: true, plotNames: ['BBP'], histogramPlots: [0],
      run(bars, values, length) {
        const average = ema(bars.map(bar => bar.close), length);
        const power = bars.map((bar, index) => Number.isFinite(average[index])
          ? (bar.high - average[index]) + (bar.low - average[index]) : null);
        power.colors = power.map(value => value >= 0 ? '#089981' : '#f23645');
        return [power];
      }
    },
    UO: {
      name: 'Ultimate Oscillator', pane: true, plotNames: ['UO'],
      inputs: [
        {id: 'fast', title: 'Fast length', value: 7, min: 1, max: 250},
        {id: 'middle', title: 'Middle length', value: 14, min: 1, max: 250},
        {id: 'slow', title: 'Slow length', value: 28, min: 1, max: 250}
      ],
      run(bars, values, length, multiplier, overrides = {}) {
        const low = bars.map((bar, index) => Math.min(bar.low, bars[index - 1]?.close ?? bar.low));
        const pressure = bars.map((bar, index) => bar.close - low[index]);
        const range = bars.map((bar, index) => Math.max(bar.high, bars[index - 1]?.close ?? bar.high) - low[index]);
        const ratios = this.inputs.map(({id, value, min, max}) => {
          const selected = overrides[id];
          const period = Number.isInteger(selected) && selected >= min && selected <= max ? selected : value;
          const numerator = sma(pressure, period);
          return sma(range, period).map((denominator, index) =>
            denominator > 0 ? numerator[index] / denominator : null);
        });
        return [bars.map((bar, index) => {
          const [fast, middle, slow] = ratios.map(series => series[index]);
          return [fast, middle, slow].every(Number.isFinite) ? 100 * (4 * fast + 2 * middle + slow) / 7 : null;
        })];
      }
    },
    Fisher: {
      name: 'Fisher Transform', length: 9, pane: true, plotNames: ['Fisher', 'Trigger'],
      plotColors: ['#2962ff', '#ff6d00'],
      run(bars, _values, length) {
        const midpoint = bars.map(bar => (bar.high + bar.low) / 2);
        let normalized = 0;
        let previous = 0;
        const fisher = midpoint.map((value, index) => {
          if (index < length - 1) return null;
          const window = midpoint.slice(index - length + 1, index + 1);
          const low = Math.min(...window);
          const high = Math.max(...window);
          const position = high > low ? (value - low) / (high - low) - 0.5 : 0;
          const next = 0.66 * position + 0.67 * normalized;
          normalized = Math.abs(next) > 0.99 ? Math.sign(next) * 0.999 : next;
          previous = 0.5 * Math.log((1 + normalized) / (1 - normalized)) + 0.5 * previous;
          return previous;
        });
        return [fisher, fisher.map((_, index) => fisher[index - 1] ?? null)];
      }
    },
    Vortex: {
      name: 'Vortex Indicator', length: 14, pane: true, plotNames: ['VI+', 'VI−'],
      plotColors: ['#089981', '#f23645'],
      run(bars, values, length) {
        const prior = bars.slice(0, -1);
        const current = bars.slice(1);
        const range = sma(current.map((bar, index) =>
          Math.max(bar.high, prior[index].close) - Math.min(bar.low, prior[index].close)), length);
        const movement = [
          current.map((bar, index) => Math.abs(bar.high - prior[index].low)),
          current.map((bar, index) => Math.abs(bar.low - prior[index].high))
        ];
        return movement.map(series => {
          const average = sma(series, length);
          return bars.map((bar, index) => range[index - 1] > 0
            ? average[index - 1] / range[index - 1] : null);
        });
      }
    },
    ROC: {
      name: 'Rate of Change', length: 9, pane: true,
      run(bars, values, length) {
        return [values.map((value, i) => {
          const prior = values[i - length];
          return Number.isFinite(prior) && prior !== 0 ? 100 * (value - prior) / prior : null;
        })];
      }
    },
    SpecialK: {
      name: "Pring's Special K", pane: true, minimumBars: 725,
      plotNames: ['Special K', 'Signal'], plotColors: ['#2962ff', '#f23645'],
      inputs: [
        {id: 'source', title: 'Source', type: 'source', value: 'close', options: studyPriceSourceNames},
        {id: 'signalLength1', title: 'Signal length 1', value: 100, min: 1, max: 2000},
        {id: 'signalLength2', title: 'Signal length 2', value: 100, min: 1, max: 2000}
      ],
      run: (bars, values, length, multiplier, inputs) => pringSpecialK(bars, inputs)
    },
    KST: {
      name: 'Know Sure Thing', pane: true, plotNames: ['KST', 'Signal'],
      plotColors: ['#089981', '#f23645'],
      inputs: [
        {id: 'roc1', title: 'ROC length 1', value: 10, min: 1, max: 250},
        {id: 'roc2', title: 'ROC length 2', value: 15, min: 1, max: 250},
        {id: 'roc3', title: 'ROC length 3', value: 20, min: 1, max: 250},
        {id: 'roc4', title: 'ROC length 4', value: 30, min: 1, max: 250},
        {id: 'sma1', title: 'SMA length 1', value: 10, min: 1, max: 250},
        {id: 'sma2', title: 'SMA length 2', value: 10, min: 1, max: 250},
        {id: 'sma3', title: 'SMA length 3', value: 10, min: 1, max: 250},
        {id: 'sma4', title: 'SMA length 4', value: 15, min: 1, max: 250},
        {id: 'signalLength', title: 'Signal length', value: 9, min: 1, max: 250}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const closes = bars.map(bar => bar.close);
        const components = [10, 15, 20, 30].map((rocLength, i) => {
          const [roc] = indicators.ROC.run(bars, closes, inputs['roc' + (i + 1)] ?? rocLength);
          return smaWithGaps(roc, inputs['sma' + (i + 1)] ?? (i === 3 ? 15 : 10));
        });
        const kst = closes.map((_, i) => {
          const readings = components.map(series => series[i]);
          return readings.every(Number.isFinite) ? readings.reduce((sum, value, j) => sum + value * (j + 1), 0) : null;
        });
        return [kst, smaWithGaps(kst, inputs.signalLength ?? 9)];
      }
    },
    Coppock: {
      name: 'Coppock Curve', pane: true, plotColors: ['#2196f3'],
      inputs: [
        {id: 'wmaLength', title: 'WMA length', value: 10, min: 1, max: 250},
        {id: 'longRocLength', title: 'Long ROC length', value: 14, min: 1, max: 250},
        {id: 'shortRocLength', title: 'Short ROC length', value: 11, min: 1, max: 250}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const closes = bars.map(bar => bar.close);
        const [long] = indicators.ROC.run(bars, closes, inputs.longRocLength ?? 14);
        const [short] = indicators.ROC.run(bars, closes, inputs.shortRocLength ?? 11);
        const combined = long.map((value, i) => Number.isFinite(value) && Number.isFinite(short[i])
          ? value + short[i] : null);
        const weighted = wma(combined.filter(Number.isFinite), inputs.wmaLength ?? 10);
        let index = 0;
        return [combined.map(value => value === null ? null : weighted[index++])];
      }
    },
    Momentum: {
      name: 'Momentum', length: 10, pane: true,
      run(bars, values, length) {
        return [pineSeriesFunctions.change(values, length)];
      }
    },
    CMO: {
      name: 'Chande Momentum Oscillator', length: 9, pane: true, plotNames: ['CMO'],
      run(bars, values, length) {
        return [cmo(values, length)];
      }
    },
    WoodiesCCI: {
      name: 'Woodies CCI', pane: true,
      plotNames: ['CCI Histogram', 'CCI', 'Turbo CCI'],
      plotColors: ['#089981', '#131722', '#2962ff'], histogramPlots: [0],
      referenceLevelNames: ['Oversold', 'Zero', 'Overbought'],
      inputs: [
        {id: 'cciPeriod', title: 'CCI period', value: 14, min: 1, max: 2000},
        {id: 'turboPeriod', title: 'TCCI period', value: 6, min: 1, max: 2000},
        {id: 'upColor', title: 'Uptrend', type: 'color', value: '#089981', section: 'Style'},
        {id: 'downColor', title: 'Downtrend', type: 'color', value: '#f23645', section: 'Style'},
        {id: 'neutralColor', title: 'Neutral', type: 'color', value: '#787b86', section: 'Style'},
        {id: 'warningColor', title: 'Trend warning', type: 'color', value: '#fdd835', section: 'Style'}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const period = (key, fallback) => Number.isInteger(inputs[key]) && inputs[key] >= 1 && inputs[key] <= 2000 ? inputs[key] : fallback;
        const prices = bars.map(bar => [bar.high, bar.low, bar.close].every(Number.isFinite)
          ? (bar.high + bar.low + bar.close) / 3 : NaN);
        const slow = woodiesCciValues(prices, period('cciPeriod', 14));
        const turbo = woodiesCciValues(prices, period('turboPeriod', 6));
        const histogram = slow.slice();
        histogram.colors = woodiesCciColors(slow, inputs);
        return [histogram, slow, turbo];
      }
    },
    CCI: {
      name: 'Commodity Channel Index', length: 20, pane: true, plotNames: ['CCI'],
      run(bars, values, length) {
        return [cci(values, length)];
      }
    },
    ChopZone: {
      name: 'Chop Zone', pane: true, plotNames: ['Chop Zone'], histogramPlots: [0],
      // Independently implemented EMA-angle model; reference:
      // https://www.tradingview.com/script/8IaHOdPX-Chop-Zone-SamX/
      // https://indie-script.github.io/indicators/trend/built-in/Chop%20Zone/
      inputs: [
        ...[
          ['strongUp', 'Strong upward slope', '#26c6da'], ['up', 'Upward slope', '#43a047'],
          ['mildUp', 'Mild upward slope', '#a5d6a7'], ['slightUp', 'Slight upward slope', '#009688'],
          ['flat', 'Flat slope', '#fdd835'], ['slightDown', 'Slight downward slope', '#ffb74d'],
          ['mildDown', 'Mild downward slope', '#ff6d00'], ['down', 'Downward slope', '#e91e63'],
          ['strongDown', 'Strong downward slope', '#d50000']
        ].map(([id, title, value]) => ({id, title, value, type: 'color', section: 'Style'}))
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const average = ema(bars.map(bar => bar.close), 34);
        const defaults = Object.fromEntries(this.inputs.map(input => [input.id, input.value]));
        const colors = [];
        const columns = bars.map((bar, index) => {
          if (![bar.open, bar.high, bar.low, bar.close].every(Number.isFinite)) {
            colors.push(null);
            return null;
          }
          const window = bars.slice(Math.max(0, index - 29), index + 1);
          const high = Math.max(...window.map(item => item.high));
          const low = Math.min(...window.map(item => item.low));
          const meanPrice = (bar.high + bar.low + bar.close) / 3;
          let angle = 0;
          if (high > low && meanPrice > 0 && Number.isFinite(average[index - 1])) {
            const slope = (average[index] - average[index - 1]) / meanPrice * (25 * low / (high - low));
            angle = Math.sign(slope) * Math.round(Math.atan(Math.abs(slope)) * 180 / Math.PI);
          }
          const key = angle >= 5 ? 'strongUp' : angle >= 3.57 ? 'up'
            : angle >= 2.14 ? 'mildUp' : angle >= .71 ? 'slightUp'
            : angle <= -5 ? 'strongDown' : angle <= -3.57 ? 'down'
            : angle <= -2.14 ? 'mildDown' : angle <= -.71 ? 'slightDown' : 'flat';
          colors.push(/^#[0-9a-f]{6}$/i.test(inputs[key] ?? '') ? inputs[key] : defaults[key]);
          return 1;
        });
        columns.colors = colors;
        return [columns];
      }
    },
    CHOP: {
      name: 'Choppiness Index', length: 14, lengthLabel: 'Length', pane: true,
      plotNames: ['CHOP'], plotColors: ['#2962ff'], referenceBand: '#2962ff',
      referenceLevelNames: ['Lower band', 'Upper band'],
      inputs: [
        {id: 'offset', title: 'Offset', value: 0, min: -500, max: 500},
        ...bandBackgroundInputs.map(input => ({
          ...input, section: 'Style', value: input.id === 'backgroundColor' ? '#2962ff' : input.value
        }))
      ],
      run(bars, values, length, multiplier, {offset = 0} = {}) {
        if (length < 2) return [bars.map(() => null)];
        const averageRange = sma(atr(bars, 1), length);
        const highs = rollingExtreme(bars.map(bar => bar.high), length, 1);
        const lows = rollingExtreme(bars.map(bar => bar.low), length, -1);
        const readings = averageRange.map((value, i) => {
          const span = highs[i] - lows[i];
          return value > 0 && span > 0 ? 100 * Math.log(value * length / span) / Math.log(length) : null;
        });
        return shiftStudyPlots([readings], offset);
      }
    },
    Aroon: {
      name: 'Aroon', length: 14, pane: true, plotNames: ['Aroon Up', 'Aroon Down'],
      run(bars, values, length) {
        const up = Array(bars.length).fill(null);
        const down = Array(bars.length).fill(null);
        for (let i = length; i < bars.length; i++) {
          let high = i, low = i;
          for (let j = i - 1; j >= i - length; j--) {
            if (bars[j].high > bars[high].high) high = j;
            if (bars[j].low < bars[low].low) low = j;
          }
          up[i] = 100 * (length - (i - high)) / length;
          down[i] = 100 * (length - (i - low)) / length;
        }
        return [up, down];
      }
    },
    AdvanceDecline: {
      name: 'Advance/Decline', length: 10, pane: true,
      plotNames: ['Advance/Decline'], plotColors: ['#2962ff'],
      run(bars, values, length) {
        const advances = sma(bars.map(bar => Number(bar.close > bar.open)), length);
        const declines = sma(bars.map(bar => Number(bar.close < bar.open)), length);
        return [advances.map((value, index) => declines[index] > 0 ? value / declines[index] : null)];
      }
    },
    ADRBarRatio: {
      name: 'Advance/Decline Ratio (Bars)', length: 9, pane: true,
      plotNames: ['Advance/Decline Ratio'], plotColors: ['#2962ff'],
      run(bars, values, length) {
        const advances = sma(bars.map(bar => Number(bar.close > bar.open)), length);
        const declines = sma(bars.map(bar => Number(bar.close < bar.open)), length);
        return [advances.map((value, index) => declines[index] > 0 ? value / declines[index] : null)];
      }
    },
    BOP: {
      name: 'Balance of Power', pane: true, plotNames: ['BOP'],
      run(bars) {
        return [bars.map(({open, high, low, close}) => high > low ? (close - open) / (high - low) : null)];
      }
    },
    EOM: {
      name: 'Ease of Movement', length: 14, pane: true, volume: true, plotNames: ['EOM'],
      plotColors: ['#43a047'],
      inputs: [{id: 'divisor', title: 'Divisor', value: 10000, min: 1, max: 1000000000000}],
      run(bars, values, length, multiplier, inputs = {}) {
        const divisor = inputs.divisor ?? 10000;
        const movement = bars.map(({high, low, volume}, i) => {
          if (i === 0 || !Number.isFinite(volume) || volume <= 0) return null;
          const previous = bars[i - 1];
          const distance = (high + low - previous.high - previous.low) / 2;
          return divisor * distance * (high - low) / volume;
        });
        return [smaWithGaps(movement, length)];
      }
    },
    MassIndex: {
      name: 'Mass Index', length: 25, lengthLabel: 'Sum length', pane: true, plotNames: ['Mass Index'],
      inputs: [{id: 'emaLength', title: 'EMA length', value: 9, min: 1, max: 250}],
      run(bars, values, length, multiplier, inputs = {}) {
        const period = inputs.emaLength ?? 9;
        const first = ema(bars.map(bar => bar.high - bar.low), period);
        const second = ema(first, period);
        const ratio = first.map((value, i) => second[i] > 0 ? value / second[i] : 0);
        const mean = sma(ratio, length);
        const coverage = sma(second.map(value => Number(value > 0)), length);
        return [mean.map((value, i) => coverage[i] === 1 ? value * length : null)];
      }
    },
    DPO: {
      name: 'Detrended Price Oscillator', length: 21, lengthLabel: 'Period', pane: true, plotNames: ['DPO'],
      inputs: [{id: 'centered', title: 'Centered', type: 'bool', value: false}],
      run(bars, values, length, multiplier, inputs = {}) {
        const closes = bars.map(bar => bar.close);
        const average = sma(closes, length);
        const shift = Math.floor(length / 2) + 1;
        return [closes.map((close, i) => {
          const baseline = average[inputs.centered ? i + shift : i - shift];
          return Number.isFinite(baseline) ? close - baseline : null;
        })];
      }
    },
    AroonOscillator: {
      name: 'Aroon Oscillator', length: 14, pane: true, plotNames: ['Aroon Oscillator'],
      plotColors: ['#2962ff'],
      run(bars, values, length) {
        const [up, down] = indicators.Aroon.run(bars, values, length);
        return [up.map((value, index) => value === null ? null : value - down[index])];
      }
    },
    SMI: {
      name: 'Stochastic Momentum Index', length: 10, lengthLabel: '%K length', pane: true,
      plotNames: ['SMI', 'SMI-based EMA'], plotColors: ['#2962ff', '#ff6d00'],
      inputs: [
        {id: 'smoothLength', title: '%D length', value: 3, min: 1, max: 5000},
        {id: 'signalLength', title: 'EMA length', value: 3, min: 1, max: 5000}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const highs = rollingExtreme(bars.map(bar => bar.high), length, 1);
        const lows = rollingExtreme(bars.map(bar => bar.low), length, -1);
        const smoothLength = inputs.smoothLength ?? 3;
        const doubleEma = series => ema(ema(series, smoothLength), smoothLength);
        const range = doubleEma(highs.map((high, index) => high - lows[index]));
        const relative = doubleEma(bars.map((bar, index) => bar.close - (highs[index] + lows[index]) / 2));
        const smi = relative.map((value, index) => range[index] > 0 ? 200 * value / range[index] : null);
        const smoothed = ema(smi.filter(Number.isFinite), inputs.signalLength ?? 3);
        let signalIndex = 0;
        return [smi, smi.map(value => value === null ? null : smoothed[signalIndex++])];
      }
    },
    SMIErgodic: {
      name: 'SMI Ergodic Indicator', pane: true,
      plotNames: ['SMI', 'Signal'], plotColors: ['#2962ff', '#ff6d00'],
      inputs: [
        {id: 'shortLength', title: 'Short length', value: 5, min: 1, max: 5000},
        {id: 'longLength', title: 'Long length', value: 20, min: 1, max: 5000},
        {id: 'signalLength', title: 'Signal length', value: 5, min: 1, max: 5000}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const changes = values.slice(1).map((value, index) => value - values[index]);
        const smooth = series => ema(ema(series, inputs.shortLength ?? 5), inputs.longLength ?? 20);
        const numerator = smooth(changes);
        const denominator = smooth(changes.map(Math.abs));
        const smi = [null, ...numerator.map((value, index) =>
          denominator[index] > 0 ? value / denominator[index] : null)].slice(0, values.length);
        const signal = ema(smi.filter(Number.isFinite), inputs.signalLength ?? 5);
        let signalIndex = 0;
        return [smi, smi.map(value => value === null ? null : signal[signalIndex++])];
      }
    },
    SMIErgodicOscillator: {
      name: 'SMI Ergodic Oscillator', pane: true, histogramPlots: [0],
      plotNames: ['Oscillator'], plotColors: ['#2962ff'],
      get inputs() { return indicators.SMIErgodic.inputs; },
      run(bars, values, length, multiplier, inputs) {
        const [smi, signal] = indicators.SMIErgodic.run(bars, values, length, multiplier, inputs);
        return [smi.map((value, index) => value === null ? null : value - signal[index])];
      }
    },
    TrendStrength: {
      name: 'Trend Strength Index', length: 14, minLength: 2, maxLength: 2000, pane: true,
      plotNames: ['Trend Strength Index'], plotColors: ['#ff5252'], plotOptions: [{width: 1}],
      inputs: [
        {id: 'bullishColor', title: 'Bullish color', type: 'color', value: '#089981'},
        {id: 'bullishOpacity', title: 'Bullish fill opacity (%)', value: 33, min: 0, max: 100},
        {id: 'bearishColor', title: 'Bearish color', type: 'color', value: '#f23645'},
        {id: 'bearishOpacity', title: 'Bearish fill opacity (%)', value: 33, min: 0, max: 100}
      ],
      run(bars, values, length) {
        const closes = bars.map(bar => bar.close);
        const slopes = linearRegression(closes, length, 0, 'slope');
        const deviations = rollingDeviation(closes, length, 1);
        const indexDeviation = Math.sqrt((length ** 2 - 1) / 12);
        return [slopes.map((slope, i) => Number.isFinite(slope) && deviations[i] > 0
          ? Math.max(-1, Math.min(1, slope * indexDeviation / deviations[i])) : null)];
      }
    },
    PMO: {
      name: 'Price Momentum Oscillator', pane: true, plotNames: ['PMO', 'Signal'],
      plotColors: ['#2962ff', '#ff6d00'],
      inputs: [
        {id: 'firstLength', title: 'Length 1', value: 35, min: 2, max: 250},
        {id: 'secondLength', title: 'Length 2', value: 20, min: 2, max: 250},
        {id: 'signalLength', title: 'Signal length', value: 10, min: 1, max: 250}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const {firstLength = 35, secondLength = 20, signalLength = 10} = inputs;
        const roc = values.map((value, i) => {
          const previous = values[i - 1];
          return Number.isFinite(value) && Number.isFinite(previous) && previous !== 0
            ? 100 * (value - previous) / previous : null;
        });
        const first = ema(roc.filter(Number.isFinite), firstLength, 2 / firstLength);
        const momentum = ema(first.map(value => value * 10), secondLength, 2 / secondLength);
        const signal = ema(momentum, signalLength);
        const plots = [[], []];
        let index = 0;
        for (const value of roc) {
          plots[0].push(value === null ? null : momentum[index]);
          plots[1].push(value === null ? null : signal[index++]);
        }
        return plots;
      }
    },
    TSI: {
      name: 'True Strength Index', pane: true, plotNames: ['TSI', 'Signal'], plotColors: ['#2962ff', '#f23645'],
      inputs: [
        {id: 'longLength', title: 'Long length', value: 25, min: 1, max: 250},
        {id: 'shortLength', title: 'Short length', value: 13, min: 1, max: 250},
        {id: 'signalLength', title: 'Signal length', value: 13, min: 1, max: 250}
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const changes = bars.slice(1).map((bar, i) => bar.close - bars[i].close);
        const doubleSmooth = series => ema(ema(series, inputs.longLength ?? 25), inputs.shortLength ?? 13);
        const numerator = doubleSmooth(changes);
        const denominator = doubleSmooth(changes.map(Math.abs));
        const oscillator = bars.slice(0, 1).map(() => null).concat(numerator.map((value, index) =>
          denominator[index] > 0 ? 100 * value / denominator[index] : null));
        const smoothed = ema(oscillator.filter(Number.isFinite), inputs.signalLength ?? 13);
        let index = 0;
        return [oscillator, oscillator.map(value => value === null ? null : smoothed[index++])];
      }
    },
    RVI: {
      name: 'Relative Volatility Index', length: 10, minLength: 2, pane: true,
      plotNames: ['RVI', 'Smoothing line', 'Upper band', 'Lower band'], backgroundBand: [2, 3],
      inputs: [
        {id: 'offset', title: 'Offset', value: 0, min: -500, max: 500},
        {id: 'smoothing', title: 'Wilder smoothing', value: 14, min: 1, max: 250},
        ...smoothingInputs
      ],
      run(bars, values, length, multiplier, inputs = {}) {
        const {offset = 0, smoothing = 14} = inputs;
        const warmup = Math.min(length - 1, bars.length);
        const directionalVolatility = prices => {
          const deviations = rollingDeviation(prices, length, 1).slice(warmup);
          const up = rma(deviations.map((value, i) =>
            prices[i + warmup] > prices[i + warmup - 1] ? value : 0), smoothing);
          const down = rma(deviations.map((value, i) =>
            prices[i + warmup] < prices[i + warmup - 1] ? value : 0), smoothing);
          return up.map((value, i) => {
            if (value === null) return null;
            const total = value + down[i];
            return total === 0 ? 50 : 100 * value / total;
          });
        };
        const highs = directionalVolatility(bars.map(bar => bar.high));
        const lows = directionalVolatility(bars.map(bar => bar.low));
        const readings = Array(warmup).fill(null).concat(highs.map((value, i) =>
          value === null ? null : (value + lows[i]) / 2));
        return shiftStudyPlots(smoothedStudy(bars, readings, inputs), offset);
      }
    },
    RVGI: {
      name: 'Relative Vigor Index', length: 10, pane: true, plotNames: ['RVGI', 'Signal'],
      plotColors: ['#089981', '#f23645'],
      run(bars, values, length) {
        const numerator = smaWithGaps(swma(bars.map(bar => bar.close - bar.open)), length);
        const denominator = smaWithGaps(swma(bars.map(bar => bar.high - bar.low)), length);
        const vigor = numerator.map((value, index) => value !== null && denominator[index] > 0
          ? value / denominator[index] : null);
        return [vigor, swma(vigor)];
      }
    },
    WilliamsR: {
      name: 'Williams %R', length: 14, pane: true, plotNames: ['%R'],
      run(bars, values, length) {
        const high = rollingExtreme(bars.map(bar => bar.high), length, 1);
        const low = rollingExtreme(bars.map(bar => bar.low), length, -1);
        return [bars.map((bar, index) => index >= length - 1 && high[index] > low[index]
          ? -100 * (high[index] - bar.close) / (high[index] - low[index]) : null)];
      }
    },
    TechnicalRatings: {
      name: 'Technical Ratings', pane: true, histogramPlots: [0], plotNames: ['Rating'],
      referenceLevelNames: ['Strong sell', 'Sell', 'Zero', 'Buy', 'Strong buy'],
      inputs: [
        {id: 'group', title: 'Rating is based on', type: 'string', value: 'All',
          options: ['All', 'MAs', 'Oscillators']},
        {id: 'showRatingTable', title: 'Show ratings table', type: 'bool', value: true},
        {id: 'ratingTableLive', title: 'Use forming candles in table', type: 'bool', value: true},
        ...[1, 2, 3].map(number => ({id: 'ratingInterval' + number, title: 'Table timeframe ' + number,
          type: 'string', value: 'Off', options: ['Off', '5m', '15m', '30m', '1h', '4h', '1D', '1W', '1M']})),
        {id: 'ratingTableVertical', title: 'Table vertical position', type: 'string', value: 'Top',
          options: ['Top', 'Middle', 'Bottom'], section: 'Style', group: 'Ratings table'},
        {id: 'ratingTableHorizontal', title: 'Table horizontal position', type: 'string', value: 'Left',
          options: ['Left', 'Center', 'Right'], section: 'Style', group: 'Ratings table'},
        {id: 'ratingTableSize', title: 'Table text size', type: 'string', value: 'Small',
          options: ['Tiny', 'Small', 'Normal', 'Large'], section: 'Style', group: 'Ratings table'},
        ...ratingColors.map(([id, label, value]) => ({
          id, title: label + ' color', type: 'color', value, section: 'Style', group: 'Rating colors'
        }))
      ],
      ratings: technicalRatings,
      ratingCategory,
      ratingColor,
      histogramColor: (value, inputs) => ratingColor(Math.sign(ratingCategory(value)), inputs),
      run(bars, values, length, multiplier, {group = 'All'} = {}) {
        const selected = ['All', 'MAs', 'Oscillators'].includes(group) ? group : 'All';
        return [technicalRatings(bars).map(rating => rating[selected])];
      }
    },
    ADX: {
      name: 'Average Directional Index', length: 14, multiplier: 14, multiplierLabel: 'ADX smoothing',
      lengthLabel: 'DI length', multiplierMax: 250, multiplierStep: 1, pane: true,
      plotNames: ['ADX'], plotColors: ['#f23645'],
      run: (bars, values, length, smoothing) => [directionalMovement(bars, length, smoothing)[2]]
    },
    DMI: {
      name: 'Directional Movement Index', length: 14, multiplier: 14, multiplierLabel: 'ADX smoothing',
      lengthLabel: 'DI length', multiplierMax: 250, multiplierStep: 1, pane: true,
      plotNames: ['+DI', '-DI', 'ADX'], plotColors: ['#2962ff', '#ff6d00', '#f23645'],
      run: (bars, values, length, smoothing) => directionalMovement(bars, length, smoothing)
    },
    ATR: {
      name: 'Average True Range', length: 14, lengthLabel: 'Length', pane: true,
      inputs: [{id: 'smoothing', title: 'Smoothing', type: 'string', value: 'RMA', options: ['RMA', 'SMA', 'EMA', 'WMA']}],
      run(bars, values, length, multiplier, inputs) {
        const averages = new Map([['SMA', sma], ['EMA', ema], ['WMA', wma]]);
        const average = averages.get(inputs?.smoothing);
        return [average ? average(trueRange(bars, () => true), length) : atr(bars, length)];
      }
    },
    'ATR%': {
      name: 'Average True Range %', length: 14, lengthLabel: 'Length', pane: true, format: 'percent', plotNames: ['ATR%'],
      run: (bars, values, length) => [rangePercent(bars, atr(bars, length))]
    },
    ADR: {
      name: 'Average Daily Range', length: 14, lengthLabel: 'Length', pane: true,
      plotNames: ['ADR'], plotColors: ['#2962ff'],
      run: (bars, values, length) => [sma(bars.map(bar => bar.high - bar.low), length)]
    },
    'ADR%': {
      name: 'Average Day Range %', length: 14, lengthLabel: 'Length', pane: true, format: 'percent', plotNames: ['ADR%'],
      run(bars, values, length) {
        const range = sma(bars.map(bar => bar.high - bar.low), length);
        return [rangePercent(bars, range)];
      }
    },
    MACD: {
      name: 'Moving Average Convergence Divergence', pane: true, plotNames: ['MACD', 'Signal', 'Histogram'],
      histogramPlots: [2], inputs: oscillatorInputs,
      run: (bars, values, length, multiplier, inputs) => movingAverageOscillator(values, inputs, false)
    },
    PriceOscillator: {
      name: 'Price Oscillator', pane: true,
      plotNames: ['Plot'], plotColors: ['#089981'],
      inputs: [
        {id: 'shortLength', title: 'Short length', value: 10, min: 1, max: 2000},
        {id: 'longLength', title: 'Long length', value: 21, min: 1, max: 2000}
      ],
      run(bars, values, length, multiplier, {shortLength = 10, longLength = 21} = {}) {
        const closes = bars.map(bar => bar.close);
        const short = sma(closes, shortLength);
        const long = sma(closes, longLength);
        return [short.map((value, index) => Number.isFinite(value) && Number.isFinite(long[index]) && long[index] !== 0
          ? 100 * (value - long[index]) / long[index] : null)];
      }
    },
    PPO: {
      name: 'Percentage Price Oscillator', pane: true, plotNames: ['PPO', 'Signal', 'Histogram'],
      histogramPlots: [2], inputs: oscillatorInputs, format: 'percent',
      run: (bars, values, length, multiplier, inputs) => movingAverageOscillator(values, inputs, true)
    },
    VolumeOscillator: {
      name: 'Volume Oscillator', pane: true, volume: true, format: 'percent',
      plotNames: ['Plot'], plotColors: ['#2196f3'], referenceLevelNames: ['Zero'],
      inputs: [
        {id: 'shortLength', title: 'Short length', value: 5, min: 1, max: 2000},
        {id: 'longLength', title: 'Long length', value: 10, min: 1, max: 2000}
      ],
      run(bars, values, length, multiplier, {shortLength = 5, longLength = 10} = {}) {
        const volumes = bars.map(bar => bar.volume);
        const valid = volume => Number.isFinite(volume) && volume >= 0;
        const available = volumes.filter(valid);
        const short = ema(available, shortLength);
        const long = ema(available, longLength);
        let index = 0;
        return [volumes.map(volume => {
          if (!valid(volume)) return null;
          const fast = short[index];
          const slow = long[index++];
          return slow > 0 ? 100 * (fast - slow) / slow : null;
        })];
      }
    },
    PVO: {
      name: 'Percentage Volume Oscillator', pane: true, volume: true, plotNames: ['PVO', 'Signal', 'Histogram'],
      histogramPlots: [2], inputs: oscillatorInputs, format: 'percent',
      run(bars, values, length, multiplier, inputs) {
        const volume = bars.map(bar => Number.isFinite(bar.volume) && bar.volume >= 0 ? bar.volume : null);
        return movingAverageOscillator(volume, inputs, true);
      }
    }
  };

  function annualizedDailyVariance(variance, periods, daysPerYear) {
    const coverage = sma(variance.map(value => Number(Number.isFinite(value))), periods);
    const mean = sma(variance.map(value => Number.isFinite(value) ? value : 0), periods);
    return mean.map((value, index) => coverage[index] === 1
      ? 100 * Math.sqrt(Math.max(0, value) * daysPerYear) : null);
  }

  function rollingPearson(values, other, length) {
    const pairs = [];
    return values.map((value, index) => {
      const second = other[index];
      if (!Number.isFinite(value) || !Number.isFinite(second)) return null;
      pairs.push([value, second]);
      if (pairs.length > length) pairs.shift();
      if (pairs.length < length) return null;
      const [originA, originB] = pairs[0];
      let meanA = 0, meanB = 0;
      for (const [a, b] of pairs) {
        meanA += (a - originA) / length;
        meanB += (b - originB) / length;
      }
      let covariance = 0, varianceA = 0, varianceB = 0;
      for (const [a, b] of pairs) {
        const da = a - originA - meanA, db = b - originB - meanB;
        covariance += da * db;
        varianceA += da * da;
        varianceB += db * db;
      }
      return varianceA && varianceB ? Math.max(-1, Math.min(1, covariance / Math.sqrt(varianceA * varianceB))) : null;
    });
  }

  function closeVolatility(values, length, periodsPerYear, sample = false) {
    const returns = values.map((value, index) => Number.isFinite(value) && value > 0
      && Number.isFinite(values[index - 1]) && values[index - 1] > 0
      ? Math.log(value) - Math.log(values[index - 1]) : null);
    const means = sma(returns.map(value => value ?? 0), length);
    const coverage = sma(returns.map(value => Number(value !== null)), length);
    const divisor = length - Number(sample);
    const scale = 100 * Math.sqrt(periodsPerYear);
    return means.map((mean, index) => {
      if (coverage[index] !== 1 || divisor <= 0) return null;
      let squared = 0;
      for (let j = index - length + 1; j <= index; j++) squared += (returns[j] - mean) ** 2;
      return scale * Math.sqrt(squared / divisor);
    });
  }

  function smaWithGaps(series, length) {
    const average = sma(series.filter(Number.isFinite), length);
    let index = 0;
    return series.map(value => Number.isFinite(value) ? average[index++] : null);
  }

  function stochastic(values, peaks, troughs, length) {
    const high = rollingExtreme(peaks, length, 1);
    const low = rollingExtreme(troughs, length, -1);
    return values.map((value, index) => index >= length - 1 && [value, high[index], low[index]].every(Number.isFinite) && high[index] > low[index]
      ? 100 * (value - low[index]) / (high[index] - low[index]) : null);
  }

  function obv(bars) {
    let total = 0;
    return bars.map((bar, index) => {
      if (!index) return total;
      const direction = Math.sign(bar.close - bars[index - 1].close);
      if (direction && (!Number.isFinite(bar.volume) || bar.volume < 0)) return null;
      if (direction) total += direction * bar.volume;
      return total;
    });
  }

  function macd(values, fastLength, slowLength, signalLength, oscillatorType, signalType, percentage = false) {
    const average = oscillatorType === 'SMA' ? sma : ema;
    const fast = average(values, fastLength);
    const slow = average(values, slowLength);
    const line = fast.map((value, i) => {
      if (value === null || slow[i] === null || (percentage && slow[i] === 0)) return null;
      const difference = value - slow[i];
      return percentage ? difference / slow[i] * 100 : difference;
    });
    const signalAverage = signalType === 'SMA' ? sma : ema;
    const smoothed = signalAverage(line.filter(Number.isFinite), signalLength);
    let index = 0;
    const signal = line.map(value => Number.isFinite(value) ? smoothed[index++] : null);
    const histogram = line.map((value, i) => value === null || signal[i] === null ? null : value - signal[i]);
    return [line, signal, histogram];
  }

  const pineSources = {
    open: bar => bar.open, high: bar => bar.high, low: bar => bar.low, close: bar => bar.close,
    volume: bar => Number.isFinite(bar.volume) && bar.volume >= 0 ? bar.volume : null,
    hl2: bar => (bar.high + bar.low) / 2,
    hlc3: bar => (bar.high + bar.low + bar.close) / 3,
    ohlc4: bar => (bar.open + bar.high + bar.low + bar.close) / 4
  };
  const pineBarFields = {
    bar_index: (_, index) => index,
    time: bar => {
      const seconds = bar.sourceTime ?? bar.time;
      return Number.isFinite(seconds) ? seconds * 1000 : null;
    }
  };
  const reservedPineName = name => Object.hasOwn(pineSources, name) || Object.hasOwn(pineBarFields, name);

  function zigZagPlots(bars, {deviation = 5, legs = 10, project = true} = {}) {
    const half = Math.floor(legs / 2);
    const extrema = [bars.map(bar => bar.high), bars.map(bar => bar.low)];
    const lastClosed = bars.findLastIndex(bar => !bar.provisional);
    const minimumReversal = deviation / 100;
    const confirmed = [];
    const source = direction => extrema[direction > 0 ? 0 : 1];
    const reverses = (pivot, price) => Number.isFinite(price) && pivot.price !== 0
      && pivot.direction * (pivot.price - price) >= Math.abs(pivot.price) * minimumReversal;
    const candidate = (index, direction, right) => {
      const values = source(direction);
      const price = values[index];
      if (index < half || !Number.isFinite(price)) return null;
      for (let i = index - half; i <= index + right; i++) {
        if (i === index) continue;
        const difference = direction * (price - values[i]);
        if (!Number.isFinite(difference) || difference < 0 || (i < index && difference === 0)) return null;
      }
      return {index, direction, price};
    };
    for (let i = half; i + half <= lastClosed; i++) {
      const last = confirmed.at(-1);
      const direction = last?.direction ?? 1;
      const continuation = candidate(i, direction, half);
      if (continuation && (!last || direction * (continuation.price - last.price) > 0)) {
        if (last) confirmed[confirmed.length - 1] = continuation;
        else confirmed.push(continuation);
        // OHLC alone cannot establish the order of two extremes on the same bar.
        continue;
      }
      const reversal = candidate(i, -direction, half);
      if (reversal && (!last || reverses(last, reversal.price))) confirmed.push(reversal);
    }

    let projection;
    if (project && bars.at(-1)?.provisional && confirmed.length) {
      let last = confirmed.at(-1);
      for (let i = last.index + 1; i < bars.length; i++) {
        if (reverses(last, source(-last.direction)[i])) break;
        if (last.direction * (source(last.direction)[i] - last.price) > 0 && confirmed.length > 1) {
          confirmed.pop();
          last = confirmed.at(-1);
          break;
        }
      }
      const direction = -last.direction;
      for (let i = Math.max(last.index + 1, lastClosed - half + 1); i < bars.length; i++) {
        const next = candidate(i, direction, bars.length - 1 - i);
        if (next && reverses(last, next.price) && (!projection || direction * (next.price - projection.price) > 0)) {
          projection = next;
        }
      }
    }

    const solid = bars.map(() => null);
    const dashed = bars.map(() => null);
    const pivots = confirmed.slice(-500);
    for (const pivot of pivots) solid[pivot.index] = pivot.price;
    solid.pivots = pivots;
    if (projection) {
      const last = pivots.at(-1);
      dashed[last.index] = last.price;
      dashed[projection.index] = projection.price;
      dashed.pivots = [last, projection];
    }
    return [solid, dashed];
  }

  function pivotValue(values, pivot, left, right, direction) {
    const value = values[pivot];
    if (pivot < left || pivot + right >= values.length || !Number.isFinite(value)) return null;
    for (let i = pivot - left; i <= pivot + right; i++) {
      if (!Number.isFinite(values[i])) return null;
      const difference = direction * (values[i] - value);
      if (difference > 0 || (i > pivot && difference === 0)) return null;
    }
    return value;
  }

  function rollingExtreme(values, length, direction, offset = false) {
    const candidates = [];
    let first = 0;
    return values.map((value, index) => {
      while (first < candidates.length && candidates[first] <= index - length) first++;
      if (Number.isFinite(value)) {
        while (candidates.length > first && direction * values[candidates.at(-1)] <= direction * value) {
          candidates.pop();
        }
        candidates.push(index);
      }
      const match = candidates[first];
      return match === undefined ? null : offset ? match - index : values[match];
    });
  }

  function cmo(values, length) {
    const changes = [];
    let previous, net = 0, magnitude = 0;
    return values.map(value => {
      if (!Number.isFinite(value)) return null;
      const change = value - previous;
      previous = value;
      if (!Number.isFinite(change)) return null;
      changes.push(change);
      net += change;
      magnitude += Math.abs(change);
      if (changes.length > length) {
        const expired = changes[changes.length - length - 1];
        net -= expired;
        magnitude -= Math.abs(expired);
      }
      return changes.length >= length && magnitude > 0 ? 100 * net / magnitude : null;
    });
  }

  function cci(values, length) {
    return values.map((value, index) => {
      if (index < length - 1) return null;
      // Center before summing: identical prices must have exactly zero
      // deviation, including after a non-flat window has expired.
      const start = index - length + 1, origin = values[start];
      let offsetSum = 0;
      for (let i = start; i <= index; i++) {
        if (!Number.isFinite(values[i])) return null;
        offsetSum += values[i] - origin;
      }
      const meanOffset = offsetSum / length;
      let deviation = 0;
      for (let i = start; i <= index; i++) deviation += Math.abs(values[i] - origin - meanOffset);
      return deviation > 0 ? (value - origin - meanOffset) / (0.015 * deviation / length) : null;
    });
  }

  function moneyFlowIndex(bars, values, length) {
    const valid = bars.map((bar, i) => i > 0 && Number.isFinite(values[i]) && Number.isFinite(values[i - 1])
      && Number.isFinite(bar.volume) && bar.volume >= 0);
    const flow = bars.map((bar, i) => {
      if (!valid[i]) return 0;
      const current = Number(values[i].toFixed(9)), previous = Number(values[i - 1].toFixed(9));
      return (current > previous ? 1 : current < previous ? -1 : 0) * values[i] * bar.volume;
    });
    return flow.map((_, i) => {
      if (i < length) return null;
      // Sum the current window directly: cancelled old flows must not leave a
      // residual that turns a zero-flow window into an apparent 0/100 reading.
      let positive = 0, negative = 0;
      for (let j = i - length + 1; j <= i; j++) {
        if (!valid[j]) return null;
        positive += Math.max(0, flow[j]);
        negative += Math.max(0, -flow[j]);
      }
      return positive + negative > 0 ? 100 * positive / (positive + negative) : null;
    });
  }

  const pineSeriesFunctions = { sma, wma, hma, ema, rma, rsi, cmo, cci,
    dema: (values, length) => indicators.DEMA.run([], values, length)[0],
    tema: (values, length) => indicators.TEMA.run([], values, length)[0],
    change: (values, length) => values.map((value, index) => index < length || !Number.isFinite(value) || !Number.isFinite(values[index - length])
      ? null : value - values[index - length]),
    roc: (values, length) => values.map((value, index) => index < length || values[index - length] === 0
      ? null : 100 * (value - values[index - length]) / values[index - length]),
    highest: (values, length) => rollingExtreme(values, length, 1),
    lowest: (values, length) => rollingExtreme(values, length, -1)
  };

  function pineString(token, max, min = 0) {
    const match = /^(['"])((?:\\.|(?!\1)[^\\\r\n])*)\1$/.exec(token ?? '');
    const value = match?.[2].replace(/\\([\\'"ntr])/g, (_, char) => ({ n: '\n', t: '\t', r: '\r' })[char] ?? char);
    return value !== undefined && value.length >= min && value.length <= max ? value : undefined;
  }

  function pineArguments(text) {
    const args = [];
    let start = 0, depth = 0, quote = null;
    for (let i = 0; i < text.length; i++) {
      if (quote) {
        if (text[i] === '\\') i++;
        else if (text[i] === quote) quote = null;
        continue;
      }
      if (text[i] === '"' || text[i] === "'") { quote = text[i]; continue; }
      if (text[i] === '(' || text[i] === '[') depth++;
      if (text[i] === ')' || text[i] === ']') depth--;
      if (depth < 0) throw new Error('Unexpected closing parenthesis.');
      if (text[i] === ',' && depth === 0) {
        args.push(text.slice(start, i).trim());
        start = i + 1;
      }
    }
    if (depth || quote) throw new Error('Unclosed parenthesis or string.');
    return [...args, text.slice(start).trim()];
  }

  function pineInputStatusLine(expression) {
    const flags = {none: 0, status_line: 1, data_window: 2, all: 3};
    const raw = expression.trim().replace(/\s+/g, '');
    if (!/^display\.(?:none|status_line|data_window|all)(?:[+-]display\.(?:none|status_line|data_window|all))*$/.test(raw)) return undefined;
    let mask = 0;
    for (const [, sign, flag] of raw.matchAll(/([+-]?)display\.(\w+)/g)) {
      mask = sign === '-' ? mask & ~flags[flag] : mask | flags[flag];
    }
    return Boolean(mask & flags.status_line);
  }

  function pineNamedInputStatusLines(source) {
    const tokens = /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\/\/[^\r\n]*/g;
    const code = source.replace(tokens, token => token.startsWith('//') ? ' '.repeat(token.length) : token);
    const masked = code.replace(tokens, token => ' '.repeat(token.length));
    const flags = new Map();
    for (const match of masked.matchAll(/^[ \t]*(?:[a-zA-Z_]\w*[ \t]+)*([a-zA-Z_]\w*)[ \t]*=[ \t]*input(?:\.\w+)?[ \t]*\(/gm)) {
      const start = match.index + match[0].length;
      let end = start;
      let depth = 1;
      for (; end < masked.length; end++) {
        if (masked[end] === '(') depth++;
        else if (masked[end] === ')' && --depth === 0) break;
      }
      if (depth !== 0) continue;
      const display = pineArguments(code.slice(start, end)).find(arg => /^display\s*=/.test(arg));
      if (!display) continue;
      const visible = pineInputStatusLine(display.slice(display.indexOf('=') + 1));
      if (visible !== undefined) flags.set(match[1], visible);
    }
    return flags;
  }

  const pineOperators = [
    { '+': (left, right) => left + right, '-': (left, right) => left - right },
    { '*': (left, right) => left * right, '/': (left, right) => left / right, '%': (left, right) => left % right }
  ];

  function pineArithmetic(text, parse) {
    const splits = [-1, -1];
    let depth = 0;
    for (let index = 0; index < text.length; index++) {
      const char = text[index];
      if ((char === '(' || char === '[')) depth++;
      if ((char === ')' || char === ']')) depth--;
      if (depth !== 0) continue;
      const level = pineOperators.findIndex(operators => Object.hasOwn(operators, char));
      if (level < 0) continue;
      const left = text.slice(0, index).trimEnd();
      if ((char === '+' || char === '-') && (!left || /[+\-*/%]$/.test(left))) continue;
      splits[level] = index;
    }
    const split = splits.findIndex(index => index >= 0);
    if (split >= 0) {
      const at = splits[split];
      const left = parse(text.slice(0, at)), right = parse(text.slice(at + 1));
      const apply = pineOperators[split][text[at]];
      return context => {
        const values = right(context);
        return left(context).map((value, index) => {
          if (!Number.isFinite(value) || !Number.isFinite(values[index])) return null;
          const result = apply(value, values[index]);
          return Number.isFinite(result) ? result : null;
        });
      };
    }
    if (text.startsWith('-') || text.startsWith('+')) {
      const source = parse(text.slice(1));
      return text.startsWith('+') ? source : context => source(context).map(value => value === null ? null : -value);
    }
    if (text.startsWith('(') && text.endsWith(')')) {
      let nesting = 1;
      for (let index = 1; index < text.length; index++) {
        if (text[index] === '(') nesting++;
        if (text[index] === ')') nesting--;
        if (nesting === 0) return index === text.length - 1 ? parse(text.slice(1, -1)) : null;
      }
    }
    return null;
  }

  const pineComparisons = {
    '==': (a, b) => a === b, '!=': (a, b) => a !== b,
    '>': (a, b) => a > b, '<': (a, b) => a < b,
    '>=': (a, b) => a >= b, '<=': (a, b) => a <= b
  };

  function pineConditional(text, parse) {
    let depth = 0, nested = 0, question = -1, comparison;
    for (let index = 0; index < text.length; index++) {
      const char = text[index];
      if ((char === '(' || char === '[')) depth++;
      if ((char === ')' || char === ']')) depth--;
      if (depth) continue;
      if (char === '?') {
        if (question < 0) question = index;
        nested++;
      } else if (char === ':' && question >= 0 && --nested === 0) {
        const condition = parse(text.slice(0, question));
        const yes = parse(text.slice(question + 1, index));
        const no = parse(text.slice(index + 1));
        return context => {
          const matches = condition(context), selected = yes(context), fallback = no(context);
          return matches.map((match, index) => match === true ? selected[index] : fallback[index]);
        };
      } else if (question < 0) {
        const token = /^(?:==|!=|>=|<=|>|<)/.exec(text.slice(index))?.[0];
        if (token) {
          comparison = comparison ? { ...comparison, chained: true } : { index, token };
          index += token.length - 1;
        }
      }
    }
    if (question >= 0) throw new Error('A conditional expression requires both branches.');
    const logical = pineLogic(text, parse, !comparison);
    if (logical) return logical;
    if (!comparison) return null;
    if (comparison.chained) throw new Error('Combine comparisons with “and” or “or”.');
    const { index, token } = comparison;
    const left = parse(text.slice(0, index)), right = parse(text.slice(index + token.length));
    return context => {
      const values = right(context);
      return left(context).map((value, index) =>
        ((Number.isFinite(value) && Number.isFinite(values[index]))
          || (['==', '!='].includes(token) && typeof value === 'string' && typeof values[index] === 'string'))
          && pineComparisons[token](value, values[index]));
    };
  }

  function pineLogic(text, parse, allowNot) {
    let depth = 0;
    const splits = new Map();
    for (let index = 0; index < text.length; index++) {
      if ((text[index] === '(' || text[index] === '[')) depth++;
      if ((text[index] === ')' || text[index] === ']')) depth--;
      if (depth || !/\s/.test(text[index])) continue;
      const token = /^\s+(or|and)\s+/.exec(text.slice(index));
      if (token) splits.set(token[1], [index, token[0].length]);
    }
    for (const operator of ['or', 'and']) {
      if (!splits.has(operator)) continue;
      const [index, width] = splits.get(operator);
      const left = parse(text.slice(0, index)), right = parse(text.slice(index + width));
      return context => {
        const values = right(context);
        return left(context).map((value, i) => operator === 'and'
          ? value === true && values[i] === true : value === true || values[i] === true);
      };
    }
    if (allowNot && /^not\s+/.test(text)) {
      const source = parse(text.replace(/^not\s+/, ''));
      return context => source(context).map(value => value === false);
    }
    return null;
  }

  function pineKeltner(args, parse) {
    if (args.length < 3 || args.length > 4 || args.some(arg => !arg)) {
      throw new Error('Keltner requires source, length, multiplier and optional useTrueRange.');
    }
    const [source, length, factor, useTrueRange] = args.map(parse);
    return context => {
      if (!context.bars.length) return [[], [], []];
      const period = length(context)[0], multiplier = factor(context)[0];
      const useRange = useTrueRange ? useTrueRange(context)[0] : true;
      if (!Number.isInteger(period) || period < 1 || period > 250
          || !Number.isFinite(multiplier) || typeof useRange !== 'boolean') {
        throw new Error('Keltner requires a length from 1 to 250, finite multiplier and Boolean useTrueRange.');
      }
      const values = source(context);
      let index = 0;
      const average = ema(values.filter(Number.isFinite), period);
      const basis = values.map(value => Number.isFinite(value) ? average[index++] : null);
      const span = useRange ? trueRange(context.bars, () => false)
        : context.bars.map(bar => bar.high - bar.low);
      index = 0;
      const smoothed = ema(span.filter(Number.isFinite), period);
      const width = span.map(value => Number.isFinite(value) ? smoothed[index++] * multiplier : null);
      const band = direction => basis.map((value, i) => Number.isFinite(value) && Number.isFinite(width[i])
        ? value + direction * width[i] : null);
      return [basis, band(1), band(-1)];
    };
  }

  function pineLength(definition, overrides) {
    const value = overrides?.[definition.id];
    return Number.isInteger(value) && (definition.options ? definition.options.includes(value) : value >= definition.min && value <= definition.max)
      ? value : definition.value;
  }

  function pineExpression(text, inputs, variables, depth = 0) {
    if (depth > 32) throw new Error('Expression nesting exceeds 32 levels.');
    text = text.trim();
    const parse = inner => pineExpression(inner, inputs, variables, depth + 1);
    const conditional = pineConditional(text, parse);
    if (conditional) return conditional;
    const arithmetic = pineArithmetic(text, parse);
    if (arithmetic) return arithmetic;
    if (text === 'true' || text === 'false') return ({ bars }) => bars.map(() => text === 'true');
    const syntheticChartFlags = {
      'chart.is_renko': 'Renko',
      'chart.is_linebreak': 'Line break',
      'chart.is_kagi': 'Kagi',
      'chart.is_heikinashi': 'Heikin Ashi'
    };
    if (text === 'chart.is_standard' || Object.hasOwn(syntheticChartFlags, text)) {
      return ({bars, symbolInfo}) => {
        const type = symbolInfo.chartType;
        const matches = text === 'chart.is_standard'
          ? !Object.values(syntheticChartFlags).includes(type)
          : type === syntheticChartFlags[text];
        return bars.map(() => matches);
      };
    }
    if (text === 'syminfo.mintick') return ({bars, symbolInfo}) => bars.map(() => symbolInfo.minTick ?? null);
    if (text === 'ta.obv') return ({bars}) => obv(bars);
    if (text === 'ta.accdist') return ({bars}) => indicators.ADL.run(bars)[0];
    if (text === 'ta.pvi' || text === 'ta.nvi') return ({bars}) => {
      const direction = text === 'ta.pvi' ? 1 : -1;
      let indexValue = 1;
      return bars.map(({close, volume}, index) => {
        const previous = bars[index - 1];
        const previousVolume = Number.isFinite(previous?.volume) ? previous.volume : 0;
        if (indexValue === 0) indexValue = 1;
        if (Number.isFinite(close) && close !== 0 && Number.isFinite(previous?.close) && previous.close !== 0
            && Number.isFinite(volume) && (volume - previousVolume) * direction > 0) {
          indexValue += (close - previous.close) / previous.close * indexValue;
        }
        return indexValue;
      });
    };
    if (text === 'ta.pvt') return ({bars}) => {
      let total = 0;
      return bars.map(({close, volume}, index) => {
        const previous = bars[index - 1]?.close;
        if (!Number.isFinite(previous) || !previous || !Number.isFinite(close)
            || !Number.isFinite(volume) || volume < 0) return null;
        total += (close - previous) / previous * volume;
        return total;
      });
    };
    if (text === 'ta.iii') return ({bars}) => bars.map(({high, low, close, volume}) =>
      high > low && Number.isFinite(volume) && volume >= 0
        ? (2 * close - high - low) / (high - low) * volume : null);
    const timeframeChange = /^timeframe\.change\(\s*(?:(?:timeframe\s*=\s*)?(.+?))?\s*\)$/.exec(text);
    if (timeframeChange) {
      const argument = timeframeChange[1];
      const literal = argument === undefined ? undefined : pineString(argument, 8);
      const input = inputs.get(argument);
      if (argument !== undefined && literal === undefined && input?.type !== 'string') {
        throw new Error('timeframe.change() requires a quoted interval or a timeframe input.');
      }
      return ({bars, symbolInfo, overrides}) => {
        const override = input && overrides[input.id];
        const choice = typeof override === 'string' && (!input.options || input.options.includes(override)) ? override : input?.value;
        const raw = (choice ?? literal) || symbolInfo.interval || '1';
        const interval = /^[DWM]$/.test(raw) ? '1' + raw : raw;
        const unit = interval.at(-1);
        const calendar = ['D', 'W', 'M'].includes(unit);
        const length = Number(calendar ? interval.slice(0, -1) : interval);
        const limit = {D: 365, W: 52, M: 12}[unit] ?? 1440;
        if (!/^[1-9]\d{0,3}[DWM]?$/.test(interval) || !Number.isInteger(length) || length > limit) {
          throw new Error('timeframe.change() requires a supported minute, day, week, or month interval.');
        }
        if (!calendar && symbolInfo.sessionOpen === null) throw new Error('Minute anchors are unavailable for this market session.');
        const offset = symbolInfo.sessionOffset ?? 0;
        let previous;
        return bars.map(bar => {
          const time = (bar.sourceTime ?? bar.time) + offset;
          const day = Math.floor(time / 86400);
          const date = unit === 'M' ? new Date(time * 1000) : undefined;
          const key = unit === 'M' ? Math.floor((date.getUTCFullYear() * 12 + date.getUTCMonth()) / length)
            : unit === 'W' ? Math.floor((day + 3) / (7 * length))
            : unit === 'D' ? Math.floor(day / length)
            : Math.floor((time - (symbolInfo.sessionOpen ?? 0)) / (length * 60));
          const changed = key !== previous;
          previous = key;
          return changed;
        });
      };
    }
    if (text === 'ta.vwap') return pineVwap(['hlc3'], parse);
    if (text === 'ta.tr') return ({bars}) => trueRange(bars, () => false);
    if (text === 'na') return ({ bars }) => bars.map(() => null);
    if (/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(text) && Number.isFinite(Number(text))) {
      const value = Number(text);
      return ({ bars }) => bars.map(() => value);
    }
    const literalString = /^"([^"\\]{0,80})"$/.exec(text);
    if (literalString) return ({bars}) => bars.map(() => literalString[1]);
    const sourceInput = inputs.get(text);
    if (sourceInput?.type === 'source') return ({bars, overrides}) => {
      const chosen = overrides[text];
      return bars.map(pineSources[sourceInput.options.includes(chosen) ? chosen : sourceInput.value]);
    };
    if (sourceInput?.type === 'string') return ({bars, overrides}) =>
      bars.map(() => typeof overrides[text] === 'string' && overrides[text].length <= 80
        && (!sourceInput.options || sourceInput.options.includes(overrides[text])) ? overrides[text] : sourceInput.value);
    if (sourceInput?.type === 'bool') return ({bars, overrides}) =>
      bars.map(() => typeof overrides[text] === 'boolean' ? overrides[text] : sourceInput.value);
    if (sourceInput?.type === 'float') return ({bars, overrides}) => {
      const value = overrides[text];
      return bars.map(() => Number.isFinite(value) && (sourceInput.options ? sourceInput.options.includes(value) : value >= sourceInput.min && value <= sourceInput.max)
        ? value : sourceInput.value);
    };
    if (sourceInput) return ({ bars, overrides }) => bars.map(() => pineLength(sourceInput, overrides));
    if (Object.hasOwn(pineBarFields, text)) return ({bars}) => bars.map(pineBarFields[text]);
    if (Object.hasOwn(pineSources, text)) return ({ bars }) => bars.map(pineSources[text]);
    if (variables.has(text)) return ({ series }) => series.get(text);
    const prior = /^([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)?(?:\([\s\S]*\))?|\([\s\S]*\))\s*\[\s*([\s\S]+?)\s*\]$/.exec(text);
    if (prior) {
      const source = parse(prior[1]);
      const token = prior[2].trim();
      if (!/^\d{1,4}$/.test(token) && !inputs.has(token)) {
        const offsets = parse(token);
        return context => {
          const values = source(context);
          const lags = offsets(context);
          return values.map((_, index) => {
            const lag = lags[index];
            return Number.isInteger(lag) && lag >= 0 && lag <= 9999 && lag <= index
              ? values[index - lag] : null;
          });
        };
      }
      const input = inputs.get(token);
      const literal = Number(token);
      if (input ? input.type || input.value < 0 || input.value > 9999 : !Number.isInteger(literal)) {
        throw new Error('History offset requires a nonnegative integer literal, input, or series.');
      }
      return context => {
        const offset = input ? pineLength(input, context.overrides) : literal;
        if (offset < 0 || offset > 9999) throw new Error('History offset must be between 0 and 9999.');
        const values = source(context);
        return values.map((_, index) => index >= offset ? values[index - offset] : null);
      };
    }
    const sumCall = /^math\.sum\((.*)\)$/.exec(text);
    if (sumCall) {
      const args = pineArguments(sumCall[1]);
      if (args.length !== 2 || args.some(arg => !arg)) throw new Error('Incorrect argument count for math.sum().');
      const source = parse(args[0]);
      const input = inputs.get(args[1]);
      const literal = /^\d+$/.test(args[1]) ? Number(args[1]) : NaN;
      if (input ? input.type : !(literal >= 1 && literal <= 250)) {
        throw new Error('Sum length requires an integer from 1 to 250 or an integer input.');
      }
      return context => {
        const length = input ? pineLength(input, context.overrides) : literal;
        if (length < 1) throw new Error('Sum length must be positive.');
        const values = [];
        let total = 0;
        return source(context).map(value => {
          if (Number.isFinite(value)) {
            total += value;
            values.push(value);
            if (values.length > length) total -= values.shift();
          }
          return values.length === length ? total : null;
        });
      };
    }
    const tickRound = /^math\.round_to_mintick\((.*)\)$/.exec(text);
    if (tickRound) {
      const args = pineArguments(tickRound[1]);
      if (args.length !== 1 || !args[0]) throw new Error('math.round_to_mintick() requires one number.');
      const evaluate = parse(args[0].replace(/^number\s*=(?!=)\s*/, ''));
      return context => {
        const {minTick} = context.symbolInfo;
        return evaluate(context).map(value => {
          if (!Number.isFinite(value) || !Number.isFinite(minTick) || minTick <= 0) return null;
          const ratio = value / minTick;
          const half = Math.floor(ratio) + 0.5;
          const nearest = Math.abs(ratio - half) <= Math.abs(ratio) * Number.EPSILON * 2 ? half : ratio;
          return Math.round(nearest) * minTick;
        });
      };
    }
    const roundCall = /^math\.round\((.*)\)$/.exec(text);
    if (roundCall) {
      const args = pineArguments(roundCall[1]);
      if (args.length < 1 || args.length > 2 || args.some(arg => !arg)) {
        throw new Error('math.round() requires a number and optional precision.');
      }
      const [number, precision] = args.map(parse);
      return context => {
        const digits = precision?.(context);
        return number(context).map((value, index) => {
          const places = digits ? digits[index] : 0;
          if (!Number.isFinite(value) || !Number.isInteger(places)) return null;
          const scale = 10 ** places;
          const scaled = value * scale;
          if (!scale || !Number.isFinite(scaled)) return null;
          const half = Math.floor(scaled) + 0.5;
          const nearest = Math.abs(scaled - half) <= Math.abs(scaled) * Number.EPSILON * 2 ? half : scaled;
          const result = Math.round(nearest) / scale;
          return Number.isFinite(result) ? result || 0 : null;
        });
      };
    }
    const mathCall = /^math\.(abs|sqrt|log|log10|exp|pow|min|max|floor|ceil|sign|sin|cos|tan|asin|acos|atan)\((.*)\)$/.exec(text);
    if (mathCall) {
      const [, name, raw] = mathCall;
      const args = pineArguments(raw);
      const variadic = name === 'min' || name === 'max';
      if (args.some(arg => !arg) || (variadic ? args.length < 2 || args.length > 16
        : args.length !== (name === 'pow' ? 2 : 1))) {
        throw new Error('Incorrect argument count for math.' + name + '().');
      }
      const operands = args.map(arg => parse(arg));
      return context => {
        const series = operands.map(evaluate => evaluate(context));
        return context.bars.map((_, i) => {
          const values = series.map(values => values[i]);
          if (!values.every(Number.isFinite)) return null;
          const result = Math[name](...values);
          return Number.isFinite(result) ? result : null;
        });
      };
    }
    const missingCall = /^(na|nz)\((.*)\)$/.exec(text);
    if (missingCall) {
      const [, name, raw] = missingCall;
      const args = pineArguments(raw);
      if (!args[0] || args.length > (name === 'na' ? 1 : 2)) {
        throw new Error('Incorrect argument count for ' + name + '().');
      }
      const source = parse(args[0]);
      const missing = value => value == null || (typeof value === 'number' && !Number.isFinite(value));
      if (name === 'na') return context => source(context).map(missing);
      const replacement = args.length === 2 ? parse(args[1]) : null;
      return context => {
        const fallback = replacement?.(context);
        return source(context).map((value, i) => missing(value) ? (fallback ? fallback[i] : 0) : value);
      };
    }
    const call = /^ta\.(vwap|sma|swma|alma|wma|vwma|hma|ema|dema|tema|rma|rsi|atr|tr|cum|max|min|barssince|valuewhen|linreg|stdev|variance|dev|range|median|mode|percentrank|correlation|percentile_nearest_rank|percentile_linear_interpolation|pivothigh|pivotlow|change|mom|roc|cmo|cci|mfi|cog|bbw|kcw|wpr|stoch|highest|lowest|highestbars|lowestbars|rising|falling|cross|crossover|crossunder)\((.*)\)$/.exec(text);
    if (!call) throw new Error('Use a price source, declared series, or supported ta function.');
    const [, name, raw] = call;
    const args = pineArguments(raw);
    if (name === 'vwap') return pineVwap(args, parse);
    if (name === 'kcw') {
      const evaluate = pineKeltner(args, parse);
      return context => {
        const [basis, upper, lower] = evaluate(context);
        return basis.map((value, i) => value && Number.isFinite(upper[i]) ? (upper[i] - lower[i]) / value : null);
      };
    }
    if (name === 'alma') {
      const parameters = ['series', 'length', 'offset', 'sigma', 'floor'];
      if (args.some(arg => /^\w+\s*=(?!=)/.test(arg))) {
        const ordered = [];
        let named = false;
        for (const arg of args) {
          const assignment = /^(\w+)\s*=(?!=)\s*(.*)$/.exec(arg);
          if (assignment) named = true;
          const index = assignment ? parameters.indexOf(assignment[1]) : named ? -1 : ordered.length;
          if (index < 0 || index >= parameters.length || Object.hasOwn(ordered, index)) {
            throw new Error('Invalid or duplicate argument for ta.alma().');
          }
          ordered[index] = assignment ? assignment[2] : arg;
        }
        args.splice(0, args.length, ...ordered);
      }
      if (args.length < 4 || args.length > 5 || args.some(arg => !arg)) {
        throw new Error('ta.alma() requires source, length, offset and sigma, with optional floor.');
      }
      const [source, lengthInput, offsetInput, sigmaInput, floorInput] = args.map(parse);
      return context => {
        if (!context.bars.length) return [];
        const length = lengthInput(context)[0];
        const offset = offsetInput(context)[0];
        const sigma = sigmaInput(context)[0];
        const floor = floorInput?.(context)[0] ?? false;
        if (!Number.isInteger(length) || length < 1 || length > 500
            || !Number.isFinite(offset) || !Number.isFinite(sigma) || sigma <= 0 || typeof floor !== 'boolean') {
          throw new Error('ALMA requires a length from 1 to 500, finite offset, positive sigma and Boolean floor.');
        }
        return alma(source(context), length, offset, sigma, floor);
      };
    }
    if (name === 'swma') {
      if (args.length !== 1 || !args[0]) throw new Error('ta.swma() requires one source.');
      const source = parse(args[0].replace(/^source\s*=(?!=)\s*/, ''));
      return context => swma(source(context));
    }
    const namedParameters = {
      correlation: ['source1', 'source2', 'length'],
      percentile_nearest_rank: ['source', 'length', 'percentage'],
      percentile_linear_interpolation: ['source', 'length', 'percentage'],
      min: ['source'], max: ['source'], wpr: ['length']
    };
    const order = Object.hasOwn(namedParameters, name) ? namedParameters[name]
      : /^(sma|wma|vwma|hma|ema|dema|tema|rma|rsi|mom|roc|cmo|cci|mfi|cog|dev|range|median|mode|percentrank)$/.test(name)
        ? ['source', 'length'] : null;
    if (order && args.some(arg => /^\w+\s*=(?!=)/.test(arg))) {
      const ordered = [];
      let named = false;
      for (const arg of args) {
        const match = /^(\w+)\s*=(?!=)\s*(.*)$/.exec(arg);
        if (match) named = true;
        const index = match ? order.indexOf(match[1]) : named ? -1 : ordered.length;
        if (index < 0 || index >= order.length || ordered[index] !== undefined) {
          throw new Error('Invalid or duplicate argument for ta.' + name + '().');
        }
        ordered[index] = match ? match[2] : arg;
      }
      if (!order.every((_, index) => ordered[index])) throw new Error('ta.' + name + '() requires ' + order.join(', ') + '.');
      args.splice(0, args.length, ...ordered);
    }
    if (args.length === 1 && ['highest', 'lowest', 'highestbars', 'lowestbars'].includes(name)) {
      args.unshift(name.startsWith('highest') ? 'high' : 'low');
    }
    if (name === 'change' && args.length === 1) args.push('1');
    if (name === 'pivothigh' || name === 'pivotlow') {
      const high = name === 'pivothigh';
      if (args.length === 2) args.unshift(high ? 'high' : 'low');
      if (args.length !== 3 || args.some(arg => !arg)) throw new Error('Incorrect argument count for ta.' + name + '().');
      const source = parse(args[0]);
      const strength = token => {
        const input = inputs.get(token);
        if (input && !input.type) return context => pineLength(input, context.overrides);
        const value = /^\d+$/.test(token) ? Number(token) : NaN;
        if (!(value >= 0 && value <= 250)) throw new Error('Pivot strengths must be integers from 0 to 250.');
        return () => value;
      };
      const leftBars = strength(args[1]), rightBars = strength(args[2]);
      return context => {
        const values = source(context);
        const left = leftBars(context), right = rightBars(context);
        if (left < 0 || right < 0) throw new Error('Pivot strengths must be non-negative.');
        const direction = high ? 1 : -1;
        return values.map((_, confirmation) => pivotValue(values, confirmation - right, left, right, direction));
      };
    }
    let bandMultiplier;
    if (name === 'bbw') {
      if (args.length !== 3 || args.some(arg => !arg)) throw new Error('Incorrect argument count for ta.bbw().');
      bandMultiplier = parse(args.pop());
    }
    const dispersion = name === 'variance' || name === 'stdev';
    const biased = dispersion && args.length === 3 ? parse(args.pop()) : null;
    let regressionOffset;
    if (name === 'linreg' && args.length === 3) {
      const token = args.pop().replace(/\s+/g, '');
      const literal = /^[+-]?\d+$/.test(token) ? Number(token) : NaN;
      const input = inputs.get(token.replace(/^[+-]/, ''));
      if (Number.isSafeInteger(literal)) regressionOffset = () => literal;
      else if (input && !input.type) {
        regressionOffset = overrides => (token.startsWith('-') ? -1 : 1) * pineLength(input, overrides);
      } else throw new Error('Regression offset requires an integer or integer input.');
    }
    if (name === 'linreg' && !regressionOffset) throw new Error('Incorrect argument count for ta.linreg().');
    const percentile = name === 'percentile_nearest_rank' || name === 'percentile_linear_interpolation';
    if (percentile && args.length !== 3) throw new Error('Incorrect argument count for ta.' + name + '().');
    const percentage = percentile ? parse(args.pop()) : null;
    const hasDefaultSource = ['highest', 'highestbars', 'lowest', 'lowestbars'].includes(name);
    const sourceAndLength = ['sma', 'ema', 'wma', 'vwma', 'hma', 'rma', 'rsi', 'dema', 'tema'].includes(name);
    if (hasDefaultSource || sourceAndLength) {
      const defaultSource = hasDefaultSource ? (name.startsWith('highest') ? 'high' : 'low') : undefined;
      if (args.some(arg => /^\w+\s*=(?!=)/.test(arg))) {
        const parameters = ['source', 'length'];
        const ordered = [];
        let named = false;
        for (const arg of args) {
          const assignment = /^(\w+)\s*=(?!=)\s*(.*)$/.exec(arg);
          if (assignment) named = true;
          const index = assignment ? parameters.indexOf(assignment[1]) : named ? -1 : ordered.length;
          if (index < 0 || index >= parameters.length || Object.hasOwn(ordered, index)) {
            throw new Error('Invalid or duplicate argument for ta.' + name + '().');
          }
          ordered[index] = assignment ? assignment[2] : arg;
        }
        args.splice(0, args.length, ordered[0] ?? defaultSource, ordered[1]);
      } else if (hasDefaultSource && args.length === 1) {
        args.unshift(defaultSource);
      }
    }
    if (name === 'atr' && args.length === 1) {
      args[0] = args[0].replace(/^length\s*=(?!=)\s*/, '');
    }
    const expected = ['atr', 'tr', 'cum', 'max', 'min', 'barssince', 'wpr'].includes(name) ? 1 : name === 'stoch' ? 4 : ['valuewhen', 'correlation'].includes(name) ? 3 : 2;
    if (args.some(arg => !arg) || args.length !== expected) throw new Error('Incorrect argument count for ta.' + name + '().');
    if (name === 'tr') {
      const flag = parse(args[0]);
      return context => {
        const values = flag(context);
        return trueRange(context.bars, index => values[index] === true);
      };
    }
    if (name === 'valuewhen') {
      const condition = parse(args[0]);
      const source = parse(args[1]);
      const input = inputs.get(args[2]);
      const occurrence = /^\d+$/.test(args[2]) ? Number(args[2]) : NaN;
      if ((!input || input.type) && !Number.isSafeInteger(occurrence)) {
        throw new Error('Occurrence must be a non-negative integer or an integer input.');
      }
      return context => {
        const offset = input ? pineLength(input, context.overrides) : occurrence;
        if (offset < 0) throw new Error('Occurrence must be non-negative.');
        const values = source(context);
        const matches = [];
        return condition(context).map((active, index) => {
          if (active === true) matches.push(values[index]);
          return matches[matches.length - 1 - offset] ?? null;
        });
      };
    }
    if (name === 'barssince') {
      const condition = parse(args[0]);
      return context => {
        let last = -1;
        return condition(context).map((value, index) => {
          if (value === true) last = index;
          return last < 0 ? null : index - last;
        });
      };
    }
    if (name === 'max' || name === 'min') {
      const source = parse(args[0]);
      const extreme = name === 'max' ? Math.max : Math.min;
      return context => {
        let result = null;
        return source(context).map(value => {
          if (Number.isFinite(value)) result = result === null ? value : extreme(result, value);
          return result;
        });
      };
    }
    if (name === 'cum') {
      const source = parse(args[0]);
      return context => {
        let total = 0;
        return source(context).map(value => {
          if (!Number.isFinite(value)) return null;
          total += value;
          return total;
        });
      };
    }
    if (['cross', 'crossover', 'crossunder'].includes(name)) {
      const left = parse(args[0]), right = parse(args[1]);
      return context => {
        const a = left(context), b = right(context);
        return a.map((value, index) => {
          if (!index || ![value, b[index], a[index - 1], b[index - 1]].every(Number.isFinite)) return false;
          const up = value > b[index] && a[index - 1] <= b[index - 1];
          const down = value < b[index] && a[index - 1] >= b[index - 1];
          return (name !== 'crossunder' && up) || (name !== 'crossover' && down);
        });
      };
    }
    const token = args.at(-1);
    const definition = inputs.get(token);
    const numeric = /^\d+$/.test(token) ? Number(token) : NaN;
    if (definition?.type) throw new Error('Length requires an integer input.');
    if (definition && definition.value < 1) {
      throw new Error('Default length must be positive for ta.' + name + '().');
    }
    if (!definition && !(numeric >= 1 && numeric <= 250)) {
      throw new Error('Length must be between 1 and 250 or use a declared input.');
    }
    const source = ['atr', 'wpr'].includes(name) ? null : parse(args[0]);
    const bounds = name === 'stoch' ? args.slice(1, 3).map(parse) : null;
    const comparison = name === 'correlation' ? parse(args[1]) : null;
    return context => {
      const length = definition ? pineLength(definition, context.overrides) : numeric;
      if (length < 1) throw new Error('Length must be positive for ta.' + name + '().');
      if (name === 'wpr') return indicators.WilliamsR.run(context.bars, [], length)[0];
      if (!source) return atr(context.bars, length);
      const values = source(context);
      if (name === 'percentrank') return percentRank(values, length);
      if (percentage) {
        const percentages = percentage(context);
        return values.map((_, index) => {
          const percent = percentages[index];
          if (index + 1 < length || !Number.isFinite(percent) || percent < 0 || percent > 100) return null;
          const nearest = name === 'percentile_nearest_rank';
          const sample = values.slice(index + 1 - length, index + 1);
          const window = nearest ? sample.filter(Number.isFinite) : sample;
          if (!window.length || (!nearest && !window.every(Number.isFinite))) return null;
          window.sort((left, right) => left - right);
          if (nearest) return window[Math.max(0, Math.ceil(percent * window.length / 100) - 1)];
          const rank = percent * (length - 1) / 100;
          const lower = Math.floor(rank);
          return window[lower] + (window[Math.ceil(rank)] - window[lower]) * (rank - lower);
        });
      }
      if (comparison) {
        const other = comparison(context);
        return rollingPearson(values, other, length);
      }
      if (bounds) return stochastic(values, bounds[0](context), bounds[1](context), length);
      if (name === 'cog') return cog(values, length);
      if (name === 'highestbars' || name === 'lowestbars') {
        return rollingExtreme(values, length, name === 'highestbars' ? 1 : -1, true);
      }
      if (name === 'rising' || name === 'falling') {
        const direction = name === 'rising' ? 1 : -1;
        const valid = values.filter(Number.isFinite);
        const extremes = rollingExtreme(valid, length, direction);
        let index = 0;
        return values.map(value => {
          if (!Number.isFinite(value)) return false;
          const previous = index++;
          return previous >= length && direction * (value - extremes[previous - 1]) > 0;
        });
      }
      if (name === 'linreg') return linearRegression(values, length, regressionOffset(context.overrides));
      if (dispersion || ['dev', 'range', 'median', 'mode'].includes(name)) {
        const flags = biased?.(context);
        const window = [];
        return values.map((value, i) => {
          if (!Number.isFinite(value)) return null;
          window.push(value);
          if (window.length > length) window.shift();
          const denominator = length - Number(flags?.[i] === false);
          if (window.length < length || !denominator) return null;
          if (name === 'range') return Math.max(...window) - Math.min(...window);
          if (name === 'mode') {
            const counts = new Map();
            let mode = Infinity, frequency = 0;
            for (const item of window) {
              const count = (counts.get(item) ?? 0) + 1;
              counts.set(item, count);
              if (count > frequency || (count === frequency && item < mode)) {
                mode = item;
                frequency = count;
              }
            }
            return mode;
          }
          if (name === 'median') return median(window);
          const mean = window.reduce((sum, item) => sum + item, 0) / length;
          if (name === 'dev') return window.reduce((sum, item) => sum + Math.abs(item - mean), 0) / length;
          const variance = window.reduce((sum, item) => sum + (item - mean) ** 2, 0) / denominator;
          return name === 'stdev' ? Math.sqrt(variance) : variance;
        });
      }
      if (bandMultiplier) {
        const [upper, basis, lower] = bollinger(values.filter(Number.isFinite), length, 1);
        const factors = bandMultiplier(context);
        let index = 0;
        return values.map((value, bar) => {
          if (!Number.isFinite(value)) return null;
          const i = index++;
          const mean = basis[i];
          return Number.isFinite(mean) && mean !== 0 && Number.isFinite(factors[bar])
            ? factors[bar] * (upper[i] - lower[i]) / mean : null;
        });
      }
      if (name === 'mfi') return moneyFlowIndex(context.bars, values, length);
      if (name === 'vwma') return vwma(context.bars, values, length);
      if (name === 'change' || name === 'mom') return pineSeriesFunctions.change(values, length);
      const calculated = pineSeriesFunctions[name](values.filter(Number.isFinite), length);
      let index = 0;
      return values.map(value => Number.isFinite(value) ? calculated[index++] : null);
    };
  }

  function pinePlotOptions(args, horizontal, inputs, variables, colors = new Map()) {
    const options = {};
    const namedColors = { red: '#f23645', green: '#089981', blue: '#2962ff', orange: '#e6a11a',
      purple: '#8757d7', gray: '#787b86', black: '#131722', white: '#ffffff', yellow: '#fdd835' };
    const resolveColor = token => {
      token = token.trim();
      if (colors.has(token)) return colors.get(token);
      const inputColor = inputs.get(token);
      if (inputColor?.type === 'color') return ({bars, overrides}) => {
        const selected = overrides[token];
        const value = typeof selected === 'string' && /^#[0-9a-f]{6}$/i.test(selected) ? selected : inputColor.value;
        return bars.map(() => value);
      };
      if (token === 'na') return 'rgba(0, 0, 0, 0)';
      if (/^#[\da-f]{6}$/i.test(token)) return token;
      if (/^#[\da-f]{8}$/i.test(token)) {
        const [red, green, blue, alpha] = token.slice(1).match(/../g).map(pair => parseInt(pair, 16));
        return 'rgba(' + [red, green, blue, alpha / 255].join(', ') + ')';
      }
      const named = /^color\.([a-z]+)$/.exec(token);
      if (named) return namedColors[named[1]];
      const gradient = /^color\.from_gradient\((.*)\)$/.exec(token);
      if (gradient) {
        const args = pineArguments(gradient[1]);
        if (args.length !== 5 || args.some(arg => !arg)) return;
        const read = args.slice(0, 3).map(arg => pineExpression(arg, inputs, variables));
        const endpoints = args.slice(3).map(resolveColor);
        if (!endpoints.every(Boolean)) return;
        const rgba = color => color.startsWith('#')
          ? [...color.slice(1).match(/../g).map(pair => parseInt(pair, 16)), 1]
          : color.slice(5, -1).split(', ').map(Number);
        return context => {
          const [value, lower, upper] = read.map(evaluate => evaluate(context));
          const colors = endpoints.map(color => typeof color === 'function' ? color(context).map(rgba) : rgba(color));
          return context.bars.map((_, index) => {
            if (![value[index], lower[index], upper[index]].every(Number.isFinite) || upper[index] < lower[index]) {
              return 'rgba(0, 0, 0, 0)';
            }
            const fraction = upper[index] === lower[index] ? Number(value[index] >= upper[index])
              : Math.max(0, Math.min(1, (value[index] - lower[index]) / (upper[index] - lower[index])));
            const [start, end] = colors.map((color, endpoint) =>
              typeof endpoints[endpoint] === 'function' ? color[index] : color);
            const mixed = start.map((channel, i) => {
              const result = channel + (end[i] - channel) * fraction;
              return i === 3 ? result : Math.round(result);
            });
            return 'rgba(' + mixed.join(', ') + ')';
          });
        };
      }
      const rgbCall = /^color\.rgb\((.*)\)$/.exec(token);
      if (rgbCall) {
        const args = pineArguments(rgbCall[1]);
        if (args.length < 3 || args.length > 4 || args.some(arg => !arg)) return;
        const paint = (red, green, blue, transparency = 0) => {
          const channels = [red, green, blue];
          if (![...channels, transparency].every(Number.isFinite)) return 'rgba(0, 0, 0, 0)';
          const rgb = channels.map(value => Math.round(Math.max(0, Math.min(255, value))));
          return 'rgba(' + [...rgb, 1 - Math.max(0, Math.min(100, transparency)) / 100].join(', ') + ')';
        };
        if (args.every(arg => /^\d+(?:\.\d+)?$/.test(arg))) {
          const values = args.map(Number);
          if (values.some((value, index) => value > (index === 3 ? 100 : 255))) return;
          return paint(...values);
        }
        const evaluate = args.map(arg => pineExpression(arg, inputs, variables));
        return context => {
          const components = evaluate.map(read => read(context));
          return context.bars.map((_, index) => paint(...components.map(series => series[index])));
        };
      }
      const transparent = /^color\.new\((.*)\)$/.exec(token);
      if (!transparent) return;
      const args = pineArguments(transparent[1]);
      if (args.length !== 2 || args.some(arg => !arg)) return;
      const base = resolveColor(args[0]);
      if (!base) return;
      if (args[0] === 'na') return base;
      const paint = (color, value) => {
        if (!Number.isFinite(value)) return 'rgba(0, 0, 0, 0)';
        const rgb = color.startsWith('#')
          ? [1, 3, 5].map(i => parseInt(color.slice(i, i + 2), 16))
          : color.slice(5, -1).split(', ').slice(0, 3);
        return 'rgba(' + [...rgb, 1 - Math.min(100, Math.max(0, value)) / 100].join(', ') + ')';
      };
      if (/^\d+(?:\.\d+)?$/.test(args[1])) {
        const literal = Number(args[1]);
        if (literal > 100) return;
        return typeof base === 'function'
          ? context => base(context).map(hex => paint(hex, literal)) : paint(base, literal);
      }
      const evaluate = pineExpression(args[1], inputs, variables);
      return context => {
        const colors = typeof base === 'function' ? base(context) : null;
        return evaluate(context).map((value, index) => paint(colors?.[index] ?? base, value));
      };
    };
    for (const [index, arg] of args.entries()) {
      const title = pineString(arg.replace(/^title\s*=\s*/, ''), 80, 1);
      const color = /^color\s*=\s*(.+)$/.exec(arg)?.[1];
      const style = /^style\s*=\s*plot\.style_(line|linebr|stepline|steplinebr|stepline_diamond|circles|cross|area|areabr|histogram|columns)$/.exec(arg)?.[1];
      const lineStyle = (horizontal
        ? /^linestyle\s*=\s*hline\.style_(solid|dashed|dotted)$/
        : /^linestyle\s*=\s*plot\.linestyle_(solid|dashed|dotted)$/).exec(arg)?.[1];
      const offset = !horizontal && /^offset\s*=\s*([+-]?\s*(?:\d+|[a-zA-Z_]\w*))$/.exec(arg)?.[1];
      const width = /^linewidth\s*=\s*([1-4])$/.exec(arg)?.[1];
      if (title && (index === 0 || arg.startsWith('title')) && !options.label) options.label = title;
      else if (!horizontal && /^precision\s*=\s*(?:[0-9]|1[0-6])$/.test(arg) && options.precision === undefined) {
        options.precision = Number(arg.split('=').at(-1));
      }
      else if (!horizontal && /^format\s*=\s*format\.(inherit|price|percent|volume)$/.test(arg) && options.format === undefined) {
        options.format = arg.split('.').at(-1);
      }
      else if (!horizontal && /^trackprice\s*=/.test(arg) && options.trackPrice === undefined) {
        const token = arg.replace(/^trackprice\s*=\s*/, '').trim();
        const input = inputs.get(token);
        if (token === 'true' || token === 'false') options.trackPrice = token === 'true';
        else if (input?.type === 'bool') options.trackPrice = overrides =>
          typeof overrides?.[token] === 'boolean' ? overrides[token] : input.value;
        else throw new Error('trackprice requires a boolean literal or input.');
      }
      else if (/^editable\s*=\s*(true|false)$/.test(arg) && options.editable === undefined) {
        options.editable = arg.endsWith('true');
      }
      else if (!horizontal && /^force_overlay\s*=\s*(true|false)$/.test(arg) && options.forceOverlay === undefined) {
        options.forceOverlay = arg.endsWith('true');
      }
      else if (!horizontal && /^histbase\s*=/.test(arg) && options.base === undefined) {
        const token = arg.replace(/^histbase\s*=\s*/, '');
        const input = inputs.get(token);
        if (input && (!input.type || input.type === 'float')) {
          options.base = overrides => {
            const value = overrides?.[token];
            return Number.isFinite(value) && (input.type === 'float' || Number.isInteger(value))
              && value >= input.min && value <= input.max ? value : input.value;
          };
        } else if (/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(token) && Number.isFinite(Number(token))) {
          options.base = Number(token);
        } else throw new Error('histbase requires a fixed number or numeric input.');
      }
      else if (color && !options.color && !options.colorSeries) {
        const resolved = resolveColor(color);
        if (typeof resolved === 'string') options.color = resolved;
        else if (resolved) options.colorSeries = resolved;
        else {
          const conditional = !horizontal && /^(.+?)\?\s*(.+?)\s*:\s*(.+)$/.exec(color);
          const yes = conditional && resolveColor(conditional[2]);
          const no = conditional && resolveColor(conditional[3]);
          if (!yes || !no) throw new Error('Use a supported plot color or color.new() with transparency from 0 to 100.');
          const evaluate = pineExpression(conditional[1], inputs, variables);
          options.colorSeries = context => {
            const positive = typeof yes === 'function' ? yes(context) : null;
            const negative = typeof no === 'function' ? no(context) : null;
            return evaluate(context).map((value, i) => value === true
              ? positive?.[i] ?? yes : negative?.[i] ?? no);
          };
        }
      } else if (style && !options.style) options.style = style;
      else if (lineStyle && !options.lineStyle) options.lineStyle = lineStyle;
      else if (!horizontal && /^show_last\s*=/.test(arg) && !options.showLast) {
        const token = arg.split('=')[1].trim();
        const input = inputs.get(token);
        const count = /^\d+$/.test(token) ? Number(token) : NaN;
        if (Number.isSafeInteger(count)) options.showLast = () => count;
        else if (input && !input.type && input.min >= 0) {
          options.showLast = overrides => pineLength(input, overrides);
        } else throw new Error('show_last requires a non-negative integer or integer input.');
      }
      else if (offset && !options.shift) {
        const token = offset.replace(/\s+/g, '');
        if (/^[+-]?\d+$/.test(token) && Math.abs(Number(token)) <= 250) {
          options.shift = () => Number(token);
        } else {
          const id = token.replace(/^[+-]/, '');
          const input = inputs.get(id);
          if (!input || input.type) throw new Error('Plot offset requires an integer from -250 to 250 or an integer input.');
          options.shift = overrides => (token.startsWith('-') ? -1 : 1) * pineLength(input, overrides);
        }
      }
      else if (/^display\s*=/.test(arg) && options.display === undefined) {
        const flags = {none: 0, pane: 1, price_scale: 2, data_window: 4, status_line: 8, all: 15};
        const terms = arg.replace(/^display\s*=\s*/, '').trim().split(/\s*([+-])\s*/);
        const masks = terms.filter((_, index) => index % 2 === 0).map(term => /^display\.(\w+)$/.exec(term)?.[1]);
        if (masks.some(flag => !Object.hasOwn(flags, flag))) throw new Error('Invalid display option.');
        options.display = masks.slice(1).reduce((mask, flag, index) =>
          terms[index * 2 + 1] === '+' ? mask | flags[flag] : mask & ~flags[flag], flags[masks[0]]);
      }
      else if (/^linewidth\s*=/.test(arg) && options.width === undefined) {
        const token = arg.replace(/^linewidth\s*=\s*/, '');
        const input = inputs.get(token);
        if (width) options.width = Number(width);
        else if (input && !input.type && input.value >= 1 && input.value <= 4) {
          options.width = overrides => Math.min(4, Math.max(1, pineLength(input, overrides)));
        } else throw new Error('linewidth requires a value from 1 to 4 or an integer input with a default in that range.');
      }
      else throw new Error('Unsupported or duplicate plot option: ' + arg);
    }
    return options;
  }

  // Parse an entire supported script before adding any plots. No user code runs as JavaScript.
  function compilePine(source) {
    if (typeof source !== 'string') throw new Error('Enter Pine Script source text.');
    const lines = source.split(/\r\n|\n|\r/).flatMap((line, index) => {
      const trimmed = line.trim();
      if (/^\/\/@version=[56]$/.test(trimmed)) return [{ text: trimmed, number: index + 1 }];
      let quote = null;
      let escaped = false;
      for (let i = 0; i < line.length; i++) {
        if (escaped) escaped = false;
        else if (quote && line[i] === '\\') escaped = true;
        else if (line[i] === quote) quote = null;
        else if (!quote && (line[i] === '"' || line[i] === "'")) quote = line[i];
        else if (!quote && line[i] === '/' && line[i + 1] === '/') {
          line = line.slice(0, i);
          break;
        }
      }
      const text = line.trim();
      return text ? [{ text, number: index + 1 }] : [];
    });
    const code = [];
    let pending;
    let depth = 0;
    for (const line of lines) {
      if (!pending) pending = { ...line };
      else pending.text += ' ' + line.text;
      let quote = null;
      let escaped = false;
      for (const char of line.text) {
        if (escaped) escaped = false;
        else if (quote && char === '\\') escaped = true;
        else if (char === quote) quote = null;
        else if (!quote && (char === '"' || char === "'")) quote = char;
        else if (!quote && char === '(') depth++;
        else if (!quote && char === ')') depth--;
        if (depth < 0) throw new Error('Line ' + line.number + ': unexpected closing parenthesis.');
      }
      if (depth === 0) {
        try {
          for (const text of pineArguments(pending.text)) code.push({ text, number: pending.number });
        } catch (error) {
          throw new Error('Line ' + pending.number + ': ' + error.message);
        }
        pending = undefined;
      }
    }
    if (pending) throw new Error('Line ' + pending.number + ': unclosed parenthesis.');
    const version = code.shift();
    if (!/^\/\/@version=[56]$/.test(version?.text || '')) {
      throw new Error('Line ' + (version?.number ?? 1) + ': start with //@version=5 or //@version=6.');
    }
    const header = code.shift();
    const declaration = /^indicator\((.*)\)$/.exec(header?.text || '');
    if (!declaration) {
      const line = header?.number ?? version.number + 1;
      const kind = /^(strategy|library)\s*\(/.exec(header?.text ?? '')?.[1];
      if (kind) {
        throw new Error('Line ' + line + ': ' + kind + '() execution requires TradingView. Sector Pulse currently runs supported indicator() scripts.');
      }
      throw new Error('Line ' + line + ': add an indicator() declaration.');
    }
    const config = {};
    for (const [index, arg] of pineArguments(declaration[1]).entries()) {
      const named = /^(title|shorttitle|overlay|format|precision|behind_chart)\s*=\s*(.+)$/.exec(arg);
      const key = named?.[1] ?? ['title', 'shorttitle', 'overlay'][index];
      const token = named?.[2] ?? arg;
      const value = key === 'overlay' || key === 'behind_chart' ? /^(true|false)$/.exec(token)?.[1]
        : key === 'precision' ? /^(?:[0-9]|1[0-6])$/.exec(token)?.[0]
        : key === 'format' ? /^format\.(inherit|price|percent|volume)$/.exec(token)?.[1]
          : pineString(token, 80, 1);
      if (!key || value === undefined || Object.hasOwn(config, key)) {
        const body = code.map(statement => statement.text).join('\n');
        const requirements = [
          [/\brequest\.security(?:_lower_tf)?\s*\(/, 'multi-timeframe requests'],
          [/^\s*type\s+\w+|(?:^|[^\w])array[.<]/m, 'arrays and custom types'],
          [/\b(?:line|box|label)\.new\s*\(/, 'drawing objects'],
          [/\btable\.new\s*\(/, 'tables']
        ].filter(([pattern]) => pattern.test(body)).map(([, feature]) => feature);
        const detail = requirements.length
          ? ' This script also requires Pine features beyond the current Sector Pulse runtime: ' + requirements.join(', ') + '.'
          : '';
        throw new Error('Line ' + header.number + ': invalid or unsupported indicator() argument: ' + arg + '.' + detail);
      }
      config[key] = value;
    }
    if (!config.title) throw new Error('Line ' + header.number + ': indicator() needs a title.');
    const inputs = new Map();
    const plots = [];
    const backgrounds = [];
    const barColors = [];
    const variables = new Map();
    const colors = new Map();
    for (const { text: statement, number } of code) {
      let text = statement;
      const inputCall = /^((?:(?:string|color|bool|float|int)\s+)?([a-zA-Z_]\w*)\s*=\s*input\.(?:string|timeframe|color|bool|float|int|source)\()(.*)\)$/.exec(text);
      const inputMetadata = {};
      if (inputCall) {
        const args = pineArguments(inputCall[3]).filter(arg => {
          const numeric = /input\.(int|float)\($/.exec(inputCall[1])?.[1];
          const choices = numeric && /^options\s*=\s*\[(.*)\]$/.exec(arg);
          if (choices) {
            const tokens = pineArguments(choices[1]);
            const options = tokens.map(Number);
            if (inputMetadata.options || options.length > 30 || !options.length
                || tokens.some(token => !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(token))
                || options.some(value => !Number.isFinite(value) || (numeric === 'int' && (!Number.isInteger(value) || Math.abs(value) > 250)))
                || new Set(options).size !== options.length) {
              throw new Error('Line ' + number + ': invalid numeric input options.');
            }
            inputMetadata.options = options;
            return false;
          }
          const display = /^display\s*=\s*(.*)$/.exec(arg);
          const statusLine = display && pineInputStatusLine(display[1]);
          if (typeof statusLine === 'boolean') {
            inputMetadata.statusLine = statusLine;
            return false;
          }
          const active = /^active\s*=\s*(\w+)$/.exec(arg);
          if (active) {
            const token = active[1];
            const control = inputs.get(token);
            if (Object.hasOwn(inputMetadata, 'active') || (!['true', 'false'].includes(token) && control?.type !== 'bool')) {
              throw new Error('Line ' + number + ': active requires a boolean literal or earlier boolean input.');
            }
            inputMetadata.active = control ? {id: token, value: control.value} : token === 'true';
            return false;
          }
          const field = /^(tooltip|group|inline)\s*=\s*(.*)$/.exec(arg);
          if (!field) return true;
          const [, key, token] = field;
          const value = pineString(token, 300);
          if (value === undefined || Object.hasOwn(inputMetadata, key)) {
            throw new Error('Line ' + number + ': ' + key + ' requires a string literal.');
          }
          inputMetadata[key] = value;
          return false;
        });
        text = inputCall[1] + args.join(', ') + ')';
      }
      const declaredColor = /^color\s+([a-zA-Z_]\w*)\s*=\s*(.*)$/.exec(text);
      if (declaredColor && !declaredColor[2].startsWith('input.color(')) {
        const [, id, expression] = declaredColor;
        if (colors.size >= 24 || colors.has(id) || variables.has(id) || inputs.has(id) || reservedPineName(id)) {
          throw new Error('Line ' + number + ': use a unique color name.');
        }
        const {color, colorSeries} = pinePlotOptions(['color=' + expression], false, inputs, variables, colors);
        colors.set(id, color ?? colorSeries);
        continue;
      }
      const stringInput = /^(?:string\s+)?([a-zA-Z_]\w*)\s*=\s*input\.(string|timeframe)\((.*)\)$/.exec(text);
      if (stringInput) {
        const [, id, kind, raw] = stringInput;
        const args = pineArguments(raw);
        const read = token => pineString(token, 80);
        const value = read(args.shift()?.replace(/^defval\s*=\s*/, ''));
        const title = read(args[0]?.replace(/^title\s*=\s*/, ''));
        if (title !== undefined) args.shift();
        const list = /^options\s*=\s*\[(.*)\]$/.exec(args[0] ?? '');
        const options = list ? pineArguments(list[1]).map(read) : undefined;
        if (inputs.size >= 12 || inputs.has(id) || variables.has(id) || colors.has(id) || reservedPineName(id)
            || value === undefined || args.length > 1 || (args.length === 1 && !list)
            || (options && (options.length > 30 || options.includes(undefined)
              || new Set(options).size !== options.length || !options.includes(value)))) {
          throw new Error('Line ' + number + ': input.string() requires a unique name, a string default, and valid options if supplied.');
        }
        if (kind === 'timeframe' && [value, ...options ?? []].some(item => !/^(?:[1-9]\d{0,3}[DWM]?|[DWM])?$/.test(item))) {
          throw new Error('Line ' + number + ': use a supported timeframe such as 60, 1D, 1W, or 1M.');
        }
        inputs.set(id, {id, type: 'string', title: title || id, ...inputMetadata, value, options});
        continue;
      }
      const colorInput = /^(?:color\s+)?([a-zA-Z_]\w*)\s*=\s*input\.color\(\s*(?:defval\s*=\s*)?(#[0-9a-f]{6}|color\.[a-z]+)\s*(?:,\s*(?:title\s*=\s*)?"([^"\\]{1,80})")?\s*\)$/i.exec(text);
      if (colorInput) {
        const [, id, token, title] = colorInput;
        if (inputs.size >= 12 || inputs.has(id) || variables.has(id) || colors.has(id) || reservedPineName(id)) {
          throw new Error('Line ' + number + ': use a unique input name.');
        }
        const {color: value} = pinePlotOptions(['color=' + token], true, inputs, variables);
        inputs.set(id, {id, type: 'color', title: title || id, ...inputMetadata, value});
        continue;
      }
      if (inputMetadata.options) {
        const choice = /^.*?input\.(?:int|float)\((.*)\)$/.exec(text);
        const args = pineArguments(choice[1]);
        const value = Number(args[0]?.replace(/^defval\s*=\s*/, ''));
        if (!inputMetadata.options.includes(value) || args.slice(1).some(arg => /^(minval|maxval|step)\s*=/.test(arg))) {
          throw new Error('Line ' + number + ': numeric options must contain the default and cannot be combined with bounds or step.');
        }
      }
      const decimal = /^(?:float\s+)?([a-zA-Z_]\w*)\s*=\s*input\.float\((.*)\)$/.exec(text);
      if (decimal) {
        const [, id, raw] = decimal;
        const args = pineArguments(raw);
        const literal = /^[-+]?(?:\d+(?:\.\d*)?|\.\d+)$/;
        const numberArg = value => literal.test(value) ? Number(value) : NaN;
        const value = numberArg(args.shift()?.replace(/^defval\s*=\s*/, ''));
        const title = /^"(.*?)"$/.exec(args[0]?.replace(/^title\s*=\s*/, ''))?.[1];
        if (title !== undefined) args.shift();
        const bounds = {minval: -Infinity, maxval: Infinity, step: 'any'};
        const seen = new Set();
        for (const arg of args) {
          const match = /^(minval|maxval|step)\s*=\s*(.+)$/.exec(arg);
          if (!match || seen.has(match[1]) || !Number.isFinite(numberArg(match[2]))) {
            throw new Error('Line ' + number + ': invalid input.float() argument.');
          }
          seen.add(match[1]);
          bounds[match[1]] = numberArg(match[2]);
        }
        const {minval: min, maxval: max, step} = bounds;
        if (inputs.size >= 12 || inputs.has(id) || variables.has(id) || colors.has(id) || reservedPineName(id)
            || !Number.isFinite(value) || value < min || value > max || (step !== 'any' && step <= 0)) {
          throw new Error('Line ' + number + ': invalid input.float() default or bounds.');
        }
        inputs.set(id, {id, type: 'float', title: title || id, ...inputMetadata, value, min, max, step});
        continue;
      }
      const boolean = /^(?:bool\s+)?([a-zA-Z_]\w*)\s*=\s*input\.bool\(\s*(?:defval\s*=\s*)?(true|false)\s*(?:,\s*(?:title\s*=\s*)?"([^"\\]{1,80})")?\s*\)$/.exec(text);
      if (boolean) {
        const [, id, value, title] = boolean;
        if (inputs.size >= 12 || inputs.has(id) || variables.has(id) || colors.has(id) || reservedPineName(id)) {
          throw new Error('Line ' + number + ': use a unique input name.');
        }
        inputs.set(id, { id, type: 'bool', title: title || id, ...inputMetadata, value: value === 'true' });
        continue;
      }
      const sourceDeclaration = /^(?:float\s+)?([a-zA-Z_]\w*)\s*=\s*input\.source\(\s*(?:defval\s*=\s*)?(\w+)\s*(?:,\s*(?:title\s*=\s*)?"([^"\\]{1,80})")?\s*\)$/.exec(text);
      if (sourceDeclaration) {
        const [, id, value, title] = sourceDeclaration;
        if (inputs.size >= 12 || inputs.has(id) || variables.has(id) || colors.has(id) || reservedPineName(id) || !Object.hasOwn(pineSources, value)) {
          throw new Error('Line ' + number + ': use a unique input name and a built-in price or volume source.');
        }
        inputs.set(id, { id, type: 'source', title: title || id, ...inputMetadata, value, options: Object.keys(pineSources) });
        continue;
      }
      const declaration = /^(?:int\s+)?([a-zA-Z_]\w*)\s*=\s*input\.int\(\s*([+-]?\d+)\s*(?:,\s*(?:title\s*=\s*)?"([^"\\]{1,80})")?\s*(?:,\s*minval\s*=\s*([+-]?\d+)\s*)?(?:,\s*maxval\s*=\s*([+-]?\d+)\s*)?\)$/.exec(text);
      if (declaration) {
        const [, id, raw, title, minText, maxText] = declaration;
        const value = Number(raw), min = Number(minText ?? Math.min(1, value)), max = Number(maxText ?? 250);
        if (inputs.size >= 12 || inputs.has(id) || variables.has(id) || colors.has(id) || reservedPineName(id) || min < -250 || max > 250 || min > value || value > max) {
          throw new Error('Line ' + number + ': input names must be unique and bounds must contain the default within −250 to 250.');
        }
        inputs.set(id, { id, title: title || id, ...inputMetadata, value, min: inputMetadata.options ? Math.min(...inputMetadata.options) : min, max: inputMetadata.options ? Math.max(...inputMetadata.options) : max });
        continue;
      }
      try {
        const tuple = /^\[\s*(\w+)\s*,\s*(\w+)(?:\s*,\s*(\w+))?\s*\]\s*=\s*ta\.(bb|macd|kc|supertrend|dmi|vwap)\((.*)\)$/.exec(text);
        if (tuple) {
          const names = tuple.slice(1, 4).filter(Boolean);
          const functionName = tuple[4];
          if (names.length !== (functionName === 'supertrend' ? 2 : 3)) {
            throw new Error('Incorrect number of output series for ta.' + functionName + '().');
          }
          const named = names.filter(id => id !== '_');
          if (variables.size + named.length > 24 || new Set(named).size !== named.length
              || named.some(id => !/^[a-zA-Z_]\w*$/.test(id) || variables.has(id) || inputs.has(id) || colors.has(id) || reservedPineName(id))) {
            throw new Error('Use up to 24 uniquely named series.');
          }
          const raw = tuple[5];
          const args = pineArguments(raw);
          if (['kc', 'supertrend', 'dmi', 'vwap'].includes(functionName)) {
            const parse = arg => pineExpression(arg, inputs, variables);
            let calculate;
            if (functionName === 'kc') {
              calculate = pineKeltner(args, parse);
            } else if (functionName === 'vwap') {
              calculate = pineVwap(args, parse, true);
            } else if (functionName === 'dmi') {
              const parameterNames = ['diLength', 'adxSmoothing'];
              const ordered = [];
              for (const arg of args) {
                const assignment = /^(\w+)\s*=\s*(.*)$/.exec(arg);
                const index = assignment ? parameterNames.indexOf(assignment[1]) : ordered.length;
                if (index < 0 || index >= parameterNames.length || Object.hasOwn(ordered, index)) {
                  throw new Error('Invalid or duplicate argument for ta.dmi().');
                }
                ordered[index] = assignment ? assignment[2] : arg;
              }
              if (!parameterNames.every((_, index) => {
                const arg = ordered[index];
                return /^\d+$/.test(arg ?? '') || (inputs.has(arg) && !inputs.get(arg).type);
              })) throw new Error('ta.dmi() requires DI length and ADX smoothing as integer literals or inputs.');
              const periods = ordered.map(parse);
              calculate = context => {
                if (!context.bars.length) return [[], [], []];
                const lengths = periods.map(period => period(context)[0]);
                if (!lengths.every(value => Number.isInteger(value) && value >= 1 && value <= 250)) {
                  throw new Error('ta.dmi() lengths must be between 1 and 250.');
                }
                return directionalMovement(context.bars, ...lengths);
              };
            } else {
              if (args.some(arg => /^\w+\s*=(?!=)/.test(arg))) {
                const parameters = ['factor', 'atrPeriod'];
                const ordered = [];
                let named = false;
                for (const arg of args) {
                  const assignment = /^(\w+)\s*=(?!=)\s*(.*)$/.exec(arg);
                  if (assignment) named = true;
                  const index = assignment ? parameters.indexOf(assignment[1]) : named ? -1 : ordered.length;
                  if (index < 0 || index >= parameters.length || Object.hasOwn(ordered, index)) {
                    throw new Error('Invalid or duplicate argument for ta.supertrend().');
                  }
                  ordered[index] = assignment ? assignment[2] : arg;
                }
                args.splice(0, args.length, ...ordered);
              }
              if (args.length !== 2 || args.some(arg => !arg)) {
                throw new Error('ta.supertrend() requires factor and ATR period.');
              }
              const [factor, period] = args.map(parse);
              calculate = context => {
                if (!context.bars.length) return [[], []];
                const multipliers = factor(context), length = period(context)[0];
                if (!Number.isInteger(length) || length < 1 || length > 250) {
                  throw new Error('Supertrend requires an ATR period from 1 to 250.');
                }
                return supertrend(context.bars, length, multipliers, true);
              };
            }
            const cache = new WeakMap();
            names.forEach((id, index) => {
              if (id === '_') return;
              variables.set(id, context => {
                if (!cache.has(context)) cache.set(context, calculate(context));
                return cache.get(context)[index];
              });
            });
            continue;
          }
          if (args.length !== (functionName === 'macd' ? 4 : 3) || args.some(arg => !arg)) {
            throw new Error('Incorrect argument count for ta.' + functionName + '().');
          }
          const source = pineExpression(args.shift(), inputs, variables);
          if (functionName === 'macd' && args.some(arg => !/^\d+$/.test(arg)
              && (!inputs.has(arg) || inputs.get(arg).type))) {
            throw new Error('MACD lengths require integer literals or inputs.');
          }
          const parameters = args.map(arg => pineExpression(arg, inputs, variables));
          const cache = new WeakMap();
          const evaluate = context => {
            if (cache.has(context)) return cache.get(context);
            if (functionName === 'macd') {
              const periods = parameters.map(parameter => parameter({...context, bars: [{}]})[0]);
              if (!periods.every(period => Number.isInteger(period) && period >= 1 && period <= 250)) {
                throw new Error('MACD lengths must be fixed integers from 1 to 250.');
              }
              const values = source(context);
              const result = macd(values.filter(Number.isFinite), ...periods).map(line => {
                let index = 0;
                return values.map(value => Number.isFinite(value) ? line[index++] : null);
              });
              cache.set(context, result);
              return result;
            }
            const [length, multiplier] = parameters;
            const values = source(context), lengths = length(context), factors = multiplier(context);
            const windows = new Map();
            let index = -1;
            const compact = values.filter(Number.isFinite);
            const result = [[], [], []];
            values.forEach((value, bar) => {
              if (Number.isFinite(value)) index++;
              const period = lengths[bar], factor = factors[bar];
              let basis = null, distance = null;
              if (Number.isFinite(value) && Number.isInteger(period) && period >= 1 && period <= 250
                  && Number.isFinite(factor)) {
                if (!windows.has(period)) windows.set(period, bollinger(compact, period, 1));
                const [upper, mean] = windows.get(period);
                basis = mean[index];
                if (Number.isFinite(basis)) distance = (upper[index] - basis) * factor;
              }
              result[0].push(basis);
              result[1].push(distance === null ? null : basis + distance);
              result[2].push(distance === null ? null : basis - distance);
            });
            cache.set(context, result);
            return result;
          };
          names.forEach((id, index) => {
            if (id !== '_') variables.set(id, context => evaluate(context)[index]);
          });
          continue;
        }
        const assignment = /^(?:(?:float|bool)\s+)?([a-zA-Z_]\w*)\s*=\s*(.+)$/.exec(text);
        if (assignment) {
          const [, id, expression] = assignment;
          if (variables.size >= 24 || variables.has(id) || inputs.has(id) || colors.has(id) || reservedPineName(id)) {
            throw new Error('Use up to 24 uniquely named series.');
          }
          try {
            if (colors.has(expression) || inputs.get(expression)?.type === 'color') {
              const {color, colorSeries} = pinePlotOptions(['color=' + expression], false, inputs, variables, colors);
              colors.set(id, color ?? colorSeries);
              continue;
            }
            variables.set(id, pineExpression(expression, inputs, variables));
          } catch (error) {
            if (!/(?:\bcolor\.|#[\da-f]{6})/i.test(expression)
                && ![...colors.keys(), ...[...inputs.values()].filter(input => input.type === 'color').map(input => input.id)]
                  .some(name => new RegExp('\\b' + name + '\\b').test(expression))) throw error;
            if (colors.size >= 24) throw new Error('Use up to 24 uniquely named colors.');
            const {color, colorSeries} = pinePlotOptions(['color=' + expression], false, inputs, variables, colors);
            colors.set(id, color ?? colorSeries);
          }
          continue;
        }
        const background = /^(bgcolor|barcolor)\((.*)\)$/.exec(text);
        if (background) {
          const [, name, raw] = background;
          const styles = name === 'bgcolor' ? backgrounds : barColors;
          const args = pineArguments(raw);
          const color = args.shift()?.replace(/^color\s*=\s*/, '');
          if (!color || styles.length >= 8 || args.some(arg =>
            !/^(?:title|show_last)\s*=/.test(arg) && !(name === 'bgcolor' && /^force_overlay\s*=/.test(arg)))) {
            throw new Error('Invalid argument for ' + name + '().');
          }
          styles.push(pinePlotOptions(['color=' + color, ...args], false, inputs, variables, colors));
          continue;
        }
        const plot = /^(plot|hline)\((.*)\)$/.exec(text);
        if (!plot) throw new Error('Use an input, a series assignment, plot(), or hline().');
        const args = pineArguments(plot[2]);
        const horizontal = plot[1] === 'hline';
        const valueName = horizontal ? 'price' : 'series';
        const namedValue = new RegExp('^' + valueName + '\\s*=(?!=)\\s*');
        const valueIndex = args.findIndex(arg => namedValue.test(arg));
        if (valueIndex >= 0) {
          const [value] = args.splice(valueIndex, 1);
          args.unshift(value.replace(namedValue, ''));
        }
        if (!horizontal && !args[0]) throw new Error('plot() needs a series.');
        if (horizontal) {
          const input = inputs.get(args[0]);
          if (!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(args[0]) && (!input || !Number.isFinite(input.value))) {
            throw new Error('hline() needs a fixed number or numeric input.');
          }
        }
        plots.push({ evaluate: pineExpression(args[0], inputs, variables),
          ...(horizontal && {lineStyle: 'solid'}), ...pinePlotOptions(args.slice(1), horizontal, inputs, variables, colors) });
      } catch (error) {
        throw new Error('Line ' + number + ': ' + error.message);
      }
    }
    if ((!plots.length && !backgrounds.length && !barColors.length) || plots.length > 8) throw new Error('Add a plot(), hline(), bgcolor(), or barcolor() statement.');
    return {
      name: config.title, shortTitle: config.shorttitle, format: config.format, precision: config.precision === undefined ? undefined : Number(config.precision), pane: config.overlay !== 'true',
      behindPrice: config.overlay === 'true' && config.behind_chart !== 'false',
      plotNames: plots.map((plot, index) => plot.label || (config.shorttitle ?? config.title) + (plots.length > 1 ? ' · ' + (index + 1) : '')),
      plotOptions: plots.map(({ color, style, width, lineStyle, display, base, forceOverlay, trackPrice, format, precision, editable }) => ({ color, style, width, lineStyle, display, base, forceOverlay, trackPrice, format, precision, editable })),
      inputs: [...inputs.values()],
      backgrounds: backgrounds.map(({forceOverlay}) => ({forceOverlay})),
      colorsBars: barColors.length > 0,
      run(bars, prices, lengthOverride, multiplier, overrides = {}, symbolInfo = {}) {
        const context = { bars, overrides, symbolInfo, series: new Map() };
        for (const [name, evaluate] of variables) context.series.set(name, evaluate(context));
        const output = plots.map(plot => {
          const values = plot.evaluate(context);
          const offset = plot.shift?.(overrides) ?? 0;
          const count = plot.showLast?.(overrides);
          const colors = plot.colorSeries?.(context);
          const output = bars.map((_, index) => {
            const sourceIndex = index - offset;
            if (count !== undefined && sourceIndex < bars.length - count) return null;
            const value = values[sourceIndex];
            return Number.isFinite(value) ? value : null;
          });
          if (colors) output.colors = bars.map((_, index) => colors[index - offset]);
          return output;
        });
        const evaluateColors = styles => styles.map(style => {
          const colors = style.colorSeries?.(context);
          const count = style.showLast?.(overrides);
          return bars.map((_, i) => count !== undefined && i < bars.length - count ? null : colors?.[i] ?? style.color);
        });
        if (backgrounds.length) output.backgrounds = evaluateColors(backgrounds);
        if (barColors.length) output.barColors = evaluateColors(barColors);
        return output;
      }
    };
  }

  function mergeLiveCandles(base, previous, updates) {
    const boundary = base.at(-1)?.time ?? 0;
    const provisional = new Map();
    for (const bar of previous) {
      if (bar.provisional && bar.time > boundary) provisional.set(bar.time, bar);
    }
    for (const [time, open, high, low, close, volume] of updates) {
      if (time > boundary) provisional.set(time, { time, open, high, low, close, volume, provisional: true });
    }
    return [...base, ...[...provisional.values()].sort((a, b) => a.time - b.time).slice(-750)];
  }

  function chartCsv(bars, series) {
    const used = new Set(['source_time_utc', 'brick_index','open','high','low','close','volume','provisional','history_only']);
    const columns = [...used];
    for (const {label} of series) {
      const safe = /^\s*[=+@-]|^[\t\r\n]/.test(label) ? "'" + label : label;
      let name = safe;
      for (let n = 2; used.has(name); n++) name = safe + ' (' + n + ')';
      used.add(name);
      columns.push(name);
    }
    const records = [columns.map(name => '"' + name.replace(/"/g, '""') + '"').join(',')];
    bars.forEach((bar, i) => {
      const synthetic = bar.sourceTime !== undefined;
      const time = new Date((bar.sourceTime ?? bar.time) * 1000).toISOString();
      const values = [synthetic ? bar.time : null, bar.open, bar.high, bar.low, bar.close,
        synthetic && bar.renkoVolume !== true ? null : bar.volume, bar.provisional ? 1 : 0, bar.provisional && bar.historyOnly ? 1 : 0, ...series.map(plot => plot.points[i])];
      records.push(time + ',' + values.map(value => Number.isFinite(value) ? String(value) : '').join(','));
    });
    return records.join('\r\n') + '\r\n';
  }

  root.SectorPulseChartStudies = { fixedRangeVolumeProfile, aggregatePivotCandles, standardPivotLevels, standardPivotPeriods, indicators, tradeDeltaPlots, shiftStudyPlots, renko, withRenkoVolume, renkoAtrSize, compilePine, pineNamedInputStatusLines, v1ReferenceRanges, shadowRanges, shadowRatios, previousShadowPeriods, shadowOscillators, shadowRangeHistory, chartCsv, mergeLiveCandles, v1TargetPrices, v1TargetStates, v1ExtraZones };
})(typeof window === 'undefined' ? globalThis : window);

/* Renko calculation-timeframe engine: 20261120-1 */
/* Analytical Renko study alignment. Not connected to chart controls yet. */
(function(root) {
  'use strict';
  function renkoStudyClock(bars) {
    let previousSource=-Infinity, previousClock=-Infinity, duplicate=0, provisional=false;
    return bars.map(bar=>{
      const source=bar.sourceTime;
      if(!Number.isFinite(source)||source<previousSource) throw new RangeError('Renko source times must be ordered and finite');
      if(provisional&&!bar.provisional) throw new RangeError('Confirmed Renko bars must precede projections');
      provisional=provisional||!!bar.provisional;
      duplicate=source===previousSource?duplicate+1:0;
      previousSource=source;
      const clock=source+duplicate/1000;
      if(clock<=previousClock)throw new RangeError('Renko synthetic times collide');
      previousClock=clock;
      return clock;
    });
  }
  function alignRenkoStudyPlots(plots,reference,host,options={}) {
    if(plots.some(plot=>plot.length!==reference.length)) throw new RangeError('Renko study plot length differs from reference');
    const sourceClock=renkoStudyClock(reference),hostClock=renkoStudyClock(host);
    const output=plots.map(plot=>{const values=[];if(Array.isArray(plot.colors))values.colors=[];return values;});
    let latest=-1;
    for(let i=0;i<host.length;i++) {
      const closed=i+1<host.length&&!host[i].provisional&&!host[i+1].provisional?hostClock[i+1]:null;
      let selected=-1;
      if(closed!==null) {
        while(latest+1<reference.length-1&&!reference[latest+1].provisional&&!reference[latest+2].provisional&&sourceClock[latest+2]<=closed) {
          latest++;
          if(sourceClock[latest+1]>hostClock[i])selected=latest;
        }
      }
      if(options.gaps===false)selected=latest;
      plots.forEach((plot,p)=>{
        output[p].push(selected<0?null:plot[selected]??null);
        if(output[p].colors)output[p].colors.push(selected<0?undefined:plot.colors[selected]);
      });
    }
    return output;
  }
  function applyConfirmedRenkoStudyTail(aligned,plots,reference,host,options={}) {
    const {live,confirmedThrough,now,updatedAt}=options;
    if(live!==true||!host.length||host.at(-1).historyOnly
        ||![confirmedThrough,now,updatedAt].every(Number.isFinite)
        ||confirmedThrough>now||updatedAt>now+2||now-updatedAt>=60) return aligned;
    if(plots.length!==aligned.length||plots.some(p=>p.length!==reference.length)
        ||aligned.some(p=>p.length!==host.length))throw new RangeError('Renko tail plot shape differs from history');
    let latest=-1;
    reference.forEach((bar,index)=>{
      if(!bar.provisional&&!bar.historyOnly&&Number.isFinite(bar.sourceTime)&&bar.sourceTime<confirmedThrough)latest=index;
    });
    if(latest<0)return aligned;
    return aligned.map((plot,index)=>{
      const copy=plot.slice();
      copy[copy.length-1]=plots[index][latest]??null;
      if(Array.isArray(plot.colors)||Array.isArray(plots[index].colors)){
        copy.colors=plot.colors?plot.colors.slice():Array(plot.length).fill(undefined);
        copy.colors[copy.length-1]=plots[index].colors?.[latest];
      }
      return copy;
    });
  }
  const publicationStates=new WeakMap();
  function renkoStudyPublication(study,scope,key) {
    if(!study||typeof study!=='object'||!scope||scope.aborted)return undefined;
    let state=publicationStates.get(study);
    if(!state||state.scope!==scope||state.key!==key){
      state={scope,key};publicationStates.set(study,state);
    }
    return state;
  }

  function applyRenkoStudyPublication(aligned,plots,reference,host,options={},state) {
    if(!state||options.live!==true||!host.length)return applyConfirmedRenkoStudyTail(aligned,plots,reference,host,options);
    const clock=renkoStudyClock(host),known=new Set(clock);
    if(!(state.rows instanceof Map)||!known.has(state.lastClock))state.rows=new Map();
    const out=aligned.map(plot=>{
      const copy=plot.slice();if(Array.isArray(plot.colors))copy.colors=plot.colors.slice();return copy;
    });
    for(let i=0;i<clock.length;i++){
      const saved=state.rows.get(clock[i]);
      if(!saved)continue;
      out.forEach((plot,p)=>{
        plot[i]=saved.values[p]??null;
        if(saved.colors){plot.colors??=Array(host.length).fill(undefined);plot.colors[i]=saved.colors[p];}
      });
    }
    const tail=applyConfirmedRenkoStudyTail(aligned,plots,reference,host,options);
    if(tail!==aligned){
      const start=clock.indexOf(state.lastClock);
      for(let i=start<0?host.length-1:start;i<host.length;i++){
        const values=tail.map(plot=>plot.at(-1));
        const colors=tail.some(plot=>Array.isArray(plot.colors))?tail.map(plot=>plot.colors?.at(-1)):undefined;
        state.rows.set(clock[i],{values,colors});
        out.forEach((plot,p)=>{
          plot[i]=values[p]??null;
          if(colors){plot.colors??=Array(host.length).fill(undefined);plot.colors[i]=colors[p];}
        });
      }
      state.lastClock=clock.at(-1);
    }
    for(const key of state.rows.keys())if(!known.has(key))state.rows.delete(key);
    return out;
  }

  // Display-only Close-source projections. Never feed these into confirmed studies.
  function closeRenkoProjection(previous,price,size,sourceTime,options={}) {
    if(!previous||![previous.open,previous.close,price,size,sourceTime].every(Number.isFinite)||size<=0)
      throw new TypeError('Invalid Renko projection input');
    const direction=Math.sign(previous.close-previous.open);
    if(!direction||Math.abs(Math.abs(previous.close-previous.open)-size)>size*1e-8)
      throw new RangeError('Projection requires a confirmed full brick');
    const delta=price-previous.close,step=Math.sign(delta),reversal=step!==direction;
    if(!step)return [];
    let open=previous.close+(reversal?step*size:0);
    if(step*(price-open)<=size*1e-10){
      // Before a reversal's first gap, show the actual unfinished movement from
      // the committed close. This is a translucent price tail, not a full brick.
      return options.showReversalRemainder===true&&Math.abs(delta)>size*1e-10
        ?[{sourceTime,provisional:true,reversalPending:true,open:previous.close,
          high:Math.max(previous.close,price),low:Math.min(previous.close,price),close:price}]:[];
    }
    const count=Math.ceil(Math.abs(price-open)/size-1e-10);
    if(count>1000)throw new RangeError('Increase the projection brick size');
    const result=[];
    for(let i=0;i<count;i++) {
      const close=i===count-1?price:open+step*size;
      result.push({sourceTime,provisional:true,open,high:Math.max(open,close),low:Math.min(open,close),close});
      open=close;
    }
    return result;
  }
  // A separate display series keeps forming prices out of confirmed strategy inputs.
  function mountCompletedRenkoProjection({chart,getBars,size,enabled=()=>true,priceScaleId,priceFormat}) {
    const series=chart.addCandlestickSeries({priceScaleId,priceFormat,
      upColor:'rgba(8,153,129,0.28)',downColor:'rgba(242,54,69,0.28)',
      borderUpColor:'#089981',borderDownColor:'#f23645',wickVisible:false,
      priceLineVisible:false,lastValueVisible:false,title:''});
    let lastPrice,lastTime,signature='',points=[];
    function update(price,sourceTime) {
      lastPrice=price;lastTime=sourceTime;
      const previous=getBars().at(-1);
      const next=enabled()&&previous&&Number.isFinite(price)&&Number.isFinite(sourceTime)
        ?closeRenkoProjection(previous,price,size,Math.max(sourceTime,previous.sourceTime??sourceTime),{showReversalRemainder:true})
          .map((bar,index)=>({...bar,time:previous.time+index+1})):[];
      const key=JSON.stringify(next);
      if(key===signature)return;
      if(next.length===points.length&&next.length&&next.every((bar,index)=>bar.time===points[index].time
          &&(index===next.length-1||JSON.stringify(bar)===JSON.stringify(points[index]))))series.update(next.at(-1));
      else series.setData(next);
      signature=key;points=next;
    }
    return {update,refresh:()=>update(lastPrice,lastTime)};
  }
  function calculateRenkoTimeframeStudy(options) {
    const {sourceBars,hostBars,renko,run,size,previousBrick,liveState}=options;
    if(!Array.isArray(sourceBars)||!Array.isArray(hostBars)||typeof renko!=='function'||typeof run!=='function'
        ||!Number.isFinite(size)||size<=0)throw new TypeError('Invalid Renko timeframe calculation');
    const confirmed=sourceBars.filter(bar=>!bar.provisional&&!bar.historyOnly);
    const reference=renko(confirmed,size,previousBrick,options.source??'close',options.showWicks===true);
    const sourcePlots=run(reference);
    const aligned=alignRenkoStudyPlots(sourcePlots,reference,hostBars,{gaps:options.waitForClose!==false});
    const plots=applyRenkoStudyPublication(aligned,sourcePlots,reference,hostBars,liveState,options.publication);
    return {reference,plots,size,projectionAvailable:false};
  }
  root.SectorPulseRenkoStudyAlignment={renkoStudyClock,alignRenkoStudyPlots,applyConfirmedRenkoStudyTail,calculateRenkoTimeframeStudy,closeRenkoProjection,mountCompletedRenkoProjection,applyRenkoStudyPublication,renkoStudyPublication};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.SectorPulseRenkoStudyAlignment;
})(typeof window==='undefined'?globalThis:window);

/* Percentage-LTP native sizing: 20261120-1 */
/* Percentage-LTP sizing inferred from captured native series.
 * Captured BTCUSD/PAXGUSD/ETHUSD cases establish selected sizes, not universal parity.
 */
(function(root){
 'use strict';
 function renkoPercentageSize(price,percentage,tick){
  if(![price,percentage,tick].every(n=>Number.isFinite(n)&&n>0))throw new TypeError('Positive finite price, percentage and tick are required');
  const raw=price*percentage/100;
  if(!Number.isFinite(raw)||raw<=0)throw new RangeError('Percentage size is outside the supported numeric range');
  const tickExponent=Math.floor(Math.log10(tick)+1e-12);
  const mantissa=tick/Math.pow(10,tickExponent);
  const quantum=.5*Math.pow(10,Math.ceil(Math.log10(mantissa)-1e-12)+Math.floor(Math.log10(raw/mantissa)+1e-12));
  if(!Number.isFinite(quantum)||quantum<=0)throw new RangeError('Percentage rounding quantum is outside the supported numeric range');
  const rounded=Math.round(raw/quantum)*quantum;
  const units=rounded/tick;
  if(!Number.isFinite(units)||units>Number.MAX_SAFE_INTEGER)throw new RangeError('Percentage size has too many broker ticks');
  return Math.max(1,Math.round(units+Math.abs(units)*Number.EPSILON*2))*tick;
 }
 root.SectorPulseRenkoSizing={renkoPercentageSize};
 if(typeof module!=='undefined'&&module.exports)module.exports=root.SectorPulseRenkoSizing;
})(typeof window==='undefined'?globalThis:window);

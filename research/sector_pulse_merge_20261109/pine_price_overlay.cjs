function attachPinePriceOverlay({chart, candles, frame}) {
  const scale = chart.timeScale();
  let times;
  let fills;
  let repaint;
  let detached = false;
  function setFrame(next) {
    frame = next;
    times = frame.bars.map(bar => bar.time);
    const seriesById = new Map(frame.plots.map(plot => [
      plot.id, new Map(plot.points.map(point => [point.time, point.value]))
    ]));
    fills = frame.plots.filter(plot => plot.options.style === 'fill' && (plot.display & 1)).flatMap(plot => {
      const upper = seriesById.get(plot.options.plot1);
      const lower = seriesById.get(plot.options.plot2);
      if (!upper || !lower) return [];
      return [plot.points.map(({time, color}) => ({time, color, high: upper.get(time), low: lower.get(time)}))];
    });
    repaint?.();
  }
  setFrame(frame);
  function renderFills(ctx) {
    ctx.save();
    for (const band of fills) {
      for (let i = 1; i < band.length; i++) {
        const left = band[i - 1], right = band[i];
        if (!right.color || ![left.high, left.low, right.high, right.low].every(Number.isFinite)) continue;
        const x1 = x(left.time, 'bar_time'), x2 = x(right.time, 'bar_time');
        const top1 = y(left.high), top2 = y(right.high), bottom1 = y(left.low), bottom2 = y(right.low);
        if (![x1, x2, top1, top2, bottom1, bottom2].every(Number.isFinite)) continue;
        ctx.fillStyle = right.color;
        ctx.beginPath();
        ctx.moveTo(x1, top1);
        ctx.lineTo(x2, top2);
        ctx.lineTo(x2, bottom2);
        ctx.lineTo(x1, bottom1);
        ctx.closePath();
        ctx.fill();
      }
    }
    ctx.restore();
  }
  const x = (value, location) => {
    if (location === 'bar_index') return scale.logicalToCoordinate(value);
    let low = 0, high = times.length;
    while (low < high) {
      const middle = (low + high) >>> 1;
      if (times[middle] < value) low = middle + 1;
      else high = middle;
    }
    if (!times.length) return null;
    if (times[low] === value) return scale.logicalToCoordinate(low);
    const index = Math.max(0, low - 1);
    const start = times[index];
    const duration = frame.bars[index].closeTime - start;
    const spacing = duration > 0 ? duration : times[index + 1] - start;
    if (!(spacing > 0)) return scale.logicalToCoordinate(index);
    const offset = (value - start) / spacing;
    return scale.logicalToCoordinate(index + (low > 0 && low < times.length ? Math.min(1, offset) : offset));
  };
  const y = value => candles.priceToCoordinate(value);
  const dash = style => style === 'style_dotted' ? [2, 3] : style === 'style_dashed' ? [6, 4] : [];
  function render(ctx) {
    ctx.save();
    for (const box of frame.objects.boxes) {
      if (![box.left,box.right,box.top,box.bottom].every(Number.isFinite)) continue;
      const left = x(box.left, box.xloc), top = y(box.top);
      const width = x(box.right, box.xloc) - left, height = y(box.bottom) - top;
      if (box.bgcolor) {
        ctx.fillStyle = box.bgcolor;
        ctx.fillRect(left, top, width, height);
      }
      if (box.border_color && box.border_width) {
        ctx.strokeStyle = box.border_color;
        ctx.lineWidth = box.border_width;
        ctx.setLineDash(dash(box.border_style));
        ctx.strokeRect(left, top, width, height);
      }
    }
    for (const line of frame.objects.lines) {
      if (!line.color || ![line.x1,line.x2,line.y1,line.y2].every(Number.isFinite)) continue;
      ctx.strokeStyle = line.color;
      ctx.lineWidth = line.width || 1;
      ctx.setLineDash(dash(line.style));
      ctx.beginPath();
      ctx.moveTo(x(line.x1,line.xloc), y(line.y1));
      ctx.lineTo(x(line.x2,line.xloc), y(line.y2));
      ctx.stroke();
    }
    ctx.font = '11px system-ui';
    for (const label of frame.objects.labels) {
      if (!label.text || !Number.isFinite(label.x) || !Number.isFinite(label.y)) continue;
      const left = x(label.x,label.xloc), top = y(label.y) - 8;
      ctx.fillStyle = label.color || 'transparent';
      ctx.fillRect(left,top,ctx.measureText(label.text).width + 8,16);
      ctx.fillStyle = label.textcolor || '#d1d4dc';
      ctx.fillText(label.text,left + 4,top + 12);
    }
    ctx.restore();
  }
  const primitive = {
    attached({requestUpdate}) { repaint = requestUpdate; },
    detached() { repaint = undefined; },
    paneViews: () => [{
      zOrder: () => 'bottom',
      renderer: () => ({draw: target => target.useMediaCoordinateSpace(({context}) => renderFills(context))})
    }, {
      zOrder: () => 'top',
      renderer: () => ({
        draw(target) { target.useMediaCoordinateSpace(({context}) => render(context)); }
      })
    }]
  };
  candles.attachPrimitive(primitive);
  return {
    update(next) { if (!detached) setFrame(next); },
    remove() {
      if (detached) return;
      detached = true;
      candles.detachPrimitive(primitive);
    }
  };
}

module.exports = {attachPinePriceOverlay};

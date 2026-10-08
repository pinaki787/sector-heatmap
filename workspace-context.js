(function () {
  'use strict';
  fetch('/api/workspace-context').then(r => r.ok ? r.json() : null).then(context => {
    if (!context?.workspace) return;
    const bar = document.createElement('aside');
    bar.style.cssText = 'position:sticky;top:0;z-index:10000;background:var(--surface-2,#0d192a);color:var(--text,#edf4ff);border-bottom:1px solid var(--border,#233c59);padding:10px 20px;display:flex;gap:20px;align-items:center;flex-wrap:wrap;font:14px Inter,system-ui,sans-serif';
    const label = document.createElement('strong');
    label.textContent = `${context.username} / ${context.workspace.label} / ${context.workspace.broker}`;
    const link = document.createElement('a'); link.textContent = 'Users & broker accounts'; link.href = context.portal_url; link.style.color = 'var(--focus,#a9dcff)'; link.target = '_blank'; link.rel = 'noopener';
    bar.append(label, link); document.body.prepend(bar);
  }).catch(() => {});
})();

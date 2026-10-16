"""Remove human typing from order-preview submission; retain preview binding."""
import re
import sys
from pathlib import Path


def transform(source):
    grouped='screener-group-confirmation' in source
    source,count=re.subn(r'<label class="field">Exact confirmation phrase<input class="screener-group-confirmation"[^>]*></label>','',source)
    if count!=(1 if grouped else 0):raise ValueError('Unexpected grouped order confirmation fields.')
    source=source.replace('data-group-index="${index}" disabled>Submit confirmed ${escapeHtml(screenerRouteLabel(group.route))} batch',
        'data-group-index="${index}" ${group.preview.live_submission_enabled && group.preview.submission_eligible ? \'\' : \'disabled\'}>Submit ${escapeHtml(screenerRouteLabel(group.route))} batch')
    source,count=re.subn(r"      for \(const input of \$\('screener-route-preview-groups'\)\.querySelectorAll\('\.screener-group-confirmation'\)\) input\.addEventListener\('input',\(\)=>\{.*?\n      \}\)\n",'',source,flags=re.S)
    if count!=(1 if grouped else 0):raise ValueError('Unexpected grouped typing gates.')
    source=source.replace('<label class="field" style="margin-top:10px">Exact fresh confirmation phrase<input id="screener-order-confirmation" class="confirmation-input" autocomplete="off" spellcheck="false"></label>',
        '<label hidden><input type="hidden" id="screener-order-confirmation" autocomplete="off"></label>')
    source=source.replace('Submit confirmed FYERS batch','Submit FYERS batch')
    source=source.replace("confirmation: $('screener-order-confirmation').value",'confirmation: screenerOrderPreview.confirmation_phrase')
    source=source.replace("$('screener-order-confirmation').value = ''\n      $('submit-screener-order').disabled = true",
                          "$('screener-order-confirmation').value = ''\n      $('submit-screener-order').disabled = !preview.live_submission_enabled || !preview.submission_eligible")
    source=source.replace('Each group requires its own explicit confirmation; no order has been submitted.', 'Click Submit on the group you want to send. No order has been submitted.')
    for field in ('screener-order','ticket','handoff-batch'):
        source=re.sub(r"  \$\('"+field+r"-confirmation'\)\.addEventListener\('input', event => \{.*?\n  \}\)\n",'',source,flags=re.S)
    if 'Exact confirmation phrase' in source or 'Exact fresh confirmation phrase' in source:
        raise ValueError('Unexpected visible confirmation field remains.')
    return source


if __name__=='__main__':
    path=Path(sys.argv[1]);path.write_text(transform(path.read_text()))

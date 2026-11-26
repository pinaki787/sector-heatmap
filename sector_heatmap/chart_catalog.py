"""Read-only chart catalogs under the chart section's permission boundary."""
from .chart_workspace import require_chart


def serve_delta_chart_catalog(handler, workspace_guard, delta):
    try:
        if workspace_guard is None:
            raise PermissionError('Choose an authorized broker workspace for chart symbols.')
        user, account = handler.workspace_identity
        require_chart(user, workspace_guard.store, '/api/chart-workspace/catalog')
        if account.get('broker') != 'DELTA_INDIA':
            handler.send_json(404, {'error': 'This chart catalog requires a Delta India workspace.'})
            return
        payload = delta.catalog(chart=True)
        if (not isinstance(payload, dict) or payload.get('broker') != 'DELTA_INDIA'
                or payload.get('complete') is not True or not isinstance(payload.get('instruments'), list)):
            raise ValueError('Incomplete native chart catalog.')
        handler.send_json(200, payload)
    except PermissionError as error:
        handler.send_json(403, {'error': str(error)})
    except (OSError, RuntimeError, ValueError):
        handler.send_json(503, {'error': 'Selected broker instrument catalog is unavailable.'})

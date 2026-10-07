"""Refresh FYERS resources without restarting the shared process or other brokers."""
def refresh_fyers_session(code,exchange,load,replace,state):
 try:
  exchange(code)
  token=load().get('FYERS_ACCESS_TOKEN')
  if not token:raise ValueError('FYERS did not save a refreshed access token.')
  replace(token)
  state.pop('oauth_state',None)
 finally:state['renewing']=False

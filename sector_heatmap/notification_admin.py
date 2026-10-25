"""Small authenticated User Master notification API; no dashboard/runner lifecycle."""
import hmac
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
from .workspaces import WorkspaceStore,cookie_token
from .trade_notifications import ROOT


def handler_factory(store,port=8090,runtime=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # Do not log recipient addresses, cookies or request bodies.

        def respond(self,status,value):
            body=json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.end_headers();self.wfile.write(body)

        def user(self,mutation=False,admin=True):
            if self.headers.get("Host")!="127.0.0.1:"+str(port):
                raise PermissionError("Use the authenticated Sector Pulse address.")
            user=store.session(cookie_token(self.headers))
            if admin and not user.get("admin"):
                raise PermissionError("Only administrators can manage notification subscribers.")
            if mutation:
                if self.headers.get("Origin") not in ("http://127.0.0.1:8080","http://127.0.0.1:"+str(port)):
                    raise PermissionError("Same-origin request required.")
                if not hmac.compare_digest(self.headers.get("X-CSRF-Token",""),user["csrf"]):
                    raise PermissionError("Refresh User Master before saving.")
            return user

        def do_GET(self):
            try:
                parsed=urlparse(self.path)
                if parsed.path=="/api/notification-admin/sector-detail":
                    user=self.user(admin=False)
                    query=parse_qs(parsed.query)
                    from .sector_detail_bridge import details
                    value=details(ROOT,store,user,(query.get("account_id") or [""])[0],
                        cookie_token(self.headers),(query.get("sector") or [""])[0],(query.get("mode") or ["intraday"])[0])
                    self.respond(200,value);return
                if parsed.path=="/api/notification-admin/handoff":
                    user=self.user(admin=False)
                    aid=(parse_qs(parsed.query).get("account_id") or [""])[0]
                    if runtime is None:raise ValueError("Handoff scheduling runtime unavailable.")
                    self.respond(200,runtime.status(user,aid));return
                user=self.user()
                if parsed.path!="/api/notification-admin/users":
                    self.respond(404,{"error":"Unknown notification settings endpoint."});return
                rows=store.users(user)
                self.respond(200,{"enabled":True,"users":[{k:r[k] for k in ("username","notification_email","notification_email_enabled")} for r in rows]})
            except PermissionError as error:self.respond(403,{"error":str(error)})
            except (ValueError,TypeError) as error:self.respond(400,{"error":str(error)})
            except Exception:self.respond(500,{"error":"Notification settings unavailable."})

        def do_POST(self):
            try:
                path=urlparse(self.path).path
                schedule=path in ("/api/notification-admin/handoff","/api/notification-admin/handoff-prepare","/api/notification-admin/handoff-submit","/api/notification-admin/handoff-diagnose")
                user=self.user(mutation=True,admin=not schedule)
                if not schedule and path!="/api/notification-admin/user-email":
                    self.respond(404,{"error":"Unknown notification settings endpoint."});return
                if self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type","").split(";")[0]!="application/json":
                    raise ValueError("Send a JSON object.")
                size=int(self.headers.get("Content-Length","0"))
                if not 0<size<=4096:raise ValueError("Invalid notification request size.")
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict):raise ValueError("Send a JSON object.")
                if schedule:
                    if runtime is None:raise ValueError("Handoff scheduling runtime unavailable.")
                    aid=payload.pop("account_id",None)
                    if path.endswith("/handoff-diagnose"):
                        result=runtime.diagnose(user,aid,cookie_token(self.headers))
                    elif path.endswith("/handoff-prepare"):
                        result=runtime.manual.prepare(user,aid,cookie_token(self.headers),payload.get("selected"))
                    elif path.endswith("/handoff-submit"):
                        result=runtime.manual.submit(user,aid,payload.get("preview_id"),payload.get("confirmation"))
                    else:result=runtime.configure(user,aid,cookie_token(self.headers),payload)
                else:
                    result=store.set_notification_email(user,payload.get("username"),payload.get("email"),payload.get("enabled"))
                self.respond(200,result)
            except PermissionError as error:self.respond(403,{"error":str(error)})
            except (ValueError,TypeError) as error:self.respond(400,{"error":str(error)})
            except Exception:self.respond(500,{"error":"Notification settings could not be saved."})
    return Handler


def main():
    store=WorkspaceStore(ROOT/".private/dashboard-login/registry.sqlite3")
    from .handoff_runtime import Runtime
    runtime=Runtime(store,ROOT)
    runtime.restore()
    try:ThreadingHTTPServer(("127.0.0.1",8090),handler_factory(store,runtime=runtime)).serve_forever()
    finally:runtime.close()


if __name__=="__main__":main()


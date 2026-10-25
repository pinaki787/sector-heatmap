import hashlib
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from sector_heatmap.notification_admin import handler_factory
from sector_heatmap.workspaces import WorkspaceStore,COOKIE


class NotificationAdminApiTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=WorkspaceStore(Path(self.temp.name)/"registry.sqlite3",clock=lambda:100)
        self.admin_token="synthetic-admin-session";self.user_token="synthetic-user-session"
        with self.store.db() as db:
            for uid,name,admin in [("admin-id","admin",1),("user-id","user",0)]:
                db.execute("INSERT INTO users VALUES(?,?,?,?,?)",(uid,name,"synthetic","synthetic",admin))
            for token,uid in [(self.admin_token,"admin-id"),(self.user_token,"user-id")]:
                db.execute("INSERT INTO sessions VALUES(?,?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),uid,"synthetic-csrf",1000))
        self.server=ThreadingHTTPServer(("127.0.0.1",0),handler_factory(self.store,0))
        self.port=self.server.server_port;self.server.RequestHandlerClass=handler_factory(self.store,self.port)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,method="GET",path="/api/notification-admin/users",token=None,payload=None,origin=None,csrf=None):
        headers={}
        if token:headers["Cookie"]=COOKIE+"="+token
        if origin:headers["Origin"]=origin
        if csrf:headers["X-CSRF-Token"]=csrf
        if payload is not None:headers["Content-Type"]="application/json"
        connection=http.client.HTTPConnection("127.0.0.1",self.port,timeout=3)
        connection.request(method,path,json.dumps(payload) if payload is not None else None,headers)
        response=connection.getresponse();result=json.loads(response.read());status=response.status;connection.close()
        return status,result

    def test_unauthenticated_and_regular_users_denied(self):
        self.assertEqual(self.request()[0],403)
        self.assertEqual(self.request(token=self.user_token)[0],403)

    def test_admin_lists_only_notification_fields(self):
        status,result=self.request(token=self.admin_token)
        self.assertEqual(status,200);self.assertTrue(result["enabled"])
        self.assertEqual(set(result["users"][0]),{"username","notification_email","notification_email_enabled"})

    def test_origin_and_csrf_required(self):
        payload={"username":"user","email":"user@example.com","enabled":True}
        for origin,csrf in [("https://other.example","synthetic-csrf"),("http://127.0.0.1:8080",None)]:
            self.assertEqual(self.request("POST","/api/notification-admin/user-email",self.admin_token,payload,origin,csrf)[0],403)

    def test_valid_save_opt_in_and_uncheck(self):
        payload={"username":"user","email":"user@example.com","enabled":True}
        args=("POST","/api/notification-admin/user-email",self.admin_token,payload,"http://127.0.0.1:8080","synthetic-csrf")
        status,result=self.request(*args);self.assertEqual(status,200);self.assertTrue(result["notification_email_enabled"])
        payload["enabled"]=False
        status,result=self.request(*args);self.assertEqual(status,200);self.assertFalse(result["notification_email_enabled"])

    def test_enabled_requires_email_and_flag_is_boolean(self):
        for payload in [{"username":"user","email":"","enabled":True},{"username":"user","email":"user@example.com","enabled":"true"}]:
            status,_=self.request("POST","/api/notification-admin/user-email",self.admin_token,payload,"http://127.0.0.1:8080","synthetic-csrf")
            self.assertEqual(status,400)


if __name__=="__main__":unittest.main()


from .. import tutils, mastertest
from mitmproxy.addons import stickycookie
from mitmproxy import master
from mitmproxy import options
from mitmproxy import proxy
from mitmproxy.test import tutils as ntutils


def test_domain_match():
    assert stickycookie.domain_match("www.google.com", ".google.com")
    assert stickycookie.domain_match("google.com", ".google.com")


class TestStickyCookie(mastertest.MasterTest):
    def mk(self):
        o = options.Options(stickycookie = ".*")
        m = master.Master(o, proxy.DummyServer())
        sc = stickycookie.StickyCookie()
        m.addons.add(sc)
        return m, sc

    def test_config(self):
        sc = stickycookie.StickyCookie()
        o = options.Options(stickycookie = "~b")
        tutils.raises(
            "invalid filter",
            sc.configure, o, o.keys()
        )

    def test_simple(self):
        m, sc = self.mk()
        m.addons.add(sc)

        f = tutils.tflow(resp=True)
        f.response.headers["set-cookie"] = "foo=bar"
        m.request(f)

        f.reply.acked = False
        m.response(f)

        assert sc.jar
        assert "cookie" not in f.request.headers

        f = f.copy()
        f.reply.acked = False
        m.request(f)
        assert f.request.headers["cookie"] == "foo=bar"

    def _response(self, m, sc, cookie, host):
        f = tutils.tflow(req=ntutils.treq(host=host, port=80), resp=True)
        f.response.headers["Set-Cookie"] = cookie
        m.response(f)
        return f

    def test_response(self):
        m, sc = self.mk()

        c = "SSID=mooo; domain=.google.com, FOO=bar; Domain=.google.com; Path=/; " \
            "Expires=Wed, 13-Jan-2021 22:23:01 GMT; Secure; "

        self._response(m, sc, c, "host")
        assert not sc.jar.keys()

        self._response(m, sc, c, "www.google.com")
        assert sc.jar.keys()

        sc.jar.clear()
        self._response(
            m, sc, "SSID=mooo", "www.google.com"
        )
        assert list(sc.jar.keys())[0] == ('www.google.com', 80, '/')

    def test_response_multiple(self):
        m, sc = self.mk()

        # Test setting of multiple cookies
        c1 = "somecookie=test; Path=/"
        c2 = "othercookie=helloworld; Path=/"
        f = self._response(m, sc, c1, "www.google.com")
        f.response.headers["Set-Cookie"] = c2
        m.response(f)
        googlekey = list(sc.jar.keys())[0]
        assert len(sc.jar[googlekey].keys()) == 2

    def test_response_weird(self):
        m, sc = self.mk()

        # Test setting of weird cookie keys
        f = tutils.tflow(req=ntutils.treq(host="www.google.com", port=80), resp=True)
        cs = [
            "foo/bar=hello",
            "foo:bar=world",
            "foo@bar=fizz",
        ]
        for c in cs:
            f.response.headers["Set-Cookie"] = c
            m.response(f)
        googlekey = list(sc.jar.keys())[0]
        assert len(sc.jar[googlekey].keys()) == len(cs)

    def test_response_overwrite(self):
        m, sc = self.mk()

        # Test overwriting of a cookie value
        c1 = "somecookie=helloworld; Path=/"
        c2 = "somecookie=newvalue; Path=/"
        f = self._response(m, sc, c1, "www.google.com")
        f.response.headers["Set-Cookie"] = c2
        m.response(f)
        googlekey = list(sc.jar.keys())[0]
        assert len(sc.jar[googlekey].keys()) == 1
        assert list(sc.jar[googlekey]["somecookie"].items())[0][1] == "newvalue"

    def test_response_delete(self):
        m, sc = self.mk()

        # Test that a cookie is be deleted
        # by setting the expire time in the past
        f = self._response(m, sc, "duffer=zafar; Path=/", "www.google.com")
        f.response.headers["Set-Cookie"] = "duffer=; Expires=Thu, 01-Jan-1970 00:00:00 GMT"
        m.response(f)
        assert not sc.jar.keys()

    def test_request(self):
        m, sc = self.mk()

        f = self._response(m, sc, "SSID=mooo", "www.google.com")
        assert "cookie" not in f.request.headers
        m.request(f)
        assert "cookie" in f.request.headers

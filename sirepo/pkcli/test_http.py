# -*- coding: utf-8 -*-
u"""multi-threaded requests to server over http

:copyright: Copyright (c) 2020 RadiaSoft LLC.  All Rights Reserved.
:license: http://www.apache.org/licenses/LICENSE-2.0.html
"""
from __future__ import absolute_import, division, print_function
from pykern import pkconfig
from pykern import pkjson
from pykern.pkcollections import PKDict
from pykern.pkdebug import pkdlog, pkdp, pkdexc, pkdc
import copy
import re
import requests
import subprocess
import threading
import time
import sirepo.util
import sirepo.sim_data


cfg = None


def run_all():
    l = []
    for a in (
#        ('a@b.c', 'myapp', 'Scooby Doo'),
        ('a@b.c', 'srw', "Young's Double Slit Experiment"),
    ):
        t = threading.Thread(target=run, args=a)
        l.append(t)
        t.start()
    for t in l:
        t.join()


def run(email, sim_type, *sim_names):
    run_sequential_parallel(_Client(email=email, sim_type=sim_type).login())
    '''
    o = list(sim_names)
    for x in l:
        if x.name in o:
            o.remove(x.name)
    assert not o, \
        'sim_names={} not found in list={}'.format(o, l)
    d = s.get(
        '/simulation/{}/{}/0'.format(s.sim_type, x.simulationId),
    )
    x = d.models.simulation
    pkdlog('sid={} name={}', x.simulationId, x.name)
    '''


def run_sequential_parallel(client):
    s = "Young's Double Slit Experiment"
    c = []
    for r in 'intensityReport', 'powerDensityReport', 'sourceIntensityReport', 'multiElectronAnimation', 'fluxAnimation':
        c.append(client.sim_run('Tabulated Undulator Example', r))
    for x in c:
        x.thread.join()
    #     'multiElectronAnimation'
    #     'brillianceReport',
    #     'fluxReport',
    #     'initialIntensityReport',
    #     'intensityReport',
    #     'powerDensityReport',
    #     'sirepo-data.json',
    #     'sourceIntensityReport',
    #     'trajectoryReport',
    #     'watchpointReport6',
    #     'watchpointReport7',




class _Client(PKDict):

    __global_lock = threading.Lock()

    __login_locks = PKDict()

    def __init__(self, **kwargs):
        super(_Client, self).__init__(**kwargs)
        _init()
        self._session = requests.Session()
        self._session.verify = False

    def copy(self):
        n = type(self)()
        # reaches inside requests.Session
        n._session.cookies = self._session.cookies.copy()
        for k, v in self.items():
            if k not in n:
                n[k] = copy.deepcopy(v)
        return n

    def get(self, uri):
        return self.parse_response(
            self._session.get(url=self.uri(uri)),
        )

    def login(self):
        r = self.post('/simulation-list', PKDict())
        assert r.srException.routeName == 'missingCookies'
        r = self.post('/simulation-list', PKDict())
        assert r.srException.routeName == 'login'
        with self.__global_lock:
            self.__login_locks.pksetdefault(self.email, threading.Lock)
        with self.__login_locks[self.email]:
            r = self.post('/auth-email-login', PKDict(email=self.email))
            t = sirepo.util.create_token(self.email)
            r = self.post(
                self.uri('/auth-email-authorized/{}/{}'.format(self.sim_type, t)),
                data=PKDict(token=t, email=self.email),
            )
            if r.state == 'redirect' and 'complete' in r.uri:
                r = self.post(
                    '/auth-complete-registration',
                    PKDict(displayName=self.email),
                )

        r = self.post('/simulation-list', PKDict())
        self._sid = PKDict([(x.name, x.simulationId) for x in r])
        self._sim_db = PKDict()
        self._sim_data = sirepo.sim_data.get_class(self.sim_type)
        return self

    def parse_response(self, resp):
        self.resp = resp
        self.json = None
        resp.raise_for_status()
        if 'json' in resp.headers['content-type']:
            self.json = pkjson.load_any(resp.content)
            return self.json
        if 'html' in resp.headers['content-type']:
            m = re.search('location = "(/[^"]+)', resp.content)
            if m:
                if 'error' in m.group(1):
                    self.json = PKDict(state='error', error='server error')
                else:
                    self.json = PKDict(state='redirect', uri=m.group(1))
                return self.json
        return resp.content

    def post(self, uri, data):
        data.simulationType = self.sim_type
        return self.parse_response(
            self._session.post(
                url=self.uri(uri),
                data=pkjson.dump_bytes(data),
                headers=PKDict({'Content-type': 'application/json'}),
            ),
        )

    def sim_db(self, sim_name):
        return self._sim_db.pksetdefault(
            sim_name,
            lambda: self.get(
                '/simulation/{}/{}/0'.format(self.sim_type, self._sid[sim_name]),
            ),
        )[sim_name]

    def sim_run(self, name, report, timeout=120):

        def _run(self):
            c = None
            i = self._sid[name]
            d = self.sim_db(name)
            pkdlog('sid={} report={} state=start', i, report)
            r = self.post(
                '/run-simulation',
                PKDict(
                    # works for sequential simulations, too
                    forceRun=True,
                    models=d.models,
                    report=report,
                    simulationId=i,
                    simulationType=self.sim_type,
                ),
            )
            p = self._sim_data.is_parallel(report)
            try:
                if r.state == 'completed':
                    return
                c = r.get('nextRequest')
                for _ in range(timeout):
                    if r.state in ('completed', 'error'):
                        c = None
                        break
                    r = self.post('/run-status', r.nextRequest)
                    time.sleep(1)
                else:
                    pkdlog('sid={} report={} timeout={}', i, report, timeout)
            finally:
                if c:
                    self.post('/run-cancel', c)
                s = 'cancel' if c else r.get('state')
                if s == 'error':
                    s = r.get('error', '<unknown error>')
                pkdlog('sid={} report={} state={}', i, report, s)
            if p:
                g = self._sim_data.frame_id(d, r, report, 0)
                f = self.get('/simulation-frame/' + g)
                assert 'title' in f, \
                    'no title in frame={}'.format(f)
                c = None
                try:
                    c = self.post(
                        '/run-simulation',
                        PKDict(
                            # works for sequential simulations, too
                            forceRun=True,
                            models=d.models,
                            report=report,
                            simulationId=i,
                            simulationType=self.sim_type,
                        ),
                    )
                    f = self.get('/simulation-frame/' + g)
                    assert f.state == 'error', \
                        'expecting error instead of frame={}'.format(f)
                finally:
                    if c:
                        self.post('/run-cancel', c.get('nextRequest'))

        self = self.copy()
        self.thread = threading.Thread(target=_run, args=[self])
        self.thread.start()
        return self


    def uri(self, uri):
        if uri.startswith('http'):
            return uri
        assert uri.startswith('/')
        return cfg.server_uri + uri

def _init():
    global cfg
    if cfg:
        return
    cfg = pkconfig.init(
        server_uri=('http://127.0.0.1:8000', str, 'where to send requests'),
    )
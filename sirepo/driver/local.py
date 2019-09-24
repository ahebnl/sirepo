# -*- coding: utf-8 -*-
"""TODO(e-carlin): Doc

:copyright: Copyright (c) 2019 RadiaSoft LLC.  All Rights Reserved.
:license: http://www.apache.org/licenses/LICENSE-2.0.html
"""
from __future__ import absolute_import, division, print_function
from pykern import pkcollections
from pykern import pkconfig
from pykern.pkdebug import pkdp, pkdlog, pkdexc
from sirepo import driver
from sirepo import job
from sirepo import job_scheduler
import os
import sirepo.mpi
import tornado.process


class LocalDriver(driver.DriverBase):
    resources = pkcollections.Dict(
        parallel=pkcollections.Dict(
            drivers=[],
            slots=pkcollections.Dict(
                total=1,
                in_use=0,
            )
        ),
        sequential=pkcollections.Dict(
            drivers=[],
            slots=pkcollections.Dict(
                total=1,
                in_use=0,
            )
        ),
    )

    def __init__(self, uid, agent_id, resource_class):
        super(LocalDriver, self).__init__(uid, agent_id, resource_class)
        # TODO(e-carlin): This is used to get starts about drivers as the code
        # is running. Only useful when closely debugging code. Probably delete.
        tornado.ioloop.IOLoop.current().spawn_callback(
            self._stats
        )

    # TODO(e-carlin): If IoLoop.spawn_callback(self._stats) is deleted then
    # this can be deleted too.
    async def _stats(self):
        import tornado.gen
        while True:
            pkdp('====================================')
            pkdp('AGENT_ID={}', self.agent_id)
            pkdp('agent_started={}', self.agent_started)
            pkdp('running_data_jobs={}', self.running_data_jobs)
            pkdp('requests={}', self.requests)
            pkdp('====================================')
            await tornado.gen.sleep(2)

    def start_agent(self):
        pkdlog('agent_id={}', self.agent_id)
        # TODO(e-carlin): Make this more robust. Ex handle failures,
        # monitor the process, be able to kill it
        env = dict(os.environ)
        env['PYENV_VERSION'] = 'py3'
        env['SIREPO_PKCLI_JOB_AGENT_AGENT_ID'] = self.agent_id
        env['SIREPO_PKCLI_JOB_AGENT_SUPERVISOR_WS_URI'] = cfg.supervisor_ws_uri
        self.agent = tornado.process.Subprocess(
            [
                'pyenv',
                'exec',
                'sirepo',
                'job_agent',
                'start',
            ],
            env=env,
        )
        self.agent_started = True
    
    def terminate_agent(self):
        # TODO(e-carlin): There is too much state about agents. At the very
        # least make more fields private
        self.agent_started = False
        self.message_handler = None
        self.message_handler_set.clear()
        self.agent.proc.terminate() 
        self.agent.proc.wait() 
        self.agent = None

cfg = pkconfig.init(
    supervisor_ws_uri=(
        job.cfg.supervisor_ws_uri,
        str,
        'uri to reach the supervisor for websocket connections',
    ),
)

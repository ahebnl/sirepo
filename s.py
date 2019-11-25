class _SBatchComputeProcess(PKDict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._terminating = False


    def start(self):
        tornado.ioloop.IOLoop.current().add_callback(
            self._start_compute
            if self.msg.jobProcessCmd == 'compute'
            else self._start_job_process
        )

    async def _start_job_process(self):
        # start shifter container that runs the desired job process



    # TODO(e-carlin): handling cancel throughout all of this is tricky
    # currently not implemented
    async def _start_compute(self):
        try:
            # 1. job process prepare_simulation
            #    this will setup the db and return the cmd we need
            cmd = await self._prepare_simulation()
            # 2. submit the job to sbatch
            job_id = await self._submit_compute_to_sbatch(cmd)
            # 3. wait for running in sbatch (need to be ready for a cancel)
            # TODO(e-carlin): no fully implemented
            await self._await_job_completion(self, job_id)
        except Exception as e:
            # TODO(e-carlin): comm send this stuff don't return it
            return PKDict(state=job.ERROR, error=str(e), stack=pkdexc())
        return PKDict(state=job.COMPLETED)

    async def _await_job_completion(self, job_id):
        while True:
            s = self._get_job_sbatch_state(job_id)
            assert s in ('running', 'pending', 'completed'), \
                'invalid state={}'.format(s)
            if s in ('running', 'completed'):
                if self.msg.isParallel:
                    self._get_parallel_status()
            if s == 'completed':
                break
            await tornado.gen.sleep(2) # TODO(e-carlin): longer poll

    def _get_parallel_status(self):
        msg = self.msg.copy().update(jobProcessCmd='get_sbatch_parallel_status')

    def _get_job_sbatch_state(self, job_id):
        o = subprocess.check_output(
            ('scontrol', 'show', 'job', job_id)
        ).decode('utf-8')
        r = re.search(r'(?<=JobState=)(.*)(?= Reason)', o) # TODO(e-carlin): Make middle [A-Z]+
        assert r, 'output={}'.format(s)
        return r.group().lower()

    async def _submit_compute_to_sbatch(self, cmd):
    # create sbatch script
        s = _get_sbatch_script(cmd)
        with open(self.msg.runDir.join('sbatch.job', 'w') as f:
                 f.write(s)
        o, e = subprocess.Popen(
            ('sbatch'),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).communicate(
            input=s)
        assert e == '', 'error={}'.format(e)
        r = re.search(r'\d+$', o)
        assert r is not None, 'output={} did not cotain job id'.format(o)
        return r.group()


    def _get_docker_cmd(self, cmd):
        return '''docker run \
       --interactive \
       --init \
       --volume /home/vagrant/src/radiasoft/sirepo/sirepo:/home/vagrant/.pyenv/versions/2.7.16/envs/py2/lib/python2.7/site-packages/sirepo \
       --volume /home/vagrant/src/radiasoft/pykern/pykern:/home/vagrant/.pyenv/versions/2.7.16/envs/py2/lib/python2.7/site-packages/pykern \
       --volume {}:{} \
       radiasoft/sirepo:dev \
       /bin/bash -l <<'EOF'
pyenv shell py2
cd {}
{}
'''.format(
        self.msg.runDir,
        self.msg.runDir,
        self.msg.runDir,
        ' '.join(cmd),# TODO(e-carlin): quote?
    )

    def _get_sbatch_script(self, cmd):
       # --volume /home/vagrant/src:/home/vagrant/src:ro \
        # TODO(e-carlin): configure the SBATCH* parameters
        return'''#!/bin/bash
#SBATCH --partition=compute
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=128M
#SBATCH -e {}
#SBATCH -o {}
{}
EOF
'''.format(
            template_common.RUN_LOG,
            template_common.RUN_LOG,
            self._get_docker_cmd(cmd),
        )

    async def _prepare_simulation(self):
        _do_compute_command = None
        _on_exit = tornado.locks.Event()

        async def on_stdout_read(self, text):
            nonlocal _do_compute_command
            _do_compute_command = text

        async def on_exit(self, returncode):
            nonlocal _on_exit
            assert returncode == 0
            _on_exit.set()

        m = self.msg.copy()
        m.jobProcessCmd = 'prepare_simulation'
        p = _JobProcess(
                msg=self.msg.copy().update(
                    jobProcessCmd='prepare_simulation'
                ),
                on_stdout_read,
                on_exit,
            )
        await _on_exit.wait()
        return _do_compute_command

############################################################3



    @classmethod
    def _get_sbatch_state(cls, job_id):
        o = subprocess.check_output(
            ('scontrol', 'show', 'job', job_id)
        ).decode('utf-8')
        r = re.search(r'(?<=JobState=)(.*)(?= Reason)', o) # TODO(e-carlin): Make middle [A-Z]+
        assert r, 'output={}'.format(s)
        return r.group().lower()


    async def _start(self):

        _submit_to_sbatch_subprocess = _Subprocess(
                self._sbatch_cmd_stdin_env,
                submit_to_sbacth_subprocess_on_stdout_read,
                msg=self.msg,
            )
        _submit_to_sbatch_subprocess.start()


    def _sbatch_cmd_stdin_env(self, msg_in_file):
        cmd =
        stdin =
        env = {}



# TODO(e-carlin): rename to cancel?
    def kill(self):
        # TODO(e-carlin): terminate?
        self._terminating = True
        self._subprocess.kill()

    def start(self):
        self._subprocess.start()
        tornado.ioloop.IOLoop.current().add_callback(
            self._on_exit
        )

    def _subprocess_cmd_stdin_env(self, in_file):
        return job.subprocess_cmd_stdin_env(
            ('sirepo', 'job_process', in_file),
            PKDict(
                PYTHONUNBUFFERED='1',
                SIREPO_AUTH_LOGGED_IN_USER=sirepo.auth.logged_in_user(),
                SIREPO_MPI_CORES=self.msg.mpiCores,
                SIREPO_SIM_LIB_FILE_URI=self.msg.get('libFileUri', ''),
                SIREPO_SRDB_ROOT=sirepo.srdb.root(),
            ),
            pyenv='py2',
        )

    async def _on_stdout_read(self, text):
        if self._terminating:
            return
        try:
            r = pkjson.load_any(text)
            if 'opDone' in r:
                del self.comm.processes[self.msg.computeJid]
            if self.msg.jobProcessCmd == 'compute':
                await self.comm.send(
                    self.comm.format_op(
                        self.msg,
                        job.OP_RUN,
                        reply=r,
                    )
                )
            else:
                await self.comm.send(
                    self.comm.format_op(
                        self.msg,
                        job.OP_ANALYSIS,
                        reply=r,
                    )
                )
        except Exception as exc:
            pkdlog('error=={}', exc)

    async def _on_exit(self):
        try:
            await self._subprocess.exit_ready()
            if self._terminating:
                await self.comm.send(
                    self.comm.format_op(
                        self.msg,
                        job.OP_OK,
                        reply=PKDict(state=job.CANCELED, opDone=True),
                    )
                )
                return
            e = self._subprocess.stderr.text.decode('utf-8', errors='ignore')
            if e:
                pkdlog('error={}', e)
            if self._subprocess.returncode != 0:
                await self.comm.send(
                    self.comm.format_op(
                        self.msg,
                        job.OP_ERROR,
                        opDone=True,
                        error=e,
                        reply=PKDict(
                            state=job.ERROR,
                            error='returncode={}'.format(self._subprocess.returncode)),
                    )
                )
        except Exception as exc:
            pkdlog('error={} returncode={}', exc, self._subprocess.returncode)

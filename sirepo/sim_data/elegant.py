# -*- coding: utf-8 -*-
u"""myapp simulation data operations

:copyright: Copyright (c) 2019 RadiaSoft LLC.  All Rights Reserved.
:license: http://www.apache.org/licenses/LICENSE-2.0.html
"""
from __future__ import absolute_import, division, print_function
from pykern import pkinspect
import sirepo.sim_data
from sirepo import simulation_db


class SimData(sirepo.sim_data.SimDataBase):

    @classmethod
    def fixup_old_data(cls, data):
        for m in [
            'bunchSource',
            'twissReport',
        ]:
            if m not in data['models']:
                data['models'][m] = pkcollections.Dict()
            cls.update_model_defaults(data['models'][m], m, cls.schema())
        if 'bunchFile' not in data['models']:
            data['models']['bunchFile'] = pkcollections.Dict(sourceFile=None)
        if 'folder' not in data['models']['simulation']:
            data['models']['simulation']['folder'] = '/'
        if 'simulationMode' not in data['models']['simulation']:
            data['models']['simulation']['simulationMode'] = 'parallel'
        if 'rpnVariables' not in data['models']:
            data['models']['rpnVariables'] = []
        if 'commands' not in data['models']:
            data['models']['commands'] = cls._create_commands(data)
            for m in data['models']['elements']:
                model_schema = cls.schema().model[m['type']]
                for k in m:
                    if k in model_schema and model_schema[k][1] == 'OutputFile' and m[k]:
                        m[k] = "1"
        for m in data['models']['elements']:
            if m['type'] == 'WATCH':
                m['filename'] = '1'
                if m['mode'] == 'coordinates' or m['mode'] == 'coord':
                    m['mode'] = 'coordinate'
            cls.update_model_defaults(m, m['type'], cls.schema())
        if 'centroid' not in data['models']['bunch']:
            bunch = data['models']['bunch']
            for f in ('emit_x', 'emit_y', 'emit_z'):
                if bunch[f] and not isinstance(bunch[f], basestring):
                    bunch[f] /= 1e9
            if bunch['sigma_s'] and not isinstance(bunch['sigma_s'], basestring):
                bunch['sigma_s'] /= 1e6
            first_bunch_command = _find_first_bunch_command(data)
            # first_bunch_command may not exist if the elegant sim has no bunched_beam command
            if first_bunch_command:
                first_bunch_command['symmetrize'] = str(first_bunch_command['symmetrize'])
                for f in cls.schema().model.bunch:
                    if f not in bunch and f in first_bunch_command:
                        bunch[f] = first_bunch_command[f]
            else:
                bunch['centroid'] = '0,0,0,0,0,0'
        for m in data['models']['commands']:
            cls.update_model_defaults(m, 'command_{}'.format(m['_type']), cls.schema())
        cls.organize_example(data)

    @classmethod
    def max_id(cls, data):
        max_id = 1
        for model_type in 'elements', 'beamlines', 'commands':
            if model_type not in data.models:
                continue
            for m in data.models[model_type]:
                id = m._id if '_id' in m else m.id
                if id > max_id:
                    max_id = id
        return max_id

    @classmethod
    def _create_command(cls, name, data):
        s = cls.schema().model[name]
        for k in s:
            if k not in data:
                data[k] = s[k][2]
        return data

    @classmethod
    def _create_commands(cls, data):
        i = cls.max_id(data)
        b = data.models.bunch
        res = []
        for x in (
            pkcollections.Dict(
                m='command_run_setup',
                _type='run_setup',
                centroid='1',
                concat_order=2,
                lattice='Lattice',
                output='1',
                p_central_mev=b.p_central_mev,
                parameters='1',
                print_statistics='1',
                sigma='1',
                use_beamline=data.models.simulation.get('visualizationBeamlineId', ''),
            ),
            pkcollections.Dict(
                m='command_run_control',
                _type='run_control',
            ),
            pkcollections.Dict(
                m='command_twiss_output',
                _type='twiss_output',
                filename='1',
            ),
            pkcollections.Dict(
                m='command_bunched_beam',
                _type='bunched_beam',
                alpha_x=b.alpha_x,
                alpha_y=b.alpha_y,
                alpha_z=b.alpha_z,
                beta_x=b.beta_x,
                beta_y=b.beta_y,
                beta_z=b.beta_z,
                distribution_cutoff='3, 3, 3',
                enforce_rms_values='1, 1, 1',
                emit_x=b.emit_x / 1e09,
                emit_y=b.emit_y / 1e09,
                emit_z=b.emit_z,
                n_particles_per_bunch=b.n_particles_per_bunch,
                one_random_bunch='0',
                sigma_dp=b.sigma_dp,
                sigma_s=b.sigma_s / 1e06,
                symmetrize='1',
                Po=0.0,
            ),
            pkcollections.Dict(
                m='command_track',
                _type='track',
            ),
        ):
            m = x[m]
            del x[m]
            i += 1
            x._id = i
            res.append(cls._create_command(m, x))
        return res

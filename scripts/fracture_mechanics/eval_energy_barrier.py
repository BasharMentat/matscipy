#! /usr/bin/env python

# ======================================================================
# matscipy - Python materials science tools
# https://github.com/libAtoms/matscipy
#
# Copyright (2014) James Kermode, King's College London
#                  Lars Pastewka, Karlsruhe Institute of Technology
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ======================================================================

import glob
import sys

import numpy as np
from scipy.integrate import cumtrapz

import ase.io
from ase.data import atomic_numbers

###

sys.path += [ "." ]
import params

###

# Atom types used for outputting the crack tip position.
ACTUAL_CRACK_TIP = 'Au'
FITTED_CRACK_TIP = 'Ag'

###

prefix = sys.argv[1]
fns = sorted(glob.glob('%s_*.xyz' % prefix))

tip_x = []
tip_y = []
epot_cluster = []
bond_lengths = []
bond_forces = []
work = []

last_a = None
for fn in fns:
    a = ase.io.read(fn)

    _tip_x, _tip_y, _tip_z = a.info['fitted_crack_tip']
    tip_x += [ _tip_x ]
    tip_y += [ _tip_y ]

    # Bond length.
    bond1 = a.info['bond1']
    bond2 = a.info['bond2']
    dr = a[bond1].position - a[bond2].position
    bond_lengths += [ np.linalg.norm(dr) ]

    # Groups
    g = a.get_array('groups')

    # Get stored potential energy.
    epot_cluster += [ a.get_potential_energy() ]

    # Stored Forces on bond.
    forces = a.get_forces()
    df = forces[bond1, :] - forces[bond2, :]
    bond_forces += [ 0.5 * np.dot(df, dr)/np.sqrt(np.dot(dr, dr)) ]

    # Work due to moving boundary.
    if last_a is None:
        work += [ 0.0 ]
    else:
        last_forces = last_a.get_array('forces')
        # This is the trapezoidal rule.
        work += [ np.sum(0.5 * (forces[g==0,:]+last_forces[g==0,:]) *
                         (a.positions[g==0,:]-last_a.positions[g==0,:])
                          ) ]

    last_a = a

epot_cluster = np.array(epot_cluster)-epot_cluster[0]
work = np.cumsum(work)

# Integrate true potential energy.
epot = -cumtrapz(bond_forces, bond_lengths, initial=0.0)
np.savetxt('%s_eval.out' % prefix,
           np.transpose([bond_lengths, # 1
                         bond_forces,  # 2
                         epot,         # 3
                         epot_cluster, # 4
                         work,         # 5
                         tip_x,        # 6
                         tip_y]),      # 7
           header='1:bond_lengths 2:bond_forces 3:epot 4:epot_cluster 5:work 6:tip_x 7:tip_y')

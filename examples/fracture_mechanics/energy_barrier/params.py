#! /usr/bin/env python

from math import log

import numpy as np

import ase.io

from matscipy.fracture_mechanics.clusters import diamond_110_110

import atomistica

###

# Interaction potential
calc = atomistica.KumagaiScr()

# Fundamental material properties
el              = 'Si'
a0              = 5.429
C11             = 166.   # GPa
C12             = 65.    # GPa
C44             = 77.    # GPa
surface_energy  = 1.08  * 10    # GPa*A = 0.1 J/m^2

# Crack system
n               = [ 16, 1, 24 ]
crack_surface   = [ 1,-1, 0 ]
crack_front     = [ 1, 1, 0 ]

vacuum          = 6.0

# Simulation control
bond            = ( 737, 800 )
k1              = 1.10
bond_lengths    = np.linspace(2.5, 5.0, 101)

fmax            = 0.001

cutoff          = 5.0

# Setup crack system
cryst = diamond_110_110(el, a0, n, crack_surface, crack_front)
ase.io.write('cryst.cfg', cryst)

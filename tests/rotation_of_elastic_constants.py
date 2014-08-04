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

import unittest

import numpy as np

from ase.constraints import StrainFilter
from ase.lattice.cubic import Diamond, FaceCenteredCubic
from ase.optimize import FIRE
from ase.units import GPa

from atomistica import Kumagai, TabulatedAlloyEAM

import matscipytest
from matscipy.elasticity import CubicElasticModuli, Voigt_6x6_to_cubic
from matscipy.elasticity import measure_triclinic_elastic_constants
from matscipy.elasticity import rotate_cubic_elastic_constants

###

class TestCubicElasticModuli(matscipytest.MatSciPyTestCase):

    fmax = 1e-6
    delta = 1e-6

    def test_rotation(self):
        for make_atoms, calc in [ 
#            ( lambda a0,x : 
#              FaceCenteredCubic('He', size=[1,1,1],
#                                latticeconstant=3.5 if a0 is None else a0,
#                                directions=x),
#              LJCut(epsilon=10.2, sigma=2.28, cutoff=5.0, shift=True) ),
            ( lambda a0,x : FaceCenteredCubic('Au', size=[1,1,1],
                                              latticeconstant=a0, directions=x),
              TabulatedAlloyEAM(fn='Au-Grochola-JCP05.eam.alloy') ),
            ( lambda a0,x : Diamond('Si', size=[1,1,1], latticeconstant=a0,
                                    directions=x),
              Kumagai() )
            ]:

            a = make_atoms(None, [[1,0,0], [0,1,0], [0,0,1]])
            a.set_calculator(calc)
            FIRE(StrainFilter(a, mask=[1,1,1,0,0,0]), logfile=None) \
                .run(fmax=self.fmax)
            latticeconstant = np.mean(a.cell.diagonal())

            C6 = measure_triclinic_elastic_constants(a, delta=self.delta,
                                                     fmax=self.fmax)
            C11, C12, C44 = Voigt_6x6_to_cubic(C6)/GPa

            el = CubicElasticModuli(C11, C12, C44)

            C_m = measure_triclinic_elastic_constants(a, delta=self.delta,
                                                      fmax=self.fmax)/GPa
            self.assertArrayAlmostEqual(el.stiffness(), C_m, tol=0.01)

            for directions in [ [[1,0,0], [0,1,0], [0,0,1]],
                                [[0,1,0], [0,0,1], [1,0,0]],
                                [[1,1,0], [0,0,1], [1,-1,0]],
                                [[1,1,1], [-1,-1,2], [1,-1,0]] ]:
                a, b, c = directions

                directions = np.array([ np.array(x)/np.linalg.norm(x) 
                                        for x in directions ])
                a = make_atoms(latticeconstant, directions)
                a.set_calculator(calc)

                C = el.rotate(directions)
                C_check = el._rotate_explicit(directions)
                self.assertArrayAlmostEqual(C, C_check, tol=1e-6)

                C_m = measure_triclinic_elastic_constants(a, delta=self.delta,
                                                          fmax=self.fmax)/GPa

                self.assertArrayAlmostEqual(C, C_m, tol=1e-2)

###

if __name__ == '__main__':
    unittest.main()

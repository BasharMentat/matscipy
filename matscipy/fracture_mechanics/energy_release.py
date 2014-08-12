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

import numpy as np

###

def J_integral(a, deformation_gradient, virial, epot, e0, tip_x, tip_y, r1, r2):
    """
    Compute the energy release rate from the J-integral. Converts contour
    integral into a domain integral.
    See: Li, Shih, Needleman, Eng. Fract. Mech. 21, 405 (1985);
    Jin, Yuan, J. Nanosci. Nanotech. 5, 2099 (2005)
    Domain function is currently fixed: q(r) = (r-r1)/(r2-r1)

    Parameters
    ----------
    a : ase.Atoms
        Relaxed atomic configuration of the crack.
    deformation_gradient : array_like
        len(a) x 3x3 array of atomic deformation gradients.
    virial : array_like
        len(a) x 3x3 array of atomic virials.
    e0 : float
        Reference energy (cohesive energy per atom of the bulk crystal at
        equilibrium).
    tip_x, tip_y : float
        Position of the crack tip.
    r1, r2 : float
        Volume integration is carried out in region at a distance between r1
        and r2 from the crack tip.

    Returns
    -------
    J : float
        Value of the J-integral.
    """

    # Cell size
    sx, sy, sz = a.cell.diagonal()

    # Positions
    x, y, z = a.positions.T.copy()
    x -= tip_x
    y -= tip_y
    r = np.sqrt(x**2+y**2)

    # Derivative of the domain function q
    nonzero = np.logical_and(r > r1, r < r2)
    gradq = np.transpose([
            np.where(nonzero,
                     x/((r2-r1)*r),
                     np.zeros_like(x)),
            np.where(nonzero,
                     y/((r2-r1)*r),
                     np.zeros_like(y)),
            np.zeros_like(z)])

    # Potential energy
    epot = ((epot-e0)*gradq[:,0]).sum()

    # Strain energy
    estrain = np.einsum('aij,ai,aj->', virial, deformation_gradient[:,0,:],
                        gradq)

    # Compute J-integral
    return (epot-estrain)/sz


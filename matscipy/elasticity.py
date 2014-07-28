# ======================================================================
# matscipy - Python materials science tools
# https://github.com/libAtoms/matscipy
#
# Copyright (2014) Lars Pastewka, Karlsruhe Institute of Technology
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
from numpy.linalg import inv

###

class CubicElasticModuli:
    tol = 1e-6

    # The indices of the full stiffness matrix of (orthorhombic) interest
    t = [(0, 0, 0, 0), (1, 1, 1, 1), (2, 2, 2, 2),  # C11
         (1, 1, 2, 2), (0, 0, 2, 2), (0, 0, 1, 1),  # C12
         (1, 2, 1, 2), (0, 2, 0, 2), (0, 1, 0, 1)]  # C44

    def __init__(self, C11, C12, C44):
        """
        Initialize a cubic system with elastic constants C11, C12, C44
        """

        self.C11 = C11
        self.C12 = C12
        self.C44 = C44

        self.la = C12
        self.mu = C44
        self.al = C11 - self.la - 2*self.mu

        A = np.eye(3, dtype=float)

        # Compute initial stiffness matrix
        self.rotate(A)


    def rotate(self, A):
        """
        Compute the rotated stiffness matrix
        """

        A = np.asarray(A)

        # Is this a rotation matrix?
        if np.sometrue(np.abs(np.dot(np.array(A), np.transpose(np.array(A))) - 
                              np.eye(3, dtype=float)) > self.tol):
            raise RuntimeError('Matrix *A* does not describe a rotation.')

        C = [ ]
        for i, j, k, m in self.t:
            h = 0.0
            if i == j and k == m:
                h += self.la
            if i == k and j == m:
                h += self.mu
            if i == m and j == k:
                h += self.mu
            h += self.al*np.sum(A[i,:]*A[j,:]*A[k,:]*A[m,:])
            C += [ h ]

        self.C11_rot = np.array(C[0:3])
        self.C12_rot = np.array(C[3:6])
        self.C44_rot = np.array(C[6:9])

        return self.C11_rot, self.C12_rot, self.C44_rot


    def _rotate_explicit(self, A):
        """
        Compute the rotated stiffness matrix by applying the rotation to the
        full stiffness matrix. This function is for debugging purposes only.
        """

        A = np.asarray(A)

        # Is this a rotation matrix?
        if np.sometrue(np.abs(np.dot(np.array(A), np.transpose(np.array(A))) - 
                              np.eye(3, dtype=float) ) > self.tol):
            raise RuntimeError('Matrix *A* does not describe a rotation.')

        C = np.zeros((3, 3, 3, 3), dtype=float)

        # Construct unrotated stiffness matrix
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for m in range(3):
                        h = 0.0
                        if i == j and k == m:
                            h += self.la
                        if i == k and j == m:
                            h += self.mu
                        if i == m and j == k:
                            h += self.mu
                        if i == j and j == k and k == m:
                            h += self.al
                        C[i, j, k, m] = h

        # Rotate
        C = np.einsum('ia,jb,kc,ld,abcd->ijkl', A, A, A, A, C)

        C9 = [ ]
        for i, j, k, m in self.t:
            C9 += [ C[i,j,k,m] ]

        self.C11_rot = np.array(C9[0:3])
        self.C12_rot = np.array(C9[3:6])
        self.C44_rot = np.array(C9[6:9])

        return self.C11_rot, self.C12_rot, self.C44_rot


    def stiffness_matrix(self):
        """
        Return the elastic constants
        """

        t = [(0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1)]

        C6 = np.zeros((6, 6), dtype=float)

        for a in range(6):
            for b in range(6):
                i, j = t[a]
                k, l = t[b]

                C6[a, b] = self.C[i, j, k, l]

        if np.sometrue(np.abs(C6 - np.transpose(C6)) > self.tol):
            raise RuntimeError('C6 not symmetric.')

        return C6


    def stiffness(self):
        """
        Return the elastic constants
        """

        return self.C11_rot, self.C12_rot, self.C44_rot


    def compliance(self):
        """
        Return the compliance coefficients
        """

        raise NotImplementedError

###
    
def measure_orthorhombic_elastic_moduli(a, delta=0.001, optimizer=None, 
                                        logfile=None, **kwargs):
    """
    Measure elastic constant for an orthorhombic unit cell

    Parameters:
    -----------
    a           ase.Atoms object
    optimizer   Optimizer to use for atomic position. Does not optimize atomic
                position if set to None.
    delta         Strain increment for analytical derivatives of stresses.
    """

    if optimizer is not None:
        optimizer(a, logfile=logfile).run(**kwargs)

    r0 = a.positions.copy()

    cell = a.cell
    s0 = a.get_stress()

    # C11
    C11 = [ ]
    for i in range(3):
        a.set_cell(cell, scale_atoms=True)
        a.set_positions(r0)
        
        D = np.eye(3)
        D[i, i] = 1.0+delta
        a.set_cell(np.dot(D, cell), scale_atoms=True)
        if optimizer is not None:
            optimizer(a, logfile=logfile).run(**kwargs)
        s = a.get_stress()
            
        C11 += [ (s[i]-s0[i])/delta ]

    volfac = 1.0/((1-delta**2)**(1./3))

    # C'
    Cp = [ ] 
    for i in range(3):
        a.set_cell(cell, scale_atoms=True)
        a.set_positions(r0)
        
        D = volfac*np.eye(3)
        j = (i+1)%3
        k = (i+2)%3
        D[j, j] *= 1+delta
        D[k, k] *= 1-delta
        a.set_cell(np.dot(D, cell), scale_atoms=True)
        if optimizer is not None:
            optimizer(a, logfile=logfile).run(**kwargs)
        s = a.get_stress()

        Cp += [ ((s[j]-s0[j])-(s[k]-s0[k]))/(4*delta) ]

    # C44
    C44 = [ ]
    for i in range(3):
        a.set_cell(cell, scale_atoms=True)
        a.set_positions(r0)

        D = volfac*np.eye(3)
        j = (i+1)%3
        k = (i+2)%3
        D[j, k] = volfac*delta
        D[k, j] = volfac*delta
        a.set_cell(np.dot(D, cell), scale_atoms=True)
        if optimizer is not None:
            optimizer(a, logfile=logfile).run(**kwargs)
        s = a.get_stress()

        C44 += [ (s[3+i]-s0[3+i])/(2*delta) ]

    a.set_cell(cell, scale_atoms=True)
    a.set_positions(r0)

    C11 = np.array(C11)
    Cp = np.array(Cp)
    C44 = np.array(C44)

    # Compute C12 from C11 and C'
    C12 = np.array([C11[1]+C11[2], C11[0]+C11[2], C11[0]+C11[1]])/2-2*Cp

    return C11, C12, C44

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

import math
import warnings

import numpy as np
try:
    from scipy.optimize import brentq, leastsq
except ImportError:
    warnings.warn('Warning: no scipy')

from ase.calculators.neighborlist import NeighborList    

from matscipy.elasticity import CubicElasticModuli
from matscipy.surface import MillerDirection, MillerPlane

###

# Constants
PLANE_STRAIN = 'plane strain'
PLANE_STRESS = 'plane stress'

###

class RectilinearAnisotropicCrack:
    """
    Near field solution for a crack in a rectilinear anisotropic elastic medium.
    See:
    G. C. Sih, P. C. Paris and G. R. Irwin, Int. J. Frac. Mech. 1, 189 (1965)
    """
    def __init__(self):
        self.a11 = None
        self.a22 = None
        self.a12 = None
        self.a16 = None
        self.a26 = None
        self.a66 = None


    def set_plane_stress(self, a11, a22, a12, a16, a26, a66):
        self.a11 = a11
        self.a22 = a22
        self.a12 = a12
        self.a16 = a16
        self.a26 = a26
        self.a66 = a66

        self._init_crack()


    def set_plane_strain(self, b11, b22, b33, b12, b13, b23, b16, b26, b36, 
                         b66):
        self.a11 = b11 - (b13*b13)/b33
        self.a22 = b22 - (b23*b23)/b33
        self.a12 = b12 - (b13*b23)/b33
        self.a16 = b16 - (b13*b36)/b33
        self.a26 = b26 - (b23*b36)/b33
        self.a66 = b66

        self._init_crack()


    def _init_crack(self):
        """
        Initialize dependend parameters.
        """
        p = np.poly1d( [ self.a11, -2*self.a16, 2*self.a12+self.a66,
                         -2*self.a26, self.a22 ] )

        mu1, mu2, mu3, mu4 = p.r

        if mu1 != mu2.conjugate():
            raise RuntimeError('Roots not in pairs.')

        if mu3 != mu4.conjugate():
            raise RuntimeError('Roots not in pairs.')

        self.mu1 = mu1
        self.mu2 = mu3

        self.p1  = self.a11*(self.mu1**2) + self.a12 - self.a16*self.mu1
        self.p2  = self.a11*(self.mu2**2) + self.a12 - self.a16*self.mu2

        self.q1  = self.a12*self.mu1 + self.a22/self.mu1 - self.a26
        self.q2  = self.a12*self.mu2 + self.a22/self.mu2 - self.a26

        self.h1 = 1/(self.mu1 - self.mu2)
        self.h2 = self.mu1 * self.p2
        self.h3 = self.mu2 * self.p1
        self.h4 = self.mu1 * self.q2
        self.h5 = self.mu2 * self.q1


    def displacements(self, r, theta, k):
        """
        Displacement field in mode I fracture.
        """

        h1 = k * np.sqrt(2.0*r/math.pi)

        h2 = np.sqrt( np.cos(theta) + self.mu2*np.sin(theta) )
        h3 = np.sqrt( np.cos(theta) + self.mu1*np.sin(theta) )

        u = h1 * ( self.h1 * ( self.h2 * h2 - self.h3 * h3 ) ).real
        v = h1 * ( self.h1 * ( self.h4 * h2 - self.h5 * h3 ) ).real

        return u, v


    def _f(self, theta, v):
        h2 = ( cos(theta) + self.mu2*sin(theta) )**0.5
        h3 = ( cos(theta) + self.mu1*sin(theta) )**0.5

        return v - ( self.h2 * h2 - self.h3 * h3 ).real/ \
            ( self.h4 * h2 - self.h5 * h3 ).real


    def rtheta(self, u, v, k):
        """
        Invert displacement field in mode I fracture, i.e. compute r and theta
        from displacements.
        """

        # u/v = (self.h2*h2 - self.h3*h3)/(self.h4*h2-self.h5*h3)
        theta = brentq(self._f, -pi, pi, args=(u/v))

        h1 = k * sqrt(2.0*r/math.pi)

        h2 = ( cos(theta) + self.mu2*sin(theta) )**0.5
        h3 = ( cos(theta) + self.mu1*sin(theta) )**0.5

        sqrt_2_r = ( self.h1 * ( self.h2 * h2 - self.h3 * h3 ) ).real/k
        r1 = sqrt_2_r**2/2
        sqrt_2_r = ( self.h1 * ( self.h4 * h2 - self.h5 * h3 ) ).real/k
        r2 = sqrt_2_r**2/2

        return ( (r1+r2)/2, theta )


    def k1g(self, surface_energy):
        """
        K1G, Griffith critical stress intensity in mode I fracture
        """

        return math.sqrt(-4*surface_energy / \
                         (self.a22*
                          ((self.mu1+self.mu2)/(self.mu1*self.mu2)).imag))


    def k1gsqG(self):
        return -2/(self.a22*((self.mu1+self.mu2)/(self.mu1*self.mu2)).imag)

###

class CubicCrystalCrack:
    """
    Crack in a cubic crystal.
    """

    def __init__(self, C11, C12, C44, crack_surface, crack_front,
                 stress_state = PLANE_STRAIN):
        """
        Initialize a crack in a cubic crystal with elastic constants C11, C12
        and C44. The crack surface is given by crack_surface, the cracks runs
        in the plane given by crack_front.
        """
        self.E = CubicElasticModuli(C11, C12, C44)

        # x (third_dir) - direction in which the crack is running
        # y (crack_surface) - free surface that forms due to the crack
        # z (crack_front) - direction of the crack front
        third_dir = np.cross(crack_surface, crack_front)
        third_dir = np.array(third_dir) / np.sqrt(np.dot(third_dir,
                                                         third_dir))
        crack_surface = np.array(crack_surface) / \
            np.sqrt(np.dot(crack_surface, crack_surface))
        crack_front = np.array(crack_front) / \
            np.sqrt(np.dot(crack_front, crack_front))

        A = np.array([third_dir, crack_surface, crack_front])
        if np.linalg.det(A) < 0:
            third_dir = -third_dir
        A = np.array([third_dir, crack_surface, crack_front])

        self.E.rotate(A)

        self.crack = RectilinearAnisotropicCrack()

        S6 = self.E.compliance()

        if stress_state == PLANE_STRESS:
            self.crack.set_plane_stress(S6[0, 0], S6[1, 1], S6[0, 1],
                                        S6[0, 5], S6[1, 5], S6[5, 5])
        elif stress_state == PLANE_STRAIN:
            self.crack.set_plane_strain(S6[0, 0], S6[1, 1], S6[2, 2],
                                        S6[0, 1], S6[0, 2], S6[1, 2],
                                        S6[0, 5], S6[1, 5], S6[2, 5],
                                        S6[5, 5])


    def k1g(self, surface_energy):
        """
        Compute Griffith critical stress intensity in mode I fracture.

        Parameters
        ----------
        surface_energy : float
            Surface energy of the respective crystal surface.

        Returns
        -------
        k1g : float
            Stress intensity factor.
        """
        return self.crack.k1g(surface_energy)

    
    def k1gsqG(self):
        return self.crack.k1gsqG()


    def displacements_from_cylinder_coordinates(self, r, theta, k):
        """
        Displacement field in mode I fracture from cylindrical coordinates.
        """
        return self.crack.displacements(r, theta, k)


    def displacements_from_cartesian_coordinates(self, dx, dz, k):
        """
        Displacement field in mode I fracture from cartesian coordinates.
        """
        abs_dr = np.sqrt(dx*dx+dz*dz)
        theta = np.arctan2(dz, dx)
        return self.displacements_from_cylinder_coordinates(abs_dr, theta, k)


    def displacements(self, ref_x, ref_y, x0, y0, k):
        """
        Displacement field for a list of cartesian positions.

        Parameters
        ----------
        ref_x : array_like
            x-positions of the reference crystal.
        ref_y : array_like
            y-positions of the reference crystal.
        x0 : float
            x-coordinate of the crack tip.
        y0 : float
            y-coordinate of the crack tip.
        k : float
            Stress intensity factor.
        
        Returns
        -------
        ux : array_like
            x-displacements.
        uy : array_like
            y-displacements.
        """
        dx = ref_x - x0
        dy = ref_y - y0
        ux, uy = self.displacements_from_cartesian_coordinates(dx, dy, k)
        return ux, uy


    def displacement_residuals(self, x, y, ref_x, ref_y, x0, y0, k):
        """
        Return actual displacement field minus ideal displacement field.
        """
        u1x = x - ref_x
        u1y = y - ref_y
        u2x, u2y = self.displacements(ref_x, ref_y, x0, y0, k)
        return u1x - u2x, u1y - u2y


    def _residual(self, r0, x, y, ref_x, ref_y, k, mask):
        x0, y0 = r0
        dux, duy = self.displacement_residuals(x, y, ref_x, ref_y, x0, y0, k)
        return dux[mask]*dux[mask]+duy[mask]*duy[mask]


    def crack_tip_position(self, x, y, ref_x, ref_y, x0, y0, k, mask=None):
        """
        Return an estimate of the real crack tip position assuming the stress
        intensity factor is k.

        Parameters
        ----------
        x : array_like
            x-positions of the atomic system containing the crack.
        y : array_like
            y-positions of the atomic system containing the crack.
        ref_x : array_like
            x-positions of the reference crystal.
        ref_y : array_like
            y-positions of the reference crystal.
        x0 : float
            Initial guess for the x-coordinate of the crack tip.
        y0 : float
            Initial guess for the y-coordinate of the crack tip.
        k : float
            Stress intensity factor.
        mask : array_like, optional
            Marks the atoms to use for this calculation.

        Returns
        -------
        x0 : float
            x-coordinate of the crack tip.
        y0 : float
            y-coordinate of the crack tip.
        """
        if mask is None:
            mask = np.ones(len(a), dtype=bool)
        ( x0, y0 ), ier = leastsq(self._residual, ( x0, y0 ),
                                  args=(x, y, ref_x, ref_y, k, mask))
        if ier not in [ 1, 2, 3, 4 ]:
            raise RuntimeError('Could not find crack tip')
        return x0, y0


    def _residual_z(self, y0, x0, x, y, ref_x, ref_y, k, mask):
        dux, duy = self.displacement_residuals(x, y, ref_x, ref_y, x0, y0, k)
        return dux[mask]*dux[mask]+duy[mask]*duy[mask]


    def crack_tip_position_y(self, x, y, ref_x, ref_y, x0, y0, k, mask=None):
        """
        Return an estimate of the y-coordinate of the real crack tip position 
        assuming the stress intensity factor is k.

        Parameters
        ----------
        x : array_like
            x-positions of the atomic system containing the crack.
        y : array_like
            y-positions of the atomic system containing the crack.
        ref_x : array_like
            x-positions of the reference crystal.
        ref_y : array_like
            y-positions of the reference crystal.
        x0 : float
            Initial guess for the x-coordinate of the crack tip.
        y0 : float
            Initial guess for the y-coordinate of the crack tip.
        k : float
            Stress intensity factor.
        mask : array_like, optional
            Marks the atoms to use for this calculation.

        Returns
        -------
        y0 : float
            y-coordinate of the crack tip
        """
        if mask is None:
            mask = np.ones(len(a), dtype=bool)
        ( y0, ), ier = leastsq(self._residual_z, y0,
                          args=(x0, x, y, ref_x, ref_y, k, mask))
        if ier not in [ 1, 2, 3, 4 ]:
            raise RuntimeError('Could not find crack tip')
        return y0


    def scale_displacements(self, x, y, ref_x, ref_y, old_k, new_k):
        """
        Rescale atomic positions from stress intensity factor old_k to the new
        stress intensity factor new_k. This is useful for extrapolation of 
        relaxed positions.

        Parameters
        ----------
        x : array_like
            x-positions of the atomic system containing the crack.
        y : array_like
            y-positions of the atomic system containing the crack.
        ref_x : array_like
            x-positions of the reference crystal.
        ref_y : array_like
            y-positions of the reference crystal.
        old_k : float
            Current stress intensity factor.
        new_k : float
            Stress intensity factor for the output positions.

        Returns
        -------
        x : array_like
            New x-positions of the atomic system containing the crack.
        y : array_like
            New y-positions of the atomic system containing the crack.
        """
        return ref_x + new_k/old_k*(x-ref_x), ref_y + new_k/old_k*(y-ref_y)




def isotropic_modeI_crack_tip_stress_field(K, r, t, xy_only=True,
                                           nu=0.5, stress_state=PLANE_STRAIN):
    """
    Compute Irwin singular crack tip stress field for mode I fracture.

    Parameters
    ----------
    K : float
       Mode I stress intensity factor. Units should match units of `r`.
    r : array_like
       Radial distances from crack tip. Can be a multidimensional
       array to evaluate stress field on a grid.
    t : array_like
       Angles from horzontal line y=0 ahead of crack tip,
       measured anticlockwise. Should have same shape as `r`.
    xy_only : bool
       If True (default) only xx, yy, xy and yx components will be set.
    nu : float
       Poisson ratio. Used only when ``xy_only=False``, to determine zz stresses
    stress_state : str
       One of"plane stress" or "plane strain". Used if xyz_only=False to
       determine zz stresses.
       
    Returns
    -------
    sigma : array with shape ``r.shape + (3,3)``
    """

    if r.shape != t.shape:
        raise ValueError('Shapes of radial and angular arrays "r" and "t" '
                         'must match.')
    
    if stress_state not in [PLANE_STRAIN, PLANE_STRESS]:
        raise ValueError('"stress_state" should be either "{0}" or "{1}".'
            .format(PLANE_STRAIN, PLANE_STRESS))

    sigma = np.zeros(r.shape + (3, 3))
    radial = K/np.sqrt(2*math.pi*r)

    sigma[...,0,0] = radial*np.cos(t/2.0)*(1.0 - np.sin(t/2.0)*np.sin(3.0*t/2.0)) # xx
    sigma[...,1,1] = radial*np.cos(t/2.0)*(1.0 + np.sin(t/2.0)*np.sin(3.0*t/2.0)) # yy
    sigma[...,0,1] = radial*np.sin(t/2.0)*np.cos(t/2.0)*np.cos(3.0*t/2.0)         # xy
    sigma[...,1,0] = sigma[...,0,1]                                               # yx=xy

    if not xy_only and stress_state == PLANE_STRAIN:
        sigma[...,2,2] = nu*(sigma[...,0,0] + sigma[...,1,1])              # zz

    return sigma
    
    
def isotropic_modeI_crack_tip_displacement_field(K, G, nu, r, t,
                                                 stress_state=PLANE_STRAIN):
    """
    Compute Irwin singular crack tip displacement field for mode I fracture.

    Parameters
    ----------
    K : float
        Mode I stress intensity factor. Units should match units of `G` and `r`.
    G : float
        Shear modulus. Units should match units of `K` and `r`.
    nu : float
        Poisson ratio.
    r : array_like
        Radial distances from crack tip. Can be a multidimensional
        array to evaluate stress field on a grid.
    t : array_like
        Angles from horizontal line y=0 ahead of crack tip,
        measured anticlockwise. Should have same shape as `r`.
    stress_state : str
        One of"plane stress" or "plane strain". Used if xyz_only=False to
        determine zz stresses.
       
    Returns
    -------
    u : array
    v : array
        Displacements. Same shape as `r` and `t`.
    """

    if r.shape != t.shape:
        raise ValueError('Shapes of radial and angular arrays "r" and "t" '
                         'must match.')
    
    if stress_state == PLANE_STRAIN:
        kappa = 3-4*nu
    elif stress_state == PLANE_STRESS:
        kappa = (3.-nu)/(1.+nu)
    else:
        raise ValueError('"stress_state" should be either "{0}" or "{1}".'
            .format(PLANE_STRAIN, PLANE_STRESS))

    radial = K*np.sqrt(r/(2.*math.pi))/(2.*G)
    u = radial*np.cos(t/2)*(kappa-1+2*np.sin(t/2)**2)
    v = radial*np.sin(t/2)*(kappa+1-2*np.cos(t/2)**2)

    # Form in Lawn book is equivalent:
    #radial = K/(4*G)*np.sqrt(r/(2.*math.pi))
    #u = radial*((2*kappa - 1)*np.cos(t/2) - np.cos(3*t/2))
    #v = radial*((2*kappa + 1)*np.sin(t/2) - np.sin(3*t/2))

    return u, v


class IsotropicStressField(object):
    """
    Calculator to return Irwin near-tip stress field at atomic sites
    """
    def __init__(self, K=None, x0=None, y0=None, sxx0=0.0, syy0=0., sxy0=0., nu=0.5,
                 stress_state='plane strain'):
        self.K = K
        self.x0 = x0
        self.y0 = y0
        self.sxx0 = sxx0
        self.syy0 = syy0
        self.sxy0 = sxy0
        self.nu = nu
        self.stress_state = stress_state

    def get_stresses(self, atoms):
        K = self.K
        if K is None:
            K = get_stress_intensity_factor(atoms)

        x0, y0 = self.x0, self.y0
        if x0 is None:
            x0 = atoms.info['CrackPos'][0]
        if y0 is None:
            y0 = atoms.info['CrackPos'][1]
            
        x = atoms.positions[:, 0]
        y = atoms.positions[:, 1]
        r = np.sqrt((x - x0)**2 + (y - y0)**2)
        t = np.arctan2(y - y0, x - x0)
        
        sigma = irwin_modeI_crack_tip_stress_field(K, r, t, self.nu,
                                                   self.stress_state)
        sigma[:,0,0] += self.sxx0
        sigma[:,1,1] += self.syy0
        sigma[:,0,1] += self.sxy0
        sigma[:,1,0] += self.sxy0

        return sigma
    

def strain_to_G(strain, E, nu, orig_height):
    """
    Convert from strain to energy release rate G for thin strip geometry

    Parameters
    ----------
    strain : float
       Dimensionless ratio ``(current_height - orig_height)/orig_height``
    E : float
       Young's modulus relevant for a pull in y direction sigma_yy/eps_yy
    nu : float
       Poission ratio -eps_yy/eps_xx
    orig_height : float
       Unstrained height of slab

    Returns
    -------
    G : float
       Energy release rate in units consistent with input
       (i.e. in eV/A**2 if eV/A/fs units used)
    """
    return 0.5 * E / (1.0 - nu * nu) * strain * strain * orig_height


def G_to_strain(G, E, nu, orig_height):
    """
    Convert from energy release rate G to strain for thin strip geometry

    Parameters
    ----------
    G : float
       Energy release rate in units consistent with `E` and `orig_height`
    E : float
       Young's modulus relevant for a pull in y direction sigma_yy/eps_yy
    nu : float
       Poission ratio -eps_yy/eps_xx
    orig_height : float
       Unstrained height of slab

    Returns
    -------
    strain : float
       Dimensionless ratio ``(current_height - orig_height)/orig_height``
    """
    return sqrt(2.0 * G * (1.0 - nu * nu) / (E * orig_height))


def get_strain(atoms):
    """
    Return the current strain on thin strip configuration `atoms`

    Requires unstrained height of slab to be stored as ``OrigHeight``
    key in ``atoms.info`` dictionary.

    Also updates value stored in ``atoms.info``.
    """
    
    orig_height = atoms.info['OrigHeight']
    current_height = atoms.positions[:, 1].max() - atoms.positions[:, 1].min()
    strain = current_height / orig_height - 1.0
    atoms.info['strain'] = strain
    return strain


def get_energy_release_rate(atoms):
    """
    Return the current energy release rate G for `atoms

    Also updates value stored in ``atoms.info`` dictionary.
    """
    
    current_strain = get_strain(atoms)
    orig_height = atoms.info['OrigHeight']
    E = atoms.info['YoungsModulus']
    nu = atoms.info['PoissonRatio_yx']
    G = strain_to_G(current_strain, E, nu, orig_height)
    atoms.info['G'] = G
    return G


def get_stress_intensity_factor(atoms):
    """
    Return stress intensity factor K_I

    Also updates value stored in ``atoms.info`` dictionary.
    """

    G = get_energy_release_rate(atoms)
    
    E = atoms.info['YoungsModulus']
    nu = atoms.info['PoissonRatio_yx']

    Ep = E/(1-nu**2)
    K = sqrt(G*Ep)
    atoms.info['K'] = K
    return K


def fit_crack_stress_field(atoms, r_range=(0., 50.), initial_params=None, fix_params=None,
                           sigma=None, avg_sigma=None, avg_decay=0.005, calc=None, verbose=False):
    """
    Perform a least squares fit of near-tip stress field to Irwin solution

    Stresses on the atoms are fit to the Irwin K-field singular crack tip
    solution, allowing the crack position, stress intensity factor and
    far-field stress components to vary during the fit.

    Parameters
    ----------
    atoms : :class:`~.Atoms` object
       Crack system. For the initial fit, the following keys are used
       from the :attr:`~Atoms.info` dictionary:

          - ``YoungsModulus``
          - ``PossionRatio_yx``
          - ``G`` --- current energy release rate
          - ``strain`` --- current applied strain
          - ``CrackPos`` --- initial guess for crack tip position

       The initial guesses for the stress intensity factor ``K`` and
       far-field stress ``sigma0`` are computed from
       ``YoungsModulus``, ``PoissonRatio_yx``, ``G`` and ``strain``,
       assuming plane strain in thin strip boundary conditions.

       On exit, new ``K``, ``sigma0`` and ``CrackPos`` entries are set
       in the :attr:`~Atoms.info` dictionary. These values are then
       used as starting guesses for subsequent fits.

    r_range : sequence of two floats, optional
       If present, restrict the stress fit to an annular region
       ``r_range[0] <= r < r_range[1]``, centred on the previous crack
       position (from the ``CrackPos`` entry in ``atoms.info``). If
       r_range is ``None``, fit is carried out for all atoms.

    initial_params : dict
       Names and initial values of parameters. Missing initial values
       are guessed from Atoms object.

    fix_params : dict
       Names and values of parameters to fix during the fit,
       e.g. ``{y0: 0.0}`` to constrain the fit to the line y=0

    sigma : None or array with shape (len(atoms), 3, 3)
       Explicitly provide the per-atom stresses. Avoids calling Atoms'
       calculators :meth:`~.get_stresses` method.

    avg_sigma : None or array with shape (len(atoms), 3, 3)
       If present, use this array to accumulate the time-averaged
       stress field. Useful when processing a trajectory.

    avg_decay : real
       Factor by which average stress is attenuated at each step.
       Should be set to ``dt/tau`` where ``dt`` is MD time-step
       and ``tau`` is a characteristic averaging time.

    calc : Calculator object, optional
       If present, override the calculator used to compute stresses
       on the atoms. Default is ``atoms.get_calculator``.

       To use the atom resolved stress tensor pass an instance of the 
       :class:`~quippy.elasticity.AtomResolvedStressField` class.

    verbose : bool, optional
       If set to True, print additional information about the fit.

    Returns
    -------
    params : dict with keys ``[K, x0, y0, sxx0, syy0, sxy0]``
       Fitted parameters, in a form suitable for passin
       :class:`IrwinStressField` constructor. These are the stress intensity
       factor `K`, the centre of the stress field ``(x0, y0)``, and the
       far field contribution to the stress ``(sxx0, syy0, sxy0)``.
    """

    params = {}
    if initial_params is not None:
       params.update(initial_params)

    if 'K' not in params:
       # Guess for stress intensity factor K
       if 'K' in atoms.info:
           params['K'] = atoms.info['K']
       else:
           try:
               params['K'] = get_stress_intensity_factor(atoms)
           except KeyError:
               params['K'] = 1.0*MPA_SQRT_M

    if 'sxx0' not in params or 'syy0' not in params or 'sxy0' not in params:
       # Guess for far-field stress
       if 'sigma0' in atoms.info:
          params['sxx0'], params['syy0'], params['sxy0'] = atoms.info['sigma0']
       else:
          try:
              E = atoms.info['YoungsModulus']
              nu = atoms.info['PoissonRatio_yx']
              Ep = E/(1-nu**2)
              params['syy0'] = Ep*atoms.info['strain']
              params['sxx0'] = nu*params['syy0']
              params['sxy0'] = 0.0
          except KeyError:
              params['syy0'] = 0.0
              params['sxx0'] = 0.0
              params['sxy0'] = 0.0

    if 'x0' not in params or 'y0' not in params:
       # Guess for crack position
       try:
           params['x0'], params['y0'], _ = atoms.info['CrackPos']
       except KeyError:
           params['x0'] = (atoms.positions[:, 0].min() +
                           (atoms.positions[:, 0].max() - atoms.positions[:, 0].min())/3.0)
           params['y0'] = 0.0

    # Override any fixed parameters
    if fix_params is None:
       fix_params = {}
    params.update(fix_params)

    x = atoms.positions[:, 0]
    y = atoms.positions[:, 1]
    r = np.sqrt((x - params['x0'])**2 + (y - params['y0'])**2)

    # Get local stresses
    if sigma is None:
       if calc is None:
           calc = atoms.get_calculator()
       sigma = calc.get_stresses(atoms)

    # Update avg_sigma in place
    if avg_sigma is not None:
       avg_sigma[...] = np.exp(-avg_decay)*avg_sigma + (1.0 - np.exp(-avg_decay))*sigma
       sigma = avg_sigma.copy()

    # Zero components out of the xy plane
    sigma[:,2,2] = 0.0
    sigma[:,0,2] = 0.0
    sigma[:,2,0] = 0.0
    sigma[:,1,2] = 0.0
    sigma[:,2,1] = 0.0

    mask = Ellipsis # all atoms
    if r_range is not None:
        rmin, rmax = r_range
        mask = (r > rmin) & (r < rmax)

    if verbose:
       print 'Fitting on %r atoms' % sigma[mask,1,1].shape
    
    def objective_function(params, x, y, sigma, var_params):
        params = dict(zip(var_params, params))
        if fix_params is not None:
            params.update(fix_params)
        irwin_sigma = IrwinStressField(**params).get_stresses(atoms)
        delta_sigma = sigma[mask,:,:] - irwin_sigma[mask,:,:]
        return delta_sigma.reshape(delta_sigma.size)

    # names and values of parameters which can vary in this fit
    var_params = sorted([key for key in params.keys() if key not in fix_params.keys() ])
    initial_params = [params[key] for key in var_params]

    from scipy.optimize import leastsq
    fitted_params, cov, infodict, mesg, success = leastsq(objective_function,
                                                         initial_params,
                                                         args=(x, y, sigma, var_params),
                                                         full_output=True)

    params = dict(zip(var_params, fitted_params))
    params.update(fix_params)

    # estimate variance in parameter estimates
    if cov is None:
       # singular covariance matrix
       err = dict(zip(var_params, [0.]*len(fitted_params)))
    else:
       s_sq = (objective_function(fitted_params, x, y, sigma, var_params)**2).sum()/(sigma.size-len(fitted_params))
       cov = cov * s_sq
       err = dict(zip(var_params, np.sqrt(np.diag(cov))))
    
    if verbose:
       print 'K = %.3f MPa sqrt(m)' % (params['K']/MPA_SQRT_M)
       print 'sigma^0_{xx,yy,xy} = (%.1f, %.1f, %.1f) GPa' % (params['sxx0']*GPA,
                                                              params['syy0']*GPA,
                                                              params['sxy0']*GPA)
       print 'Crack position (x0, y0) = (%.1f, %.1f) A' % (params['x0'], params['y0'])

    atoms.info['K'] = params['K']
    atoms.info['sigma0'] = (params['sxx0'], params['syy0'], params['sxy0'])
    atoms.info['CrackPos'] = np.array((params['x0'], params['y0'], atoms.cell[2,2]/2.0))

    return params, err


def find_tip_coordination(a, bondlength=2.6, bulk_nn=4):
    """
    Find position of tip in crack cluster from coordination
    """
    nl = NeighborList([bondlength/2.0]*len(a),
                      self_interaction=False,
                      bothways=True)
    nl.update(a)
    nn = np.array([len(nl.get_neighbors(i)[0]) for i in range(len(a))])
    a.set_array('n_neighb', nn)
    g = a.get_array('groups')

    y = a.positions[:, 1]
    above = (nn < bulk_nn) & (g == 1) & (y > a.cell[1,1]/2.0)
    below = (nn < bulk_nn) & (g == 1) & (y < a.cell[1,1]/2.0)

    a.set_array('above', above)
    a.set_array('below', below)

    bond1 = above.nonzero()[0][a.positions[above, 0].argmax()]
    bond2 = below.nonzero()[0][a.positions[below, 0].argmax()]

    a.info['bond1'] = bond1
    a.info['bond2'] = bond2

    return (bond1, bond2)
    

def find_tip_stress_field(atoms, r_range=None, initial_params=None, fix_params=None,
                                sigma=None, avg_sigma=None, avg_decay=0.005, calc=None):
    """
    Find the position of the crack tip by fitting to the Irwin `K`-field solution

    Fit is carried out using :func:`fit_crack_stress_field`, and parameters
    have the same meaning as there.

    See also
    --------
    fit_crack_stress_field
    """

    params, err = fit_crack_stress_field(atoms, r_range, initial_params, fix_params, sigma,
                                         avg_sigma, avg_decay, calc)

    return np.array((params['x0'], params['y0'], atoms.cell[2,2]/2.0))
    

def plot_stress_fields(atoms, r_range=None, initial_params=None, fix_params=None,
                       sigma=None, avg_sigma=None, avg_decay=0.005, calc=None):
    """
    Fit and plot atomistic and continuum stress fields

    Firstly a fit to the Irwin `K`-field solution is carried out using
    :func:`fit_crack_stress_field`, and parameters have the same
    meaning as for that function. Then plots of the
    :math:`\sigma_{xx}`, :math:`\sigma_{yy}`, :math:`\sigma_{xy}`
    fields are produced for atomistic and continuum cases, and for the
    residual error after fitting.
    """

    from pylab import griddata, meshgrid, subplot, cla, contourf, colorbar, draw, title, clf, gca

    params, err = fit_crack_stress_field(atoms, r_range, initial_params, fix_params, sigma,
                                         avg_sigma, avg_decay, calc)

    K, x0, y0, sxx0, syy0, sxy0 = (params['K'], params['x0'], params['y0'],
                                   params['sxx0'], params['syy0'], params['sxy0'])
   
    x = atoms.positions[:, 0]
    y = atoms.positions[:, 1]

    X = np.linspace((x-x0).min(), (x-x0).max(), 500)
    Y = np.linspace((y-y0).min(), (y-y0).max(), 500)

    t = np.arctan2(y-y0, x-x0)
    r = np.sqrt((x-x0)**2 + (y-y0)**2)

    if r_range is not None:
       rmin, rmax = r_range
       mask = (r > rmin) & (r < rmax)
    else:
       mask = Ellipsis

    atom_sigma = sigma
    if atom_sigma is None:
       atom_sigma = atoms.get_stresses()

    grid_sigma = np.dstack([griddata(x[mask]-x0, y[mask]-y0, atom_sigma[mask,0,0], X, Y),
                            griddata(x[mask]-x0, y[mask]-y0, atom_sigma[mask,1,1], X, Y),
                            griddata(x[mask]-x0, y[mask]-y0, atom_sigma[mask,0,1], X, Y)])

    X, Y = meshgrid(X, Y)
    R = np.sqrt(X**2+Y**2)
    T = np.arctan2(Y, X)

    grid_sigma[((R < rmin) | (R > rmax)),:] = np.nan # mask outside fitting region

    irwin_sigma = irwin_modeI_crack_tip_stress_field(K, R, T, x0, y0)
    irwin_sigma[...,0,0] += sxx0
    irwin_sigma[...,1,1] += syy0
    irwin_sigma[...,0,1] += sxy0
    irwin_sigma[...,1,0] += sxy0
    irwin_sigma = ma.masked_array(irwin_sigma, mask=grid_sigma.mask)

    irwin_sigma[((R < rmin) | (R > rmax)),:,:] = np.nan # mask outside fitting region

    contours = [np.linspace(0, 20, 10),
                np.linspace(0, 20, 10),
                np.linspace(-10,10, 10)]

    dcontours = [np.linspace(0, 5, 10),
                np.linspace(0, 5, 10),
                np.linspace(-5, 5, 10)]

    clf()
    for i, (ii, jj), label in zip(range(3),
                                  [(0,0), (1,1), (0,1)],
                                  ['\sigma_{xx}', r'\sigma_{yy}', r'\sigma_{xy}']):
        subplot(3,3,i+1)
        gca().set_aspect('equal')
        contourf(X, Y, grid_sigma[...,i]*GPA, contours[i])
        colorbar()
        title(r'$%s^\mathrm{atom}$' % label)
        draw()

        subplot(3,3,i+4)
        gca().set_aspect('equal')
        contourf(X, Y, irwin_sigma[...,ii,jj]*GPA, contours[i])
        colorbar()
        title(r'$%s^\mathrm{Irwin}$' % label)
        draw()

        subplot(3,3,i+7)
        gca().set_aspect('equal')
        contourf(X, Y, abs(grid_sigma[...,i] -
                           irwin_sigma[...,ii,jj])*GPA, dcontours[i])
        colorbar()
        title(r'$|%s^\mathrm{atom} - %s^\mathrm{Irwin}|$' % (label, label))
        draw()



def thin_strip_displacement_y(x, y, strain, a, b):
    """
    Return vertical displacement ramp used to apply initial strain to slab

    Strain is increased from 0 to strain over distance :math:`a <= x <= b`.
    Region :math:`x < a` is rigidly shifted up/down by ``strain*height/2``.

    Here is an example of how to use this function on an artificial
    2D square atomic lattice. The positions are plotted before (left)
    and after (right) applying the displacement, and the horizontal and
    vertical lines show the `strain` (red), `a` (green) and `b` (blue)
    parameters. ::

       import matplotlib.pyplot as plt
       import numpy as np

       w = 1; h = 1; strain = 0.1; a = -0.5; b =  0.0
       x = np.linspace(-w, w, 20)
       y = np.linspace(-h, h, 20)
       X, Y = np.meshgrid(x, y)
       u_y = thin_strip_displacement_y(X, Y, strain, a, b)

       for i, disp in enumerate([0, u_y]):
           plt.subplot(1,2,i+1)
           plt.scatter(X, Y + disp, c='k', s=5)
           for y in [-h, h]:
               plt.axhline(y, color='r', linewidth=2, linestyle='dashed')
               plt.axhline(y*(1+strain), color='r', linewidth=2)
           for x, c in zip([a, b], ['g', 'b']):
               plt.axvline(x, color=c, linewidth=2)

    .. image:: thin-strip-displacement-y.png
       :width: 600
       :align: center

    Parameters
    ----------
    x : array
    y : array
       Atomic positions in unstrained slab, centered on origin x=0,y=0
    strain : float
       Far field strain to apply
    a : float
       x coordinate for beginning of strain ramp
    b : float
       x coordinate for end of strain ramp
    """

    u_y = np.zeros_like(y)
    height = y.max() - y.min()     # measure height of slab
    shift = strain * height / 2.0  # far behind crack, shift = strain*height/2

    u_y[x < a] = np.sign(y[x < a]) * shift  # region shift for x < a
    u_y[x > b] = strain * y[x > b]          # constant strain for x > b
    
    middle = (x >= a) & (x <= b)            # interpolate for a <= x <= b
    f = (x[middle] - a) / (b - a)
    u_y[middle] = (f * strain * y[middle] +
                   (1 - f) * shift * np.sign(y[middle]))
    
    return u_y


def print_crack_system(crack_direction, cleavage_plane, crack_front):
    """
    Pretty printing of crack crystallographic coordinate system 

    Specified by Miller indices for crack_direction (x),
    cleavage_plane (y) and crack_front (z), each of which should be
    a sequence of three floats
    """
    crack_direction = MillerDirection(crack_direction)
    cleavage_plane = MillerPlane(cleavage_plane)
    crack_front = MillerDirection(crack_front)

    print('Crack system              %s%s' % (cleavage_plane, crack_front))
    print('Crack direction (x-axis)  %s' % crack_direction)
    print('Cleavage plane  (y-axis)  %s' % cleavage_plane)
    print('Crack front     (z-axis)  %s\n' % crack_front)



class ConstantStrainRate(object):
    """
    Constraint which increments epsilon_yy at a constant strain rate

    Rescaling is applied only to atoms where `mask` is True (default is all atoms)
    """

    def __init__(self, orig_height, delta_strain, mask=None):
        self.orig_height = orig_height
        self.delta_strain = delta_strain
        if mask is None:
            mask = Ellipsis
        self.mask = mask

    def adjust_forces(self, positions, forces):
        pass

    def adjust_positions(self, oldpos, newpos):
        current_height = newpos[:, 1].max() - newpos[:, 1].min()
        current_strain = current_height / self.orig_height - 1.0
        new_strain = current_strain + self.delta_strain
        alpha = (1.0 + new_strain) / (1.0 + current_strain)
        newpos[self.mask, 1] = newpos[self.mask, 1]*alpha



    

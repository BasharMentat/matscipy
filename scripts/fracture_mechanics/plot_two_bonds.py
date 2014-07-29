import numpy as np
import matplotlib.pyplot as plt

from scipy.signal import argrelextrema

bond_lengths1, bond1_forces1, epot1, epot_cluster1, work1, tip_x1, tip_z1 = \
  np.loadtxt('bond_1_eval.out', unpack=True)
bond_lengths2, bond2_forces2, epot2, epot_cluster2, work2, tip_x2, tip_z2 = \
  np.loadtxt('bond_2_eval.out', unpack=True)

minima1 = argrelextrema(epot1, np.less)
minima2 = argrelextrema(epot2, np.less)

maxima1 = argrelextrema(epot1, np.greater)
maxima2 = argrelextrema(epot2, np.greater)

Ea_1 = epot1[maxima1][0] - epot1[minima1][0]
dE_1 = epot1[minima1][1] - epot1[minima1][0]
print 'Ea_1 = %.3f eV' % Ea_1
print 'dE_1 = %.3f eV' % dE_1
print

Ea_2 = epot2[maxima2][0] - epot2[minima2][0]
dE_2 = epot2[minima2][1] - epot2[minima2][0]
print 'Ea_2 = %.3f eV' % Ea_2
print 'dE_2 = %.3f eV' % dE_2
print

E0_1 = epot1[minima1][0]
E0_2 = epot2[minima2][0]
E0_12 = epot1[minima1][-1] - epot2[minima1][0]

plt.figure(1)
plt.clf()

plt.plot(tip_x1, epot1 - E0_1, 'b.-', label='Bond 1')
plt.plot(tip_x2, epot2 - E0_1 + E0_12, 'c.-', label='Bond 2')

plt.plot(tip_x2 - tip_x2[minima2][0] + tip_x1[minima1][0],
         epot2 - E0_2, 'c.--', label='Bond 2, shifted')

plt.plot(tip_x1[minima1], epot1[minima1] - E0_1, 'ro', mec='r',
         label='Bond 1 minima')
plt.plot(tip_x2[minima2], epot2[minima1] - E0_1 + E0_12, 'mo', mec='m',
         label='Bond 2 minima')
plt.plot(tip_x2[minima2]-tip_x2[minima2][0] + tip_x1[minima1][0],
            epot2[minima1] - E0_1, 'mo', mec='m', mfc='w',
            label='Bond 2 minima, shifted')

plt.plot(tip_x1[maxima1], epot1[maxima1] - E0_1, 'rd', mec='r', label='Bond 1 TS')
plt.plot(tip_x2[maxima2], epot2[maxima1] - E0_1 + E0_12, 'md', mec='m', label='Bond 2 TS')
plt.plot(tip_x2[maxima2] - tip_x2[minima2][0] + tip_x1[minima1][0],
            epot2[maxima1] - E0_1, 'md', mec='m', mfc='w', label='Bond 2 TS, shifted')


plt.xlabel(r'Crack position / $\mathrm{\AA}$')
plt.ylabel(r'Potential energy / eV')
plt.legend(loc='upper left')
plt.ylim(-0.05, 0.30)
plt.draw()

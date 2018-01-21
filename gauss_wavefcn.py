import numpy as np
import itertools
from pyquil.quil import Program
import pyquil.api as api


class GaussianWavefunction:

    def __init__(self, sigma_, mu_, num_qubits=5):
        """
        Specify the standard deviation and mean of the single-variable Gaussian wavefunction,
        aa well as the number of qubits to be used in the construction;
        """
        self.sigma = sigma_
        self.mu = mu_
        self.num_qubits = num_qubits
        self.quantum_simulator = api.QVMConnection()
        self.prog = Program()

    def norm_(self, sigma_, mu_, N):
        """
        Normalization factor for the state. Defined in Eq (7) of paper.

        Inputs:-
        sigma_: standard deviation
        mu_: mean
        N: cutoff the for the infinite sum, i.e. sum_{i=-N}^{i=N} (...)
        """
        return np.sum(np.exp((-(np.arange(-N, N+1, 1) - mu_)**2)/float(sigma_**2)))

    def angle_(self, sigma_, mu_, N=10**3):
        """
        The angle $\alpha$ defined in Eq (12)
        """
        return np.arccos(np.sqrt(self.norm_(sigma_/2., mu_/2., N)/self.norm_(sigma_, mu_, N)))

    def qubit_strings(self, n):
        """
        Return list of strings for n-qubit states in increasing lexicographic order
        """
        qubit_strings = []
        for q in itertools.product(['0', '1'], repeat=n):
            qubit_strings.append(''.join(q))
        return qubit_strings

    def mean_qubit_combo(self, qub, mu):
        """
        Given an n-qubit string, return the mean used for the rotation angle
        at level n for the corresponding n-qubit
        """
        mu_out = mu
        for bit in qub:
            mu_out = (mu_out/2.) - ((1/2.)*int(bit))
        return mu_out

    def level_means(self, mu, n):
        """
        At level n, return all the means used for the various rotation angles (see Eq (11) in the paper)
        """
        list_mu_out = []
        qb_strings = self.qubit_strings(n)
        for qb in qb_strings:
            mu_out = self.mean_qubit_combo(qb, mu)
            list_mu_out.append(mu_out)
        return list_mu_out

    def level_angles(self, sigma, mu, n):
        """
        At level n, return all the angles (see Eq (12) in the paper)
        """
        sigma_out = sigma/(2.**n)
        list_mu = self.level_means(mu, n)
        # for each (sigma, mu) pair, calculate the corresponding angle
        angles_out = []
        for mu_ in list_mu:
            angles_out.append(self.angle_(sigma_out, mu_))
        return angles_out

    def rotation_block(self, alpha):
        """
        Given a rotation angle $\alpha$, return a 2x2 rotation block
        """
        return np.array([[np.cos(alpha), -np.sin(alpha)], [np.sin(alpha), np.cos(alpha)]])

    def level_gate(self, sigma, mu, n):
        """
        Generated n-qubit controlled operation as a 2^(n+1) x 2^(n+1) matrix,
        with 2^n rotation blocks along the diagonal
        """
        list_row_block = []
        list_level_angles = self.level_angles(sigma, mu, n)
        for nn, angle in enumerate(list_level_angles):
            rot_block = self.rotation_block(angle)
            row_block = np.hstack((np.zeros((2, 2*nn)), rot_block, np.zeros((2, 2*(2**(n) - nn - 1)))))
            list_row_block.append(row_block)
        level_n_gate = np.vstack(tuple(list_row_block))
        return level_n_gate

    def list_all_gates(self, sigma, mu, N):
        """
        Given sigma, mu (standard dev, mean) and the number of qubits N,
        return a list of all gates used for the controlled operations required
        to produce a Gaussian wavefunction
        """
        list_gates = []
        for n in range(N):
            list_gates.append(self.level_gate(sigma, mu, n))
        return list_gates

    def defn_all_gates(self, sigma, mu, N, prog):
        """
        Define all gates specified by N qubits, for (standard deviation, mean) given by (sigma, mu),
        into the program input which is specified by prog
        """
        list_gates_ = self.list_all_gates(sigma, mu, N)
        for i, gate in enumerate(list_gates_):
            prog.defgate("Level_" + str(i) + "_gate", gate)

    def apply_all_gates(self, sigma, mu, N, prog):
        """
        Apply all controlled rotation gates to produce the Gaussian wavefunction,
        """
        list_gates_ = self.list_all_gates(sigma, mu, N)
        for i, gate in enumerate(list_gates_):
            tup_gate = ("Level_" + str(i) + "_gate",) + tuple(range(i+1))
            prog.inst(tup_gate)

    def gaussian_wavefunc(self):
        # define all gates to the program
        self.defn_all_gates(self.sigma, self.mu, self.num_qubits, self.prog)
        # apply all gates to the program
        self.apply_all_gates(self.sigma, self.mu, self.num_qubits, self.prog)
        # create the gaussian wavefunction
        gaussian_wavefunc = self.quantum_simulator.wavefunction(self.prog)
        return gaussian_wavefunc
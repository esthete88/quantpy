import numpy as np
import scipy.linalg as la
from scipy.optimize import minimize

from .geometry import hs_dst, if_dst, trace_dst
from .qobj import Qobj
from .measurements import generate_measurement_matrix
from .routines import _left_inv, SIGMA_I


def _is_feasible(bloch_vec):
    """Positivity constraint for minimize function based on the trace condition"""
    bloch_len = len(bloch_vec) + 1  # 4 ** dim
    print('bloch len:', bloch_len)
    return np.sqrt(bloch_len) - 1 - bloch_len * np.sum(bloch_vec ** 2)


class Tomograph:
    """Basic class for QST"""
    def __init__(self, state, dst='hs', verbose=False):
        self.state = state
        self.verbose = verbose
        if isinstance(dst, str):
            if dst == 'hs':
                self.dst = hs_dst
            elif dst == 'trace':
                self.dst = trace_dst
            elif dst == 'if':
                self.dst = if_dst
            else:
                raise ValueError('Invalid value for argument `dst`')
        else:
            self.dst = dst

    def experiment(self, n_measurements, POVM='proj', warm_start=False):
        POVM_matrix = generate_measurement_matrix(POVM, self.state.dim)
        probas = POVM_matrix @ self.state.bloch * (2 ** self.state.dim)
        results = np.random.multinomial(n_measurements, probas)
        if warm_start:
            self.POVM_matrix = np.vstack((
                self.POVM_matrix * self.n_measurements,
                POVM_matrix * n_measurements,
            )) / (self.n_measurements + n_measurements)
            self.results = np.hstack((self.results, results))
            self.n_measurements += n_measurements
        else:
            self.POVM_matrix = POVM_matrix
            self.results = results
            self.n_measurements = n_measurements

    def point_estimate(self, method='lin', physical=True):
        if method == 'lin':
            return self._point_estimate_lin(physical=physical)
        else:
            return self._point_estimate_mle(physical=physical)

    def bootstrap_state(self, state, n_measurements, n_repeats, method='lin', dst='hs'):
        pass

    def _point_estimate_lin(self, physical):
        frequencies = self.results / self.results.sum()
        bloch_vec = _left_inv(self.POVM_matrix) @ frequencies / (2 ** self.state.dim)  # norm coef
        max_norm = np.sqrt((2 ** self.state.dim - 1) / (4 ** self.state.dim))
        if physical and la.norm(bloch_vec[1:], ord=2) > max_norm:
            bloch_vec[1:] *= max_norm / la.norm(bloch_vec[1:], ord=2)
        return Qobj(bloch_vec)

    def _point_estimate_mle(self, physical=True):
        constraints = [
            {'type': 'ineq', 'fun': _is_feasible},
        ]
        x0 = Qobj(SIGMA_I / 2).bloch[1:]
        # x0 = self.point_estimate('lin').bloch[1:]  # first parameter should be constant
        opt_res = minimize(self._neg_log_likelihood, x0, constraints=constraints, method='SLSQP')
        bloch_vec = opt_res.x
        max_norm = np.sqrt((2 ** self.state.dim - 1) / (4 ** self.state.dim))
        if physical and la.norm(bloch_vec, ord=2) > max_norm:
            bloch_vec *= max_norm / la.norm(bloch_vec, ord=2)
        bloch_vec = np.append(1 / 2 ** self.state.dim, bloch_vec)
        return Qobj(bloch_vec)

    def _neg_log_likelihood(self, bloch_vec, eps=1e-10):
        bloch_vec = np.append(1 / 2 ** self.state.dim, bloch_vec)
        probas = self.POVM_matrix @ bloch_vec * (2 ** self.state.dim)
        if self.verbose:
            print('probas', probas)
        log_likelihood = np.sum(self.results * np.log(probas + eps))
        return -log_likelihood

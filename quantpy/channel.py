import numpy as np

from .base_quantum import BaseQuantum
from .routines import generate_single_entries
from .qobj import Qobj
from .routines import kron


class Channel(BaseQuantum):
    """Class for representing quantum gates

    Parameters
    ----------
    data : callable, array-like or Qobj
        If callable, treated as a transformation function. `n_qubits` argument is necessary in this case.
        If array-like or Qobj, treated as a Choi matrix
    n_qubits : int or None, default=None (optional)
        Number of qubits

    Attributes
    ----------
    choi : Qobj (property)
        Choi matrix of the channel
    H : Channel (property)
        Channel with adjoint Choi matrix
    n_qubits : int
        Number of qubits
    T : Channel (property)
        Channel with transposed Choi matrix

    Methods
    -------
    conj()
        Channel with conjugated Choi matrix
    copy()
        Create a copy of this Gate instance
    kron()
        Kronecker product of 2 Qobj instances
    set_func()
        Set a new channel via function
    trace()
        Trace of the quantum object
    transform()
        Apply this channel to a quantum state
    """
    def __init__(self, data, n_qubits=None):
        self._types = set()
        if callable(data):
            self._choi = None
            self._func = data
            self._types.add('func')
            if n_qubits is None:
                raise ValueError('`n_qubits` argument is compulsory when using init with function')
            self.n_qubits = n_qubits
        elif isinstance(data, np.ndarray) or isinstance(data, Qobj):
            self._choi = Qobj(data)
            self._func = None
            self._types.add('choi')
            self.n_qubits = int(np.log2(data.shape[0]) / 2)
        else:
            raise ValueError('Invalid data format')

    def set_func(self, data, n_qubits):
        """Set a new transformation function that defines the channel"""
        self._types.add('func')
        self._types.discard('choi')
        self._func = data
        self.n_qubits = n_qubits

    @property
    def choi(self):
        """Choi matrix of the channel"""
        if 'choi' not in self._types:
            self._types.add('choi')
            self._choi = Qobj(np.zeros((4 ** self.n_qubits, 4 ** self.n_qubits), dtype=np.complex128))
            for single_entry in generate_single_entries(2 ** self.n_qubits):
                self._choi += kron(Qobj(single_entry), self.transform(single_entry))
        return self._choi

    @choi.setter
    def choi(self, data):
        self._types.add('choi')
        self._types.discard('func')
        if not isinstance(data, Qobj):
            data = Qobj(data)
        self._choi = data
        self.n_qubits = int(np.log2(data.shape[0]) / 2)

    def transform(self, state):
        """Apply this channel to the quantum state"""
        if not isinstance(state, Qobj):
            state = Qobj(state)
        if 'func' in self._types:
            output_state = self._func(state)
        else:  # compute output state using Choi matrix
            common_state = kron(state.T, Qobj(np.eye(2 ** self.n_qubits)))
            output_state = (common_state @ self.choi).ptrace(list(range(self.n_qubits, 2 * self.n_qubits)))
        return output_state

    @property
    def T(self):
        """Transpose of the quantum object"""
        return self.__class__(self.choi.T)

    @property
    def H(self):
        """Adjoint matrix of the quantum object"""
        return self.__class__(self.choi.H)

    def conj(self):
        """Conjugate of the quantum object"""
        return self.__class__(self.choi.conj())

    def __repr__(self):
        return 'Quantum channel w Choi matrix\n' + repr(self.choi.matrix)
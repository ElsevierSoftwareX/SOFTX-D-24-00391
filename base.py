from abc import ABC, abstractmethod

from joblib import delayed, effective_n_jobs, Parallel
from typing import List, Union

import numpy as np
import pandas as pd
import scipy.sparse as sparse

# from scipy.sparse import vstack, csr_array
from sklearn.base import BaseEstimator, TransformerMixin

from rdkit.Chem import MolFromSmiles
from rdkit.Chem.rdchem import Mol


class FingerprintTransformer(ABC, TransformerMixin, BaseEstimator):
    def __init__(self, n_jobs: int = None):
        """
        result_vector_tape has to be one of the following:
        bit, spares, count, sparse_count
        """
        self.n_jobs = effective_n_jobs(n_jobs)
        self.fp_generator_kwargs = {}

    def fit(self, X, y=None, **fit_params):
        return self

    def fit_transform(self, X, y=None, **fit_params):
        return self.transform(X)

    def transform(self, X: Union[pd.DataFrame, np.ndarray]):
        """
        :param X: np.array or DataFrame of rdkit.Mol objects
        :return: np.array of calculated fingerprints for each molecule
        """

        if self.n_jobs == 1:
            return self._calculate_fingerprint(X)
        else:
            batch_size = max(len(X) // self.n_jobs, 1)

            args = (
                X[i : i + batch_size] for i in range(0, len(X), batch_size)
            )

            results = Parallel(n_jobs=self.n_jobs)(
                delayed(self._calculate_fingerprint)(X_sub) for X_sub in args
            )
            if isinstance(results[0], sparse.csr_array):
                return sparse.vstack(results)
            else:
                return np.concatenate(results)

    @abstractmethod
    def _calculate_fingerprint(
        self, X: Union[np.ndarray]
    ) -> Union[np.ndarray, sparse.csr_array]:
        """
        Helper function to be executed in each sub-process.

        :param X: subset of original X data
        :return: np.array containing calculated fingerprints for each molecule
        """
        pass

    def _validate_input(self, X: List):
        if not all(
            [
                isinstance(molecule, Mol) or type(molecule) == str
                for molecule in X
            ]
        ):
            raise ValueError(
                "Passed value is neither rdkit.Chem.rdChem.Mol nor SMILES"
            )

        X = [MolFromSmiles(x) if type(x) == str else x for x in X]
        return X


class FingerprintGeneratorMixin(ABC):
    def __init__(self, fingerprint_type: str = "bit", sparse=False):
        """
        result_vector_tape has to be one of the following:
        bit, spares, count, sparse_count
        """
        assert fingerprint_type in ["bit", "count"]
        self.result_vector_type = fingerprint_type
        self.fp_generator_kwargs = {}
        self.sparse_output = sparse

    @abstractmethod
    def _get_generator(self):
        """
        Function that creates a generator object in each sub-process.

        :return: rdkit fingerprint generator for current fp_generator_kwargs parameter
        """
        pass

    def _generate_fingerprints(
        self, X: Union[pd.DataFrame, np.ndarray]
    ) -> Union[np.ndarray, sparse.csr_array]:
        fp_generator = self._get_generator()

        if self.result_vector_type == "bit":
            X = [fp_generator.GetFingerprintAsNumPy(x) for x in X]
        else:
            X = [fp_generator.GetCountFingerprintAsNumPy(x) for x in X]

        if self.sparse_output:
            return sparse.csr_array(X)
        else:
            return np.array(X)

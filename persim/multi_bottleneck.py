"""

    Implementation of the bottleneck distance using binary
    search and the Hopcroft-Karp algorithm

    Author: Chris Tralie

"""

import numpy as np

from bisect import bisect_left
import warnings
from ortools.graph import pywrapgraph

__all__ = ["multi_bottleneck"]


def multi_bottleneck(dgm1, dgm2, matching=False):
    """
    Perform the Bottleneck distance matching between persistence diagrams.
    Assumes first two columns of S and T are the coordinates of the persistence
    points, but allows for other coordinate columns (which are ignored in
    diagonal matching).

    See the `distances` notebook for an example of how to use this.

    Parameters
    -----------
    dgm1: Mx(>=2)
        array of birth/death pairs for PD 1
    dgm2: Nx(>=2)
        array of birth/death paris for PD 2
    matching: bool, default False
        if True, return matching infromation and cross-similarity matrix

    Returns
    --------

    d: float
        bottleneck distance between dgm1 and dgm2
    matching: ndarray(Mx+Nx, 3), Only returns if `matching=True`
        A list of correspondences in an optimal matching, as well as their distance, where:
        * First column is index of point in first persistence diagram, or -1 if diagonal
        * Second column is index of point in second persistence diagram, or -1 if diagonal
        * Third column is the distance of each matching
    """

    return_matching = matching

    S = np.array(dgm1)
    M = min(S.shape[0], S.size)
    if S.size > 0:
        S = S[np.isfinite(S[:, 1]), :]
        if S.shape[0] < M:
            warnings.warn(
                "dgm1 has points with non-finite death times;" +
                "ignoring those points"
            )
            M = S.shape[0]
    T = np.array(dgm2)
    N = min(T.shape[0], T.size)
    if T.size > 0:
        T = T[np.isfinite(T[:, 1]), :]
        if T.shape[0] < N:
            warnings.warn(
                "dgm2 has points with non-finite death times;" +
                "ignoring those points"
            )
            N = T.shape[0]

    if M == 0:
        S = np.array([[0, 0]])
        M = 1
    if N == 0:
        T = np.array([[0, 0]])
        N = 1

    # Step 1: Compute CSM between S and T, including points on diagonal
    # L Infinity distance
    Sb, Sd = S[:, 0], S[:, 1]
    Tb, Td = T[:, 0], T[:, 1]
    D1 = np.abs(Sb[:, None] - Tb[None, :])
    D2 = np.abs(Sd[:, None] - Td[None, :])
    DUL = np.maximum(D1, D2)

    # Put diagonal elements into the matrix, being mindful that Linfinity
    # balls meet the diagonal line at a diamond vertex
    D = np.zeros((M + 1, N + 1))
    # Upper left is Linfinity cross-similarity between two diagrams
    D[0:M, 0:N] = DUL
    # Upper right is diagonal matching of points from S
    # UR = np.inf * np.ones((M, M))
    # np.fill_diagonal(UR, 0.5 * (S[:, 1] - S[:, 0]))
    D[M, :N] = 0.5 * (S[:, 1] - S[:, 0])
    # D[0:M, N::] = UR
    # Lower left is diagonal matching of points from T
    # UL = np.inf * np.ones((N, N))
    # np.fill_diagonal(UL, 0.5 * (T[:, 1] - T[:, 0]))
    D[:M, N] = 0.5 * (T[:, 1] - T[:, 0])
    # D[M::, 0:N] = UL
    # Lower right is all 0s by default (remaining diagonals match to diagonals)
    multiT = N
    multiS = M

    # Step 2: Perform a binary search + Hopcroft Karp to find the
    # bottleneck distance
    ds = np.sort(np.unique(D.flatten()))[0:-1]  # Everything but np.inf
    bdist = ds[-1]
    matching = {}
    n0 = D.shape[0]
    n1 = D.shape[1]
    while len(ds) >= 1:
        idx = 0
        if len(ds) > 1:
            idx = bisect_left(range(ds.size), int(ds.size / 2))
        d = ds[idx]
        graph = pywrapgraph.SimpleMaxFlow()
        source = n0 + n1
        sink = n0 + n1 + 1
        T_diagonal = n0 + n1 - 1
        S_diagonal = n0 - 1
        for i in range(n0):
            for j in range(n1):
                if D[i, j] <= d:
                    if (i, j) == (n0 - 1, n1 - 1):
                        graph.AddArcWithCapacity(i, j + n0, multiS)
                    else:
                        graph.AddArcWithCapacity(i, j + n0, 1)

        for i in range(n0 - 1):
            graph.AddArcWithCapacity(source, i, 1)

        for j in range(n1 - 1):
            graph.AddArcWithCapacity(j + n0, sink, 1)

        # for i in range(n0):
        #     if D[i, n1] <= d:
        #         graph.AddArcWithCapacity(i, T_diagonal, multiT)
        #
        # for i in range(n1):
        #     if D[n0, i] <= d:
        #         graph.AddArcWithCapacity(i, S_diagonal, multiS)

        graph.AddArcWithCapacity(source, S_diagonal, multiS)
        graph.AddArcWithCapacity(T_diagonal, sink, multiT)

        graph.Solve(source, sink)
        res = {}
        for i in range(graph.NumArcs()):
            if graph.Flow(i) == 1 and graph.Tail(i) != source and graph.Head(i) != sink:
                res[graph.Tail(i)] = graph.Head(i)

        if M + N == graph.OptimalFlow() and d <= bdist:
            bdist = d
            matching = res
            ds = ds[0:idx]
        else:
            ds = ds[idx + 1::]

    if return_matching:
        matchidx = []
        for i in range(M + N):
            # Subtract n1, we initially add it to ensure uniqueness of ids
            j = matching[i] - n1
            d = D[i, j]
            if i < M:
                if j >= N:
                    j = -1  # Diagonal match from first persistence diagram
            else:
                if j >= N:  # Diagonal to diagonal, so don't include this
                    continue
                i = -1
            matchidx.append([i, j, d])
        return bdist, np.array(matchidx)
    else:
        return bdist

#################################################################################
# The Institute for the Design of Advanced Energy Systems Integrated Platform
# Framework (IDAES IP) was produced under the DOE Institute for the
# Design of Advanced Energy Systems (IDAES), and is copyright (c) 2018-2022
# by the software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia University
# Research Corporation, et al.  All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and
# license information.
#################################################################################
import numpy as np
from idaes.apps.matopt import *
from copy import deepcopy

if __name__ == "__main__":

    IAD = 2.828427  # Angstrom
    Lat = FCCLattice.alignedWith111(IAD)

    nAtomsOnEdge = 4
    nLayers = 6
    a = nAtomsOnEdge * IAD
    b = a
    c = nLayers * Lat.FCC111LayerSpacing
    alpha = np.pi / 2
    beta = np.pi / 2
    gamma = np.pi / 3
    S = Parallelepiped.fromEdgesAndAngles(a, b, c, alpha, beta, gamma)
    S.shift(np.array([-0.01 * a, -0.01 * b, -0.01 * c]))
    T = PlanarTiling(S)

    Canv = Canvas.fromLatticeAndTilingScan(Lat, T)

    D = Design(Canv, Atom("Pt"))
    D.toPDB("undefected.pdb")
    D.toCFG("undefected.cfg", GS=1.0, BBox=S)

    Atoms = [Atom("Pt")]
    TargetGCN = 8.0
    CNsurfMin = 3
    CNsurfMax = 9
    TileSizeSquared = nAtomsOnEdge**2
    UndefectedSurfE = 0.129758
    maxSurfE = 999
    CatWeight = 1.0

    m = MatOptModel(Canv, Atoms)

    CanvTwoBotLayers = [
        i for i in range(len(Canv)) if Canv.Points[i][2] < 1.5 * Lat.FCC111LayerSpacing
    ]
    CanvMinusTwoBotLayers = [i for i in range(len(Canv)) if i not in CanvTwoBotLayers]
    OneSiteInTopLayer = [
        min(
            [
                i
                for i in range(len(Canv))
                if Canv.Points[i][2] > (nLayers - 1.5) * Lat.FCC111LayerSpacing
            ]
        )
    ]
    m.Yi.rules.append(FixedTo(1, sites=OneSiteInTopLayer))
    m.Yi.rules.append(FixedTo(1, sites=CanvTwoBotLayers))
    NeighborsBelow = [
        [
            j
            for j in Canv.NeighborhoodIndexes[i]
            if (j is not None and Canv.Points[j][2] < Canv.Points[i][2] - DBL_TOL)
        ]
        for i in range(len(Canv))
    ]
    m.Yi.rules.append(
        ImpliesNeighbors(
            concs=(m.Yi, GreaterThan(1)),
            sites=CanvMinusTwoBotLayers,
            neighborhoods=NeighborsBelow,
        )
    )
    m.addSitesDescriptor(
        "GCNi",
        bounds=(0, 12),
        integer=False,
        rules=EqualTo(SumNeighborSites(desc=m.Ci, coefs=1 / 12)),
        sites=CanvMinusTwoBotLayers,
    )
    m.addSitesDescriptor(
        "IdealSitei",
        binary=True,
        rules=[
            Implies(concs=(m.Ci, GreaterThan(3))),
            Implies(concs=(m.Ci, LessThan(9))),
            Implies(concs=(m.GCNi, EqualTo(TargetGCN))),
        ],
        sites=CanvMinusTwoBotLayers,
    )
    m.addGlobalDescriptor(
        "Activity", rules=EqualTo(SumSites(m.IdealSitei, coefs=1 / TileSizeSquared))
    )
    EiVals = [
        0,
        -0.04293 * 3 + 0.41492,
        -0.04293 * 10 + 0.41492,
        0.05179 * 11 - 0.62148,
        0,
    ]
    EiBPs = [0, 3, 10, 11, 12]
    m.addSitesDescriptor(
        "Ei",
        rules=PiecewiseLinear(values=EiVals, breakpoints=EiBPs, input_desc=m.Ci),
        sites=CanvMinusTwoBotLayers,
    )
    m.addGlobalDescriptor(
        "Esurf",
        rules=EqualTo(SumSites(m.Ei, coefs=1 / TileSizeSquared, offset=0.101208)),
    )
    m.addGlobalDescriptor(
        "Stability",
        rules=EqualTo(LinearExpr(descs=m.Esurf, coefs=-1 / UndefectedSurfE, offset=1)),
    )
    m.addGlobalDescriptor(
        "ActAndStab",
        rules=EqualTo(
            LinearExpr(
                descs=[m.Activity, m.Stability], coefs=[CatWeight, (1 - CatWeight)]
            )
        ),
    )

    D = None
    try:
        D = m.maximize(m.ActAndStab, tilim=360)
    except:
        print("MaOpt can not find usable solver (CPLEX or NEOS-CPLEX)")
    if D is not None:
        for i in m.IdealSitei.keys():
            if m.IdealSitei.values[i] > 0.5:
                D.setContent(i, Atom("S"))
        D.toPDB("result.pdb")
        PeriodicD = T.replicateDesign(D, 4)
        PeriodicS = deepcopy(S)
        PeriodicS.scale(np.array([4, 4, 1]))
        PeriodicD.toCFG("periodic_result.cfg", BBox=PeriodicS)
